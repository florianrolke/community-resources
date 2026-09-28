/**
 * Job handlers — one async function per job type. Each receives the job row
 * and a context for progress updates, cancellation checks, and child-process
 * registration (so cancel can kill a running ffmpeg).
 */
import type { ChildProcess } from "child_process";
import path from "path";
import fs from "fs/promises";

import {
  assetsTable,
  db,
  jobsTable,
  projectsTable,
  scriptsTable,
  voicesTable,
  type Asset,
  type Job,
  type Project,
} from "@workspace/db";
import { eq, and, inArray } from "drizzle-orm";

import * as fish from "./fish";
import { generateBrollClip } from "./broll";
import { deliverFileViaFtp, ftpConfigured } from "./ftp";
import {
  cleanupWorkDir,
  downloadObjectToFile,
  makeWorkDir,
  probeMedia,
  runFfmpeg,
  uploadFileAsObject,
} from "./media";

export interface JobContext {
  update: (progress: number, message?: string) => Promise<void>;
  isCanceled: () => Promise<boolean>;
  registerChild: (child: ChildProcess) => void;
}

type Handler = (job: Job, ctx: JobContext) => Promise<void>;

async function getAssetOrThrow(assetId: string, label: string): Promise<Asset> {
  const [asset] = await db
    .select()
    .from(assetsTable)
    .where(eq(assetsTable.id, assetId));
  if (!asset) throw new Error(`${label} asset no longer exists.`);
  return asset;
}

async function getProjectOrThrow(job: Job): Promise<Project> {
  if (!job.projectId) throw new Error("Job has no project attached.");
  const [project] = await db
    .select()
    .from(projectsTable)
    .where(eq(projectsTable.id, job.projectId));
  if (!project) throw new Error("Project no longer exists.");
  return project;
}

async function createAssetRow(values: {
  name: string;
  kind: Asset["kind"];
  objectPath: string;
  contentType: string;
  size: number;
  durationSeconds?: number | null;
  width?: number | null;
  height?: number | null;
  projectId?: string | null;
}): Promise<Asset> {
  const [row] = await db.insert(assetsTable).values(values).returning();
  if (!row) throw new Error("Failed to record output asset.");
  return row;
}

function extAudioName(contentType: string | null): string {
  if (contentType?.includes("wav")) return "sample.wav";
  if (contentType?.includes("m4a") || contentType?.includes("mp4"))
    return "sample.m4a";
  return "sample.mp3";
}

/** Download an asset; if it's a video, extract clean mono audio from it. */
async function materializeAudio(
  asset: Asset,
  workDir: string,
  tag: string,
): Promise<string> {
  const rawPath = path.join(workDir, `${tag}-raw`);
  await downloadObjectToFile(asset.objectPath, rawPath);
  const info = await probeMedia(rawPath);
  if (!info.hasAudio) {
    throw new Error(`"${asset.name}" contains no audio track.`);
  }
  if (!info.hasVideo && asset.contentType?.startsWith("audio/")) {
    return rawPath;
  }
  const audioPath = path.join(workDir, `${tag}.mp3`);
  await runFfmpeg([
    "-i",
    rawPath,
    "-vn",
    "-ac",
    "1",
    "-ar",
    "44100",
    "-b:a",
    "160k",
    audioPath,
  ]);
  return audioPath;
}

