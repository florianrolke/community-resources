/**
 * In-process job queue. Single worker (ffmpeg is CPU-heavy), dependency
 * chaining via dependsOnJobId, crash recovery on boot, cooperative
 * cancellation (kills a running ffmpeg child).
 *
 * Terminal transitions are compare-and-set on the current status so a late
 * completion can never overwrite a cancellation (or vice versa), and project
 * status is only touched when the job-row transition actually happened.
 */
import type { ChildProcess } from "child_process";

import { db, jobsTable, projectsTable, type Job } from "@workspace/db";
import { and, asc, eq, inArray, or } from "drizzle-orm";

import { handlers, type JobContext } from "./jobHandlers";
import { logger } from "./logger";

const TICK_MS = 2000;
let running = false;
let started = false;
const children = new Map<string, ChildProcess>();

export function startJobWorker(): void {
  if (started) return;
  started = true;
  void recoverStuckJobs().catch((err) =>
    logger.error({ err }, "job worker recovery failed"),
  );
  setInterval(() => {
    void tick().catch((err) => logger.error({ err }, "job worker tick failed"));
  }, TICK_MS);
  logger.info("job worker started");
}

async function recoverStuckJobs(): Promise<void> {
  const recovered = await db
    .update(jobsTable)
    .set({
      status: "queued",
      progress: 0,
      message: "Restarted after server restart",
      startedAt: null,
    })
    .where(eq(jobsTable.status, "running"))
    .returning({ id: jobsTable.id });
  if (recovered.length > 0) {
    logger.info({ count: recovered.length }, "requeued interrupted jobs");
  }
}

async function tick(): Promise<void> {
  if (running) return;
  const job = await claimNextJob();
  if (!job) return;
  running = true;
  try {
    await runJob(job);
  } finally {
    running = false;
  }
}

async function claimNextJob(): Promise<Job | null> {
  const queued = await db
    .select()
    .from(jobsTable)
    .where(eq(jobsTable.status, "queued"))
    .orderBy(asc(jobsTable.createdAt))
    .limit(25);

  for (const job of queued) {
    if (!job.dependsOnJobId) return job;
    const [dep] = await db
      .select({ status: jobsTable.status })
      .from(jobsTable)
      .where(eq(jobsTable.id, job.dependsOnJobId));
    if (!dep) return job; // dependency vanished — run anyway
    if (dep.status === "done") return job;
    if (dep.status === "failed") {
      await finishJob(
        job,
        "failed",
        "An earlier pipeline step failed, so this step was skipped.",
      );
    } else if (dep.status === "canceled") {
      await cancelQueuedJob(job, "Skipped because an earlier step was canceled");
    }
    // dep still pending — leave this job and consider the next queued one
  }
  return null;
}

async function runJob(job: Job): Promise<void> {
  const claimed = await db
    .update(jobsTable)
    .set({ status: "running", startedAt: new Date(), message: "Starting" })
    .where(and(eq(jobsTable.id, job.id), eq(jobsTable.status, "queued")))
    .returning();
  const fresh = claimed[0];
  if (!fresh) return; // canceled (or otherwise transitioned) meanwhile

  const ctx: JobContext = {
    update: async (progress, message) => {
      const patch: { progress: number; message?: string } = {
        progress: Math.max(0, Math.min(100, Math.round(progress))),
      };
      if (message !== undefined) patch.message = message;
      await db
        .update(jobsTable)
        .set(patch)
        .where(and(eq(jobsTable.id, job.id), eq(jobsTable.status, "running")));
    },
    isCanceled: async () => {
      const [row] = await db
        .select({ status: jobsTable.status })
        .from(jobsTable)
        .where(eq(jobsTable.id, job.id));
      return row?.status === "canceled";
    },
    registerChild: (child) => {
      children.set(job.id, child);
    },
  };

  logger.info({ jobId: job.id, type: job.type }, "job started");
  try {
    const handler = handlers[fresh.type];
    await handler(fresh, ctx);
    await finishJob(fresh, "done", null);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    await finishJob(fresh, "failed", message);
  } finally {
    children.delete(job.id);
    // If the job was canceled mid-flight, close out bookkeeping now.
    const [after] = await db
      .select()
      .from(jobsTable)
      .where(eq(jobsTable.id, job.id));
    if (after?.status === "canceled" && !after.finishedAt) {
      await db
        .update(jobsTable)
        .set({ finishedAt: new Date(), message: "Canceled" })
        .where(eq(jobsTable.id, job.id));
      await updateProjectAfterJob(after, "canceled");
      logger.info({ jobId: job.id }, "job canceled");
    } else if (after) {
      logger.info({ jobId: job.id, status: after.status }, "job finished");
    }
  }
}

/**
 * CAS transition queued/running → done/failed. Project status is only
 * updated when this call actually performed the transition, so a job that
 * was canceled meanwhile cannot mark its project ready/delivered/failed.
 */
