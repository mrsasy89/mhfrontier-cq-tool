interface Point { x: number; y: number }
interface Polynomial { a: number; b: number }
interface Stage { calculationX?: Polynomial; calculationY?: Polynomial }

const folders: Record<string, string> = {
  "Snowy Mountains Day": "Snowy Mountain Day",
  "Snowy Mountains Night": "Snowy Mountain Night",
  "Castle Schrade": "Schrade Castle",
  "Tower 1": "Tower 01",
  "Tower 2": "Tower 02",
  "Tower 3": "Tower 03",
};

export function mapImagePath(name: string, area: string): string | undefined {
  const number = area === "Base" ? "0" : /^Area (\d+)$/.exec(area)?.[1];
  return number === undefined ? undefined : `/maps/${encodeURIComponent(folders[name] ?? name)}/${number}.png`;
}

export function hasCalibration(stage: Stage): boolean {
  return [stage.calculationX, stage.calculationY].every(
    value => value !== undefined && Number.isFinite(value.a) && value.a !== 0 && Number.isFinite(value.b)
  );
}

function convert(point: Point, stage: Stage, calculate: boolean, inverse: boolean): Point | undefined {
  if (!Number.isFinite(point.x) || !Number.isFinite(point.y)) return undefined;
  if (!calculate) return { ...point };
  if (!hasCalibration(stage)) return undefined;
  const x = stage.calculationX!;
  const y = stage.calculationY!;
  const result = inverse
    ? { x: (point.x - x.b) / x.a, y: (point.y - y.b) / y.a }
    : { x: point.x * x.a + x.b, y: point.y * y.a + y.b };
  return Number.isFinite(result.x) && Number.isFinite(result.y) ? result : undefined;
}

export const toCanvasPoint = (point: Point, stage: Stage, calculate = true) => convert(point, stage, calculate, true);
export const toGamePoint = (point: Point, stage: Stage, calculate = true) => convert(point, stage, calculate, false);

export function pointerToCanvas(
  clientX: number, clientY: number,
  rect: { left: number; top: number; width: number; height: number },
  width: number, height: number
): Point | undefined {
  if (![clientX, clientY, rect.left, rect.top, rect.width, rect.height, width, height].every(Number.isFinite)
    || rect.width <= 0 || rect.height <= 0 || width <= 0 || height <= 0) return undefined;
  const x = (clientX - rect.left) / rect.width;
  const y = (clientY - rect.top) / rect.height;
  if (x < 0 || x > 1 || y < 0 || y > 1) return undefined;
  return { x: x * width, y: y * height };
}
