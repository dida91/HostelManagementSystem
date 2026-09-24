"use client";

/**
 * The Machhapuchhre horizon: faceted foothills and the fishtail summit at dusk,
 * lit by alpenglow, reflected in Phewa lake, with slow mist.
 *
 * Presentation only: no data, no API calls. Loaded with next/dynamic (no SSR).
 */
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import { RIDGE, SHORE_Z, colourFor, heightAt } from "./terrain";

export type HorizonVariant = "full" | "band";

function useRidgeGeometry() {
  return useMemo(() => {
    const plane = new THREE.PlaneGeometry(RIDGE.width, RIDGE.depth, RIDGE.segX, RIDGE.segZ);
    plane.rotateX(-Math.PI / 2);
    plane.translate(0, 0, RIDGE.centerZ);
    const pos = plane.attributes.position as THREE.BufferAttribute;
    for (let i = 0; i < pos.count; i++) {
      pos.setY(i, heightAt(pos.getX(i), pos.getZ(i)));
    }
    // Non-indexed so every triangle is its own facet with one colour.
    const geometry = plane.toNonIndexed();
    plane.dispose();
    const p = geometry.attributes.position as THREE.BufferAttribute;
    const colours = new Float32Array(p.count * 3);
    for (let i = 0; i < p.count; i += 3) {
      const cx = (p.getX(i) + p.getX(i + 1) + p.getX(i + 2)) / 3;
      const cz = (p.getZ(i) + p.getZ(i + 1) + p.getZ(i + 2)) / 3;
      const cy = (p.getY(i) + p.getY(i + 1) + p.getY(i + 2)) / 3;
      const [r, g, b] = colourFor(cy, cx, cz);
      for (let k = 0; k < 3; k++) colours.set([r, g, b], (i + k) * 3);
    }
    geometry.setAttribute("color", new THREE.BufferAttribute(colours, 3));
    geometry.computeVertexNormals();
    return geometry;
  }, []);
}

function Ridge() {
  const geometry = useRidgeGeometry();
  useEffect(() => () => geometry.dispose(), [geometry]);
  return (
    <>
      <mesh geometry={geometry}>
        <meshStandardMaterial vertexColors flatShading roughness={0.92} metalness={0} />
      </mesh>
      {/* Reflection: the same land, mirrored under the translucent lake. */}
      <mesh geometry={geometry} scale={[1, -1, 1]} position={[0, -0.02, 0]}>
        <meshBasicMaterial vertexColors color="#6d8790" side={THREE.DoubleSide} />
      </mesh>
    </>
  );
}

function Lake() {
  const glint = useRef<THREE.MeshBasicMaterial>(null);
  useFrame(({ clock }) => {
    if (glint.current) glint.current.opacity = 0.1 + Math.sin(clock.elapsedTime * 0.6) * 0.04;
  });
  return (
    <>
      <mesh rotation-x={-Math.PI / 2} position={[0, 0, SHORE_Z + 30]}>
        <planeGeometry args={[420, 64]} />
        <meshBasicMaterial color="#0b242c" transparent opacity={0.82} depthWrite={false} />
      </mesh>
      {/* Alpenglow caught on the water under the fishtail. */}
      <mesh rotation-x={-Math.PI / 2} position={[6, 0.01, SHORE_Z + 1.2]}>
        <planeGeometry args={[7, 0.5]} />
        <meshBasicMaterial
          ref={glint}
          color="#f08a76"
          transparent
          opacity={0.16}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </mesh>
    </>
  );
}

const skyVertex = /* glsl */ `
  varying vec3 vDir;
  void main() {
    vDir = normalize(position);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const skyFragment = /* glsl */ `
  uniform vec3 top;
  uniform vec3 mid;
  uniform vec3 horizon;
  uniform vec3 glow;
  uniform vec3 glowDir;
  varying vec3 vDir;
  void main() {
    float h = vDir.y;
    vec3 col = mix(horizon, mid, smoothstep(0.0, 0.22, h));
    col = mix(col, top, smoothstep(0.22, 0.6, h));
    float g = pow(max(dot(normalize(vDir), normalize(glowDir)), 0.0), 7.0);
    col += glow * g * 0.4 * smoothstep(-0.02, 0.04, h);
    // Below the horizon the "sky" is only ever seen through the lake: keep it dark.
    col = mix(vec3(0.035, 0.09, 0.11), col, smoothstep(-0.06, 0.0, h));
    gl_FragColor = vec4(col, 1.0);
  }
