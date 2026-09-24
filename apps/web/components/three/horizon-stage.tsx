"use client";

import dynamic from "next/dynamic";
import { useState } from "react";

import { cn } from "@/lib/cn";
import { useSvgId } from "@/lib/use-svg-id";

import type { HorizonVariant } from "./horizon-scene";
import { useSceneActivity } from "./use-scene-activity";

const HorizonScene = dynamic(() => import("./horizon-scene"), { ssr: false });

/**
 * The same composition as the 3D scene, drawn in SVG. Shown immediately (it is
 * server-rendered), under the canvas while three.js loads, and alone when WebGL
 * is unavailable — so there is never an empty frame or a layout shift.
 */
export function HorizonFallback({
  className,
  variant = "full",
}: {
  className?: string;
  variant?: HorizonVariant;
}) {
  const id = useSvgId("hf");
  const ridge =
    "M0 560 L90 520 L170 540 L260 470 L330 500 L420 430 L500 470 L560 450 L640 380 L690 420 L760 300 L800 360 L850 250 L905 150 L935 205 L965 170 L1030 330 L1090 300 L1160 390 L1240 360 L1320 420 L1400 400 L1500 470 L1600 450 L1600 640 L0 640 Z";
  return (
    <svg
      aria-hidden
      // The band crops to the ridge so the summit is never cut off.
      viewBox={variant === "band" ? "0 90 1600 640" : "0 0 1600 900"}
      preserveAspectRatio="xMidYMid slice"
      className={cn("h-full w-full", className)}
    >
      <defs>
        <linearGradient id={`${id}-sky`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#0B1C23" />
          <stop offset="0.45" stopColor="#35293F" />
          <stop offset="0.7" stopColor="#D9907A" />
        </linearGradient>
        <linearGradient id={`${id}-land`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#E6ECEF" />
          <stop offset="0.35" stopColor="#8F9EA8" />
          <stop offset="0.6" stopColor="#233A40" />
          <stop offset="1" stopColor="#12292B" />
        </linearGradient>
        <linearGradient id={`${id}-lake`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#10303A" />
          <stop offset="1" stopColor="#0A1A20" />
        </linearGradient>
        <radialGradient id={`${id}-glow`} cx="0.72" cy="0.62" r="0.5">
          <stop offset="0" stopColor="#F2B544" stopOpacity="0.35" />
          <stop offset="1" stopColor="#F2B544" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="1600" height="640" fill={`url(#${id}-sky)`} />
      <rect width="1600" height="640" fill={`url(#${id}-glow)`} />
      <path d={ridge} fill={`url(#${id}-land)`} />
      <rect y="640" width="1600" height="260" fill={`url(#${id}-lake)`} />
      <path d={ridge} fill={`url(#${id}-land)`} opacity="0.18" transform="translate(0 1280) scale(1 -1)" />
    </svg>
  );
}

/**
 * Stage for the horizon. Content passed as children sits above the scene.
 * The scene fades in when its first frame is ready — the one orchestrated
 * moment of the visit — and pauses whenever it would be wasted work.
 */
export function HorizonStage({
  variant = "full",
  className,
  children,
}: {
  variant?: HorizonVariant;
  className?: string;
  children?: React.ReactNode;
}) {
  const { ref, supported, active } = useSceneActivity<HTMLDivElement>();
  const [ready, setReady] = useState(false);
  return (
    <div ref={ref} className={cn("relative isolate overflow-hidden", className)}>
      <HorizonFallback variant={variant} className="absolute inset-0 -z-20" />
      {supported && (
        <div
          className={cn(
            "absolute inset-0 -z-10 transition-opacity duration-[1400ms] ease-out",
            ready ? "opacity-100" : "opacity-0",
          )}
        >
          <HorizonScene active={active} variant={variant} onReady={() => setReady(true)} />
        </div>
      )}
      {children}
    </div>
  );
}
