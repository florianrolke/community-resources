"""Remote box helper — FILL IN YOUR OWN SERVER DETAILS.

This is a redacted stub. The original pointed at a private render box; the host,
user and SSH key have been replaced with placeholders so nothing in this repo
identifies real infrastructure.

You only need this if you want to:
  - run whisper transcription remotely (`whisper_hostinger_client.py`), or
  - render with `build_vo_edit.py --remote`.

Both are optional. To stay entirely local, install faster-whisper yourself and
replace `whisper_hostinger_client.transcribe()` with a local call — the rest of
the pipeline does not care where the transcript came from, only that it is
whisper-shaped JSON with word-level timings.

Set these via environment variables rather than editing the file:
    REMOTE_SSH_HOST=user@your.server.ip
    REMOTE_SSH_KEY=~/.ssh/your_key
"""
import os
import subprocess

KEY = os.path.expanduser(os.environ.get("REMOTE_SSH_KEY", "~/.ssh/CHANGE_ME"))
HOST = os.environ.get("REMOTE_SSH_HOST", "user@CHANGE_ME")

_BASE = ["-i", KEY, "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=25"]


def _check_configured() -> None:
    if "CHANGE_ME" in HOST or "CHANGE_ME" in KEY:
        raise RuntimeError(
            "Remote box not configured. Set REMOTE_SSH_HOST and REMOTE_SSH_KEY, "
            "or run the pipeline fully locally (see this file's docstring)."
        )


def ssh(cmd: str, timeout: int = 900):
    _check_configured()
    return subprocess.run(["ssh", *_BASE, HOST, cmd],
                          capture_output=True, text=True, timeout=timeout)


def scp_up(local: str, remote: str, recursive: bool = False, timeout: int = 3600):
    _check_configured()
    args = ["scp", *_BASE]
    if recursive:
        args.append("-r")
    args += [local, f"{HOST}:{remote}"]
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def scp_down(remote: str, local: str, timeout: int = 1800):
    _check_configured()
    return subprocess.run(["scp", *_BASE, f"{HOST}:{remote}", local],
                          capture_output=True, text=True, timeout=timeout)
