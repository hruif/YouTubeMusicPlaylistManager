// Shared setup for UI tests (files marked `// @vitest-environment jsdom`). jsdom lacks a few
// browser APIs the app uses; these stand-ins are enough for it to render. Node-environment tests
// skip all of this.
import { afterEach } from "vitest";

if (typeof window !== "undefined") {
  // Recent Node versions define their own (disabled) `localStorage` global, which hides jsdom's.
  // An in-memory Storage is all the app needs.
  if (!globalThis.localStorage) {
    const data = new Map<string, string>();
    const storage: Storage = {
      get length() {
        return data.size;
      },
      key: (i) => [...data.keys()][i] ?? null,
      getItem: (k) => data.get(k) ?? null,
      setItem: (k, v) => void data.set(k, String(v)),
      removeItem: (k) => void data.delete(k),
      clear: () => data.clear(),
    };
    Object.defineProperty(globalThis, "localStorage", { value: storage, configurable: true });
  }

  await import("@testing-library/jest-dom/vitest"); // toBeInTheDocument, toHaveFocus, …
  const { cleanup } = await import("@testing-library/react");
  afterEach(() => {
    cleanup();
    localStorage.clear();
  });

  window.matchMedia ??= ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as typeof window.matchMedia;

  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
}
