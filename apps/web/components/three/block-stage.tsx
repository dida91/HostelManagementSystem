"use client";

import dynamic from "next/dynamic";
import { useState } from "react";

import { cn } from "@/lib/cn";

import type { ModelBlock, ModelRoom } from "./block-model-scene";
import { useSceneActivity } from "./use-scene-activity";

const BlockModelScene = dynamic(() => import("./block-model-scene"), { ssr: false });

/**
 * Frame for the 3D block model with a hover label. Without WebGL it shows a
 * short note instead: the room grid below the stage carries the same data.
 */
export function BlockStage({
  blocks,
  rooms,
  selectedId,
  onSelect,
  className,
}: {
  blocks: ModelBlock[];
  rooms: ModelRoom[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  className?: string;
}) {
  const { ref, supported, active } = useSceneActivity<HTMLDivElement>();
  const [ready, setReady] = useState(false);
  const [hover, setHover] = useState<{ room: ModelRoom; x: number; y: number } | null>(null);

  return (
    <div
      ref={ref}
      className={cn(
        "relative isolate overflow-hidden rounded-stage border border-hairline shadow-panel",
        "bg-[radial-gradient(120%_90%_at_70%_0%,rgba(240,138,118,0.12),transparent_55%),linear-gradient(180deg,#0f252c,#0a1a20)]",
        className,
      )}
    >
      {supported ? (
        <div className={cn("absolute inset-0 transition-opacity duration-slow", ready ? "opacity-100" : "opacity-0")}>
          <BlockModelScene
            blocks={blocks}
            rooms={rooms}
            selectedId={selectedId}
            onSelect={onSelect}
            active={active}
            onReady={() => setReady(true)}
            onHover={(room, point) => {
              if (!room || !point || !ref.current) return setHover(null);
              const box = ref.current.getBoundingClientRect();
              setHover({ room, x: point.x - box.left, y: point.y - box.top });
            }}
          />
        </div>
      ) : (
        <p className="absolute inset-0 grid place-items-center px-6 text-center text-ui text-stone">
          The 3D view needs WebGL, which this browser doesn’t offer. Every room is listed below.
        </p>
      )}
      {hover && (
        <div
          role="tooltip"
          style={{ left: hover.x, top: hover.y }}
          className="glass pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-[calc(100%+14px)] whitespace-nowrap rounded-control px-3 py-2 text-small shadow-overlay"
        >
          <span className="font-semibold text-snow">Room {hover.room.number}</span>
          <span className="ml-2 text-mist">
            {hover.room.occupied} of {hover.room.beds} beds filled
          </span>
        </div>
      )}
    </div>
  );
}
