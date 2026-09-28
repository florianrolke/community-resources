import { type NextFunction, type Request, type Response } from "express";

/** Rejects unauthenticated requests. Mount after authMiddleware. */
export function requireAuth(
  req: Request,
  res: Response,
  next: NextFunction,
): void {
  if (typeof req.isAuthenticated !== "function" || !req.isAuthenticated()) {
    res.status(401).json({ error: "Unauthorized" });
    return;
  }
  next();
}
