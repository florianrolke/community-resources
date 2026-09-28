# Course Kinetic Text Video Skill

Remotion + Agent Zero/Codex skill for turning long-form talking-head videos into course-style edits with kinetic text, champagne/gold highlighter bars, circled emphasis words, face punch-ins, slower push-ins, flash transitions, and SFX cues.

This repo packages the editing style, not any private source videos or API keys.

## What It Does

- Adds big lower-third kinetic text moments on transcript idea boundaries.
- Uses champagne/gold highlight strips that pair well with a luxury green/gold visual system.
- Draws SVG circles around important words.
- Punches in on the speaker's face when a word is circled.
- Adds slower 5-second face push-ins for pacing changes.
- Syncs SFX to text hits, circles, punch-ins, and flash transitions.
- Keeps rendering on a server/Hostinger-style worker instead of filling local storage.

## Repo Structure

```text
remotion/
  src/components/course-style/CourseOverlayKit.tsx
  src/compositions/CourseStyleEdit.tsx
examples/
  moment-plan.example.json
  course-v2-full-props.real-example.json
scripts/
  build-course-props.mjs
docs/
  style-spec.md
  hostinger-render-workflow.md
  sfx-sources.md
skill/
  SKILL.md
```

## Install Into A Remotion Project

1. Copy `remotion/src/components/course-style/CourseOverlayKit.tsx` into your Remotion project.
2. Copy `remotion/src/compositions/CourseStyleEdit.tsx` into your Remotion project.
3. Register `CourseStyleEdit` in your Remotion root. See `docs/hostinger-render-workflow.md`.
4. Put your source video in `public/`.
5. Put SFX files in `public/sfx/` with these names, or update the props:
   - `course-ding.mp3`
   - `course-pop.mp3`
   - `course-whoosh.mp3`
6. Create props from an idea-timed moment plan:

```bash
node scripts/build-course-props.mjs examples/moment-plan.example.json props/course-props.json
```

7. Render:

```bash
npx remotion render CourseStyleEdit out/course-edit.mp4 --props=props/course-props.json --concurrency=1 --codec=h264 --crf=20
```

## Safety

Do not commit:

- `.env`
- API keys
- source videos
- final renders
- private transcripts
- server SSH keys

Use the `.gitignore` in this repo as the default.

## License

MIT for the code and docs in this repo. SFX assets must be downloaded under their own license from the provider you choose.
