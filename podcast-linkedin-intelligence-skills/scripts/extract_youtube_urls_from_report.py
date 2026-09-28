from __future__ import annotations
import argparse, csv, io, re
from pathlib import Path
from scripts.common import write_csv

FIELDS = ["scope", "podcast_or_series", "upload_channel", "channel_url", "episode_title", "guest_or_speaker", "youtube_url", "notes"]
YOUTUBE_RE = re.compile(r"https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[A-Za-z0-9_-]+[^\s,)]*")
CHANNEL_RE = re.compile(r"https?://(?:www\.)?youtube\.com/@[A-Za-z0-9_.-]+")
PODCAST_HEADING_RE = re.compile(r"^(Family Law Growth Podcast|Family Law Formula Podcast|[A-Z][A-Za-z0-9 &'?:-]+ Podcast)\s*$")


def _blank_row() -> dict:
    return {field: "" for field in FIELDS}


def _rows_from_csv_blocks(text: str) -> list[dict]:
    rows = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        header = line.strip().lower()
        if "youtube_url" not in header or "episode_title" not in header:
            continue
        block = [line]
        for nxt in lines[i + 1:]:
            if not nxt.strip() or "Using Tool" in nxt or nxt.strip() == "View":
                break
            block.append(nxt)
        reader = csv.DictReader(io.StringIO("\n".join(block)))
        for raw in reader:
            url = (raw.get("youtube_url") or raw.get("YouTube URL") or "").strip()
            if "youtube.com/watch" not in url and "youtu.be/" not in url:
                continue
            row = _blank_row()
            for key, value in raw.items():
                if key in row:
                    row[key] = value or ""
            row["youtube_url"] = url.rstrip(".,")
            rows.append(row)
    return rows


def _rows_from_structured_answer(text: str) -> list[dict]:
    rows = []
    current_podcast = ""
    for line in text.splitlines():
        clean = line.strip()
        if not clean:
            continue
        heading = PODCAST_HEADING_RE.match(clean)
        if heading:
            current_podcast = heading.group(1)
            continue
        if "youtube.com/watch?v=" not in clean and "youtu.be/" not in clean:
            continue
        url_match = YOUTUBE_RE.search(clean)
        if not url_match:
            continue
        url = url_match.group(0).rstrip(".,")
        before = clean[:url_match.start()].strip(" -|\t")
        if not before or before.startswith("https://"):
            rows.append({**_blank_row(), "scope": "pasted report", "podcast_or_series": current_podcast, "youtube_url": url, "notes": "final URL list only"})
            continue

        title = before
        guest = ""
        # Handles markdown/table-ish rows: Episode title <tab/spaces> Guest <tab/spaces> URL
        parts = [p.strip(" |") for p in re.split(r"\t+|\s{2,}", before) if p.strip(" |")]
        if len(parts) >= 2:
            title, guest = parts[0], parts[1]
        elif " ? " in before:
            title = before.split(" ? ", 1)[0].strip()
        row = _blank_row()
        row.update({
            "scope": "pasted report",
            "podcast_or_series": current_podcast,
            "episode_title": title,
            "guest_or_speaker": guest,
            "youtube_url": url,
            "notes": "extracted from final answer row",
        })
        rows.append(row)
    return rows


def _rows_from_text_urls(text: str) -> list[dict]:
    rows = []
    pending_title = ""
    pending_channel = ""
    for line in text.splitlines():
        clean = line.strip()
        if not clean:
            continue
        channel = CHANNEL_RE.search(clean)
        if channel:
            pending_channel = channel.group(0)
        urls = YOUTUBE_RE.findall(clean)
        if urls:
            title = pending_title or clean.split("http", 1)[0].strip(" ,-|")
            for url in urls:
                rows.append({
                    "scope": "pasted report",
                    "podcast_or_series": "",
                    "upload_channel": "",
                    "channel_url": pending_channel,
                    "episode_title": title if not title.startswith("https://") else "",
                    "guest_or_speaker": "",
                    "youtube_url": url.rstrip(".,"),
                    "notes": "extracted from pasted report text",
                })
            continue
        lowered = clean.lower()
        if not lowered.startswith(("using tool", "view", "source", "parallel", "video search", "write file")) and len(clean) < 180:
            pending_title = clean
    return rows


def extract_youtube_rows(text: str) -> list[dict]:
    rows = _rows_from_csv_blocks(text) + _rows_from_structured_answer(text) + _rows_from_text_urls(text)
    seen = set()
    out = []
    for row in rows:
        url = row.get("youtube_url", "")
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(row)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = extract_youtube_rows(Path(args.input).read_text(encoding="utf-8"))
    write_csv(args.output, rows, FIELDS)
    print(f"Rows written: {len(rows)} -> {args.output}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
