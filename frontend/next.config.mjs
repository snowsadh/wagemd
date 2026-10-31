import { PHASE_DEVELOPMENT_SERVER } from "next/constants.js";

// Keep dev output separate so a production build cannot corrupt the running server.
/** @returns {import('next').NextConfig} */
export default (phase) => ({
  distDir: phase === PHASE_DEVELOPMENT_SERVER ? ".next-dev" : ".next",
});
