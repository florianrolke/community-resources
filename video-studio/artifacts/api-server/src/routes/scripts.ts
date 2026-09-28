import {
  CreateScriptBody,
  DeleteScriptParams,
  GetScriptParams,
  UpdateScriptBody,
  UpdateScriptParams,
} from "@workspace/api-zod";
import { db, projectsTable, scriptsTable } from "@workspace/db";
import { desc, eq } from "drizzle-orm";
import { Router, type IRouter, type Request, type Response } from "express";

import { toApiScript } from "../lib/serialize";
import { requireAuth } from "../middlewares/requireAuth";

const router: IRouter = Router();

router.use("/scripts", requireAuth);

router.get("/scripts", async (_req: Request, res: Response) => {
  const rows = await db
    .select()
    .from(scriptsTable)
    .orderBy(desc(scriptsTable.updatedAt));
  res.json(rows.map(toApiScript));
});

router.post("/scripts", async (req: Request, res: Response) => {
  const parsed = CreateScriptBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: "Title and body are required" });
    return;
  }
  const [row] = await db
    .insert(scriptsTable)
    .values({ title: parsed.data.title, body: parsed.data.body })
    .returning();
  if (!row) {
    res.status(500).json({ error: "Failed to create script" });
    return;
  }
  res.status(201).json(toApiScript(row));
});

router.get("/scripts/:scriptId", async (req: Request, res: Response) => {
  const parsed = GetScriptParams.safeParse(req.params);
  if (!parsed.success) {
    res.status(404).json({ error: "Script not found" });
    return;
  }
  const [row] = await db
    .select()
    .from(scriptsTable)
    .where(eq(scriptsTable.id, parsed.data.scriptId));
  if (!row) {
    res.status(404).json({ error: "Script not found" });
    return;
  }
  res.json(toApiScript(row));
});

router.put("/scripts/:scriptId", async (req: Request, res: Response) => {
  const params = UpdateScriptParams.safeParse(req.params);
  const body = UpdateScriptBody.safeParse(req.body);
  if (!params.success) {
    res.status(404).json({ error: "Script not found" });
    return;
  }
  if (!body.success) {
    res.status(400).json({ error: "Invalid script fields" });
    return;
  }
  const patch: { title?: string; body?: string; updatedAt: Date } = {
    updatedAt: new Date(),
  };
  if (body.data.title !== undefined) patch.title = body.data.title;
  if (body.data.body !== undefined) patch.body = body.data.body;

  const [row] = await db
    .update(scriptsTable)
    .set(patch)
    .where(eq(scriptsTable.id, params.data.scriptId))
    .returning();
  if (!row) {
    res.status(404).json({ error: "Script not found" });
    return;
  }
  res.json(toApiScript(row));
});

router.delete("/scripts/:scriptId", async (req: Request, res: Response) => {
  const parsed = DeleteScriptParams.safeParse(req.params);
  if (!parsed.success) {
    res.status(404).json({ error: "Script not found" });
    return;
  }
  const scriptId = parsed.data.scriptId;
  const [row] = await db
    .select({ id: scriptsTable.id })
    .from(scriptsTable)
    .where(eq(scriptsTable.id, scriptId));
  if (!row) {
    res.status(404).json({ error: "Script not found" });
    return;
  }
  await db
    .update(projectsTable)
    .set({ scriptId: null, updatedAt: new Date() })
    .where(eq(projectsTable.scriptId, scriptId));
  await db.delete(scriptsTable).where(eq(scriptsTable.id, scriptId));
  res.status(204).end();
});

export default router;
