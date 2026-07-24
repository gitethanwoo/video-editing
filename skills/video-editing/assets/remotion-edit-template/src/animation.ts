import {interpolate} from 'remotion';

export const cosine = (progress: number): number =>
  0.5 - 0.5 * Math.cos(Math.PI * progress);

export const segmentProgress = (
  frame: number,
  startFrame: number,
  endFrame: number,
): number => {
  return interpolate(frame, [startFrame, endFrame], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: cosine,
  });
};