const extractAudio: Handler = async (job, ctx) => {
  const project = await getProjectOrThrow(job);
  if (!project.sourceAssetId)
    throw new Error("Project has no source video attached.");
  const source = await getAssetOrThrow(project.sourceAssetId, "Source video");

  const workDir = await makeWorkDir();
  try {
    await ctx.update(5, "Downloading source video");
    const srcPath = path.join(workDir, "source");
    await downloadObjectToFile(source.objectPath, srcPath);
    const info = await probeMedia(srcPath);
    if (!info.hasAudio) {
      throw new Error(
        "The source video has no audio track — nothing to extract.",
      );
    }

    await ctx.update(25, "Extracting and cleaning audio");
    const outPath = path.join(workDir, "audio.mp3");
    await runFfmpeg(
      [
        "-i",
        srcPath,
        "-vn",
        "-af",
        "highpass=f=80,lowpass=f=12000,loudnorm=I=-16:TP=-1.5:LRA=11",
        "-ac",
        "1",
        "-ar",
        "44100",
        "-b:a",
        "160k",
        outPath,
      ],
      {
        totalDurationSeconds: info.durationSeconds ?? undefined,
        onProgress: (f) => void ctx.update(25 + Math.round(f * 55)),
        onChild: ctx.registerChild,
      },
    );

    await ctx.update(85, "Uploading extracted audio");
    const outInfo = await probeMedia(outPath);
    const uploaded = await uploadFileAsObject(outPath, "audio/mpeg");
    const asset = await createAssetRow({
      name: `${project.title} — extracted audio`,
      kind: "audio",
      objectPath: uploaded.objectPath,
      contentType: "audio/mpeg",
      size: uploaded.size,
      durationSeconds: outInfo.durationSeconds,
      projectId: project.id,
    });
    await db
      .update(jobsTable)
      .set({ outputAssetId: asset.id })
      .where(eq(jobsTable.id, job.id));
  } finally {
    await cleanupWorkDir(workDir);
  }
};

const transcribeJob: Handler = async (job, ctx) => {
  const project = await getProjectOrThrow(job);
  if (!project.sourceAssetId)
    throw new Error("Project has no source video attached.");
  const source = await getAssetOrThrow(project.sourceAssetId, "Source video");

  const workDir = await makeWorkDir();
  try {
    await ctx.update(10, "Preparing audio for transcription");
    const audioPath = await materializeAudio(source, workDir, "transcribe");
    await ctx.update(40, "Transcribing with Fish Audio");
    const audio = await fs.readFile(audioPath);
    const result = await fish.transcribe({
      filename: "audio.mp3",
      data: audio,
      contentType: "audio/mpeg",
    });
    if (!result.text.trim()) {
      throw new Error("Transcription returned no text.");
    }

    await ctx.update(85, "Saving transcript as script");
    const [script] = await db
      .insert(scriptsTable)
      .values({
        title: `${project.title} — transcript`,
        body: result.text.trim(),
      })
      .returning();
    if (script && !project.scriptId) {
      await db
        .update(projectsTable)
        .set({ scriptId: script.id, updatedAt: new Date() })
        .where(eq(projectsTable.id, project.id));
    }
    await ctx.update(95, `Transcript saved as “${project.title} — transcript”`);
  } finally {
    await cleanupWorkDir(workDir);
  }
};

const createVoice: Handler = async (job, ctx) => {
  if (!job.voiceId) throw new Error("Job has no voice attached.");
  const [voice] = await db
    .select()
    .from(voicesTable)
    .where(eq(voicesTable.id, job.voiceId));
  if (!voice) throw new Error("Voice no longer exists.");

  await db
    .update(voicesTable)
    .set({ status: "training", statusMessage: null })
    .where(eq(voicesTable.id, voice.id));

  const sampleIds = job.payload.sampleAssetIds ?? voice.sampleAssetIds;
  if (sampleIds.length === 0)
    throw new Error("No voice samples were attached.");
  const samples = await db
    .select()
    .from(assetsTable)
    .where(inArray(assetsTable.id, sampleIds));
  if (samples.length === 0)
    throw new Error("The attached voice sample assets no longer exist.");

  const workDir = await makeWorkDir();
  try {
    const files: fish.VoiceSampleFile[] = [];
    let index = 0;
    for (const sample of samples) {
      index += 1;
      await ctx.update(
        Math.round((index / (samples.length + 1)) * 40),
        `Preparing sample ${index} of ${samples.length}`,
      );
      const audioPath = await materializeAudio(sample, workDir, `s${index}`);
      files.push({
        filename: audioPath.endsWith(".mp3")
          ? `sample-${index}.mp3`
          : extAudioName(sample.contentType),
        data: await fs.readFile(audioPath),
        contentType: "audio/mpeg",
      });
    }

    if (await ctx.isCanceled()) throw new Error("Canceled");
    await ctx.update(55, "Cloning voice with Fish Audio");
    const modelId = await fish.createVoiceModel({
      title: voice.name,
      samples: files,
    });

    await db
      .update(voicesTable)
      .set({ status: "ready", providerModelId: modelId, statusMessage: null })
      .where(eq(voicesTable.id, voice.id));
    await ctx.update(95, "Voice clone ready");
  } catch (error) {
    await db
      .update(voicesTable)
      .set({
        status: "failed",
        statusMessage: error instanceof Error ? error.message : String(error),
      })
      .where(eq(voicesTable.id, voice.id));
    throw error;
  } finally {
    await cleanupWorkDir(workDir);
  }
};

