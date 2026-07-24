import {Audio, Video} from '@remotion/media';
import {
  AbsoluteFill,
  Img,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {segmentProgress} from './animation';
import type {EditProps} from './types';

const GraphicLayer = ({title, subtitle, accent}: Pick<EditProps, 'title' | 'subtitle' | 'accent'>) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const entrance = segmentProgress(frame, Math.round(fps * 0.25), Math.round(fps * 0.7));
  const y = interpolate(entrance, [0, 1], [48, 0]);
  const lineProgress = segmentProgress(frame, Math.round(fps * 0.55), Math.round(fps * 1.2));

  return (
    <AbsoluteFill>
      <svg
        viewBox="0 0 1920 1080"
        preserveAspectRatio="xMidYMid slice"
        style={{position: 'absolute', inset: 0, width: '100%', height: '100%'}}
      >
        <path
          d="M 116 836 C 330 770, 480 890, 720 806"
          fill="none"
          stroke={accent}
          strokeWidth="7"
          strokeLinecap="round"
          pathLength="1"
          strokeDasharray="1"
          strokeDashoffset={1 - lineProgress}
        />
        <circle cx="116" cy="836" r="12" fill={accent} opacity={lineProgress} />
      </svg>
      <div
        style={{
          position: 'absolute',
          left: 116,
          bottom: 118,
          maxWidth: 860,
          padding: '30px 38px 32px',
          borderRadius: 24,
          color: 'white',
          background: 'rgba(12, 16, 24, 0.82)',
          boxShadow: '0 24px 70px rgba(0, 0, 0, 0.26)',
          transform: `translateY(${y}px)`,
          opacity: entrance,
          fontFamily: "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        }}
      >
        <div style={{fontSize: 58, fontWeight: 760, letterSpacing: -1.8, lineHeight: 1.02}}>
          {title}
        </div>
        <div style={{fontSize: 28, lineHeight: 1.28, opacity: 0.76, marginTop: 14}}>
          {subtitle}
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const Edit = (props: EditProps) => {
  const background = props.transparent ? undefined : props.canvas.background ?? '#000000';

  return (
    <AbsoluteFill style={{backgroundColor: background}}>
      {props.media.video ? (
        <Video
          src={staticFile(props.media.video)}
          muted
          objectFit="cover"
          style={{width: '100%', height: '100%'}}
        />
      ) : null}
      {props.media.image ? (
        <Img
          src={staticFile(props.media.image)}
          style={{width: '100%', height: '100%', objectFit: 'cover'}}
        />
      ) : null}
      {props.media.audio ? <Audio src={staticFile(props.media.audio)} /> : null}
      <Sequence from={0}>
        <GraphicLayer title={props.title} subtitle={props.subtitle} accent={props.accent} />
      </Sequence>
    </AbsoluteFill>
  );
};