`;

function Sky() {
  const uniforms = useMemo(
    () => ({
      top: { value: new THREE.Color("#0b1c23") },
      mid: { value: new THREE.Color("#35293f") },
      horizon: { value: new THREE.Color("#e29a7f") },
      glow: { value: new THREE.Color("#f2b544") },
      glowDir: { value: new THREE.Vector3(1.0, 0.1, -1.2) },
    }),
    [],
  );
  return (
    <mesh>
      <sphereGeometry args={[140, 32, 16]} />
      <shaderMaterial
        side={THREE.BackSide}
        depthWrite={false}
        fog={false}
        uniforms={uniforms}
        vertexShader={skyVertex}
        fragmentShader={skyFragment}
      />
    </mesh>
  );
}

function softDot(): THREE.Texture {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d") as CanvasRenderingContext2D;
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0, "rgba(255,255,255,1)");
  g.addColorStop(0.4, "rgba(255,255,255,0.35)");
  g.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function Mist({ count }: { count: number }) {
  const points = useRef<THREE.Points>(null);
  const texture = useMemo(softDot, []);
  const { positions, speeds } = useMemo(() => {
    const positions = new Float32Array(count * 3);
    const speeds = new Float32Array(count);
    for (let i = 0; i < count; i++) {
      positions[i * 3] = (Math.random() - 0.5) * 70;
      positions[i * 3 + 1] = 0.25 + Math.random() * 2.6;
      positions[i * 3 + 2] = SHORE_Z - 2 + Math.random() * 24;
      speeds[i] = 0.12 + Math.random() * 0.28;
    }
    return { positions, speeds };
  }, [count]);
  useEffect(() => () => texture.dispose(), [texture]);

  useFrame((_, dt) => {
    const attr = points.current?.geometry.attributes.position as THREE.BufferAttribute | undefined;
    if (!attr) return;
    const step = Math.min(dt, 0.05);
    for (let i = 0; i < count; i++) {
      let x = attr.getX(i) + speeds[i] * step;
      if (x > 35) x = -35;
      attr.setX(i, x);
    }
    attr.needsUpdate = true;
  });

  return (
    <points ref={points}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        map={texture}
        size={1.9}
        color="#c9dde3"
        transparent
        opacity={0.13}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

function Stars() {
  const positions = useMemo(() => {
    const out = new Float32Array(170 * 3);
    for (let i = 0; i < 170; i++) {
      const theta = Math.random() * Math.PI * 2;
      const y = 0.28 + Math.random() * 0.7;
      const r = Math.sqrt(1 - y * y);
      out.set([Math.cos(theta) * r * 120, y * 120, Math.sin(theta) * r * 120 - 20], i * 3);
    }
    return out;
  }, []);
  return (
    <points>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial size={0.32} color="#edf3f2" transparent opacity={0.55} fog={false} />
    </points>
  );
}

/** Slow drift plus a little pointer parallax; framing adapts to the aspect ratio. */
function Rig({ variant }: { variant: HorizonVariant }) {
  const { camera, size, invalidate } = useThree();
  const target = useRef(new THREE.Vector3());
  const look = useRef(new THREE.Vector3());

  const frame = useMemo(() => {
    const aspect = size.width / Math.max(1, size.height);
    const narrow = aspect < 1.1;
    const base =
      variant === "band"
        ? new THREE.Vector3(0, narrow ? 4.6 : 3.4, narrow ? 24 : 15)
        : new THREE.Vector3(narrow ? 5 : -2, narrow ? 3.4 : 3.0, narrow ? 24 : 14);
    const lookAt =
      variant === "band"
        ? new THREE.Vector3(narrow ? 5 : 1, narrow ? 7 : 6.2, -30)
        : new THREE.Vector3(narrow ? 5.5 : 0, narrow ? 7.5 : 6.4, -30);
    return { base, lookAt };
  }, [variant, size.width, size.height]);

  useEffect(() => {
    camera.position.copy(frame.base);
    look.current.copy(frame.lookAt);
    camera.lookAt(frame.lookAt);
    // In still mode nothing else will ask for a frame.
    invalidate();
  }, [camera, frame, invalidate]);

  useFrame((state, dt) => {
    const t = state.clock.elapsedTime;
    target.current.set(
      frame.base.x + Math.sin(t * 0.045) * 0.9 + state.pointer.x * 0.8,
      frame.base.y + Math.sin(t * 0.07) * 0.12 + state.pointer.y * 0.25,
      frame.base.z,
    );
    camera.position.lerp(target.current, 1 - Math.exp(-Math.min(dt, 0.05) * 1.4));
    camera.lookAt(look.current);
  });
  return null;
}

export default function HorizonScene({
  active,
  variant = "full",
  onReady,
}: {
  active: boolean;
  variant?: HorizonVariant;
  onReady?: () => void;
}) {
  return (
    <Canvas
      dpr={[1, 1.75]}
      frameloop={active ? "always" : "demand"}
      camera={{ fov: variant === "band" ? 30 : 36, near: 0.1, far: 400 }}
      gl={{ antialias: true, powerPreference: "high-performance" }}
      onCreated={({ gl, scene }) => {
        gl.setClearColor("#0a1a20");
        scene.fog = new THREE.Fog("#1a2a33", 36, 120);
        requestAnimationFrame(() => onReady?.());
      }}
      aria-hidden
    >
      <hemisphereLight args={["#8fa3c4", "#0a1a20", 0.6]} />
      {/* Alpenglow: a low warm key from the right, catching the faces toward the lake. */}
      <directionalLight position={[22, 11, 16]} intensity={2.7} color="#f4a07f" />
      <directionalLight position={[-20, 9, 10]} intensity={0.45} color="#7fb7db" />
      <Sky />
      <Stars />
      <Ridge />
      <Lake />
      <Mist count={variant === "band" ? 140 : 220} />
      <Rig variant={variant} />
    </Canvas>
  );
}
