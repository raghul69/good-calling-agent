/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Expose both VITE_* (Vite default) and NEXT_PUBLIC_* (Vercel dashboard naming) to the client.
export default defineConfig({
  plugins: [react()],
  envPrefix: ["VITE_", "NEXT_PUBLIC_"],
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    pool: "threads",
    maxWorkers: 1,
    fileParallelism: false,
  },
});