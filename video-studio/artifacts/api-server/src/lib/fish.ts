/**
 * Fish Audio API client — voice cloning, TTS, ASR, account credit.
 * Docs: https://docs.fish.audio (REST base: https://api.fish.audio)
 */

const FISH_BASE = "https://api.fish.audio";

export function fishConfigured(): boolean {
  return Boolean(process.env.FISH_AUDIO_API_KEY);
}

function authHeader(): Record<string, string> {
  const key = process.env.FISH_AUDIO_API_KEY;
  if (!key) {
    throw new Error(
      "Fish Audio is not configured. Add the FISH_AUDIO_API_KEY secret.",
    );
  }
  return { Authorization: `Bearer ${key}` };
}

async function fishError(res: Response, action: string): Promise<Error> {
  let detail = "";
  try {
    detail = (await res.text()).slice(0, 400);
  } catch {
    // ignore
  }
  if (res.status === 402 || /credit|insufficient|balance/i.test(detail)) {
    return new Error(
      `Fish Audio rejected ${action}: account credit is insufficient (HTTP ${res.status}). Top up at fish.audio and retry. ${detail}`,
    );
  }
  return new Error(`Fish Audio ${action} failed (HTTP ${res.status}): ${detail}`);
}

/** Remaining API credit in USD. */
export async function getCredit(): Promise<number> {
  const res = await fetch(`${FISH_BASE}/wallet/self/api-credit`, {
    headers: authHeader(),
  });
  if (!res.ok) throw await fishError(res, "credit lookup");
  const data = (await res.json()) as { credit?: string | number };
  const credit = Number(data.credit ?? 0);
  return Number.isFinite(credit) ? credit : 0;
}

export interface VoiceSampleFile {
  filename: string;
  data: Buffer;
  contentType: string;
}

/** Create a cloned voice model from audio samples. Returns the provider model id. */
export async function createVoiceModel(options: {
  title: string;
  samples: VoiceSampleFile[];
}): Promise<string> {
  const form = new FormData();
  form.append("type", "tts");
  form.append("title", options.title);
  form.append("train_mode", "fast");
  form.append("visibility", "private");
  form.append("enhance_audio_quality", "true");
  for (const sample of options.samples) {
    form.append(
      "voices",
      new Blob([new Uint8Array(sample.data)], { type: sample.contentType }),
      sample.filename,
    );
  }

  const res = await fetch(`${FISH_BASE}/model`, {
    method: "POST",
    headers: authHeader(),
    body: form,
  });
  if (!res.ok) throw await fishError(res, "voice model creation");
  const data = (await res.json()) as { _id?: string; id?: string };
  const id = data._id ?? data.id;
  if (!id) {
    throw new Error(
      `Fish Audio voice model creation returned no model id: ${JSON.stringify(data).slice(0, 300)}`,
    );
  }
  return id;
}

/** Best-effort deletion of a provider voice model. */
export async function deleteVoiceModel(modelId: string): Promise<void> {
  const res = await fetch(`${FISH_BASE}/model/${encodeURIComponent(modelId)}`, {
    method: "DELETE",
    headers: authHeader(),
  });
  if (!res.ok && res.status !== 404) {
    throw await fishError(res, "voice model deletion");
  }
}

/** Generate speech in a cloned voice. Returns MP3 bytes. */
export async function synthesize(options: {
  text: string;
  referenceId: string;
}): Promise<Buffer> {
  const res = await fetch(`${FISH_BASE}/v1/tts`, {
    method: "POST",
    headers: {
      ...authHeader(),
      "Content-Type": "application/json",
      model: "s1",
    },
    body: JSON.stringify({
      text: options.text,
      reference_id: options.referenceId,
      format: "mp3",
      mp3_bitrate: 128,
      normalize: true,
      latency: "normal",
    }),
  });
  if (!res.ok) throw await fishError(res, "speech synthesis");
  const bytes = Buffer.from(await res.arrayBuffer());
  if (bytes.length === 0) {
    throw new Error("Fish Audio speech synthesis returned empty audio.");
  }
  return bytes;
}

/** Transcribe audio to text. */
export async function transcribe(options: {
  filename: string;
  data: Buffer;
  contentType: string;
}): Promise<{ text: string; duration: number }> {
  const form = new FormData();
  form.append(
    "audio",
    new Blob([new Uint8Array(options.data)], { type: options.contentType }),
    options.filename,
  );
  form.append("ignore_timestamps", "true");

  const res = await fetch(`${FISH_BASE}/v1/asr`, {
    method: "POST",
    headers: authHeader(),
    body: form,
  });
  if (!res.ok) throw await fishError(res, "transcription");
  const data = (await res.json()) as { text?: string; duration?: number };
  return { text: data.text ?? "", duration: data.duration ?? 0 };
}
