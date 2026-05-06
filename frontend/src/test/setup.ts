import "@testing-library/jest-dom/vitest";

// Vitest/jsdom compatibility for browser-only deps (xterm initializes with `self`)
if (typeof globalThis.self === "undefined") {
  (globalThis as unknown as { self: typeof globalThis }).self = globalThis;
}
