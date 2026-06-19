import { describe, it, expect } from "vitest";
import { parseSpotifyPlaylistId } from "./spotify";

describe("parseSpotifyPlaylistId", () => {
  const ID = "37i9dQZF1DXcBWIGoYBM5M";
  it("parses a full open.spotify.com URL", () => {
    expect(parseSpotifyPlaylistId(`https://open.spotify.com/playlist/${ID}`)).toBe(ID);
  });
  it("parses a URL with query params", () => {
    expect(parseSpotifyPlaylistId(`https://open.spotify.com/playlist/${ID}?si=abc123`)).toBe(ID);
  });
  it("parses a spotify: URI", () => {
    expect(parseSpotifyPlaylistId(`spotify:playlist:${ID}`)).toBe(ID);
  });
  it("accepts a bare 22-char id", () => {
    expect(parseSpotifyPlaylistId(ID)).toBe(ID);
  });
  it("rejects non-playlist input", () => {
    expect(parseSpotifyPlaylistId("not a playlist")).toBeNull();
    expect(parseSpotifyPlaylistId("")).toBeNull();
    expect(parseSpotifyPlaylistId("https://open.spotify.com/track/" + ID)).toBeNull();
  });
});
