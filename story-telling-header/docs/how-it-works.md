# How it works

The hero is a **scroll-scrubbed video**: the page has a tall invisible scroll track, and the
video's playback position is tied to how far down that track you've scrolled. Scroll down →
the video advances; scroll up → it rewinds. Because the four scenes were generated as one
continuous upward camera move, it feels like you're flying up through the story.

## The mechanics

```
#ascent            → a tall element, e.g. height: 520vh  (the "scroll track")
  .stage           → position: sticky; top: 0; height: 100vh  (pinned while you scroll the track)
    <video>        → the stitched ascent.mp4
    .scene × 4     → the still keyframes (fallback layer)
    .beat × 4      → the headline text for each scene
```

On every scroll frame the script computes a progress value `p` from 0 → 1 across the `#ascent`
track, then:

```js
p = clamp(-ascent.getBoundingClientRect().top / (ascent.offsetHeight - innerHeight), 0, 1);
targetTime  = p * video.duration;
currentTime += (targetTime - currentTime) * 0.16;   // ease toward the target (no jitter)
video.currentTime = currentTime;
```

The `0.16` lerp is what makes the scrub feel smooth instead of jumpy — the video eases toward
the scroll target rather than snapping to it.

The **beats** cross-fade in and out per quarter of the track, and a small progress rail on the
right highlights the active scene.

## Two layers, one falls back to the other

- **Video layer** (`videoMode`): the real effect. Requires the mp4 to load and be seekable.
- **Stills layer**: the four `.scene` images cross-fade with a subtle zoom + pan. Used when
  there's no video, when the browser can't play it, when `prefers-reduced-motion` is set, or
  when the page is opened over `file://` (see [gotchas.md](gotchas.md)).

You always get *something* — the stills fallback is a perfectly nice hero on its own.

## Why 4 scenes

Four is enough to tell a beginning → middle → arrival story and keep each HappyHorse clip
short (5s) and cheap. The scenes cross-fade, so they don't need to match perfectly — but a
consistent color grade and a shared upward camera motion make them read as one shot.
