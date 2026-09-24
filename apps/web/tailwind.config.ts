import type { Config } from "tailwindcss";

// Tokens from DESIGN_SYSTEM.md ("Phewa Dusk"). Named after the place, not the role:
// the lake is the canvas, marigold means act, crimson means stop.
export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        lake: {
          950: "#0A1A20",
          900: "#0E2229",
          850: "#12292F",
          800: "#173139",
          700: "#21424B",
          600: "#2F5864",
          500: "#44717E",
        },
        snow: "#EDF3F2",
        mist: "#A9BCBF",
        stone: "#7A9095",
        marigold: { DEFAULT: "#F2B544", 300: "#F7CF7E", 600: "#D9982A", ink: "#231704" },
        alpenglow: { DEFAULT: "#F08A76", 300: "#F6B3A5" },
        laligurans: { DEFAULT: "#E5455F", 300: "#F08496" },
        terrace: { DEFAULT: "#57BD8E", 300: "#8ED6B3" },
        glacier: { DEFAULT: "#7FB7DB", 300: "#B2D4EA" },
      },
      fontFamily: {
        sans: ["var(--font-latin)", "var(--font-deva)", "system-ui", "sans-serif"],
      },
      fontSize: {
        display: ["48px", { lineHeight: "52px", letterSpacing: "-0.015em", fontWeight: "600" }],
        title: ["36px", { lineHeight: "40px", letterSpacing: "-0.015em", fontWeight: "600" }],
        heading: ["21px", { lineHeight: "28px", fontWeight: "600" }],
        sub: ["16px", { lineHeight: "24px", fontWeight: "600" }],
        body: ["16px", { lineHeight: "26px" }],
        ui: ["14px", { lineHeight: "20px" }],
        small: ["12px", { lineHeight: "16px" }],
      },
      borderRadius: {
        control: "10px",
        menu: "14px",
        panel: "18px",
        overlay: "22px",
        stage: "28px",
      },
      boxShadow: {
        edge: "inset 0 1px 0 rgba(255,255,255,0.05)",
        panel: "inset 0 1px 0 rgba(255,255,255,0.05), 0 16px 40px -24px rgba(0,0,0,0.6)",
        overlay: "0 32px 80px -24px rgba(0,0,0,0.75), 0 0 0 1px rgba(237,243,242,0.08)",
        action: "0 0 0 1px rgba(242,181,68,0.5), 0 10px 30px -12px rgba(242,181,68,0.5)",
      },
      transitionTimingFunction: {
        out: "cubic-bezier(0.22, 1, 0.36, 1)",
        "in-out": "cubic-bezier(0.65, 0, 0.35, 1)",
      },
      transitionDuration: {
        instant: "90ms",
        quick: "160ms",
        base: "220ms",
        slow: "360ms",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "scale-in": {
          from: { opacity: "0", transform: "translateY(6px) scale(0.98)" },
          to: { opacity: "1", transform: "none" },
        },
        "slide-in-right": {
          from: { opacity: "0.4", transform: "translateX(24px)" },
          to: { opacity: "1", transform: "none" },
        },
        "slide-in-left": {
          from: { transform: "translateX(-100%)" },
          to: { transform: "none" },
        },
        "toast-in": {
          from: { opacity: "0", transform: "translateY(12px)" },
          to: { opacity: "1", transform: "none" },
        },
        shimmer: {
          from: { backgroundPosition: "200% 0" },
          to: { backgroundPosition: "-200% 0" },
        },
        "light-rise": {
          from: { opacity: "0", transform: "translateY(8%)" },
          to: { opacity: "1", transform: "none" },
        },
        spin: { to: { transform: "rotate(360deg)" } },
      },
      animation: {
        "fade-in": "fade-in 220ms cubic-bezier(0.22, 1, 0.36, 1) both",
        "scale-in": "scale-in 220ms cubic-bezier(0.22, 1, 0.36, 1) both",
        "slide-in-right": "slide-in-right 360ms cubic-bezier(0.22, 1, 0.36, 1) both",
        "slide-in-left": "slide-in-left 360ms cubic-bezier(0.22, 1, 0.36, 1) both",
        "toast-in": "toast-in 220ms cubic-bezier(0.22, 1, 0.36, 1) both",
        shimmer: "shimmer 2.4s linear infinite",
        "light-rise": "light-rise 1400ms cubic-bezier(0.22, 1, 0.36, 1) both",
        spin: "spin 0.8s linear infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
