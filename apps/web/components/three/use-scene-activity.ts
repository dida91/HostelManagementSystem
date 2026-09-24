"use client";

import { useEffect, useRef, useState } from "react";

import { usePrefs } from "@/lib/store";

function webglAvailable(): boolean {
  try {
    const canvas = document.createElement("canvas");
    return !!(canvas.getContext("webgl2") || canvas.getContext("webgl"));
  } catch {
    return false;
  }
}

/**
 * Whether a scene may render at all (client + WebGL), and whether it may
 * animate: only when on screen, the tab is visible, and neither the OS nor the
 * in-app preference asks for reduced motion.
 */
export function useSceneActivity<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [supported, setSupported] = useState(false);
  const [onScreen, setOnScreen] = useState(true);
  const [tabVisible, setTabVisible] = useState(true);
  const [osReduced, setOsReduced] = useState(false);
  const reduceEffects = usePrefs((s) => s.reduceEffects);

  useEffect(() => {
    setSupported(webglAvailable());
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    setOsReduced(media.matches);
    const onMedia = () => setOsReduced(media.matches);
    media.addEventListener("change", onMedia);
    const onVisibility = () => setTabVisible(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      media.removeEventListener("change", onMedia);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, []);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(([entry]) => setOnScreen(entry.isIntersecting), {
      rootMargin: "80px",
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const still = osReduced || reduceEffects;
  return { ref, supported, active: supported && onScreen && tabVisible && !still, still };
}
