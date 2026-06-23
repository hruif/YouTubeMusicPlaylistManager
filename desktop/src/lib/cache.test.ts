import { describe, it, expect, vi, beforeEach } from "vitest";

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({ invoke: (...args: unknown[]) => invokeMock(...args) }));

import { loadCache, EMPTY_CACHE } from "./cache";

describe("loadCache", () => {
  beforeEach(() => invokeMock.mockReset());

  it("returns an empty cache when nothing is stored", async () => {
    invokeMock.mockResolvedValue(null);
    expect(await loadCache()).toEqual(EMPTY_CACHE);
  });

  it("fills every missing field from a partial cache (forward/back compat)", async () => {
    invokeMock.mockResolvedValue(JSON.stringify({ playlists: [{ id: "A", title: "P" }] }));
    const c = await loadCache();
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
  });

  it("falls back to an empty cache on corrupt JSON (never throws)", async () => {
    invokeMock.mockResolvedValue("{ not valid json");
    expect(await loadCache()).toEqual(EMPTY_CACHE);
  });
});
