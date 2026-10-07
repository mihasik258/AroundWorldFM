
export interface ScreenPoint {
  x: number;
  y: number;
  visible: boolean;
}

export const flightOverlay = {
  plane: { x: 0, y: 0, visible: false } as ScreenPoint,
  pins: new Map<string, ScreenPoint>(),
};
