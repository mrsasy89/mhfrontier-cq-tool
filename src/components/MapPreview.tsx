import classNames from "classnames";
import { useEffect, useRef, useState } from "react";

import { findMapAndStage } from "../utils";
import { hasCalibration, mapImagePath, pointerToCanvas, toCanvasPoint, toGamePoint } from "../utils/mapPreview";

interface MaPreviewObject {
  x: number;
  y: number;
  id: string | number;
}

interface MapPreviewProps {
  mapId: number;
  areaId: number;
  objects: MaPreviewObject[];
  shouldCalculate?: boolean;
  canDraw?: boolean;
  onChange?: (object: MaPreviewObject) => void;
}

const colors = ["rgb(250,82,222)", "red", "blue", "green", "yellow"];

export function MapPreview({ areaId, mapId, objects, canDraw = true, shouldCalculate = true, onChange }: MapPreviewProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [selected, setSelected] = useState<string | number | undefined>(objects[0]?.id);
  const [loaded, setLoaded] = useState<{ path: string; image?: HTMLImageElement }>();
  const { map, stage } = findMapAndStage(mapId, areaId);
  const path = map && stage ? mapImagePath(map.name, stage.areaNumber) : undefined;
  const image = loaded?.path === path ? loaded?.image : undefined;
  const failed = path !== undefined && loaded?.path === path && !image;
  const calibrated = stage ? hasCalibration(stage) : false;
  const active = objects.find(object => object.id === selected) ?? objects[0];
  const editable = !!image && !!active && !!onChange && canDraw && (!shouldCalculate || calibrated);

  useEffect(() => {
    if (!path) return;
    let cancelled = false;
    const next = new Image();
    next.onload = () => { if (!cancelled) setLoaded({ path, image: next }); };
    next.onerror = () => { if (!cancelled) setLoaded({ path }); };
    next.src = path;
    return () => {
      cancelled = true;
      next.onload = null;
      next.onerror = null;
    };
  }, [path]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx || !image || !stage) return;
    canvas.width = image.naturalWidth;
    canvas.height = image.naturalHeight;
    ctx.drawImage(image, 0, 0);
    objects.forEach((object, index) => {
      const point = toCanvasPoint(object, stage, shouldCalculate);
      if (!point) return;
      ctx.fillStyle = colors[index % colors.length];
      ctx.beginPath();
      ctx.arc(point.x, point.y, 10, 0, 2 * Math.PI);
      ctx.fill();
    });
  }, [image, stage, objects, shouldCalculate]);

  const move: React.MouseEventHandler<HTMLCanvasElement> = event => {
    const canvas = canvasRef.current;
    if (!editable || !canvas || !stage || !active) return;
    const pixel = pointerToCanvas(event.clientX, event.clientY, canvas.getBoundingClientRect(), canvas.width, canvas.height);
    const point = pixel && toGamePoint(pixel, stage, shouldCalculate);
    if (point) onChange?.({ ...point, id: active.id });
  };

  if (!map || !stage) return null;

  return (
    <div className="text-center min-w-0 max-w-full" style={{ width: 180 }}>
      {objects.length > 1 && (
        <div className="flex flex-row flex-wrap gap-2 mb-1">
          {objects.map((object, index) => (
            <button
              key={object.id}
              type="button"
              aria-label={`Select marker ${index + 1}`}
              aria-pressed={active?.id === object.id}
              onClick={() => setSelected(object.id)}
              className={classNames("w-4 h-4 rounded-full shadow-sm", {
                "ring-2 ring-slate-400 ring-offset-2 border-2 border-emerald-500": active?.id === object.id,
              })}
              style={{ backgroundColor: colors[index % colors.length] }}
            />
          ))}
        </div>
      )}
      {image ? (
        <canvas ref={canvasRef} className="bg-black ring-1 ring-gray-400" style={{ maxWidth: "100%", height: "auto", cursor: editable ? "crosshair" : "default" }} onClick={move} />
      ) : (
        <p role="status">{!path ? "No map image for this area." : failed ? "Map image not found." : "Loading map…"}</p>
      )}
      {image && shouldCalculate && !calibrated && (
        <small>Preview only: this area has no calibrated game coordinates. Edit X/Y/Z directly.</small>
      )}
      {editable && <small>Click on the image to move.</small>}
    </div>
  );
}
