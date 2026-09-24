// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";

const setBackgroundColor = vi.fn(async () => {});
vi.mock("./native", () => ({ setBackgroundColor }));

const { DEFAULT_UI, UI_KEY, applyTheme, loadUi, saveUi } = await import("./settings");

beforeEach(() => {
  localStorage.clear();
  setBackgroundColor.mockClear();
  delete document.documentElement.dataset.theme;
});

describe("loadUi", () => {
  it("returns defaults when nothing is saved or the saved value is corrupt", () => {
    expect(loadUi()).toEqual(DEFAULT_UI);
    localStorage.setItem(UI_KEY, "{not json");
    expect(loadUi()).toEqual(DEFAULT_UI);
  });

  it("converts the old separate filter flags into the Filter menu's settings", () => {
    localStorage.setItem(UI_KEY, JSON.stringify({ dupOnly: true, unavailableOnly: false, sortKey: "artist" }));
    const ui = loadUi();
    expect(ui.filters).toEqual({ duplicates: true, unavailable: false });
    expect(ui.sortKey).toBe("artist");
    expect(ui.theme).toBe("system"); // new settings get their defaults
  });

  it("round-trips through saveUi", () => {
    const ui = { ...DEFAULT_UI, theme: "dark" as const, filters: { duplicates: false, unavailable: true } };
    saveUi(ui);
    expect(loadUi()).toEqual(ui);
  });
});

describe("applyTheme", () => {
  it("forces light or dark on the document and the native window, and clears it for system", () => {
    applyTheme("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(setBackgroundColor).toHaveBeenLastCalledWith([27, 23, 24]);
    applyTheme("light");
    expect(setBackgroundColor).toHaveBeenLastCalledWith([250, 246, 246]);
    applyTheme("system");
    expect(document.documentElement.dataset.theme).toBeUndefined();
  });
});
