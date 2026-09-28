import { Router, type IRouter, type Request, type Response } from "express";

import { brollConfigured, brollProviderName } from "../lib/broll";
import { fishConfigured, getCredit } from "../lib/fish";
import { ftpConfigured } from "../lib/ftp";
import { requireAuth } from "../middlewares/requireAuth";

const router: IRouter = Router();

router.use("/settings", requireAuth);

router.get("/settings/status", async (_req: Request, res: Response) => {
  let voice: {
    configured: boolean;
    detail: string | null;
    credit: number | null;
  };
  if (!fishConfigured()) {
    voice = {
      configured: false,
      detail: "Add the FISH_AUDIO_API_KEY secret to enable voice cloning.",
      credit: null,
    };
  } else {
    try {
      const credit = await getCredit();
      voice = {
        configured: true,
        detail:
          credit <= 0
            ? "Fish Audio connected, but account credit is empty — top up at fish.audio before cloning or generating speech."
            : "Fish Audio connected.",
        credit,
      };
    } catch (error) {
      voice = {
        configured: true,
        detail: `Fish Audio key present but the API returned an error: ${
          error instanceof Error ? error.message : String(error)
        }`,
        credit: null,
      };
    }
  }

  res.json({
    voice,
    broll: {
      configured: brollConfigured(),
      detail: brollConfigured()
        ? `Provider: ${brollProviderName()}`
        : "No b-roll provider configured yet — pipeline runs work with b-roll set to 0.",
      credit: null,
    },
    ftp: {
      configured: ftpConfigured(),
      detail: ftpConfigured()
        ? `Delivering to ${process.env.FTP_HOST}`
        : "Add FTP_HOST, FTP_USER and FTP_PASSWORD secrets to enable delivery to your site.",
      credit: null,
    },
  });
});

export default router;
