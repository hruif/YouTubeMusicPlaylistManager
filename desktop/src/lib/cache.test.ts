import { describe, it, expect, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({ invoke: (...args: unknown[]) => invokeMock(...args) }));

import { loadCache, EMPTY_CACHE, CACHE_VERSION } from "./cache";

describe("loadCache", () => {
  beforeEach(() => invokeMock.mockReset());

  it("returns an empty cache when nothing is stored", async () => {
    invokeMock.mockResolvedValue(null);
    expect(await loadCache()).toEqual({ cache: EMPTY_CACHE, migrated: false });
  });

  it("fills every missing field from a partial cache (forward/back compat)", async () => {
    invokeMock.mockResolvedValue(JSON.stringify({ version: CACHE_VERSION, playlists: [{ id: "A", title: "P" }] }));
    const { cache: c } = await loadCache();
    expect(c.playlists).toEqual([{ id: "A", title: "P" }]);
    expect(c.tracksByPlaylist).toEqual({});
    expect(c.updatedAt).toEqual({});
    expect(c.shown).toEqual([]);
    expect(c.external).toEqual([]);
    expect(c.editable).toEqual([]);
    expect(c.deleted).toEqual([]);
    expect(c.unmatched).toEqual({});
    expect(c.customNames).toEqual({});
    expect(c.removedSongs).toEqual({});
    expect(c.version).toBe(CACHE_VERSION);
  });

  it("drops cached tracks when upgrading from an older / unversioned schema, keeping metadata", async () => {
    invokeMock.mockResolvedValue(
      JSON.stringify({
        // no `version` field → treated as schema 0 → migrate
        playlists: [{ id: "A", title: "P" }],
        tracksByPlaylist: { A: [{ videoId: "v", title: "t", artist: "" }] },
        updatedAt: { A: 123 },
        customNames: { v: "alias" },
        shown: ["A"],
      }),
    );
    const { cache, migrated } = await loadCache();
    expect(migrated).toBe(true);
    expect(cache.tracksByPlaylist).toEqual({}); // cleared → re-fetched with the current parser
    expect(cache.updatedAt).toEqual({});
    expect(cache.customNames).toEqual({ v: "alias" }); // schema-stable metadata preserved
    expect(cache.shown).toEqual(["A"]); // sidebar selection preserved
    expect(cache.version).toBe(CACHE_VERSION);
  });

  it("does not migrate a cache already at the current version", async () => {
    const tracks = { A: [{ videoId: "v", title: "t", artist: "x" }] };
    invokeMock.mockResolvedValue(
      JSON.stringify({ version: CACHE_VERSION, playlists: [{ id: "A", title: "P" }], tracksByPlaylist: tracks, updatedAt: { A: 123 } }),
    );
    const { cache, migrated } = await loadCache();
    expect(migrated).toBe(false);
    expect(cache.tracksByPlaylist).toEqual(tracks);
    expect(cache.updatedAt).toEqual({ A: 123 });
  });

  it("falls back to an empty cache on corrupt JSON (never throws)", async () => {
    invokeMock.mockResolvedValue("{ not valid json");
    expect(await loadCache()).toEqual({ cache: EMPTY_CACHE, migrated: false });
  });
});
