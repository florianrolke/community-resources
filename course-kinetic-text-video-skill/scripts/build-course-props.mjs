#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";

const [inputPath, outputPath] = process.argv.slice(2);

if (!inputPath || !outputPath) {
  console.error("Usage: node scripts/build-course-props.mjs <moment-plan.json> <output-props.json>");
  process.exit(1);
}

const input = JSON.parse(fs.readFileSync(inputPath, "utf8"));

const fps = input.fps ?? 30;
const secondsToFrame = (seconds) => Math.round(seconds * fps);

const captionBlocks = [];
const zoomEvents = [];
const flashTransitions = [];
const sfxCues = [];

for (const [index, moment] of (input.moments ?? []).entries()) {
  const startFrame = secondsToFrame(moment.start);
  const durationFrames = secondsToFrame(moment.duration ?? 4.2);
  const id = String(index + 1).padStart(3, "0");
  const lines = moment.lines ?? splitText(moment.text ?? "");
  const circleWord = moment.circleWord ?? pickCircleWord(lines);

  captionBlocks.push({
    id: `hs${id}`,
    startFrame,
    durationFrames,
    mode: "highlight_stack",
    text: lines.join(" / "),
    lines,
    highlightLines: moment.highlightLines ?? [Math.max(0, lines.length - 1)],
    circleWord,
    circleLeftPct: moment.circleLeftPct ?? 70,
    circleWidth: moment.circleWidth ?? circleWidthFor(circleWord),
  });

  if (moment.zoom !== false) {
    zoomEvents.push({
      id: `z${id}`,
      startFrame: startFrame + (moment.zoomDelayFrames ?? 10),
      durationFrames: secondsToFrame(moment.zoomDuration ?? 3.4),
      zoom: moment.zoom ?? 1.08,
      mode: "punch",
    });
  }

  if (moment.flash) {
    const flashFrame = startFrame + secondsToFrame(moment.flashAt ?? 3.0);
    flashTransitions.push({
      id: `f${id}`,
      startFrame: flashFrame,
      durationFrames: 10,
      intensity: moment.flashIntensity ?? 0.72,
      coolWash: moment.coolWash ?? true,
    });
    sfxCues.push({
      id: `sf${id}-whoosh`,
      startFrame: flashFrame,
      file: "sfx/course-whoosh.mp3",
      volume: moment.whooshVolume ?? 0.3,
    });
  }

  if (moment.sfx !== false) {
    sfxCues.push({
      id: `sf${id}-ding`,
      startFrame: startFrame + (moment.sfxDelayFrames ?? 12),
      file: moment.sfxFile ?? "sfx/course-ding.mp3",
      volume: moment.sfxVolume ?? 0.32,
    });
  }
}

for (const [index, push] of (input.slowPushIns ?? []).entries()) {
  zoomEvents.push({
    id: `slow-${String(index + 1).padStart(2, "0")}`,
    startFrame: secondsToFrame(push.start),
    durationFrames: secondsToFrame(push.duration ?? 5.6),
    zoom: push.zoom ?? 1.055,
    mode: "slow",
    outFrames: push.outFrames ?? 20,
  });
  if (push.sfx !== false) {
    sfxCues.push({
      id: `sf-slow-${String(index + 1).padStart(2, "0")}`,
      startFrame: secondsToFrame(push.start),
      file: "sfx/course-whoosh.mp3",
      volume: push.volume ?? 0.25,
    });
  }
}

captionBlocks.sort(byStart);
zoomEvents.sort(byStart);
flashTransitions.sort(byStart);
sfxCues.sort(byStart);

const props = {
  manifest: {
    videoSrc: input.videoSrc,
    fps,
    width: input.width ?? 1920,
    height: input.height ?? 1080,
    durationFrames: input.durationFrames ?? secondsToFrame(input.durationSeconds),
    depthMask: {
      enabled: false,
      xPct: 51,
      yPct: 35,
      widthPct: 19,
      heightPct: 31,
      opacity: 0.98,
    },
    captionBlocks,
    titleCards: [],
    lightLeaks: [],
    flashTransitions,
    pushTransitions: [],
    zoomEvents,
    behindGraphics: [],
    sfxCues,
  },
};

fs.mkdirSync(path.dirname(outputPath), { recursive: true });
fs.writeFileSync(outputPath, `${JSON.stringify(props, null, 2)}\n`);

console.log(`Wrote ${outputPath}`);
console.log(`Caption moments: ${captionBlocks.length}`);
console.log(`Zoom events: ${zoomEvents.length}`);
console.log(`Flash transitions: ${flashTransitions.length}`);
console.log(`SFX cues: ${sfxCues.length}`);

function splitText(text) {
  const normalized = text.trim();
  if (!normalized) return [];
  if (normalized.includes("/")) {
    return normalized.split("/").map((part) => part.trim()).filter(Boolean);
  }
  const words = normalized.split(/\s+/);
  const midpoint = Math.ceil(words.length / 2);
  return [words.slice(0, midpoint).join(" "), words.slice(midpoint).join(" ")].filter(Boolean);
}

function pickCircleWord(lines) {
  const words = lines.join(" ").split(/\s+/).filter(Boolean);
  return words[words.length - 1]?.replace(/[^a-zA-Z0-9'-]/g, "") ?? "";
}

function circleWidthFor(word) {
  const length = Math.max(4, String(word ?? "").length);
  return Math.min(520, Math.max(190, length * 38));
}

function byStart(a, b) {
  return a.startFrame - b.startFrame;
}
