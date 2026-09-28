import React from "react";
import {
  AbsoluteFill,
  OffthreadVideo,
  staticFile,
  useCurrentFrame,
} from "remotion";
import {
  BehindGraphicLayer,
  CourseCaptionLayer,
  CourseGrainLayer,
  CourseStyleManifest,
  CourseTitleCards,
  DepthForegroundMask,
  FlashTransitionLayer,
  getVideoTreatment,
  LightLeakLayer,
  SfxCueLayer,
  sourceFile,
} from "../components/course-style/CourseOverlayKit";

type CourseStyleEditProps = {
  manifest: CourseStyleManifest;
};

const defaultManifest: CourseStyleManifest = {
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
  depthMask: {
    enabled: false,
    xPct: 52,
    yPct: 37,
    widthPct: 18,
    heightPct: 31,
  },
};

export const CourseStyleEditWrapper: React.FC<CourseStyleEditProps> = ({
  manifest = defaultManifest,
}) => {
  return <CourseStyleEdit manifest={manifest} />;
};

const CourseStyleEdit: React.FC<CourseStyleEditProps> = ({ manifest }) => {
  const frame = useCurrentFrame();
  const videoTreatment = getVideoTreatment(frame, manifest);
  const src = staticFile(sourceFile(manifest.videoSrc));
  const videoStyle: React.CSSProperties = {
    width: "100%",
    height: "100%",
    objectFit: "cover",
    transform: videoTreatment.transform,
    filter: videoTreatment.filter,
    transformOrigin: "center",
  };

  return (
    <AbsoluteFill
      style={{
        background: "#07140D",
        overflow: "hidden",
        fontFamily: "Inter, Arial, sans-serif",
      }}
    >
      <AbsoluteFill>
        <OffthreadVideo src={src} style={videoStyle} />
      </AbsoluteFill>

      <OrganicVignette />

      <BehindGraphicLayer graphics={manifest.behindGraphics} />

      <DepthForegroundMask
        videoSrc={manifest.videoSrc}
        mask={manifest.depthMask}
        videoStyle={videoStyle}
      >
        {(maskedSrc, maskedStyle) => (
          <AbsoluteFill>
            <OffthreadVideo src={maskedSrc} muted style={maskedStyle} />
          </AbsoluteFill>
        )}
      </DepthForegroundMask>

      <CourseCaptionLayer
        blocks={manifest.captionBlocks}
        blockedRanges={manifest.titleCards}
      />
      <CourseTitleCards cards={manifest.titleCards} />
      <LightLeakLayer leaks={manifest.lightLeaks} />
      <FlashTransitionLayer flashes={manifest.flashTransitions} />
      <CourseGrainLayer />
      <SfxCueLayer cues={manifest.sfxCues} />
    </AbsoluteFill>
  );
};

const OrganicVignette: React.FC = () => (
  <AbsoluteFill
    style={{
      pointerEvents: "none",
      background:
        "radial-gradient(circle at 50% 40%, rgba(255,255,255,0) 0%, rgba(7,20,13,0.05) 54%, rgba(7,20,13,0.28) 100%)",
      mixBlendMode: "multiply",
    }}
  />
);
