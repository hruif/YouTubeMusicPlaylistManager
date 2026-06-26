// Update check: is there a newer `desktop-v*` GitHub release than this app's version?
// Startup uses the quiet wrapper; Settings uses the strict version so manual checks can report errors.

import pkg from "../../package.json";

const RELEASES_API = "https://api.github.com/repos/hruif/YouTubeMusicPlaylistManager/releases?per_page=30";
const TAG_PREFIX = "desktop-v";

export type UpdateInfo = { version: string; url: string };
type ReleaseAsset = { name?: string; browser_download_url?: string };
type Release = {
  tag_name?: string;
  html_url?: string;
  draft?: boolean;
  prerelease?: boolean;
  assets?: ReleaseAsset[];
};

export function getCurrentVersion(): string {
  return pkg.version;
}

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

function downloadUrlForRelease(release: Release): string {
  const assets = release.assets ?? [];
  const dmg =
    assets.find((a) => /universal\.dmg$/i.test(a.name ?? "")) ??
    assets.find((a) => /\.dmg$/i.test(a.name ?? ""));
  return dmg?.browser_download_url ?? release.html_url ?? "";
}

export function findLatestUpdate(releases: Release[], currentVersion: string): UpdateInfo | null {
  const current = parseVersion(currentVersion);
  let best: { version: string; url: string; nums: number[] } | null = null;
  for (const r of releases) {
    if (r.draft || r.prerelease || !r.tag_name?.startsWith(TAG_PREFIX)) continue;
    const version = r.tag_name.slice(TAG_PREFIX.length);
    const nums = parseVersion(version);
    if (!nums.length) continue;
    if (!best || isNewer(nums, best.nums)) best = { version, url: downloadUrlForRelease(r), nums };
  }
  if (best && isNewer(best.nums, current)) return { version: best.version, url: best.url };
  return null;
}

export async function checkForUpdateStrict(): Promise<UpdateInfo | null> {
  const res = await fetch(RELEASES_API, { headers: { Accept: "application/vnd.github+json" } });
  if (!res.ok) throw new Error(`GitHub returned HTTP ${res.status}`);
  return findLatestUpdate((await res.json()) as Release[], getCurrentVersion());
}

export async function checkForUpdate(): Promise<UpdateInfo | null> {
  try {
    return await checkForUpdateStrict();
  } catch {
    return null;
  }
}
