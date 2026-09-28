/**
 * Media helpers — move files between object storage and /tmp, probe and
 * transform them with ffmpeg.
 */
import { spawn, type ChildProcess } from "child_process";
import { randomUUID } from "crypto";
import fs from "fs/promises";
import os from "os";
import path from "path";

import { ObjectStorageService } from "./objectStorage";

const objectStorage = new ObjectStorageService();

const WORK_DIR = path.join(os.tmpdir(), "video-studio-jobs");

export async function makeWorkDir(): Promise<string> {
  const dir = path.join(WORK_DIR, randomUUID());
  await fs.mkdir(dir, { recursive: true });
  return dir;
}

export async function cleanupWorkDir(dir: string): Promise<void> {
  try {
    await fs.rm(dir, { recursive: true, force: true });
  } catch {
    // best effort
  }
}

/** Download an object (by `/objects/...` path) to a local file. */
export async function downloadObjectToFile(
  objectPath: string,
  destPath: string,
): Promise<string> {
  const file = await objectStorage.getObjectEntityFile(objectPath);
  await file.download({ destination: destPath });
  return destPath;
}

/** Upload a local file into private object storage. Returns its `/objects/...` path. */
export async function uploadFileAsObject(
  localPath: string,
  contentType: string,
): Promise<{ objectPath: string; size: number }> {
  const uploadURL = await objectStorage.getObjectEntityUploadURL();
  const data = await fs.readFile(localPath);
  const res = await fetch(uploadURL, {
    method: "PUT",
    headers: { "Content-Type": contentType },
    body: new Uint8Array(data),
  });
  if (!res.ok) {
    throw new Error(`Object upload failed (HTTP ${res.status})`);
  }
  return {
    objectPath: objectStorage.normalizeObjectEntityPath(uploadURL),
    size: data.length,
  };
}

export interface MediaInfo {
  durationSeconds: number | null;
  width: number | null;
  height: number | null;
  hasAudio: boolean;
  hasVideo: boolean;
}

export async function probeMedia(localPath: string): Promise<MediaInfo> {
  const out = await runCommand("ffprobe", [
    "-v",
    "error",
    "-print_format",
    "json",
    "-show_format",
    "-show_streams",
    localPath,
  ]);
  const parsed = JSON.parse(out) as {
    format?: { duration?: string };
    streams?: Array<{
      codec_type?: string;
      width?: number;
      height?: number;
    }>;
  };
  const streams = parsed.streams ?? [];
  const video = streams.find((s) => s.codec_type === "video");
  const audio = streams.find((s) => s.codec_type === "audio");
  const duration = parsed.format?.duration
    ? Number(parsed.format.duration)
    : null;
  return {
    durationSeconds:
      duration !== null && Number.isFinite(duration) ? duration : null,
    width: video?.width ?? null,
    height: video?.height ?? null,
    hasAudio: Boolean(audio),
    hasVideo: Boolean(video),
  };
}

function runCommand(cmd: string, args: string[]): Promise<string> {
  return new Promise((resolve, reject) => {
    const child = spawn(cmd, args, { stdio: ["ignore", "pipe", "pipe"] });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d) => (stdout += d));
    child.stderr.on("data", (d) => (stderr += d));
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) resolve(stdout);
      else
        reject(
          new Error(`${cmd} exited with code ${code}: ${stderr.slice(-600)}`),
        );
    });
  });
}

export interface FfmpegRunOptions {
  /** Total output duration, used to compute progress from ffmpeg -progress output. */
  totalDurationSeconds?: number;
  onProgress?: (fraction: number) => void;
  onChild?: (child: ChildProcess) => void;
}

/** Run ffmpeg with the given args (input/output args only; -y and progress flags added here). */
export function runFfmpeg(
  args: string[],
  options: FfmpegRunOptions = {},
): Promise<void> {
  return new Promise((resolve, reject) => {
    const fullArgs = [
      "-y",
      "-hide_banner",
      "-nostdin",
      ...args,
      "-progress",
      "pipe:1",
      "-loglevel",
      "error",
    ];
    const child = spawn("ffmpeg", fullArgs, {
      stdio: ["ignore", "pipe", "pipe"],
    });
    options.onChild?.(child);
    let stderr = "";
    let stdoutBuf = "";
    child.stdout.on("data", (d) => {
      stdoutBuf += String(d);
      if (!options.onProgress || !options.totalDurationSeconds) return;
      const lines = stdoutBuf.split("\n");
      stdoutBuf = lines.pop() ?? "";
      for (const line of lines) {
        const match = /^out_time_ms=(\d+)/.exec(line.trim());
        if (match) {
          const seconds = Number(match[1]) / 1_000_000;
          const fraction = Math.min(
            1,
            seconds / options.totalDurationSeconds,
          );
          options.onProgress(fraction);
        }
      }
    });
    child.stderr.on("data", (d) => (stderr += d));
    child.on("error", reject);
    child.on("close", (code, signal) => {
      if (code === 0) resolve();
      else if (signal) reject(new Error(`ffmpeg was terminated (${signal})`));
      else
        reject(
          new Error(`ffmpeg exited with code ${code}: ${stderr.slice(-800)}`),
        );
    });
  });
}
