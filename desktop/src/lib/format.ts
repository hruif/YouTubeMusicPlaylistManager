export const ROW_H = 30;
export const STALE_MS = 7 * 24 * 3600 * 1000;

// Best-effort: YouTube replaces a gone video's title with a placeholder. Catches deleted/private
// videos; misses region-locked ones that keep their title (youtubei.js exposes no playability flag).
export function isUnavailableTitle(title: string): boolean {
  return /\[(deleted|private|unavailable|restricted)\b/i.test(title);
}

export function relativeAge(ms?: number): string {
  if (!ms) return "never";
  const mins = Math.floor((Date.now() - ms) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}
