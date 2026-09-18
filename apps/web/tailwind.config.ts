import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f0f7f4", 100: "#dbece4", 500: "#2f7a5d",
          600: "#256349", 700: "#1d4e3a", 900: "#12301f",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
