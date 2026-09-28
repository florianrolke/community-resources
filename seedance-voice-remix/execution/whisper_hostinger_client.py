#!/usr/bin/env python3
"""
whisper_hostinger_client.py - LOCAL driver for server-side faster-whisper.

Replaces the OpenAI whisper-1 API call in meeting_call_to_shorts.transcribe():
compresses the call audio locally, ships the small mp3 to the remote box, runs
faster-whisper there (whisper-venv, CPU int8, niced), downloads the transcript
JSON (whisper-1 verbose shape). No external API, no local encode load beyond the
one-off mp3 compression, keeps your machine free.
"""
import json
import subprocess
import time
from pathlib import Path

import hostinger  # KEY, HOST, _BASE

ROOT = Path(__file__).resolve().parents[1]
REMOTE_DIR = "/home/agent-zero-data/whisper-jobs"
WVENV = "/home/agent-zero-data/whisper-venv/bin/python"
SCRIPT = REMOTE_DIR + "/hostinger_whisper.py"
_SSH = ["ssh", "-n", *hostinger._BASE, "-o", "ServerAliveInterval=20"]
_SCP = ["scp", *hostinger._BASE]


def _ssh(cmd, timeout=90):
    return subprocess.run([*_SSH, hostinger.HOST, cmd], stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=timeout)


def _scp_up(local, remote, timeout=600):
    return subprocess.run([*_SCP, str(local), "%s:%s" % (hostinger.HOST, remote)],
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)


def _scp_down(remote, local, timeout=600):
    return subprocess.run([*_SCP, "%s:%s" % (hostinger.HOST, remote), str(local)],
                          stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)


def deploy():
    _ssh("mkdir -p %s" % REMOTE_DIR)
    r = _scp_up(ROOT / "execution" / "hostinger_whisper.py", SCRIPT)
    if r.returncode != 0:
        raise RuntimeError("deploy hostinger_whisper.py failed: %s" % r.stderr)


def transcribe(mp3_path, out_json, model="small", threads=4, log=print):
    """Transcribe mp3 on the remote box; write out_json (whisper-1 shape) and return it."""
    deploy()
    slug = "%s-%d" % (Path(mp3_path).stem[:24], int(time.time()))
    rmp3 = "%s/%s.mp3" % (REMOTE_DIR, slug)
    rjson = "%s/%s.json" % (REMOTE_DIR, slug)
    log("[whisper/hostinger] uploading audio ...")
    r = _scp_up(mp3_path, rmp3, timeout=900)
    if r.returncode != 0:
        raise RuntimeError("audio upload failed: %s" % r.stderr)
    log("[whisper/hostinger] transcribing on server (model=%s, %d threads, niced) ..." % (model, threads))
    r = _ssh("nice -n 15 %s %s %s %s --model %s --threads %d"
             % (WVENV, SCRIPT, rmp3, rjson, model, threads), timeout=3600)
    if r.returncode != 0 or "done:" not in (r.stdout + r.stderr):
        raise RuntimeError("server whisper failed:\nSTDOUT %s\nSTDERR %s" % (r.stdout[-500:], r.stderr[-800:]))
    log("[whisper/hostinger] %s" % r.stdout.strip().splitlines()[-1] if r.stdout.strip() else "[whisper/hostinger] done")
    r = _scp_down(rjson, out_json, timeout=300)
    if r.returncode != 0:
        raise RuntimeError("transcript download failed: %s" % r.stderr)
    _ssh("rm -f %s %s" % (rmp3, rjson))  # tidy up
    return json.loads(Path(out_json).read_text(encoding="utf-8"))
