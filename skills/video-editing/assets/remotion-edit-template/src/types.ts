export type CanvasSpec = {
  width: number;
  height: number;
  fps: number;
  durationInFrames: number;
  background: string | null;
};

export type MediaSpec = {
  video?: string;
  image?: string;
  audio?: string;
};

export type EditProps = {
  canvas: CanvasSpec;
  media: MediaSpec;
  title: string;
  subtitle: string;
  accent: string;
  transparent: boolean;
};
