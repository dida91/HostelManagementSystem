/**
 * Procedural Annapurna foothills with Machhapuchhre's fishtail summit.
 * Pure functions (no three.js state), so the geometry is deterministic.
 *
 * World axes: y up, the camera stands on the lake shore looking toward -z.
 */

function hash(x: number, y: number): number {
  const s = Math.sin(x * 127.1 + y * 311.7) * 43758.5453123;
  return s - Math.floor(s);
}

const fade = (t: number) => t * t * (3 - 2 * t);

/** Value noise in [0, 1]. */
export function noise2(x: number, y: number): number {
  const xi = Math.floor(x);
  const yi = Math.floor(y);
  const u = fade(x - xi);
  const v = fade(y - yi);
  const a = hash(xi, yi);
  const b = hash(xi + 1, yi);
  const c = hash(xi, yi + 1);
  const d = hash(xi + 1, yi + 1);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}

export function fbm(x: number, y: number, octaves = 4): number {
  let sum = 0;
  let amp = 0.5;
  let freq = 1;
  for (let i = 0; i < octaves; i++) {
    sum += amp * noise2(x * freq, y * freq);
    freq *= 2;
    amp *= 0.5;
  }
  return sum;
}

export function smoothstep(edge0: number, edge1: number, x: number): number {
  const t = Math.min(1, Math.max(0, (x - edge0) / (edge1 - edge0)));
  return t * t * (3 - 2 * t);
}

function peak(x: number, z: number, cx: number, cz: number, h: number, r: number, sharp = 1.7) {
  const d = Math.hypot(x - cx, (z - cz) * 1.25);
  return h * Math.pow(Math.max(0, 1 - d / r), sharp);
}

export const RIDGE = { width: 150, depth: 34, segX: 160, segZ: 44, centerZ: -33 };
export const SHORE_Z = -15;

/** Height of the land at (x, z). Zero on the lake. */
export function heightAt(x: number, z: number): number {
  const behindShore = smoothstep(SHORE_Z, SHORE_Z - 9, z);
  const range = (2.8 + 4.6 * fbm(x * 0.045 + 3.1, z * 0.05 + 7.4)) * behindShore;
  const massif = Math.max(
    peak(x, z, -24, -41, 11.8, 14),
    peak(x, z, -12, -43, 9.8, 11),
    peak(x, z, -34, -38, 8.4, 10),
    peak(x, z, 21, -41, 9.6, 12),
    peak(x, z, 33, -38, 7.6, 10),
  );
  // Machhapuchhre: two sharp summits a breath apart, standing forward of the range.
  const fishtail = Math.max(peak(x, z, 4.5, -31, 15.8, 9.8, 2.05), peak(x, z, 6.9, -31.8, 14.1, 7.6, 2.25));
  // Forested foothills framing the lake, like Sarangkot on the left.
  const foothills =
    peak(x, z, -27, -18.5, 4.2, 10, 1.25) + peak(x, z, 26, -18, 3.4, 11, 1.25) + peak(x, z, -7, -19, 2.2, 8, 1.3);
  const detail = (fbm(x * 0.32 + 11, z * 0.32 - 4) - 0.5) * 1.3 * behindShore;
  return Math.max(0, range + Math.max(massif, fishtail) + foothills + detail);
}

/** Face colour by altitude: forest, rock, then snow. RGB in 0..1. */
export function colourFor(height: number, x: number, z: number): [number, number, number] {
  const snowLine = 7.2 + (noise2(x * 0.5, z * 0.5) - 0.5) * 2.2;
  if (height > snowLine) return [0.9, 0.93, 0.95];
  if (height > snowLine - 1.6) return [0.56, 0.62, 0.66];
  if (height > 3.4) return [0.2, 0.28, 0.31];
  return [0.08, 0.19, 0.19];
}
