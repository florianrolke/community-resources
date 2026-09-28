import React from "react";
import {
  AbsoluteFill,
  Audio,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export type LuxuryOverlayKind =
  | "gp_preloader_card"
  | "lx4_icon_bridge"
  | "delta_panel"
  | "fade_up_key"
  | "bullet_reveal"
  | "full_screen_statement"
  | "number_counter"
  | "recap";

export interface LuxuryOverlayEvent {
  kind: LuxuryOverlayKind;
  startFrame: number;
  durationFrames: number;
  eyebrow?: string;
  title: string;
  goldTitle?: string;
  body?: string;
  bullets?: string[];
  accentColor?: string;
  side?: "left" | "right" | "center";
  numberTarget?: number;
  numberPrefix?: string;
  numberSuffix?: string;
  numberLabel?: string;
  numberSubLabel?: string;
  revealSpeed?: "normal" | "fast";
}

export interface LuxuryTickerBandEvent {
  startFrame: number;
  durationFrames: number;
  items: string[];
  emphasis?: string;
}

export interface LuxurySfxCue {
  id: string;
  startFrame: number;
  file: string;
  volume?: number;
}

export interface LuxuryJumpCutEvent {
  id: string;
  startFrame: number;
  durationFrames: number;
  zoom: number;
  resetFrame?: number;
  reason?: string;
}

export interface LuxuryVideoOverlayManifest {
  videoSrc: string;
  fps: number;
  width: number;
  height: number;
  durationFrames: number;
  overlays: LuxuryOverlayEvent[];
  tickerBands: LuxuryTickerBandEvent[];
  sfxCues: LuxurySfxCue[];
  videoEffects?: {
    jumpCuts?: LuxuryJumpCutEvent[];
  };
}

export type LuxuryTwoMistakesManifest = LuxuryVideoOverlayManifest;

const COLORS = {
  forest: "#09240f",
  forest2: "#06180b",
  navy: "#0a1a2e",
  cream: "#f6f2ec",
  gold: "#c9a96e",
  copper: "#b87333",
  red: "#990000",
  white: "#ffffff",
};

const ease = [0.16, 1, 0.3, 1] as const;

const clamp = (value: number, input: [number, number], output: [number, number]) =>
  interpolate(value, input, output, {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

const OverlayShell: React.FC<{
  children: React.ReactNode;
  side?: "left" | "right" | "center";
  accentColor?: string;
  durationFrames: number;
}> = ({ children, side = "left", accentColor = COLORS.gold, durationFrames }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enter = spring({
    frame,
    fps,
    config: { damping: 22, stiffness: 150 },
  });
  const exit = clamp(frame, [durationFrames - 14, durationFrames], [0, 1]);
  const opacity = clamp(frame, [0, 18], [0, 1]) * (1 - exit);
  const y = interpolate(enter, [0, 1], [30, 0]) + exit * 16;
  const x = side === "right" ? "auto" : side === "center" ? "50%" : "24px";
  const right = side === "right" ? 24 : "auto";
  const transform =
    side === "center"
      ? `translate(-50%, ${y}px)`
      : `translateY(${y}px)`;

  return (
    <div
      style={{
        position: "absolute",
        left: x,
        right,
        top: side === "center" ? "16%" : "11%",
        width: side === "center" ? "78%" : "calc(50% - 44px)",
        maxWidth: side === "center" ? "none" : 306,
        opacity,
        transform,
        pointerEvents: "none",
        boxSizing: "border-box",
      }}
    >
      <div
        style={{
          position: "relative",
          overflow: "hidden",
          borderRadius: 2,
          border: `1px solid ${accentColor}55`,
          background:
            "linear-gradient(135deg, rgba(9,36,15,0.92), rgba(7,12,10,0.88))",
          boxShadow: "0 28px 80px rgba(0,0,0,0.48)",
          backdropFilter: "blur(12px)",
        }}
      >
        {children}
      </div>
    </div>
  );
};

const LuxuryTitle: React.FC<{
  title: string;
  goldTitle?: string;
  side?: "left" | "right" | "center";
  size?: number;
}> = ({ title, goldTitle, side = "left", size }) => {
  const fontSize = size ?? (side === "center" ? 30 : 22);

  if (!goldTitle) {
    return (
      <div
        style={{
          color: COLORS.white,
          fontFamily: "Georgia, 'Times New Roman', serif",
          fontSize,
          lineHeight: 1.04,
        }}
      >
        {title}
      </div>
    );
  }

  return (
    <div
      style={{
        fontFamily: "Georgia, 'Times New Roman', serif",
        fontSize,
        lineHeight: 1.02,
      }}
    >
      <div style={{ color: COLORS.white }}>{title}</div>
      <div
        style={{
          color: COLORS.gold,
          fontStyle: "italic",
          marginTop: 2,
          textShadow: "0 0 24px rgba(201,169,110,0.22)",
        }}
      >
        {goldTitle}
      </div>
    </div>
  );
};

const GoldLineReveal: React.FC<{ delay?: number; color?: string }> = ({
  delay = 0,
  color = COLORS.gold,
}) => {
  const frame = useCurrentFrame();
  const width = clamp(frame - delay, [0, 30], [0, 100]);
  return (
    <div
      style={{
        width: `${width}%`,
        height: 2,
        background: `linear-gradient(90deg, ${color}, #b8944f)`,
        boxShadow: `0 0 18px ${color}70`,
      }}
    />
  );
};

const FadeText: React.FC<{
  children: React.ReactNode;
  delay?: number;
  style?: React.CSSProperties;
}> = ({ children, delay = 0, style }) => {
  const frame = useCurrentFrame();
  const opacity = clamp(frame - delay, [0, 24], [0, 1]);
  const y = clamp(frame - delay, [0, 24], [20, 0]);
  return (
    <div style={{ opacity, transform: `translateY(${y}px)`, ...style }}>
      {children}
    </div>
  );
};

const LuxuryFullScreenStatement: React.FC<LuxuryOverlayEvent> = ({
  durationFrames,
  eyebrow,
  title,
  goldTitle,
  body,
  accentColor = COLORS.gold,
}) => {
  const frame = useCurrentFrame();
  const exit = clamp(frame, [durationFrames - 18, durationFrames], [0, 1]);
  const opacity = clamp(frame, [0, 22], [0, 1]) * (1 - exit);
  const y = clamp(frame, [0, 28], [22, 0]) + exit * 18;

  return (
    <AbsoluteFill
      style={{
        opacity,
        overflow: "hidden",
        background:
          "radial-gradient(circle at 50% 28%, rgba(201,169,110,0.08), transparent 36%), linear-gradient(180deg, #09240f 0%, #06180b 100%)",
        fontFamily: "Georgia, 'Times New Roman', serif",
      }}
    >
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          bottom: -1,
          height: 76,
          background: COLORS.cream,
          clipPath: "polygon(0 58%, 100% 0, 100% 100%, 0 100%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: "0 48px 34px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          transform: `translateY(${y}px)`,
        }}
      >
        <FadeText delay={2}>
          <div
            style={{
              color: accentColor,
              fontFamily: "Inter, Arial, sans-serif",
              fontSize: 9,
              letterSpacing: "0.34em",
              textTransform: "uppercase",
              marginBottom: 22,
              fontWeight: 800,
            }}
          >
            {eyebrow ?? "Point"}
          </div>
        </FadeText>
        <FadeText delay={9}>
          <LuxuryTitle title={title} goldTitle={goldTitle} side="center" size={42} />
        </FadeText>
        <div style={{ width: 76, marginTop: 22 }}>
          <GoldLineReveal delay={23} color={accentColor} />
        </div>
        {body ? (
          <FadeText delay={30}>
            <div
              style={{
                color: "rgba(255,255,255,0.68)",
                fontFamily: "Inter, Arial, sans-serif",
                fontSize: 14,
                lineHeight: 1.48,
                marginTop: 24,
                maxWidth: 520,
                fontWeight: 650,
              }}
            >
              {body}
            </div>
          </FadeText>
        ) : null}
      </div>
    </AbsoluteFill>
  );
};

const LuxuryNumberCounter: React.FC<LuxuryOverlayEvent> = ({
  durationFrames,
  eyebrow,
  title,
  goldTitle,
  accentColor = COLORS.gold,
  numberTarget = 2,
  numberPrefix = "",
  numberSuffix = "",
  numberLabel,
  numberSubLabel,
}) => {
  const frame = useCurrentFrame();
  const exit = clamp(frame, [durationFrames - 16, durationFrames], [0, 1]);
  const opacity = clamp(frame, [0, 18], [0, 1]) * (1 - exit);
  const value = Math.round(clamp(frame, [8, 58], [0, numberTarget]));
  const y = clamp(frame, [0, 22], [18, 0]) + exit * 14;

  return (
    <AbsoluteFill
      style={{
        opacity,
        overflow: "hidden",
        background:
          "linear-gradient(180deg, rgba(9,36,15,0.98), rgba(6,24,11,0.98))",
        fontFamily: "Georgia, 'Times New Roman', serif",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: "0 34px 38px",
          display: "grid",
          gridTemplateColumns: "0.9fr 1.1fr",
          alignItems: "center",
          gap: 34,
          transform: `translateY(${y}px)`,
        }}
      >
        <div style={{ textAlign: "center" }}>
          <div
            style={{
              color: COLORS.white,
              fontSize: 78,
              lineHeight: 0.92,
              fontVariantNumeric: "tabular-nums",
              letterSpacing: 0,
            }}
          >
            {numberPrefix}
            {value}
            <span style={{ color: accentColor, fontSize: 24, marginLeft: 4 }}>
              {numberSuffix}
            </span>
          </div>
          <div
            style={{
              color: accentColor,
              fontFamily: "Inter, Arial, sans-serif",
              fontSize: 10,
              letterSpacing: "0.28em",
              marginTop: 14,
              textTransform: "uppercase",
              fontWeight: 800,
            }}
          >
            {numberLabel ?? title}
          </div>
          {numberSubLabel ? (
            <div
              style={{
                color: "rgba(255,255,255,0.46)",
                fontFamily: "Inter, Arial, sans-serif",
                fontSize: 11,
                marginTop: 9,
                fontWeight: 650,
              }}
            >
              {numberSubLabel}
            </div>
          ) : null}
        </div>
        <div>
          <FadeText delay={2}>
            <div
              style={{
                color: accentColor,
                fontFamily: "Inter, Arial, sans-serif",
                fontSize: 9,
                letterSpacing: "0.32em",
                textTransform: "uppercase",
                marginBottom: 18,
                fontWeight: 800,
              }}
            >
              {eyebrow ?? "Signal"}
            </div>
          </FadeText>
          <FadeText delay={10}>
            <LuxuryTitle title={title} goldTitle={goldTitle} side="center" size={34} />
          </FadeText>
          <div style={{ width: 70, marginTop: 22 }}>
            <GoldLineReveal delay={24} color={accentColor} />
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const LuxuryOverlayCard: React.FC<LuxuryOverlayEvent> = ({
  kind,
  durationFrames,
  eyebrow,
  title,
  goldTitle,
  body,
  bullets = [],
  side = "left",
  accentColor = COLORS.gold,
  numberTarget,
  numberPrefix,
  numberSuffix,
  numberLabel,
  numberSubLabel,
  revealSpeed = "normal",
}) => {
  const frame = useCurrentFrame();
  const isPreloader = kind === "gp_preloader_card";
  const isPanel = kind === "delta_panel" || kind === "recap";
  const isIconBridge = kind === "lx4_icon_bridge";
  const isBullet = kind === "bullet_reveal";
  const fastReveal = revealSpeed === "fast";
  const split = clamp(frame, fastReveal ? [22, 40] : [54, 78], [0, 50]);
  const activePulse = Math.sin(Math.min(frame, 60) / 60 * Math.PI);
  const pulseLift = isIconBridge ? activePulse * -4 : 0;

  if (kind === "full_screen_statement") {
    return (
      <LuxuryFullScreenStatement
        kind={kind}
        startFrame={0}
        durationFrames={durationFrames}
        eyebrow={eyebrow}
        title={title}
        goldTitle={goldTitle}
        body={body}
        accentColor={accentColor}
        side={side}
      />
    );
  }

  if (kind === "number_counter") {
    return (
      <LuxuryNumberCounter
        kind={kind}
        startFrame={0}
        durationFrames={durationFrames}
        eyebrow={eyebrow}
        title={title}
        goldTitle={goldTitle}
        accentColor={accentColor}
        side={side}
        numberTarget={numberTarget}
        numberPrefix={numberPrefix}
        numberSuffix={numberSuffix}
        numberLabel={numberLabel}
        numberSubLabel={numberSubLabel}
      />
    );
  }

  if (isPanel) {
    return (
      <OverlayShell
        side={side}
        accentColor={accentColor}
        durationFrames={durationFrames}
      >
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            minHeight: 190,
            fontFamily: "Georgia, 'Times New Roman', serif",
          }}
        >
          <div style={{ background: COLORS.forest, padding: "24px 26px" }}>
            <FadeText delay={4}>
              <div
                style={{
                  color: COLORS.gold,
                  fontSize: 9,
                  letterSpacing: "0.22em",
                  textTransform: "uppercase",
                  marginBottom: 18,
                }}
              >
                {eyebrow ?? "Mistake"}
              </div>
            </FadeText>
            <FadeText delay={10}>
              <LuxuryTitle title={title} goldTitle={goldTitle} side={side} />
            </FadeText>
            <div style={{ width: 52, marginTop: 16 }}>
              <GoldLineReveal delay={20} color={accentColor} />
            </div>
          </div>
          <div style={{ background: COLORS.red, padding: "24px 26px" }}>
            <FadeText delay={18}>
              <div
                style={{
                  color: "rgba(255,255,255,0.66)",
                  fontFamily: "Inter, Arial, sans-serif",
                  fontSize: 13,
                  lineHeight: 1.42,
                  fontWeight: 600,
                }}
              >
                {body}
              </div>
            </FadeText>
          </div>
        </div>
      </OverlayShell>
    );
  }

  if (isIconBridge) {
    const items = bullets.length
      ? bullets
      : ["Niche clarity", "Pain intensity", "Proof path"];
    return (
      <OverlayShell
        side={side}
        accentColor={accentColor}
        durationFrames={durationFrames}
      >
        <div
          style={{
            display: "grid",
            gridTemplateColumns: `repeat(${items.length}, 1fr)`,
            background: "rgba(10,26,46,0.9)",
            border: "1px solid rgba(184,115,51,0.18)",
            fontFamily: "Inter, Arial, sans-serif",
          }}
        >
          {items.map((item, index) => {
            const localPulse = clamp(frame - 12 - index * 10, [0, 18], [0, 1]);
            return (
              <div
                key={item}
                style={{
                  padding: "24px 14px",
                  textAlign: "center",
                  borderLeft: index === 0 ? "none" : "1px solid rgba(255,255,255,0.08)",
                  transform: `translateY(${pulseLift * localPulse}px)`,
                  boxShadow:
                    localPulse > 0.2
                      ? "0 16px 48px rgba(0,0,0,0.22)"
                      : "none",
                }}
              >
                <div
                  style={{
                    color: COLORS.copper,
                    fontSize: 20,
                    lineHeight: 1,
                    marginBottom: 14,
                    textShadow:
                      localPulse > 0.4 ? `0 0 18px ${accentColor}` : "none",
                  }}
                >
                  {index === 0 ? "□" : index === 1 ? "◦" : "◇"}
                </div>
                <div
                  style={{
                    color: COLORS.white,
                    fontFamily: "Georgia, 'Times New Roman', serif",
                    fontSize: 15,
                    marginBottom: 8,
                  }}
                >
                  {item}
                </div>
                <div
                  style={{
                    color: "rgba(255,255,255,0.38)",
                    fontSize: 8,
                    letterSpacing: "0.18em",
                    textTransform: "uppercase",
                  }}
                >
                  Active signal
                </div>
              </div>
            );
          })}
        </div>
      </OverlayShell>
    );
  }

  return (
    <OverlayShell
      side={side}
      accentColor={accentColor}
      durationFrames={durationFrames}
    >
      {isPreloader ? (
        <div
          style={{
            position: "absolute",
            inset: 0,
            background: COLORS.forest,
            clipPath: `inset(${split}% 0 ${split}% 0)`,
            zIndex: 3,
          }}
        >
          <div
            style={{
              position: "absolute",
              inset: 0,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 10,
            }}
          >
            <div style={{ width: 120 }}>
              <GoldLineReveal delay={0} color={accentColor} />
            </div>
            <div
              style={{
                width: 7,
                height: 7,
                border: `1px solid ${accentColor}`,
                transform: `rotate(${45 + frame * 1.4}deg)`,
                boxShadow: `0 0 18px ${accentColor}66`,
              }}
            />
          </div>
        </div>
      ) : null}
      <div style={{ padding: isBullet ? "22px 22px 24px" : "24px 24px 26px" }}>
        <FadeText delay={isPreloader ? (fastReveal ? 36 : 70) : 4}>
          <div
            style={{
              color: accentColor,
              fontFamily: "Inter, Arial, sans-serif",
              fontSize: 9,
              letterSpacing: "0.28em",
              textTransform: "uppercase",
              marginBottom: 18,
              fontWeight: 800,
            }}
          >
            {eyebrow ?? "Key point"}
          </div>
        </FadeText>
        <FadeText delay={isPreloader ? (fastReveal ? 42 : 78) : 12}>
          <LuxuryTitle title={title} goldTitle={goldTitle} side={side} />
        </FadeText>
        {body ? (
          <FadeText delay={isPreloader ? (fastReveal ? 50 : 88) : 22}>
            <div
              style={{
                color: "rgba(255,255,255,0.78)",
                fontFamily: "Inter, Arial, sans-serif",
                fontSize: 13,
                lineHeight: 1.42,
                marginTop: 18,
                fontWeight: 650,
              }}
            >
              {body}
            </div>
          </FadeText>
        ) : null}
        {bullets.length ? (
          <div style={{ display: "grid", gap: 12, marginTop: 22 }}>
            {bullets.map((bullet, index) => {
              const bulletFrame = frame - 22 - index * 12;
              const bulletOpacity = clamp(bulletFrame, [0, 12], [0, 1]);
              const bulletY = clamp(bulletFrame, [0, 16], [18, 0]);
              return (
                <div
                  key={bullet}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "30px 1fr",
                    alignItems: "center",
                    gap: 12,
                    opacity: bulletOpacity,
                    transform: `translateY(${bulletY}px)`,
                    color: COLORS.white,
                    fontFamily: "Inter, Arial, sans-serif",
                    fontSize: 13,
                    fontWeight: 750,
                  }}
                >
                  <span
                    style={{
                      height: 2,
                      background: accentColor,
                      boxShadow: `0 0 14px ${accentColor}88`,
                    }}
                  />
                  <span>{bullet}</span>
                </div>
              );
            })}
          </div>
        ) : null}
        <div style={{ width: 70, marginTop: 24 }}>
          <GoldLineReveal delay={isPreloader ? (fastReveal ? 50 : 88) : 24} color={accentColor} />
        </div>
      </div>
    </OverlayShell>
  );
};