async function synthesizeToAsset(options: {
  text: string;
  referenceId: string;
  assetName: string;
  projectId?: string | null;
  ctx: JobContext;
  progressBase: number;
}): Promise<Asset> {
  const { ctx } = options;
  await ctx.update(options.progressBase, "Generating speech with Fish Audio");
  const audio = await fish.synthesize({
    text: options.text,
    referenceId: options.referenceId,
  });

  const workDir = await makeWorkDir();
  try {
    const outPath = path.join(workDir, "voiceover.mp3");
    await fs.writeFile(outPath, audio);
    const info = await probeMedia(outPath);
    await ctx.update(80, "Uploading generated audio");
    const uploaded = await uploadFileAsObject(outPath, "audio/mpeg");
    return await createAssetRow({
      name: options.assetName,
      kind: "voiceover",
      objectPath: uploaded.objectPath,
      contentType: "audio/mpeg",
      size: uploaded.size,
      durationSeconds: info.durationSeconds,
      projectId: options.projectId ?? null,
    });
  } finally {
    await cleanupWorkDir(workDir);
  }
}

async function getReadyVoice(voiceId: string) {
  const [voice] = await db
    .select()
    .from(voicesTable)
    .where(eq(voicesTable.id, voiceId));
  if (!voice) throw new Error("Voice no longer exists.");
  if (voice.status !== "ready" || !voice.providerModelId) {
    throw new Error(`Voice "${voice.name}" is not ready yet (status: ${voice.status}).`);
  }
  return voice;
}

const voicePreview: Handler = async (job, ctx) => {
  if (!job.voiceId) throw new Error("Job has no voice attached.");
  const voice = await getReadyVoice(job.voiceId);
  const text = job.payload.text?.trim();
  if (!text) throw new Error("No preview text provided.");

  const asset = await synthesizeToAsset({
    text,
    referenceId: voice.providerModelId as string,
    assetName: `${voice.name} — preview`,
    ctx,
    progressBase: 20,
  });
  await db
    .update(voicesTable)
    .set({ previewAssetId: asset.id })
    .where(eq(voicesTable.id, voice.id));
  await db
    .update(jobsTable)
    .set({ outputAssetId: asset.id })
    .where(eq(jobsTable.id, job.id));
};

const generateVoiceover: Handler = async (job, ctx) => {
  const project = await getProjectOrThrow(job);
  if (!project.voiceId) throw new Error("Project has no voice selected.");
  if (!project.scriptId) throw new Error("Project has no script attached.");
  const voice = await getReadyVoice(project.voiceId);
  const [script] = await db
    .select()
    .from(scriptsTable)
    .where(eq(scriptsTable.id, project.scriptId));
  if (!script) throw new Error("Script no longer exists.");
  if (!script.body.trim()) throw new Error("The script is empty.");

  const asset = await synthesizeToAsset({
    text: script.body.trim(),
    referenceId: voice.providerModelId as string,
    assetName: `${project.title} — voiceover`,
    projectId: project.id,
    ctx,
    progressBase: 15,
  });
  await db
    .update(projectsTable)
    .set({ voiceoverAssetId: asset.id, updatedAt: new Date() })
    .where(eq(projectsTable.id, project.id));
  await db
    .update(jobsTable)
    .set({ outputAssetId: asset.id })
    .where(eq(jobsTable.id, job.id));
};

