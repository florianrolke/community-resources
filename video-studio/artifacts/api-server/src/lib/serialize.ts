/**
 * Convert DB rows into API response shapes (dates → ISO strings, undefined → null).
 */
import type { Asset, Job, Project, Script, Voice } from "@workspace/db";

const iso = (d: Date): string => d.toISOString();
const isoOrNull = (d: Date | null): string | null => (d ? d.toISOString() : null);

export function toApiAsset(a: Asset) {
  return {
    id: a.id,
    name: a.name,
    kind: a.kind,
    objectPath: a.objectPath,
    contentType: a.contentType ?? null,
    size: a.size ?? null,
    durationSeconds: a.durationSeconds ?? null,
    width: a.width ?? null,
    height: a.height ?? null,
    projectId: a.projectId ?? null,
    createdAt: iso(a.createdAt),
  };
}

export function toApiScript(s: Script) {
  return {
    id: s.id,
    title: s.title,
    body: s.body,
    wordCount: s.body.trim() === "" ? 0 : s.body.trim().split(/\s+/).length,
    createdAt: iso(s.createdAt),
    updatedAt: iso(s.updatedAt),
  };
}

export function toApiVoice(v: Voice) {
  return {
    id: v.id,
    name: v.name,
    provider: v.provider,
    providerModelId: v.providerModelId ?? null,
    status: v.status,
    statusMessage: v.statusMessage ?? null,
    sampleAssetIds: v.sampleAssetIds,
    previewAssetId: v.previewAssetId ?? null,
    createdAt: iso(v.createdAt),
  };
}

export function toApiProject(p: Project) {
  return {
    id: p.id,
    title: p.title,
    status: p.status,
    sourceAssetId: p.sourceAssetId ?? null,
    scriptId: p.scriptId ?? null,
    voiceId: p.voiceId ?? null,
    voiceoverAssetId: p.voiceoverAssetId ?? null,
    renderAssetId: p.renderAssetId ?? null,
    createdAt: iso(p.createdAt),
    updatedAt: iso(p.updatedAt),
  };
}

export function toApiJob(j: Job) {
  return {
    id: j.id,
    type: j.type,
    status: j.status,
    progress: j.progress,
    message: j.message ?? null,
    error: j.error ?? null,
    projectId: j.projectId ?? null,
    voiceId: j.voiceId ?? null,
    outputAssetId: j.outputAssetId ?? null,
    dependsOnJobId: j.dependsOnJobId ?? null,
    createdAt: iso(j.createdAt),
    startedAt: isoOrNull(j.startedAt),
    finishedAt: isoOrNull(j.finishedAt),
  };
}
