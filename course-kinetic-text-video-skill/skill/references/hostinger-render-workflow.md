# Hostinger / Agent Zero Render Workflow

This workflow assumes rendering happens on a server/container, not the local machine.

## Register Composition

Add this to your Remotion root:

```tsx
import { Composition } from "remotion";
import { CourseStyleEditWrapper } from "./compositions/CourseStyleEdit";
import type { CourseStyleManifest } from "./components/course-style/CourseOverlayKit";

<Composition
  id="CourseStyleEdit"
  component={CourseStyleEditWrapper}
  durationInFrames={5400}
  fps={30}
  width={1920}
  height={1080}
  calculateMetadata={({ props }) => {
    const manifest = (props as { manifest?: CourseStyleManifest }).manifest;
    return {
      durationInFrames: manifest?.durationFrames ?? 5400,
      width: manifest?.width ?? 1920,
      height: manifest?.height ?? 1080,
      fps: manifest?.fps ?? 30,
    };
  }}
  defaultProps={{
    manifest: {
      videoSrc: "",
      fps: 30,
      width: 1920,
      height: 1080,
      durationFrames: 5400,
      captionBlocks: [],
      titleCards: [],
      lightLeaks: [],
      flashTransitions: [],
      pushTransitions: [],
      zoomEvents: [],
      sfxCues: [],
      behindGraphics: [],
      depthMask: { enabled: false, xPct: 51, yPct: 35, widthPct: 19, heightPct: 31 },
    } satisfies CourseStyleManifest,
  }}
/>
```

## Server Folder Pattern

Example:

```text
/a0/usr/projects/luxury-render-20260606/remotion-editor/
  public/
    source-video.mp4
    sfx/
      course-ding.mp3
      course-pop.mp3
      course-whoosh.mp3
  props/
    course-props.json
  out/
```

## Validate

```bash
npx tsc --noEmit
```

## Render Proof Stills First

```bash
npx remotion still CourseStyleEdit out/proof.png \
  --props=props/course-props.json \
  --frame=706 \
  --log=warn
```

## Full Render

```bash
npx remotion render CourseStyleEdit out/course-edit-1080p.mp4 \
  --props=props/course-props.json \
  --concurrency=1 \
  --codec=h264 \
  --crf=20 \
  --log=warn
```

For long renders in Docker:

```bash
docker exec -d -w /a0/usr/projects/YOUR_PROJECT/remotion-editor remotion-worker-gold \
  bash -lc 'mkdir -p out && npx remotion render CourseStyleEdit out/course-edit-1080p.mp4 --props=props/course-props.json --concurrency=1 --codec=h264 --crf=20 --log=warn > out/course-render.log 2>&1'
```

## Verify

```bash
ffprobe -v error \
  -show_entries format=duration,size \
  -show_entries stream=index,codec_type,codec_name,width,height,r_frame_rate \
  -of default=nw=1 \
  out/course-edit-1080p.mp4
```

## Storage Rule

Avoid storing large originals locally.

Preferred flow:

1. Upload source video directly to the server.
2. Render on the server.
3. Download only final MP4s, preview PNGs, logs, props, and transcripts.
4. Never commit source videos or rendered MP4s.