const generateBroll: Handler = async (job, ctx) => {
  const project = await getProjectOrThrow(job);
  const count = job.payload.brollCount ?? 1;
  let promptSeed = project.title;
  if (project.scriptId) {
    const [script] = await db
      .select()
      .from(scriptsTable)
      .where(eq(scriptsTable.id, project.scriptId));
    if (script) promptSeed = `${project.title}. ${script.body.slice(0, 240)}`;
  }

  const workDir = await makeWorkDir();
  try {
    for (let i = 0; i < count; i += 1) {
      if (await ctx.isCanceled()) throw new Error("Canceled");
      await ctx.update(
        Math.round((i / count) * 80) + 5,
        `Generating b-roll clip ${i + 1} of ${count}`,
      );
      const outPath = path.join(workDir, `broll-${i + 1}.mp4`);
      await generateBrollClip({
        prompt: `Cinematic b-roll, no text overlays: ${promptSeed}`,
        durationSeconds: 6,
        outPath,
      });
      const info = await probeMedia(outPath);
      const uploaded = await uploadFileAsObject(outPath, "video/mp4");
      await createAssetRow({
        name: `${project.title} — b-roll ${i + 1}`,
        kind: "broll",
        objectPath: uploaded.objectPath,
        contentType: "video/mp4",
        size: uploaded.size,
        durationSeconds: info.durationSeconds,
        width: info.width,
        height: info.height,
        projectId: project.id,
      });
    }
  } finally {
    await cleanupWorkDir(workDir);
  }
};

