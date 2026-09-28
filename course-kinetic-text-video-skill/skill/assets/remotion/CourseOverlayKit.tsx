import React from "react";
import {
  AbsoluteFill,
  Audio,
  Easing,
  interpolate,
  Sequence,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export type CourseCaptionMode =
  | "pop_group"
  | "emphasis_box"
  | "karaoke"
  | "highlight_stack";

export type CourseCaptionBlock = {
  id: string;
  startFrame: number;
  durationFrames: number;
  text: string;
  lines?: string[];
  emphasis?: string;
  mode?: CourseCaptionMode;
  highlightLines?: number[];
  circleWord?: string;
  circleLine?: number;
  circleLeftPct?: number;
  circleWidth?: number;
  y?: number;
  maxWidth?: number;
  align?: "center" | "left" | "right";
};

export type CourseTitleCard = {
  id: string;
  startFrame: number;
  durationFrames: number;
  kicker?: string;
  title: string;
  subtitle?: string;
  accent?: string;
};

export type CourseLightLeak = {
  id: string;
  startFrame: number;
  durationFrames: number;
  direction?: "left" | "right";
  intensity?: number;
};

export type CoursePushTransition = {
  id: string;
  startFrame: number;
  durationFrames: number;
  direction?: "left" | "right";
};

export type CourseFlashTransition = {
  id: string;
  startFrame: number;
  durationFrames: number;
  intensity?: number;
  coolWash?: boolean;
};

export type CourseZoomEvent = {
  id: string;
  startFrame: number;
  durationFrames: number;
  zoom: number;
  mode?: "punch" | "slow";
  outFrames?: number;
};

export type CourseSfxCue = {
  id: string;
  startFrame: number;
  file: string;
  volume?: number;
};

export type CourseBehindGraphic = {
  id: string;
  startFrame: number;
  durationFrames: number;
  kind: "question_marks" | "keyword_burst" | "halo";
  text?: string;
  anchor?: "head-left" | "head-right" | "shoulder-left" | "shoulder-right";
  color?: string;
};

export type CourseDepthMask = {
  enabled: boolean;
  xPct: number;
  yPct: number;
  widthPct: number;
  heightPct: number;
  opacity?: number;
};

export type CourseStyleManifest = {
  videoSrc: string;
  fps: number;
  width: number;
  height: number;
  durationFrames: number;
  captionBlocks: CourseCaptionBlock[];
  titleCards: CourseTitleCard[];
  lightLeaks: CourseLightLeak[];
  flashTransitions?: CourseFlashTransition[];
  pushTransitions: CoursePushTransition[];
  zoomEvents: CourseZoomEvent[];
  sfxCues: CourseSfxCue[];
  behindGraphics: CourseBehindGraphic[];
  depthMask?: CourseDepthMask;
};

const palette = {
  sage: "#A9BA9D",
  mustard: "#E1AD01",
  beige: "#E6D5C3",
  champagne: "#D6B56D",
  paleGold: "#F0D68A",
  warmWhite: "#FFF4E0",
  white: "#FFFFFF",
  charcoal: "#101915",
  ink: "#07140D",
  lime: "#C1E1A6",
  shadow: "rgba(0, 0, 0, 0.38)",
};

const clamp01 = (value: number) => Math.max(0, Math.min(1, value));

export const sourceFile = (src: string) => {
  const normalized = src.replace(/\\/g, "/");
  return normalized.split("/").filter(Boolean).pop() ?? src;
};

export const getVideoTreatment = (
  frame: number,
  manifest: CourseStyleManifest
) => {
  let scale = 1;
  const activeSlowZoom = [...manifest.zoomEvents]
    .reverse()
    .find(
      (event) =>
        event.mode === "slow" &&
        frame >= event.startFrame &&
        frame < event.startFrame + event.durationFrames
    );

  if (activeSlowZoom) {
    const local = frame - activeSlowZoom.startFrame;
    const outFrames = activeSlowZoom.outFrames ?? 18;
    const pushFrames = Math.max(1, activeSlowZoom.durationFrames - outFrames);
    scale =
      local <= pushFrames
        ? interpolate(local, [0, pushFrames], [1, activeSlowZoom.zoom], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.33, 1, 0.68, 1),
          })
        : interpolate(
            local,
            [pushFrames, activeSlowZoom.durationFrames],
            [activeSlowZoom.zoom, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          );
  }

  const activePunchZoom = [...manifest.zoomEvents]
    .reverse()
    .find(
      (event) =>
        (event.mode ?? "punch") === "punch" &&
        frame >= event.startFrame &&
        frame < event.startFrame + event.durationFrames
    );

  if (activePunchZoom) {
    const z = spring({
      frame: frame - activePunchZoom.startFrame,
      fps: manifest.fps,
      config: { stiffness: 100, damping: 10, mass: 0.7 },
      durationInFrames: 18,
    });
    const exitStart = activePunchZoom.durationFrames - 14;
    const exit =
      frame - activePunchZoom.startFrame > exitStart
        ? interpolate(
            frame - activePunchZoom.startFrame,
            [exitStart, activePunchZoom.durationFrames],
            [1, 0],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
          )
        : 1;
    scale = Math.max(scale, 1 + (activePunchZoom.zoom - 1) * z * exit);
  }

  const activePush = manifest.pushTransitions.find(
    (event) =>
      frame >= event.startFrame && frame < event.startFrame + event.durationFrames
  );
  let translateX = 0;
  let blur = 0;

  if (activePush) {
    const local = frame - activePush.startFrame;
    const progress = interpolate(local, [0, activePush.durationFrames], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
      easing: Easing.bezier(0.45, 0, 0.55, 1),
    });
    const dir = activePush.direction === "right" ? 1 : -1;
    translateX = dir * interpolate(progress, [0, 0.5, 1], [0, 82, 0]);
    blur = interpolate(progress, [0, 0.5, 1], [0, 10, 0]);
  }

  return {
    transform: `translateX(${translateX}px) scale(${scale})`,
    filter: `blur(${blur}px)`,
  };
};

