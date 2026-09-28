/**
 * Pluggable AI b-roll generation.
 *
 * The pipeline is designed for interchangeable providers. No provider is
 * bundled yet — when a provider key is configured (e.g. a video model API),
 * implement it here and set BROLL_PROVIDER accordingly. Until then, b-roll
 * jobs fail fast with a clear message instead of producing fake output.
 */

export interface BrollRequest {
  prompt: string;
  durationSeconds: number;
  outPath: string;
}

export function brollProviderName(): string | null {
  return process.env.BROLL_PROVIDER || null;
}

export function brollConfigured(): boolean {
  return brollProviderName() !== null;
}

export async function generateBrollClip(_request: BrollRequest): Promise<void> {
  const provider = brollProviderName();
  if (!provider) {
    throw new Error(
      "B-roll generation is not configured yet. Add a video-generation provider API key and set the BROLL_PROVIDER environment variable, then retry this job. The rest of the pipeline works without b-roll (set b-roll clips to 0).",
    );
  }
  throw new Error(
    `B-roll provider "${provider}" is set but no implementation exists for it yet.`,
  );
}
