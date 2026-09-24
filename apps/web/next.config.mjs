/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Keep the dev-only Next.js badge off the sidebar's collapse control.
  devIndicators: { position: "bottom-right" },
  // The Gemini key lives only in the FastAPI process. Nothing here may expose it:
  // the browser never talks to Gemini, and never holds an API token.
  env: {},
};
export default nextConfig;