export const CourseCaptionLayer: React.FC<{
  blocks: CourseCaptionBlock[];
  blockedRanges?: Array<{ startFrame: number; durationFrames: number }>;
}> = ({ blocks, blockedRanges = [] }) => {
  const absoluteFrame = useCurrentFrame();
  const isBlocked = blockedRanges.some(
    (range) =>
      absoluteFrame >= range.startFrame &&
      absoluteFrame < range.startFrame + range.durationFrames
  );

  if (isBlocked) {
    return null;
  }

  return (
    <>
      {blocks.map((block) => (
        <Sequence
          key={block.id}
          from={block.startFrame}
          durationInFrames={block.durationFrames}
        >
          {block.mode === "highlight_stack" ? (
            <HighlightStack block={block} />
          ) : block.mode === "emphasis_box" ? (
            <EmphasisBox block={block} />
          ) : block.mode === "karaoke" ? (
            <KaraokeBlock block={block} />
          ) : (
            <PopGroup block={block} />
          )}
        </Sequence>
      ))}
    </>
  );
};

const HighlightStack: React.FC<{ block: CourseCaptionBlock }> = ({ block }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const lines =
    block.lines && block.lines.length > 0
      ? block.lines
      : block.text.split(" / ").filter(Boolean);
  const highlightLines = new Set(block.highlightLines ?? [lines.length - 1]);
  const shadeOpacity = interpolate(frame, [0, 8], [0.42, 0.55], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const exit = interpolate(frame, [block.durationFrames - 10, block.durationFrames], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(to top, rgba(0,0,0,0.5) 0%, rgba(0,0,0,0.34) 34%, rgba(0,0,0,0) 64%)",
          opacity: shadeOpacity * exit,
        }}
      />
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: 92,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: 5,
          paddingLeft: 110,
          paddingRight: 110,
        }}
      >
        {lines.map((line, index) => {
          const lineSpring = spring({
            frame: frame - index * 4,
            fps,
            config: { stiffness: 180, damping: 12, mass: 1 },
            durationInFrames: 12,
          });
          const highlighterSpring = spring({
            frame: frame - index * 4 - 2,
            fps,
            config: { stiffness: 190, damping: 15, mass: 0.8 },
            durationInFrames: 10,
          });
          const translateY = interpolate(lineSpring, [0, 1], [30, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          const scale = interpolate(lineSpring, [0, 0.72, 1], [0.8, 1.055, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          const opacity = clamp01(lineSpring) * exit;
          const isHighlighted = highlightLines.has(index);
          const shouldCircle =
            block.circleWord &&
            line.toLowerCase().includes(block.circleWord.toLowerCase());

          return (
            <div
              key={`${block.id}-${line}-${index}`}
              style={{
                position: "relative",
                display: "inline-flex",
                alignItems: "center",
                justifyContent: "center",
                transform: `translateY(${translateY}px) scale(${scale})`,
                opacity,
                padding: isHighlighted ? "2px 22px 6px" : "0 10px",
              }}
            >
              {isHighlighted ? (
                <div
                  style={{
                    position: "absolute",
                    left: 0,
                    right: 0,
                    top: "18%",
                    bottom: "7%",
                    background:
                      "linear-gradient(92deg, rgba(214,181,109,0.72), rgba(240,214,138,0.9))",
                    borderRadius: 4,
                    opacity: 0.9,
                    transform: `rotate(-1.7deg) scaleX(${highlighterSpring})`,
                    transformOrigin: "left center",
                    boxShadow: "0 4px 14px rgba(0, 0, 0, 0.18)",
                  }}
                />
              ) : null}
              <span
                style={{
                  position: "relative",
                  zIndex: 2,
                  fontFamily: "Inter, Montserrat, Arial, sans-serif",
                  fontWeight: 900,
                  fontSize: 82,
                  lineHeight: 0.94,
                  letterSpacing: "-0.02em",
                  color: palette.white,
                  textAlign: "center",
                  textShadow: "0 2px 7px rgba(0, 0, 0, 0.34)",
                  whiteSpace: "pre-wrap",
                }}
              >
                {line}
              </span>
              {shouldCircle ? (
                <StrokeCircle
                  frame={frame}
                  lineIndex={index}
                  leftPct={block.circleLeftPct ?? 64}
                  width={block.circleWidth ?? 260}
                />
              ) : null}
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const StrokeCircle: React.FC<{
  frame: number;
  lineIndex: number;
  leftPct: number;
  width: number;
}> = ({ frame, lineIndex, leftPct, width }) => {
  const local = frame - lineIndex * 4 - 10;
  const progress = interpolate(local, [0, 15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.33, 1, 0.68, 1),
  });
  const dash = 720;

  return (
    <svg
      width={width}
      height={98}
      viewBox="0 0 260 98"
      style={{
        position: "absolute",
        left: `${leftPct}%`,
        top: "50%",
        transform: "translate(-50%, -50%) rotate(-4deg)",
        zIndex: 3,
        overflow: "visible",
      }}
    >
      <ellipse
        cx="130"
        cy="49"
        rx="120"
        ry="36"
        fill="none"
        stroke={palette.paleGold}
        strokeWidth="8"
        strokeLinecap="round"
        strokeDasharray={dash}
        strokeDashoffset={dash * (1 - progress)}
      />
    </svg>
  );
};

const PopGroup: React.FC<{ block: CourseCaptionBlock }> = ({ block }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const words = block.text.split(/\s+/).filter(Boolean);
  const emphasis = (block.emphasis ?? "").toLowerCase();
  const appear = interpolate(frame, [0, 5, block.durationFrames - 8, block.durationFrames], [0, 1, 1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const slowGrow = interpolate(frame, [0, block.durationFrames], [1, 1.045], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-start",
        alignItems: block.align === "left" ? "flex-start" : block.align === "right" ? "flex-end" : "center",
        paddingTop: `${Math.round((block.y ?? 0.7) * 100)}%`,
        paddingLeft: 130,
        paddingRight: 130,
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          maxWidth: block.maxWidth ?? 1180,
          textAlign: block.align ?? "center",
          opacity: appear,
          transform: `translateY(-50%) scale(${slowGrow})`,
          transformOrigin: "center",
          lineHeight: 1.06,
          fontFamily: "Montserrat, Inter, Arial, sans-serif",
          fontWeight: 900,
          fontSize: 76,
          letterSpacing: 0,
          textShadow: `0 3px 12px ${palette.shadow}`,
          color: palette.white,
        }}
      >
        {words.map((word, index) => {
          const clean = word.toLowerCase().replace(/[^a-z0-9]/g, "");
          const isEmphasis =
            emphasis.length > 0 &&
            (clean === emphasis.replace(/[^a-z0-9]/g, "") ||
              word.toLowerCase().includes(emphasis));
          const wordSpring = spring({
            frame: frame - index * 3,
            fps,
            config: { stiffness: 210, damping: 13, mass: 0.45 },
            durationInFrames: 13,
          });
          const opacity = clamp01(interpolate(frame - index * 3, [0, 4], [0, 1]));
          const scale = interpolate(wordSpring, [0, 0.72, 1], [0.52, 1.13, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
          return (
            <span
              key={`${block.id}-${word}-${index}`}
              style={{
                display: "inline-block",
                marginRight: 18,
                color: isEmphasis ? palette.mustard : palette.white,
                transform: `scale(${scale})`,
                opacity,
                WebkitTextStroke: isEmphasis ? "0.8px rgba(255, 255, 255, 0.18)" : "0",
              }}
            >
              {word}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

const EmphasisBox: React.FC<{ block: CourseCaptionBlock }> = ({ block }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const boxScale = spring({
    frame,
    fps,
    config: { stiffness: 180, damping: 17, mass: 0.55 },
    durationInFrames: 12,
  });
  const textScale = spring({
    frame: frame - 5,
    fps,
    config: { stiffness: 220, damping: 14, mass: 0.45 },
    durationInFrames: 13,
  });
  const exit = interpolate(frame, [block.durationFrames - 10, block.durationFrames], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          background: "rgba(7, 20, 13, 0.9)",
          border: `2px solid ${palette.sage}`,
          boxShadow: "0 18px 48px rgba(0, 0, 0, 0.34)",
          padding: "36px 58px",
          transform: `scaleX(${boxScale})`,
          transformOrigin: "center",
          opacity: exit,
        }}
      >
        <div
          style={{
            fontFamily: "Montserrat, Inter, Arial, sans-serif",
            fontWeight: 900,
            fontSize: 78,
            letterSpacing: 2,
            textTransform: "uppercase",
            color: palette.white,
            transform: `scale(${textScale})`,
            opacity: clamp01(textScale) * exit,
            textShadow: `0 3px 12px ${palette.shadow}`,
          }}
        >
          {block.text}
        </div>
      </div>
    </AbsoluteFill>
  );
};

const KaraokeBlock: React.FC<{ block: CourseCaptionBlock }> = ({ block }) => {
  const frame = useCurrentFrame();
  const words = block.text.split(/\s+/).filter(Boolean);
  const activeIndex = Math.min(
    words.length - 1,
    Math.max(0, Math.floor((frame / Math.max(1, block.durationFrames)) * words.length))
  );

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-start",
        alignItems: "center",
        paddingTop: `${Math.round((block.y ?? 0.7) * 100)}%`,
        paddingLeft: 130,
        paddingRight: 130,
        pointerEvents: "none",
      }}
    >
      <div
        style={{
          maxWidth: block.maxWidth ?? 1180,
          textAlign: "center",
          transform: "translateY(-50%)",
          fontFamily: "Montserrat, Inter, Arial, sans-serif",
          fontWeight: 900,
          fontSize: 72,
          lineHeight: 1.06,
          color: palette.white,
          textShadow: `0 3px 12px ${palette.shadow}`,
        }}
      >
        {words.map((word, index) => (
          <span
            key={`${block.id}-${word}-${index}`}
            style={{
              display: "inline-block",
              marginRight: 17,
              color: index === activeIndex ? palette.mustard : palette.white,
              opacity: index === activeIndex ? 1 : 0.42,
              transform: `scale(${index === activeIndex ? 1.12 : 1})`,
            }}
          >
            {word}
          </span>
        ))}
      </div>
    </AbsoluteFill>
  );
};

export const CourseTitleCards: React.FC<{
  cards: CourseTitleCard[];
}> = ({ cards }) => {
  return (
    <>
      {cards.map((card) => (
        <Sequence
          key={card.id}
          from={card.startFrame}
          durationInFrames={card.durationFrames}
        >
          <CourseTitleCard card={card} />
        </Sequence>
      ))}
    </>
  );
};

const CourseTitleCard: React.FC<{ card: CourseTitleCard }> = ({ card }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const wipe = spring({
    frame,
    fps,
    config: { stiffness: 120, damping: 15, mass: 0.75 },
    durationInFrames: 18,
  });
  const title = spring({
    frame: frame - 7,
    fps,
    config: { stiffness: 170, damping: 16, mass: 0.5 },
    durationInFrames: 18,
  });
  const exit = interpolate(frame, [card.durationFrames - 16, card.durationFrames], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        background:
          "linear-gradient(135deg, rgba(7, 20, 13, 0.92), rgba(7, 20, 13, 0.72))",
        justifyContent: "center",
        alignItems: "center",
        overflow: "hidden",
        opacity: exit,
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: "auto 0 0 0",
          height: 190,
          background: palette.beige,
          clipPath: "polygon(0 58%, 100% 30%, 100% 100%, 0 100%)",
          opacity: 0.94,
        }}
      />
      <div
        style={{
          width: 1060,
          transform: `scaleX(${wipe})`,
          transformOrigin: "center",
          padding: "54px 72px 62px",
          background: "rgba(16, 25, 21, 0.78)",
          borderTop: `3px solid ${palette.mustard}`,
          borderBottom: `1px solid rgba(230, 213, 195, 0.38)`,
          boxShadow: "0 26px 80px rgba(0, 0, 0, 0.4)",
          textAlign: "center",
        }}
      >
        {card.kicker ? (
          <div
            style={{
              fontFamily: "Montserrat, Inter, Arial, sans-serif",
              fontSize: 28,
              fontWeight: 800,
              letterSpacing: 9,
              color: card.accent ?? palette.mustard,
              marginBottom: 20,
              textTransform: "uppercase",
              opacity: clamp01(title),
            }}
          >
            {card.kicker}
          </div>
        ) : null}
        <div
          style={{
            fontFamily: "Montserrat, Inter, Arial, sans-serif",
            fontSize: 92,
            fontWeight: 900,
            lineHeight: 0.98,
            color: palette.white,
            letterSpacing: 0,
            transform: `scale(${interpolate(title, [0, 0.7, 1], [0.8, 1.08, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            })})`,
            opacity: clamp01(title),
            textShadow: `0 3px 12px ${palette.shadow}`,
          }}
        >
          {card.title}
        </div>
        {card.subtitle ? (
          <div
            style={{
              fontFamily: "Inter, Arial, sans-serif",
              fontSize: 34,
              fontWeight: 700,
              lineHeight: 1.28,
              color: palette.sage,
              marginTop: 26,
              opacity: interpolate(frame, [14, 24], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              }),
            }}
          >
            {card.subtitle}
          </div>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

export const LightLeakLayer: React.FC<{
  leaks: CourseLightLeak[];
}> = ({ leaks }) => {
  return (
    <>
      {leaks.map((leak) => (
        <Sequence
          key={leak.id}
          from={leak.startFrame}
          durationInFrames={leak.durationFrames}
        >
          <LightLeak leak={leak} />
        </Sequence>
      ))}
    </>
  );
};

export const FlashTransitionLayer: React.FC<{
  flashes?: CourseFlashTransition[];
}> = ({ flashes = [] }) => {
  return (
    <>
      {flashes.map((flash) => (
        <Sequence
          key={flash.id}
          from={flash.startFrame}
          durationInFrames={flash.durationFrames}
        >
          <FlashTransition flash={flash} />
        </Sequence>
      ))}
    </>
  );
};

const FlashTransition: React.FC<{ flash: CourseFlashTransition }> = ({
  flash,
}) => {
  const frame = useCurrentFrame();
  const peakFrame = Math.max(1, Math.round(flash.durationFrames * 0.4));
  const opacity = interpolate(
    frame,
    [0, peakFrame, flash.durationFrames],
    [0, flash.intensity ?? 0.75, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        opacity,
        mixBlendMode: "screen",
        background: flash.coolWash
          ? "linear-gradient(135deg, rgba(255,255,255,1), rgba(172,210,255,0.9))"
          : "#FFFFFF",
      }}
    />
  );
};

const LightLeak: React.FC<{ leak: CourseLightLeak }> = ({ leak }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(
    frame,
    [0, leak.durationFrames * 0.5, leak.durationFrames],
    [0, leak.intensity ?? 0.82, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );
  const dir = leak.direction === "right" ? 1 : -1;
  const translateX = interpolate(frame, [0, leak.durationFrames], [-35 * dir, 35 * dir], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        pointerEvents: "none",
        opacity,
        mixBlendMode: "screen",
        transform: `translateX(${translateX}%)`,
        background:
          "linear-gradient(105deg, transparent 8%, rgba(255,244,224,0.06) 24%, rgba(255,244,224,0.9) 46%, rgba(225,173,1,0.48) 53%, rgba(255,244,224,0.12) 65%, transparent 84%)",
      }}
    />
  );
};

export const BehindGraphicLayer: React.FC<{
  graphics: CourseBehindGraphic[];
}> = ({ graphics }) => {
  return (
    <>
      {graphics.map((graphic) => (
        <Sequence
          key={graphic.id}
          from={graphic.startFrame}
          durationInFrames={graphic.durationFrames}
        >
          <BehindGraphic graphic={graphic} />
        </Sequence>
      ))}
    </>
  );
};

const anchorStyles: Record<NonNullable<CourseBehindGraphic["anchor"]>, React.CSSProperties> = {
  "head-left": { left: "18%", top: "18%" },
  "head-right": { left: "63%", top: "18%" },
  "shoulder-left": { left: "14%", top: "42%" },
  "shoulder-right": { left: "63%", top: "42%" },
};

const BehindGraphic: React.FC<{ graphic: CourseBehindGraphic }> = ({ graphic }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const pop = spring({
    frame,
    fps,
    config: { stiffness: 170, damping: 12, mass: 0.55 },
    durationInFrames: 16,
  });
  const exit = interpolate(frame, [graphic.durationFrames - 12, graphic.durationFrames], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const color = graphic.color ?? palette.mustard;
  const anchor = graphic.anchor ?? "head-right";
  const base: React.CSSProperties = {
    position: "absolute",
    ...anchorStyles[anchor],
    transform: `scale(${pop}) rotate(${interpolate(frame, [0, graphic.durationFrames], [-5, 5])}deg)`,
    opacity: clamp01(pop) * exit,
    pointerEvents: "none",
    filter: "drop-shadow(0 12px 24px rgba(0, 0, 0, 0.28))",
  };

  if (graphic.kind === "halo") {
    return (
      <AbsoluteFill>
        <div
          style={{
            ...base,
            width: 330,
            height: 330,
            borderRadius: "50%",
            border: `7px solid ${color}`,
            boxShadow: `0 0 54px ${color}`,
            opacity: 0.23 * exit,
          }}
        />
      </AbsoluteFill>
    );
  }

  if (graphic.kind === "keyword_burst") {
    return (
      <AbsoluteFill>
        <div
          style={{
            ...base,
            fontFamily: "Montserrat, Inter, Arial, sans-serif",
            fontWeight: 900,
            fontSize: 86,
            lineHeight: 0.92,
            textTransform: "uppercase",
            color,
            WebkitTextStroke: "1px rgba(255,255,255,0.25)",
          }}
        >
          {graphic.text ?? "KEY"}
        </div>
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill>
      <div
        style={{
          ...base,
          fontFamily: "Montserrat, Inter, Arial, sans-serif",
          fontWeight: 900,
          fontSize: 136,
          color,
          letterSpacing: 12,
        }}
      >
        ???
      </div>
    </AbsoluteFill>
  );
};

export const SfxCueLayer: React.FC<{
  cues: CourseSfxCue[];
}> = ({ cues }) => {
  return (
    <>
      {cues.map((cue) => (
        <Sequence key={cue.id} from={cue.startFrame} durationInFrames={120}>
          <Audio src={staticFile(cue.file)} volume={cue.volume ?? 0.42} />
        </Sequence>
      ))}
    </>
  );
};

export const CourseGrainLayer: React.FC = () => (
  <AbsoluteFill
    style={{
      pointerEvents: "none",
      opacity: 0.05,
      mixBlendMode: "overlay",
      backgroundImage:
        "radial-gradient(circle at 12% 24%, rgba(255,255,255,0.8) 0 1px, transparent 1px), radial-gradient(circle at 74% 42%, rgba(0,0,0,0.55) 0 1px, transparent 1px), radial-gradient(circle at 48% 79%, rgba(255,255,255,0.5) 0 1px, transparent 1px)",
      backgroundSize: "23px 19px, 31px 29px, 41px 37px",
    }}
  />
);

export const DepthForegroundMask: React.FC<{
  videoSrc: string;
  mask?: CourseDepthMask;
  videoStyle: React.CSSProperties;
  children: (src: string, style: React.CSSProperties) => React.ReactNode;
}> = ({ videoSrc, mask, videoStyle, children }) => {
  if (!mask?.enabled) {
    return null;
  }

  const style: React.CSSProperties = {
    ...videoStyle,
    clipPath: `ellipse(${mask.widthPct}% ${mask.heightPct}% at ${mask.xPct}% ${mask.yPct}%)`,
    opacity: mask.opacity ?? 0.98,
    pointerEvents: "none",
  };

  return <>{children(staticFile(sourceFile(videoSrc)), style)}</>;
};
