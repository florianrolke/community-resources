import React from "react";
import {
  AbsoluteFill,
  OffthreadVideo,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";
import {
  LuxuryOverlayCard,
  LuxuryTickerBand,
  SfxCueLayer,
  type LuxuryVideoOverlayManifest,
} from "../components/luxury-overlays/LuxuryOverlayKit";

interface Props {
  manifest: LuxuryVideoOverlayManifest;
}

const resolveStaticVideo = (videoSrc: string) => {
  if (videoSrc.startsWith("http") || videoSrc.startsWith("/")) {
    return videoSrc;
  }

  return staticFile(videoSrc.split(/[\\/]/).pop() || videoSrc);
};

export const LuxuryTalkingHeadEdit: React.FC<Props> = ({ manifest }) => {
  const videoSrc = resolveStaticVideo(manifest.videoSrc);
  const frame = useCurrentFrame();
  const activeOverlay = manifest.overlays.find(
    (overlay) =>
      frame >= overlay.startFrame &&
      frame < overlay.startFrame + overlay.durationFrames
  );
  const fullScreenKinds = new Set(["full_screen_statement", "number_counter"]);
  const isFullScreenOverlay = activeOverlay
    ? fullScreenKinds.has(activeOverlay.kind)
    : false;
  const useSplitStage = Boolean(activeOverlay && !isFullScreenOverlay);
  const jumpCuts = manifest.videoEffects?.jumpCuts ?? [];
  const activeJumpCut = [...jumpCuts]
    .reverse()
    .find((effect) => {
      const resetFrame =
        effect.resetFrame ??
        manifest.overlays.find((overlay) => overlay.startFrame > effect.startFrame)
          ?.startFrame ??
        effect.startFrame + effect.durationFrames;

      return frame >= effect.startFrame && frame < resetFrame;
    });
  const jumpZoom = activeJumpCut
    ? interpolate(
        frame - activeJumpCut.startFrame,
        [0, Math.min(8, Math.max(1, activeJumpCut.durationFrames))],
        [1, activeJumpCut.zoom],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
      )
    : 1;
  const baseScale = useSplitStage ? 1.06 : 1;
  const videoScale = baseScale * jumpZoom;

  return (
    <AbsoluteFill style={{ backgroundColor: "black" }}>
      <AbsoluteFill
        style={{
          background: useSplitStage
            ? "linear-gradient(90deg, #06180b 0%, #06180b 50%, #000 50%, #000 100%)"
            : "black",
          overflow: "hidden",
        }}
      >
        <OffthreadVideo
          src={videoSrc}
          style={{
            position: "absolute",
            right: useSplitStage ? 0 : "auto",
            left: useSplitStage ? "auto" : 0,
            width: useSplitStage ? "50%" : "100%",
            height: "100%",
            objectFit: "cover",
            objectPosition: useSplitStage ? "58% center" : "center center",
            opacity: isFullScreenOverlay ? 0.14 : 1,
            transform: `scale(${videoScale})`,
            transformOrigin: "center center",
          }}
        />
      </AbsoluteFill>

      <AbsoluteFill
        style={{
          pointerEvents: "none",
          background:
            useSplitStage
              ? "linear-gradient(90deg, rgba(9,36,15,0.34) 0%, rgba(9,36,15,0.18) 48%, rgba(0,0,0,0.18) 50%, rgba(0,0,0,0.06) 100%)"
              : "radial-gradient(circle at 18% 20%, rgba(201,169,110,0.10), transparent 28%), linear-gradient(90deg, rgba(0,0,0,0.16), transparent 32%, rgba(0,0,0,0.08))",
        }}
      />

      {manifest.overlays.map((overlay, index) => (
        <Sequence
          key={`luxury-overlay-${index}-${overlay.startFrame}`}
          from={overlay.startFrame}
          durationInFrames={overlay.durationFrames}
          name={`${overlay.kind}: ${overlay.title.substring(0, 24)}`}
        >
          <LuxuryOverlayCard {...overlay} />
        </Sequence>
      ))}

      {manifest.tickerBands.map((ticker, index) => (
        <Sequence
          key={`luxury-ticker-${index}-${ticker.startFrame}`}
          from={ticker.startFrame}
          durationInFrames={ticker.durationFrames}
          name={`Ticker: ${ticker.items.join(" / ").substring(0, 32)}`}
        >
          <LuxuryTickerBand {...ticker} />
        </Sequence>
      ))}

      <SfxCueLayer cues={manifest.sfxCues} />
    </AbsoluteFill>
  );
};

export const LuxuryTalkingHeadEditWrapper: React.FC<{
  manifest?: LuxuryVideoOverlayManifest;
}> = ({ manifest }) => {
  if (!manifest) {
    throw new Error(
      "LuxuryTalkingHeadEdit requires --props with a { manifest } object."
    );
  }

  return <LuxuryTalkingHeadEdit manifest={manifest} />;
};

export const LuxuryTwoMistakesEdit = LuxuryTalkingHeadEdit;
export const LuxuryTwoMistakesEditWrapper = LuxuryTalkingHeadEditWrapper;

export default LuxuryTalkingHeadEditWrapper;
