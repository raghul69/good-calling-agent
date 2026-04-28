import '@testing-library/jest-dom';

// jsdom has no IntersectionObserver (browser does); stub for mount smoke tests.
globalThis.IntersectionObserver = class IntersectionObserver {
  readonly root: Element | null = null;
  readonly rootMargin = "";
  readonly thresholds: ReadonlyArray<number> = [];
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
} as unknown as typeof IntersectionObserver;
