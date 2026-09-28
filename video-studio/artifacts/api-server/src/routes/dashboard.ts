import {
  assetsTable,
  db,
  jobsTable,
  projectsTable,
  scriptsTable,
  voicesTable,
} from "@workspace/db";
import { count, desc, inArray } from "drizzle-orm";
import { Router, type IRouter, type Request, type Response } from "express";

import { toApiJob } from "../lib/serialize";
import { requireAuth } from "../middlewares/requireAuth";

const router: IRouter = Router();

router.use("/dashboard", requireAuth);

router.get("/dashboard/summary", async (_req: Request, res: Response) => {
  const [projects, voices, scripts, assets, activeJobs, recentJobs] =
    await Promise.all([
      db.select({ n: count() }).from(projectsTable),
      db.select({ n: count() }).from(voicesTable),
      db.select({ n: count() }).from(scriptsTable),
      db.select({ n: count() }).from(assetsTable),
      db
        .select({ n: count() })
        .from(jobsTable)
        .where(inArray(jobsTable.status, ["queued", "running"])),
      db.select().from(jobsTable).orderBy(desc(jobsTable.createdAt)).limit(8),
    ]);

  res.json({
    projects: projects[0]?.n ?? 0,
    voices: voices[0]?.n ?? 0,
    scripts: scripts[0]?.n ?? 0,
    assets: assets[0]?.n ?? 0,
    activeJobs: activeJobs[0]?.n ?? 0,
    recentJobs: recentJobs.map(toApiJob),
  });
});

export default router;
