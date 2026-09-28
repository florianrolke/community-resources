# SFX Sources

This repo does not redistribute third-party SFX files.

Create this folder in your Remotion project:

```text
public/sfx/
```

Use these filenames:

```text
course-ding.mp3
course-pop.mp3
course-whoosh.mp3
```

## Recommended Searches

Use royalty-free sources such as Pixabay and verify the current license before publishing.

Pixabay search links:

- Ding/bell emphasis: https://pixabay.com/sound-effects/search/soft%20bell%20ding/
- UI pop/tap: https://pixabay.com/sound-effects/search/ui%20pop%20tap/
- Whoosh transition: https://pixabay.com/sound-effects/search/soft%20whoosh/
- Light flash/whoosh: https://pixabay.com/sound-effects/search/light%20whoosh/
- Subtle cinematic swoosh: https://pixabay.com/sound-effects/search/cinematic%20swoosh/

## API Direction

If automating SFX collection:

1. Search by intent:
   - `soft bell ding`
   - `ui pop tap`
   - `soft whoosh`
   - `cinematic swoosh`
2. Download only assets with a license that allows your intended use.
3. Normalize loudness before render.
4. Keep filenames stable or update `sfxCues` in the props.

## Timing Defaults

- `course-pop.mp3`: text entrance.
- `course-ding.mp3`: circled word plus face punch-in.
- `course-whoosh.mp3`: flash transition, section reset, or slow push-in.

Suggested volumes:

- Pop: `0.22-0.26`
- Ding: `0.30-0.34`
- Whoosh: `0.25-0.32`
