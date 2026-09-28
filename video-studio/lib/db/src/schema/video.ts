import {
  pgTable,
  pgEnum,
  text,
  uuid,
  integer,
  real,
  bigint,
  jsonb,
  timestamp,
} from "drizzle-orm/pg-core";

export const assetKindEnum = pgEnum("asset_kind", [
  "source_video",
  "voice_sample",
  "audio",
  "voiceover",
  "broll",
  "render",
]);

export const voiceStatusEnum = pgEnum("voice_status", [
  "pending",
  "training",
  "ready",
  "failed",
]);

export const projectStatusEnum = pgEnum("project_status", [
  "draft",
  "processing",
  "ready",
  "delivered",
  "failed",
]);

export const jobTypeEnum = pgEnum("job_type", [
  "extract_audio",
  "transcribe",
  "create_voice",
  "voice_preview",
  "generate_voiceover",
  "generate_broll",
  "assemble",
  "deliver",
]);

export const jobStatusEnum = pgEnum("job_status", [
  "queued",
  "running",
  "done",
  "failed",
  "canceled",
]);

export const assetsTable = pgTable("assets", {
  id: uuid("id").primaryKey().defaultRandom(),
  name: text("name").notNull(),
  kind: assetKindEnum("kind").notNull(),
  objectPath: text("object_path").notNull(),
  contentType: text("content_type"),
  size: bigint("size", { mode: "number" }),
  durationSeconds: real("duration_seconds"),
  width: integer("width"),
  height: integer("height"),
  projectId: uuid("project_id"),
  createdAt: timestamp("created_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
});

export const scriptsTable = pgTable("scripts", {
  id: uuid("id").primaryKey().defaultRandom(),
  title: text("title").notNull(),
  body: text("body").notNull(),
  createdAt: timestamp("created_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
});

export const voicesTable = pgTable("voices", {
  id: uuid("id").primaryKey().defaultRandom(),
  name: text("name").notNull(),
  provider: text("provider").notNull().default("fish"),
  providerModelId: text("provider_model_id"),
  status: voiceStatusEnum("status").notNull().default("pending"),
  statusMessage: text("status_message"),
  sampleAssetIds: jsonb("sample_asset_ids")
    .$type<string[]>()
    .notNull()
    .default([]),
  previewAssetId: uuid("preview_asset_id"),
  createdAt: timestamp("created_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
});

export const projectsTable = pgTable("projects", {
  id: uuid("id").primaryKey().defaultRandom(),
  title: text("title").notNull(),
  status: projectStatusEnum("status").notNull().default("draft"),
  sourceAssetId: uuid("source_asset_id"),
  scriptId: uuid("script_id"),
  voiceId: uuid("voice_id"),
  voiceoverAssetId: uuid("voiceover_asset_id"),
  renderAssetId: uuid("render_asset_id"),
  createdAt: timestamp("created_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
});

export type JobPayload = {
  /** Free-form parameters a job needs to run (and re-run on retry). */
  text?: string;
  brollCount?: number;
  deliver?: boolean;
  sampleAssetIds?: string[];
};

export const jobsTable = pgTable("jobs", {
  id: uuid("id").primaryKey().defaultRandom(),
  type: jobTypeEnum("type").notNull(),
  status: jobStatusEnum("status").notNull().default("queued"),
  progress: integer("progress").notNull().default(0),
  message: text("message"),
  error: text("error"),
  projectId: uuid("project_id"),
  voiceId: uuid("voice_id"),
  outputAssetId: uuid("output_asset_id"),
  dependsOnJobId: uuid("depends_on_job_id"),
  payload: jsonb("payload").$type<JobPayload>().notNull().default({}),
  createdAt: timestamp("created_at", { withTimezone: true })
    .notNull()
    .defaultNow(),
  startedAt: timestamp("started_at", { withTimezone: true }),
  finishedAt: timestamp("finished_at", { withTimezone: true }),
});

export type Asset = typeof assetsTable.$inferSelect;
export type InsertAsset = typeof assetsTable.$inferInsert;
export type Script = typeof scriptsTable.$inferSelect;
export type InsertScript = typeof scriptsTable.$inferInsert;
export type Voice = typeof voicesTable.$inferSelect;
export type InsertVoice = typeof voicesTable.$inferInsert;
export type Project = typeof projectsTable.$inferSelect;
export type InsertProject = typeof projectsTable.$inferInsert;
export type Job = typeof jobsTable.$inferSelect;
export type InsertJob = typeof jobsTable.$inferInsert;
