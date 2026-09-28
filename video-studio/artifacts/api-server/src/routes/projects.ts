import {
  CreateProjectBody,
  DeleteProjectParams,
  GetProjectParams,
  RunProjectPipelineBody,
  RunProjectPipelineParams,
  UpdateProjectBody,
  UpdateProjectParams,
} from "@workspace/api-zod";
import {
  assetsTable,
  db,
  jobsTable,
  projectsTable,
  scriptsTable,
  voicesTable,
  type Job,
  type Project,
} from "@workspace/db";
import { and, desc, eq, inArray } from "drizzle-orm";
import { Router, type IRouter, type Request, type Response } from "express";

import { fishConfigured } from "../lib/fish";
import { toApiJob, toApiProject } from "../lib/serialize";
import { requireAuth } from "../middlewares/requireAuth";

const router: IRouter = Router();

router.use("/projects", requireAuth);

async function assertExists(
  table: "asset" | "script" | "voice",
  id: string,
): Promise<boolean> {
  if (table === "asset") {
    const [row] = await db
      .select({ id: assetsTable.id })
      .from(assetsTable)
      .where(eq(assetsTable.id, id));
    return Boolean(row);
  }
  if (table === "script") {
    const [row] = await db
      .select({ id: scriptsTable.id })
      .from(scriptsTable)
      .where(eq(scriptsTable.id, id));
    return Boolean(row);
  }
  const [row] = await db
    .select({ id: voicesTable.id })
    .from(voicesTable)
    .where(eq(voicesTable.id, id));
  return Boolean(row);
}

router.get("/projects", async (_req: Request, res: Response) => {
  const rows = await db
    .select()
    .from(projectsTable)
    .orderBy(desc(projectsTable.updatedAt));
  res.json(rows.map(toApiProject));
});

router.post("/projects", async (req: Request, res: Response) => {
  const parsed = CreateProjectBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: "A project title is required" });
    return;
  }
  const { title, sourceAssetId, scriptId, voiceId } = parsed.data;
  if (sourceAssetId && !(await assertExists("asset", sourceAssetId))) {
    res.status(400).json({ error: "Source video asset not found" });
    return;
  }
  if (scriptId && !(await assertExists("script", scriptId))) {
    res.status(400).json({ error: "Script not found" });
    return;
  }
  if (voiceId && !(await assertExists("voice", voiceId))) {
    res.status(400).json({ error: "Voice not found" });
    return;
  }
  const [row] = await db
    .insert(projectsTable)
    .values({
      title,
      sourceAssetId: sourceAssetId ?? null,
      scriptId: scriptId ?? null,
      voiceId: voiceId ?? null,
    })
    .returning();
  if (!row) {
    res.status(500).json({ error: "Failed to create project" });
    return;
  }
  res.status(201).json(toApiProject(row));
});

router.get("/projects/:projectId", async (req: Request, res: Response) => {
  const parsed = GetProjectParams.safeParse(req.params);
  if (!parsed.success) {
    res.status(404).json({ error: "Project not found" });
    return;
  }
  const [row] = await db
    .select()
    .from(projectsTable)
    .where(eq(projectsTable.id, parsed.data.projectId));
  if (!row) {
    res.status(404).json({ error: "Project not found" });
    return;
  }
  res.json(toApiProject(row));
});

router.patch("/projects/:projectId", async (req: Request, res: Response) => {
  const params = UpdateProjectParams.safeParse(req.params);
  if (!params.success) {
    res.status(404).json({ error: "Project not found" });
    return;
  }
  const body = UpdateProjectBody.safeParse(req.body);
  if (!body.success) {
    res.status(400).json({ error: "Invalid project fields" });
    return;
  }
  const data = body.data;
  const patch: Partial<{
    title: string;
    sourceAssetId: string | null;
    scriptId: string | null;
    voiceId: string | null;
    updatedAt: Date;
  }> = { updatedAt: new Date() };

  if (data.title !== undefined) patch.title = data.title;
  for (const key of ["sourceAssetId", "scriptId", "voiceId"] as const) {
    const value = data[key];
    if (value === undefined) continue;
    if (value !== null) {
      const kind =
        key === "sourceAssetId"
          ? "asset"
          : key === "scriptId"
            ? "script"
            : "voice";
      if (!(await assertExists(kind, value))) {
        res.status(400).json({ error: `Referenced ${kind} not found` });
        return;
      }
    }
    patch[key] = value;
  }

  const [row] = await db
    .update(projectsTable)
    .set(patch)
    .where(eq(projectsTable.id, params.data.projectId))
    .returning();
  if (!row) {
    res.status(404).json({ error: "Project not found" });
    return;
  }
  res.json(toApiProject(row));
});

