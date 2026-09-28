import { Router, type IRouter } from "express";

import assetsRouter from "./assets";
import authRouter from "./auth";
import dashboardRouter from "./dashboard";
import healthRouter from "./health";
import jobsRouter from "./jobs";
import projectsRouter from "./projects";
import scriptsRouter from "./scripts";
import settingsRouter from "./settings";
import storageRouter from "./storage";
import voicesRouter from "./voices";

const router: IRouter = Router();

router.use(healthRouter);
router.use(authRouter);
router.use(storageRouter);
router.use(assetsRouter);
router.use(scriptsRouter);
router.use(voicesRouter);
router.use(projectsRouter);
router.use(jobsRouter);
router.use(dashboardRouter);
router.use(settingsRouter);

export default router;
