import {
  CancelJobParams,
  GetJobParams,
  ListJobsQueryParams,
  RetryJobParams,
} from "@workspace/api-zod";
import { db, jobsTable } from "@workspace/db";
import { and, desc, eq, type SQL } from "drizzle-orm";
import { Router, type IRouter, type Request, type Response } from "express";

import { cancelJobById } from "../lib/jobQueue";
import { toApiJob } from "../lib/serialize";
import { requireAuth } from "../middlewares/requireAuth";

const router: IRouter = Router();

router.use("/jobs", requireAuth);

router.get("/jobs", async (req: Request, res: Response) => {
  const parsed = ListJobsQueryParams.safeParse(req.query);
  if (!parsed.success) {
    res.status(400).json({ error: "Invalid query parameters" });
    return;
  }
  const conditions: SQL[] = [];
  if (parsed.data.projectId)
    conditions.push(eq(jobsTable.projectId, parsed.data.projectId));
  if (parsed.data.status)
    conditions.push(eq(jobsTable.status, parsed.data.status));

  const base = db.select().from(jobsTable);
  const rows =
    conditions.length > 0
      ? await base
          .where(and(...conditions))
          .orderBy(desc(jobsTable.createdAt))
          .limit(200)
      : await base.orderBy(desc(jobsTable.createdAt)).limit(200);
  res.json(rows.map(toApiJob));
});

router.get("/jobs/:jobId", async (req: Request, res: Response) => {
  const parsed = GetJobParams.safeParse(req.params);
  if (!parsed.success) {
    res.status(404).json({ error: "Job not found" });
    return;
  }
  const [row] = await db
    .select()
    .from(jobsTable)
    .where(eq(jobsTable.id, parsed.data.jobId));
  if (!row) {
    res.status(404).json({ error: "Job not found" });
    return;
  }
  res.json(toApiJob(row));
});

router.post("/jobs/:jobId/cancel", async (req: Request, res: Response) => {
  const parsed = CancelJobParams.safeParse(req.params);
  if (!parsed.success) {
    res.status(404).json({ error: "Job not found" });
    return;
  }
  const [job] = await db
    .select()
    .from(jobsTable)
    .where(eq(jobsTable.id, parsed.data.jobId));
  if (!job) {
    res.status(404).json({ error: "Job not found" });
    return;
  }
  if (job.status !== "queued" && job.status !== "running") {
    res.status(409).json({ error: "This job has already finished." });
    return;
  }
  const updated = await cancelJobById(job.id);
  res.json(toApiJob(updated ?? job));
});

router.post("/jobs/:jobId/retry", async (req: Request, res: Response) => {
  const parsed = RetryJobParams.safeParse(req.params);
  if (!parsed.success) {
    res.status(404).json({ error: "Job not found" });
    return;
  }
  const [job] = await db
    .select()
    .from(jobsTable)
    .where(eq(jobsTable.id, parsed.data.jobId));
  if (!job) {
    res.status(404).json({ error: "Job not found" });
    return;
  }
  if (job.status !== "failed" && job.status !== "canceled") {
    res
      .status(409)
      .json({ error: "Only failed or canceled jobs can be retried." });
    return;
  }
  const [retried] = await db
    .insert(jobsTable)
    .values({
      type: job.type,
      projectId: job.projectId,
      voiceId: job.voiceId,
      payload: job.payload,
      dependsOnJobId: null,
    })
    .returning();
  if (!retried) {
    res.status(500).json({ error: "Failed to queue retry" });
    return;
  }
  res.status(202).json(toApiJob(retried));
});

export default router;