async function finishJob(
  job: Job,
  status: "done" | "failed",
  error: string | null,
): Promise<void> {
  const transitioned = await db
    .update(jobsTable)
    .set({
      status,
      error,
      finishedAt: new Date(),
      progress: status === "done" ? 100 : job.progress,
      ...(status === "done" ? { message: "Completed" } : {}),
    })
    .where(
      and(
        eq(jobsTable.id, job.id),
        or(eq(jobsTable.status, "running"), eq(jobsTable.status, "queued")),
      ),
    )
    .returning({ id: jobsTable.id });
  if (transitioned.length === 0) return;
  await updateProjectAfterJob(job, status);
}

/** CAS transition queued → canceled (used for dependents of canceled work). */
async function cancelQueuedJob(job: Job, message: string): Promise<void> {
  const transitioned = await db
    .update(jobsTable)
    .set({
      status: "canceled",
      message,
      finishedAt: new Date(),
    })
    .where(and(eq(jobsTable.id, job.id), eq(jobsTable.status, "queued")))
    .returning({ id: jobsTable.id });
  if (transitioned.length === 0) return;
  await updateProjectAfterJob(job, "canceled");
}

/** Keep project.status in sync with its pipeline jobs. */
async function updateProjectAfterJob(
  job: Job,
  status: "done" | "failed" | "canceled",
): Promise<void> {
  if (!job.projectId) return;
  if (job.type === "voice_preview" || job.type === "create_voice") return;

  if (status === "failed") {
    await db
      .update(projectsTable)
      .set({ status: "failed", updatedAt: new Date() })
      .where(eq(projectsTable.id, job.projectId));
    return;
  }
  if (status === "canceled") {
    const active = await activeJobCount(job.projectId);
    if (active === 0) {
      // Everything stopped by cancellation: return the project to an
      // editable state (it may still hold earlier outputs).
      await db
        .update(projectsTable)
        .set({ status: "draft", updatedAt: new Date() })
        .where(
          and(
            eq(projectsTable.id, job.projectId),
            eq(projectsTable.status, "processing"),
          ),
        );
    }
    return;
  }
  if (job.type === "assemble") {
    await db
      .update(projectsTable)
      .set({ status: "ready", updatedAt: new Date() })
      .where(eq(projectsTable.id, job.projectId));
  } else if (job.type === "deliver") {
    await db
      .update(projectsTable)
      .set({ status: "delivered", updatedAt: new Date() })
      .where(eq(projectsTable.id, job.projectId));
  }
}

async function activeJobCount(projectId: string): Promise<number> {
  const rows = await db
    .select({ id: jobsTable.id })
    .from(jobsTable)
    .where(
      and(
        eq(jobsTable.projectId, projectId),
        inArray(jobsTable.status, ["queued", "running"]),
      ),
    );
  return rows.length;
}

/**
 * Cancel a job plus all queued jobs that (transitively) depend on it, then
 * kill any running ffmpeg child so the worker unblocks quickly.
 */
export async function cancelJobById(jobId: string): Promise<Job | null> {
  const [job] = await db
    .select()
    .from(jobsTable)
    .where(eq(jobsTable.id, jobId));
  if (!job) return null;
  if (job.status !== "queued" && job.status !== "running") return job;

  const wasQueued = job.status === "queued";
  const [updated] = await db
    .update(jobsTable)
    .set({
      status: "canceled",
      message: "Canceled",
      finishedAt: wasQueued ? new Date() : null,
    })
    .where(
      and(
        eq(jobsTable.id, jobId),
        or(eq(jobsTable.status, "queued"), eq(jobsTable.status, "running")),
      ),
    )
    .returning();
  if (!updated) {
    // finished in the meantime
    const [current] = await db
      .select()
      .from(jobsTable)
      .where(eq(jobsTable.id, jobId));
    return current ?? null;
  }

  await cancelDependents(jobId);

  const child = children.get(jobId);
  if (child && !child.killed) {
    child.kill("SIGKILL");
  }
  if (wasQueued) {
    // Nothing is running for this job; finalize project state here. (For a
    // running job the worker's finally block performs this bookkeeping.)
    await updateProjectAfterJob(updated, "canceled");
  }
  return updated;
}

/** Cancel every queued job whose dependency chain leads to rootJobId. */
async function cancelDependents(rootJobId: string): Promise<void> {
  const queued = await db
    .select()
    .from(jobsTable)
    .where(eq(jobsTable.status, "queued"));
  const byDependency = new Map<string, Job[]>();
  for (const j of queued) {
    if (!j.dependsOnJobId) continue;
    const list = byDependency.get(j.dependsOnJobId) ?? [];
    list.push(j);
    byDependency.set(j.dependsOnJobId, list);
  }
  const stack = [rootJobId];
  while (stack.length > 0) {
    const current = stack.pop() as string;
    for (const dependent of byDependency.get(current) ?? []) {
      await cancelQueuedJob(
        dependent,
        "Skipped because an earlier step was canceled",
      );
      stack.push(dependent.id);
    }
  }
}
