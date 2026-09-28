import {
  CreateAssetBody,
  DeleteAssetParams,
  GetAssetParams,
  ListAssetsQueryParams,
} from "@workspace/api-zod";
import { assetsTable, db, projectsTable, voicesTable } from "@workspace/db";
import { desc, eq, or } from "drizzle-orm";
import { Router, type IRouter, type Request, type Response } from "express";

import {
  ObjectNotFoundError,
  ObjectStorageService,
} from "../lib/objectStorage";
import { toApiAsset } from "../lib/serialize";
import { requireAuth } from "../middlewares/requireAuth";

const router: IRouter = Router();
const objectStorage = new ObjectStorageService();

router.use("/assets", requireAuth);

router.get("/assets", async (req: Request, res: Response) => {
  const parsed = ListAssetsQueryParams.safeParse(req.query);
  if (!parsed.success) {
    res.status(400).json({ error: "Invalid query parameters" });
    return;
  }
  const kind = parsed.data.kind;
  const rows = kind
    ? await db
        .select()
        .from(assetsTable)
        .where(eq(assetsTable.kind, kind))
        .orderBy(desc(assetsTable.createdAt))
    : await db
        .select()
        .from(assetsTable)
        .orderBy(desc(assetsTable.createdAt));
  res.json(rows.map(toApiAsset));
});

router.post("/assets", async (req: Request, res: Response) => {
  const parsed = CreateAssetBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: "Missing or invalid required fields" });
    return;
  }
  const { name, kind, objectPath, contentType, size } = parsed.data;

  try {
    await objectStorage.trySetObjectEntityAclPolicy(objectPath, {
      owner: req.user?.id ?? "owner",
      visibility: "private",
    });
  } catch (error) {
    if (error instanceof ObjectNotFoundError) {
      res
        .status(400)
        .json({ error: "Uploaded object not found — upload may have failed" });
      return;
    }
    throw error;
  }

  const [row] = await db
    .insert(assetsTable)
    .values({
      name,
      kind,
      objectPath,
      contentType: contentType ?? null,
      size: size ?? null,
    })
    .returning();
  if (!row) {
    res.status(500).json({ error: "Failed to register asset" });
    return;
  }
  res.status(201).json(toApiAsset(row));
});

router.get("/assets/:assetId", async (req: Request, res: Response) => {
  const parsed = GetAssetParams.safeParse(req.params);
  if (!parsed.success) {
    res.status(404).json({ error: "Asset not found" });
    return;
  }
  const [row] = await db
    .select()
    .from(assetsTable)
    .where(eq(assetsTable.id, parsed.data.assetId));
  if (!row) {
    res.status(404).json({ error: "Asset not found" });
    return;
  }
  res.json(toApiAsset(row));
});

router.delete("/assets/:assetId", async (req: Request, res: Response) => {
  const parsed = DeleteAssetParams.safeParse(req.params);
  if (!parsed.success) {
    res.status(404).json({ error: "Asset not found" });
    return;
  }
  const assetId = parsed.data.assetId;
  const [row] = await db
    .select()
    .from(assetsTable)
    .where(eq(assetsTable.id, assetId));
  if (!row) {
    res.status(404).json({ error: "Asset not found" });
    return;
  }

  const referencingProjects = await db
    .select({ id: projectsTable.id })
    .from(projectsTable)
    .where(
      or(
        eq(projectsTable.sourceAssetId, assetId),
        eq(projectsTable.voiceoverAssetId, assetId),
        eq(projectsTable.renderAssetId, assetId),
      ),
    );
  if (referencingProjects.length > 0) {
    res.status(409).json({
      error: "This asset is used by a project. Remove it from the project first.",
    });
    return;
  }
  const voices = await db.select().from(voicesTable);
  const usedByVoice = voices.some(
    (v) => v.sampleAssetIds.includes(assetId) || v.previewAssetId === assetId,
  );
  if (usedByVoice) {
    res.status(409).json({
      error: "This asset is used by a voice. Delete the voice first.",
    });
    return;
  }

  // Best-effort removal of the stored object itself.
  try {
    const file = await objectStorage.getObjectEntityFile(row.objectPath);
    await file.delete();
  } catch {
    // keep going — DB row is the source of truth
  }

  await db.delete(assetsTable).where(eq(assetsTable.id, assetId));
  res.status(204).end();
});

export default router;