router.delete("/projects/:projectId", async (req: Request, res: Response) => {
  const parsed = DeleteProjectParams.safeParse(req.params);
  if (!parsed.success) {
    res.status(404).json({ error: "Project not found" });
    return;
  }
  const [row] = await db
    .select({ id: projectsTable.id })
    .from(projectsTable)
    .where(eq(projectsTable.id, parsed.data.projectId));
  if (!row) {
    res.status(404).json({ error: "Project not found" });
    return;
  }
  const activeJobs = await db
    .select({ id: jobsTable.id })
    .from(jobsTable)
    .where(
      and(
        eq(jobsTable.projectId, row.id),
        inArray(jobsTable.status, ["queued", "running"]),
      ),
    );
  if (activeJobs.length > 0) {
    res.status(409).json({
      error:
        "This project still has jobs queued or running. Cancel them first.",
    });
    return;
  }
  await db.delete(jobsTable).where(eq(jobsTable.projectId, row.id));
  await db.delete(projectsTable).where(eq(projectsTable.id, row.id));
  res.status(204).end();
});

const PIPELINE_ORDER: Job["type"][] = [
  "extract_audio",
  "transcribe",
  "generate_voiceover",
  "generate_broll",
  "assemble",
  "deliver",
];

router.post(
  "/projects/:projectId/pipeline",
  async (req: Request, res: Response) => {
    const params = RunProjectPipelineParams.safeParse(req.params);
    if (!params.success) {
      res.status(404).json({ error: "Project not found" });
      return;
    }
    const body = RunProjectPipelineBody.safeParse(req.body ?? {});
    if (!body.success) {
      res.status(400).json({ error: "Invalid pipeline options" });
      return;
    }
    const [project] = await db
      .select()
      .from(projectsTable)
      .where(eq(projectsTable.id, params.data.projectId));
    if (!project) {
      res.status(404).json({ error: "Project not found" });
      return;
    }

    const active = await db
      .select({ id: jobsTable.id })
      .from(jobsTable)
      .where(
        and(
          eq(jobsTable.projectId, project.id),
          inArray(jobsTable.status, ["queued", "running"]),
        ),
      );
    if (active.length > 0) {
      res.status(409).json({
        error: "This project already has jobs queued or running.",
      });
      return;
    }

    const brollCount = body.data.brollCount ?? 0;
    const deliver = body.data.deliver ?? false;
    let steps: Job["type"][];
    if (body.data.steps && body.data.steps.length > 0) {
      steps = PIPELINE_ORDER.filter((s) => body.data.steps?.includes(s));
    } else {
      steps = ["extract_audio", "generate_voiceover"];
      if (brollCount > 0) steps.push("generate_broll");
      steps.push("assemble");
    }
    if (deliver && !steps.includes("deliver")) steps.push("deliver");

    const problems = await validateSteps(project, steps);
    if (problems) {
      res.status(400).json({ error: problems });
      return;
    }

    const createdJobs: Job[] = [];
    let previousId: string | null = null;
    for (const type of steps) {
      const inserted: Job[] = await db
        .insert(jobsTable)
        .values({
          type,
          projectId: project.id,
          voiceId: project.voiceId,
          dependsOnJobId: previousId,
          payload: { brollCount, deliver },
        })
        .returning();
      const job = inserted[0];
      if (!job) {
        res.status(500).json({ error: "Failed to queue pipeline jobs" });
        return;
      }
      createdJobs.push(job);
      previousId = job.id;
    }
    await db
      .update(projectsTable)
      .set({ status: "processing", updatedAt: new Date() })
      .where(eq(projectsTable.id, project.id));

    res.status(202).json({ jobs: createdJobs.map(toApiJob) });
  },
);

async function validateSteps(
  project: Project,
  steps: Job["type"][],
): Promise<string | null> {
  if (steps.length === 0) return "No pipeline steps selected.";
  const needsSource = ["extract_audio", "transcribe", "assemble"].some((s) =>
    steps.includes(s as Job["type"]),
  );
  if (needsSource && !project.sourceAssetId) {
    return "Attach a source video to this project first.";
  }
  if (steps.includes("generate_voiceover")) {
    if (!project.scriptId) return "Attach a script before generating a voiceover.";
    if (!project.voiceId) return "Select a voice before generating a voiceover.";
    const [voice] = await db
      .select()
      .from(voicesTable)
      .where(eq(voicesTable.id, project.voiceId));
    if (!voice) return "The selected voice no longer exists.";
    if (voice.status !== "ready")
      return `The selected voice is not ready yet (status: ${voice.status}).`;
  }
  if (
    (steps.includes("generate_voiceover") || steps.includes("transcribe")) &&
    !fishConfigured()
  ) {
    return "Fish Audio is not configured. Add the FISH_AUDIO_API_KEY secret first.";
  }
  if (steps.includes("assemble") && !steps.includes("generate_voiceover")) {
    if (!project.voiceoverAssetId)
      return "Assembly needs a voiceover — include the voiceover step or generate one first.";
  }
  if (steps.includes("deliver") && !steps.includes("assemble")) {
    if (!project.renderAssetId)
      return "Delivery needs a finished render — include the assemble step or render first.";
  }
  return null;
}

export default router;
