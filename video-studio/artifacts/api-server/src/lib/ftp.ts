/**
 * FTP delivery to the user's hosting (e.g. Hostinger).
 */
import { Client } from "basic-ftp";

export function ftpConfigured(): boolean {
  return Boolean(
    process.env.FTP_HOST && process.env.FTP_USER && process.env.FTP_PASSWORD,
  );
}

export async function deliverFileViaFtp(
  localPath: string,
  remoteName: string,
): Promise<void> {
  const client = new Client(30_000);
  try {
    await client.access({
      host: process.env.FTP_HOST as string,
      user: process.env.FTP_USER as string,
      password: process.env.FTP_PASSWORD as string,
      secure: process.env.FTP_SECURE === "true",
    });
    const dir = process.env.FTP_DIR;
    if (dir) {
      await client.ensureDir(dir);
    }
    await client.uploadFrom(localPath, remoteName);
  } finally {
    client.close();
  }
}
