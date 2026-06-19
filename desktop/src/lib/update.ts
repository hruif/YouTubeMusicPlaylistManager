// Startup update check: is there a newer `desktop-v*` GitHub release than this app's version?
// Best-effort and non-fatal — any failure (offline, rate limit) just returns null.

import { getVersion } from "@tauri-apps/api/app";

const RELEASES_API = "https://api.github.com/repos/hruif/YouTubeMusicPlaylistManager/releases?per_page=30";
const TAG_PREFIX = "desktop-v";

function parseVersion(v: string): number[] {
  return v
    .split(/[.\-+]/)
    .map((p) => parseInt(p, 10))
    .filter((n) => !Number.isNaN(n));
}

// Is `a` a newer version than `b`?
function isNewer(a: number[], b: number[]): boolean {
  const len = Math.max(a.length, b.length);
  for (let i = 0; i < len; i += 1) {
    const x = a[i] ?? 0;
    const y = b[i] ?? 0;
    if (x !== y) return x > y;
  }
  return false;
}

export async function checkForUpdate(): Promise<{ version: string; url: string } | null> {
  try {
    const current = parseVersion(await getVersion());
    const res = await fetch(RELEASES_API, { headers: { Accept: "application/vnd.github+json" } });
    if (!res.ok) return null;
    const releases = (await res.json()) as Array<{ tag_name?: string; html_url?: string; draft?: boolean }>;

    let best: { version: string; url: string; nums: number[] } | null = null;
    for (const r of releases) {
      if (r.draft || !r.tag_name?.startsWith(TAG_PREFIX)) continue;
      const version = r.tag_name.slice(TAG_PREFIX.length);
      const nums = parseVersion(version);
      if (!nums.length) continue;
      if (!best || isNewer(nums, best.nums)) best = { version, url: r.html_url ?? "", nums };
    }
    if (best && isNewer(best.nums, current)) return { version: best.version, url: best.url };
    return null;
  } catch {
    return null;
  }
}
