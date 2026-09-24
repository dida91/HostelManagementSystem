"use client";

/**
 * The hostel's blocks as stacked floors of rooms, coloured by occupancy.
 * Presentation only: rooms arrive as props; hover and selection leave as
 * callbacks. Loaded with next/dynamic (no SSR).
 */
import { Canvas, type ThreeEvent, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";

import { roomState } from "./room-states";

export interface ModelBlock {
  id: string;
  name: string;
}

export interface ModelRoom {
  id: string;
  blockId: string;
  floor: number;
  number: string;
  beds: number;
  occupied: number;
  status: string;
}

const ROOM = { w: 1.5, h: 0.78, d: 1.6, gap: 0.24, floorH: 1.08, plinth: 0.14, blockGap: 2.8 };

interface Placed {
  room: ModelRoom;
  position: [number, number, number];
}

interface BlockLayout {
  block: ModelBlock;
  center: [number, number];
  width: number;
  depth: number;
  height: number;
  placed: Placed[];
}

function naturalCompare(a: string, b: string) {
  return a.localeCompare(b, undefined, { numeric: true });
}

function layout(blocks: ModelBlock[], rooms: ModelRoom[]) {
  const out: BlockLayout[] = [];
  let cursor = 0;
  for (const block of blocks) {
    const mine = rooms.filter((r) => r.blockId === block.id);
    if (mine.length === 0) continue;
    const floors = new Map<number, ModelRoom[]>();
    for (const r of mine) floors.set(r.floor, [...(floors.get(r.floor) ?? []), r]);
    const perRow = Math.min(6, Math.max(...[...floors.values()].map((f) => f.length)));
    const rows = Math.max(...[...floors.values()].map((f) => Math.ceil(f.length / perRow)));
    const width = perRow * (ROOM.w + ROOM.gap) - ROOM.gap;
    const depth = rows * (ROOM.d + ROOM.gap) - ROOM.gap;
    const floorKeys = [...floors.keys()].sort((a, b) => a - b);
    const lowest = floorKeys[0];
    const placed: Placed[] = [];
    for (const floor of floorKeys) {
      const list = (floors.get(floor) ?? []).sort((a, b) => naturalCompare(a.number, b.number));
      list.forEach((room, i) => {
        const col = i % perRow;
        const row = Math.floor(i / perRow);
        placed.push({
          room,
          position: [
            cursor + col * (ROOM.w + ROOM.gap) + ROOM.w / 2,
            ROOM.plinth + (floor - lowest) * ROOM.floorH + ROOM.h / 2,
            row * (ROOM.d + ROOM.gap) + ROOM.d / 2 - depth / 2,
          ],
        });
      });
    }
    out.push({
      block,
      center: [cursor + width / 2, 0],
      width,
      depth,
      height: ROOM.plinth + (floorKeys[floorKeys.length - 1] - lowest + 1) * ROOM.floorH,
      placed,
    });
    cursor += width + ROOM.blockGap;
  }
  const total = Math.max(0, cursor - ROOM.blockGap);
  const shift = total / 2;
  for (const b of out) {
    b.center[0] -= shift;
    for (const p of b.placed) p.position[0] -= shift;
  }
  const height = Math.max(1, ...out.map((b) => b.height));
  const extent = Math.max(3.5, total, ...out.map((b) => b.depth), height * 1.2);
  return { blocks: out, extent, height };
}

function labelTexture(text: string): { texture: THREE.CanvasTexture; aspect: number } {
  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d") as CanvasRenderingContext2D;
  const family = getComputedStyle(document.body).fontFamily;
  const font = `600 64px ${family}`;
  ctx.font = font;
  const width = Math.ceil(ctx.measureText(text).width) + 48;
  canvas.width = width;
  canvas.height = 96;
  ctx.font = font;
  ctx.fillStyle = "#edf3f2";
  ctx.textBaseline = "middle";
  ctx.fillText(text, 24, 50);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return { texture, aspect: width / 96 };
}

function BlockLabel({ text, position }: { text: string; position: [number, number, number] }) {
  const { texture, aspect } = useMemo(() => labelTexture(text), [text]);
  useEffect(() => () => texture.dispose(), [texture]);
  return (
    <sprite position={position} scale={[0.62 * aspect, 0.62, 1]}>
      <spriteMaterial map={texture} transparent depthWrite={false} />
    </sprite>
  );
}

function Controls({
  target,
  distance,
  autoRotate,
}: {
  target: THREE.Vector3;
  distance: number;
  autoRotate: boolean;
}) {
  const { camera, gl, invalidate } = useThree();
  const aspect = useThree((s) => s.size.width / Math.max(1, s.size.height));
  const controls = useRef<OrbitControls | null>(null);
  // Framed for a wide stage; a narrow one (a phone) steps back so every block fits.
  const fit = distance * (aspect > 0 ? Math.min(2, Math.max(1, 1.3 / aspect)) : 1);

  useEffect(() => {
    camera.position.set(fit * 0.62, fit * 0.52, fit * 0.78);
    const c = new OrbitControls(camera, gl.domElement);
    c.target.copy(target);
    c.enableDamping = true;
    c.dampingFactor = 0.08;
    c.enablePan = false;
    c.minDistance = fit * 0.45;
    c.maxDistance = fit * 1.8;
    c.minPolarAngle = 0.35;
    c.maxPolarAngle = Math.PI * 0.46;
    c.autoRotateSpeed = 0.45;
    // On touch screens, let the page scroll: the 2D grid is the touch path.
    if (window.matchMedia("(pointer: coarse)").matches) {
      c.enableRotate = false;
      c.enableZoom = false;
      gl.domElement.style.touchAction = "pan-y";
    }
    c.addEventListener("change", () => invalidate());
    c.addEventListener("start", () => {
      c.autoRotate = false;
    });
    c.update();
    controls.current = c;
    invalidate();
    return () => c.dispose();
  }, [camera, gl, target, fit, invalidate]);

  useEffect(() => {
    if (controls.current) controls.current.autoRotate = autoRotate;
  }, [autoRotate]);

  useFrame(() => controls.current?.update());
  return null;
}

function Room({
  placed,
  geometry,
  selected,
  hovered,
  onHover,
  onSelect,
}: {
  placed: Placed;
  geometry: THREE.BufferGeometry;
  selected: boolean;
  hovered: boolean;
  onHover: (room: ModelRoom | null, e?: ThreeEvent<PointerEvent>) => void;
  onSelect: (id: string) => void;
}) {
  const color = roomState(placed.room).color;
  const lift = selected ? 0.1 : hovered ? 0.05 : 0;
  return (
    <mesh
      geometry={geometry}
      position={[placed.position[0], placed.position[1] + lift, placed.position[2]]}
      onPointerOver={(e) => {
        e.stopPropagation();
        onHover(placed.room, e);
      }}
      onPointerMove={(e) => {
        e.stopPropagation();
        onHover(placed.room, e);
      }}
      onPointerOut={() => onHover(null)}
      onClick={(e) => {
        e.stopPropagation();
        // A drag that ends on a room is an orbit, not a click.
        if (e.delta < 6) onSelect(placed.room.id);
      }}
    >
      <meshStandardMaterial
        color={color}
        roughness={0.55}
        metalness={0.05}
        emissive={selected ? "#f2b544" : color}
        emissiveIntensity={selected ? 0.55 : hovered ? 0.32 : 0.12}
      />
    </mesh>
  );
}

export default function BlockModelScene({
  blocks,
  rooms,
  selectedId,
  onSelect,
  onHover,
  active,
  onReady,
}: {
  blocks: ModelBlock[];
  rooms: ModelRoom[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onHover: (room: ModelRoom | null, point?: { x: number; y: number }) => void;
  active: boolean;
  onReady?: () => void;
}) {
  const scene = useMemo(() => layout(blocks, rooms), [blocks, rooms]);
  const geometry = useMemo(() => new RoundedBoxGeometry(ROOM.w, ROOM.h, ROOM.d, 3, 0.1), []);
  useEffect(() => () => geometry.dispose(), [geometry]);
  const [hovered, setHovered] = useState<string | null>(null);
  const target = useMemo(() => new THREE.Vector3(0, scene.height * 0.42, 0), [scene.height]);
  const distance = scene.extent * 1.35 + 2;

  const hover = (room: ModelRoom | null, e?: ThreeEvent<PointerEvent>) => {
    setHovered(room?.id ?? null);
    document.body.style.cursor = room ? "pointer" : "";
    onHover(room, e ? { x: e.nativeEvent.clientX, y: e.nativeEvent.clientY } : undefined);
  };
  useEffect(() => () => void (document.body.style.cursor = ""), []);

  return (
    <Canvas
      dpr={[1, 1.75]}
      frameloop={active ? "always" : "demand"}
      camera={{ fov: 34, near: 0.1, far: 400, position: [distance * 0.62, distance * 0.52, distance * 0.78] }}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      onCreated={() => requestAnimationFrame(() => onReady?.())}
      onPointerMissed={() => hover(null)}
    >
      <hemisphereLight args={["#9fb4d6", "#0a1a20", 0.75]} />
      <directionalLight position={[10, 16, 9]} intensity={1.7} color="#f6c3b2" />
      <directionalLight position={[-12, 8, -6]} intensity={0.5} color="#7fb7db" />

      <mesh rotation-x={-Math.PI / 2} position={[0, -0.001, 0]}>
        <circleGeometry args={[scene.extent * 0.9, 64]} />
        <meshStandardMaterial color="#163640" roughness={1} transparent opacity={0.85} />
      </mesh>

      {scene.blocks.map((b) => (
        <group key={b.block.id}>
          <mesh position={[b.center[0], ROOM.plinth / 2, 0]}>
            <boxGeometry args={[b.width + 0.7, ROOM.plinth, b.depth + 0.7]} />
            <meshStandardMaterial color="#1a363f" roughness={0.9} />
          </mesh>
          <BlockLabel text={b.block.name} position={[b.center[0], b.height + 0.55, 0]} />
          {b.placed.map((p) => (
            <Room
              key={p.room.id}
              placed={p}
              geometry={geometry}
              selected={p.room.id === selectedId}
              hovered={p.room.id === hovered}
              onHover={hover}
              onSelect={onSelect}
            />
          ))}
        </group>
      ))}
      <Controls target={target} distance={distance} autoRotate={active && !selectedId} />
    </Canvas>
  );
}
