import {
  CreateVoiceBody,
  DeleteVoiceParams,
  GetVoiceParams,
  PreviewVoiceBody,
  PreviewVoiceParams,
} from "@workspace/api-zod";
import {
  assetsTable,
  db,
  jobsTable,
  projectsTable,
  voicesTable,
} from "@workspace/db";
import { and, desc, eq, inArray } from "drizzle-orm";
import { Router, type IRouter, type Request, type Response } from "express";

import { fishConfigured } from "../lib/fish";
import * as fish from "../lib/fish";
import { toApiJob, toApiVoice } from "../lib/serialize";
import { requireAuth } from "../middlewares/requireAuth";

const router: IRouter = Router();

router.use("/voices", requireAuth);

router.get("/voices", async (_req: Request, res: Response) => {
  const rows = await db
    .select()
    .from(voicesTable)
    .orderBy(desc(voicesTable.createdAt));
  res.json(rows.map(toApiVoice));
});

router.post("/voices", async (req: Request, res: Response) => {
  const parsed = CreateVoiceBody.safeParse(req.body);
  if (!parsed.success) {
    res
      .status(400)
      .json({ error: "A name and at least one voice sample are required" });
    return;
  }
  if (!fishConfigured()) {
    res.status(409).json({
      error:
        "Fish Audio is not configured. Add the FISH_AUDIO_API_KEY secret first.",
    });
    return;
  }
  const { name, sampleAssetIds } = parsed.data;
  const samples = await db
    .select({ id: assetsTable.id })
    .from(assetsTable)
    .where(inArray(assetsTable.id, sampleAssetIds));
  if (samples.length !== sampleAssetIds.length) {
    res
      .status(400)
      .json({ error: "One or more sample assets could not be found" });
    return;
  }

  const [voice] = await db
    .insert(voicesTable)
    .values({ name, sampleAssetIds, provider: "fish", status: "pending" })
    .returning();
  if (!voice) {
    res.status(500).json({ error: "Failed to create voice" });
    return;
  }
  await db.insert(jobsTable).values({
    type: "create_voice",
    voiceId: voice.id,
    payload: { sampleAssetIds },
  });
  res.status(201).json(toApiVoice(voice));
});

router.get("/voices/:voiceId", async (req: Request, res: Response) => {
  const parsed = GetVoiceParams.safeParse(req.params);
  if (!parsed.success) {
    res.status(404).json({ error: "Voice not found" });
    return;
  }
  const [row] = await db
    .select()
    .from(voicesTable)
    .where(eq(voicesTable.id, parsed.data.voiceId));
  if (!row) {
    res.status(404).json({ error: "Voice not found" });
    return;
  }
  res.json(toApiVoice(row));
});

router.delete("/voices/:voiceId", async (req: Request, res: Response) => {
  const parsed = DeleteVoiceParams.safeParse(req.params);
  if (!parsed.success) {
    res.status(404).json({ error: "Voice not found" });
    return;
  }
  const [voice] = await db
    .select()
    .from(voicesTable)
    .where(eq(voicesTable.id, parsed.data.voiceId));
  if (!voice) {
    res.status(404).json({ error: "Voice not found" });
    return;
  }
  const activeJobs = await db
    .select({ id: jobsTable.id })
    .from(jobsTable)
    .where(
      and(
        eq(jobsTable.voiceId, voice.id),
        inArray(jobsTable.status, ["queued", "running"]),
      ),
    );
  if (activeJobs.length > 0) {
    res.status(409).json({
      error:
        "This voice still has jobs queued or running. Cancel them first.",
    });
    return;
  }
  if (voice.providerModelId && fishConfigured()) {
    try {
      await fish.deleteVoiceModel(voice.providerModelId);
    } catch (error) {
      req.log.warn({ err: error }, "provider voice model deletion failed");
    }
  }
  await db
    .update(projectsTable)
    .set({ voiceId: null, updatedAt: new Date() })
    .where(eq(projectsTable.voiceId, voice.id));
  await db.delete(voicesTable).where(eq(voicesTable.id, voice.id));
  res.status(204).end();
});

router.post(
  "/voices/:voiceId/preview",
  async (req: Request, res: Response) => {
    const params = PreviewVoiceParams.safeParse(req.params);
    if (!params.success) {
      res.status(404).json({ error: "Voice not found" });
      return;
    }
    const body = PreviewVoiceBody.safeParse(req.body);
    if (!body.success) {
      res.status(400).json({ error: "Preview text is required" });
      return;
    }
    const [voice] = await db
      .select()
      .from(voicesTable)
      .where(eq(voicesTable.id, params.data.voiceId));
    if (!voice) {
      res.status(404).json({ error: "Voice not found" });
      return;
    }
    if (voice.status !== "ready") {
      res.status(409).json({
        error: `This voice is not ready yet (status: ${voice.status}).`,
      });
      return;
    }
    const [job] = await db
      .insert(jobsTable)
      .values({
        type: "voice_preview",
        voiceId: voice.id,
        payload: { text: body.data.text },
      })
      .returning();
    if (!job) {
      res.status(500).json({ error: "Failed to queue preview" });
      return;
    }
    res.status(202).json(toApiJob(job));
  },
);

export default router;