const assemble: Handler = async (job, ctx) => {
  const project = await getProjectOrThrow(job);
  if (!project.sourceAssetId)
    throw new Error("Project has no source video attached.");
  if (!project.voiceoverAssetId)
    throw new Error(
      "Project has no generated voiceover yet — run the voiceover step first.",
    );
  const source = await getAssetOrThrow(project.sourceAssetId, "Source video");
  const voiceover = await getAssetOrThrow(
    project.voiceoverAssetId,
    "Voiceover",
  );
  const brolls = await db
    .select()
    .from(assetsTable)
    .where(
      and(
        eq(assetsTable.kind, "broll"),
        eq(assetsTable.projectId, project.id),
      ),
    );

  const workDir = await makeWorkDir();
  try {
    await ctx.update(5, "Downloading inputs");
    const videoPath = path.join(workDir, "source");
    const voPath = path.join(workDir, "voiceover.mp3");
    await downloadObjectToFile(source.objectPath, videoPath);
    await downloadObjectToFile(voiceover.objectPath, voPath);
    const videoInfo = await probeMedia(videoPath);
    if (!videoInfo.hasVideo)
      throw new Error("The source asset has no video track.");
    const width = videoInfo.width ?? 1920;
    const height = videoInfo.height ?? 1080;
    const duration = videoInfo.durationSeconds ?? 0;

    const brollPaths: Array<{ path: string; duration: number }> = [];
    for (let i = 0; i < brolls.length; i += 1) {
      const broll = brolls[i] as Asset;
      const p = path.join(workDir, `broll-${i}.mp4`);
      await downloadObjectToFile(broll.objectPath, p);
      const info = await probeMedia(p);
      brollPaths.push({
        path: p,
        duration: Math.min(info.durationSeconds ?? 6, 8),
      });
    }

    await ctx.update(20, "Rendering final cut");
    const outPath = path.join(workDir, "render.mp4");
    const args: string[] = ["-i", videoPath, "-i", voPath];
    for (const b of brollPaths) args.push("-i", b.path);

    if (brollPaths.length > 0 && duration > 4) {
      // Overlay each b-roll clip as a cutaway at evenly spaced points while
      // the new voiceover keeps playing underneath.
      const filters: string[] = [];
      let base = "[0:v]";
      brollPaths.forEach((b, i) => {
        const start = Math.max(
          1,
          Math.min(
            (duration * (i + 1)) / (brollPaths.length + 1),
            duration - b.duration - 1,
          ),
        );
        const end = start + b.duration;
        const inLabel = `[${i + 2}:v]`;
        filters.push(
          `${inLabel}scale=${width}:${height}:force_original_aspect_ratio=decrease,` +
            `pad=${width}:${height}:(ow-iw)/2:(oh-ih)/2:color=black,` +
            `setpts=PTS-STARTPTS+${start.toFixed(3)}/TB[b${i}]`,
        );
        filters.push(
          `${base}[b${i}]overlay=eof_action=pass:enable='between(t,${start.toFixed(3)},${end.toFixed(3)})'[v${i}]`,
        );
        base = `[v${i}]`;
      });
      args.push(
        "-filter_complex",
        filters.join(";"),
        "-map",
        base,
        "-map",
        "1:a",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
      );
    } else {
      // No b-roll: keep the original video stream untouched, swap the audio.
      args.push("-map", "0:v", "-map", "1:a", "-c:v", "copy");
    }
    args.push("-c:a", "aac", "-b:a", "192k", "-shortest", outPath);

    await runFfmpeg(args, {
      totalDurationSeconds: duration || undefined,
      onProgress: (f) => void ctx.update(20 + Math.round(f * 60)),
      onChild: ctx.registerChild,
    });

    await ctx.update(85, "Uploading finished render");
    const outInfo = await probeMedia(outPath);
    const uploaded = await uploadFileAsObject(outPath, "video/mp4");
    const asset = await createAssetRow({
      name: `${project.title} — final cut`,
      kind: "render",
      objectPath: uploaded.objectPath,
      contentType: "video/mp4",
      size: uploaded.size,
      durationSeconds: outInfo.durationSeconds,
      width: outInfo.width,
      height: outInfo.height,
      projectId: project.id,
    });
    await db
      .update(projectsTable)
      .set({ renderAssetId: asset.id, updatedAt: new Date() })
      .where(eq(projectsTable.id, project.id));
    await db
      .update(jobsTable)
      .set({ outputAssetId: asset.id })
      .where(eq(jobsTable.id, job.id));
  } finally {
    await cleanupWorkDir(workDir);
  }
};

const deliver: Handler = async (job, ctx) => {
  const project = await getProjectOrThrow(job);
  if (!ftpConfigured()) {
    throw new Error(
      "FTP delivery is not configured. Add FTP_HOST, FTP_USER and FTP_PASSWORD secrets (and optional FTP_DIR), then retry.",
    );
  }
  if (!project.renderAssetId)
    throw new Error("Project has no finished render to deliver.");
  const render = await getAssetOrThrow(project.renderAssetId, "Render");

  const workDir = await makeWorkDir();
  try {
    await ctx.update(10, "Downloading render");
    const localPath = path.join(workDir, "render.mp4");
    await downloadObjectToFile(render.objectPath, localPath);
    await ctx.update(40, "Uploading to your site via FTP");
    const slug = project.title
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 60);
    const remoteName = `${slug || "video"}-${project.id.slice(0, 8)}.mp4`;
    await deliverFileViaFtp(localPath, remoteName);
    await ctx.update(95, `Delivered as ${remoteName}`);
  } finally {
    await cleanupWorkDir(workDir);
  }
};

export const handlers: Record<Job["type"], Handler> = {
  extract_audio: extractAudio,
  transcribe: transcribeJob,
  create_voice: createVoice,
  voice_preview: voicePreview,
  generate_voiceover: generateVoiceover,
  generate_broll: generateBroll,
  assemble,
  deliver,
};