export const LuxuryTickerBand: React.FC<LuxuryTickerBandEvent> = ({
  durationFrames,
  items,
  emphasis,
}) => {
  const frame = useCurrentFrame();
  const exit = clamp(frame, [durationFrames - 18, durationFrames], [0, 1]);
  const enterY = clamp(frame, [0, 20], [54, 0]);
  const opacity = clamp(frame, [0, 16], [0, 1]) * (1 - exit);
  const loopText = Array.from({ length: 24 }, (_, group) =>
    items.map((item) => ({ item, group }))
  ).flat();
  const x = -frame * 0.78;

  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 0,
        height: 48,
        overflow: "hidden",
        background: "rgba(9,36,15,0.94)",
        borderTop: `1px solid ${COLORS.gold}44`,
        opacity,
        transform: `translateY(${enterY + exit * 40}px)`,
        fontFamily: "Georgia, 'Times New Roman', serif",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          height: "100%",
          transform: `translateX(${x}px)`,
          whiteSpace: "nowrap",
        }}
      >
        {loopText.map(({ item, group }, index) => (
          <span
            key={`${item}-${group}-${index}`}
            style={{
              color: item === emphasis ? COLORS.gold : "rgba(255,255,255,0.22)",
              fontSize: 27,
              letterSpacing: "0.08em",
              padding: "0 22px",
              textTransform: "uppercase",
            }}
          >
            {item} <span style={{ color: "rgba(255,255,255,0.24)" }}>|</span>
          </span>
        ))}
      </div>
    </div>
  );
};

export const SfxCueLayer: React.FC<{ cues: LuxurySfxCue[] }> = ({ cues }) => {
  return (
    <>
      {cues.map((cue) => (
        <Sequence key={cue.id} from={cue.startFrame} durationInFrames={90}>
          <Audio
            src={staticFile(cue.file)}
            volume={Math.min(1, (cue.volume ?? 0.16) * 2)}
          />
        </Sequence>
      ))}
    </>
  );
};
