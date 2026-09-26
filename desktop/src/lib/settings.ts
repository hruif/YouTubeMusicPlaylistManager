// Small persisted UI state (selection, sort, filters, preferences) in localStorage — tiny, frequent
// writes that don't belong in the library cache file.

import type { PlaylistPrivacy } from "./ytmusic";
import { setBackgroundColor } from "./native";

export type SortKey = "title" | "artist" | "album" | "count" | "duration";
export type PlaylistSort = "name" | "updated" | "count";
export type Theme = "system" | "light" | "dark";
export type PlayMode = "front" | "background"; // where the browser opens when playing
export type SongFilters = {
  duplicates: boolean; // in more than one selected playlist
  inAll: boolean; // in every selected playlist
  repeated: boolean; // appears more than once within a single playlist
  unavailable: boolean;
};
export const NO_FILTERS: SongFilters = { duplicates: false, inAll: false, repeated: false, unavailable: false };

export type UiState = {
  selected: string[];
  sortKey: SortKey;
  sortAsc: boolean;
  filters: SongFilters;
  replaceNames: boolean;
  autoDeleteQueues: boolean;
  checkUpdates: boolean;
  autoRefreshOnLaunch: boolean;
  playlistSort: PlaylistSort;
  queuePrivacy: PlaylistPrivacy;
  theme: Theme;
  playMode: PlayMode;
};

export const UI_KEY = "ytm.ui";

export const DEFAULT_UI: UiState = {
  selected: [],
  sortKey: "title",
  sortAsc: true,
  filters: NO_FILTERS,
  replaceNames: false,
  autoDeleteQueues: false,
  checkUpdates: true,
  autoRefreshOnLaunch: true,
  playlistSort: "name",
  queuePrivacy: "UNLISTED",
  theme: "system",
  playMode: "front",
};

export function loadUi(): UiState {
  try {
    const raw = localStorage.getItem(UI_KEY);
    if (!raw) return DEFAULT_UI;
    const parsed = JSON.parse(raw) as Partial<UiState> & { dupOnly?: boolean; unavailableOnly?: boolean };
    // Before the combined Filter menu, the two filters were stored as separate flags.
    const filters: SongFilters = {
      ...NO_FILTERS,
      ...(parsed.filters ?? { duplicates: parsed.dupOnly ?? false, unavailable: parsed.unavailableOnly ?? false }),
    };
    return { ...DEFAULT_UI, ...parsed, filters };
  } catch {
    return DEFAULT_UI;
  }
}

export function saveUi(ui: UiState): void {
  try {
    localStorage.setItem(UI_KEY, JSON.stringify(ui));
  } catch {
    /* ignore */
  }
}

// Native window backgrounds, matching --app-bg in App.css, so a live resize never shows a
// mismatched strip at the trailing edge.
const BACKGROUNDS: Record<"light" | "dark", [number, number, number]> = {
  light: [250, 246, 246],
  dark: [27, 23, 24],
};

// Looked up on use rather than at import, so non-browser code (and tests) can import this module.
const darkMq = () => window.matchMedia("(prefers-color-scheme: dark)");

export function resolvedTheme(theme: Theme): "light" | "dark" {
  if (theme === "system") return darkMq().matches ? "dark" : "light";
  return theme;
}

// Apply the theme to the document (App.css keys off data-theme) and the native window background.
export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === "system") delete root.dataset.theme;
  else root.dataset.theme = theme;
  void setBackgroundColor(BACKGROUNDS[resolvedTheme(theme)]);
}

// Re-apply when the OS appearance changes (only matters while following the system).
export function watchSystemTheme(getTheme: () => Theme): () => void {
  const onChange = () => applyTheme(getTheme());
  const mq = darkMq();
  mq.addEventListener("change", onChange);
  return () => mq.removeEventListener("change", onChange);
}
