import { beforeEach, describe, expect, it, vi } from "vitest";
import { fetchSpotifyPlaylist, parseSpotifyPlaylistId, SpotifyError } from "./spotify";
import { invoke } from "./native";

vi.mock("./native", () => ({ invoke: vi.fn() }));

const invokeMock = vi.mocked(invoke);
const ID = "37i9dQZF1DXcBWIGoYBM5M";

function proxyResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  const value = typeof body === "string" ? body : JSON.stringify(body);
  return { status, headers, body_base64: Buffer.from(value).toString("base64") };
}

describe("parseSpotifyPlaylistId", () => {
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

describe("fetchSpotifyPlaylist", () => {
  beforeEach(() => {
    invokeMock.mockReset();
  });

  it("rejects invalid input without contacting the proxy", async () => {
    await expect(fetchSpotifyPlaylist("not a playlist")).rejects.toThrow(SpotifyError);
    expect(invokeMock).not.toHaveBeenCalled();
  });

  it("bootstraps a session, paginates tracks, and reports progress", async () => {
    const config = Buffer.from(JSON.stringify({ clientVersion: "1.2.3" })).toString("base64");
    const home = `<script id="appServerConfig" type="text/plain">${config}</script>` +
      '<script src="https://open.spotifycdn.com/cdn/build/web-player/web-player.abc.js"></script>';
    const requests: Array<{ url: string; headers: Record<string, string> }> = [];
    invokeMock.mockImplementation((async (command, args) => {
      expect(command).toBe("proxy_http_request");
      const input = (args?.input ?? {}) as { url: string; headers: Record<string, string> };
      requests.push(input);
      if (input.url.includes("secretDict.json")) return proxyResponse(500, "unavailable");
      if (input.url === "https://open.spotify.com") {
        return proxyResponse(200, home, { "set-cookie": "sp_t=device-id; Path=/" });
      }
      if (input.url.includes("web-player.abc.js")) {
        return proxyResponse(200, 'x="fetchPlaylist","query","abc123"');
      }
      if (input.url.includes("/api/token")) {
        return proxyResponse(200, { accessToken: "access-token", clientId: "client-id" });
      }
      if (input.url.includes("clienttoken.spotify.com")) {
        return proxyResponse(200, { granted_token: { token: "client-token" } });
      }
      if (input.url.includes("api-partner.spotify.com")) {
        const decoded = decodeURIComponent(input.url);
        const secondPage = decoded.includes('"offset":100');
        return proxyResponse(200, {
          data: {
            playlistV2: {
              name: "Road Trip",
              content: {
                totalCount: 101,
                items: [{
                  itemV2: {
                    data: {
                      name: secondPage ? "Second Song" : "First Song",
                      artists: { items: [{ profile: { name: secondPage ? "Artist Two" : "Artist One" } }] },
                    },
                  },
                }],
              },
            },
          },
        });
      }
      throw new Error(`Unexpected proxy request: ${input.url}`);
    }) as typeof invoke);
    const progress = vi.fn();

    await expect(fetchSpotifyPlaylist(ID, progress)).resolves.toEqual({
      title: "Road Trip",
      tracks: [
        { title: "First Song", artist: "Artist One" },
        { title: "Second Song", artist: "Artist Two" },
      ],
    });
    expect(progress.mock.calls).toEqual([[1, 101], [2, 101]]);
    const playlistRequests = requests.filter((request) => request.url.includes("api-partner.spotify.com"));
    expect(playlistRequests).toHaveLength(2);
    expect(playlistRequests[0].headers).toMatchObject({
      Authorization: "Bearer access-token",
      "Client-Token": "client-token",
      "Spotify-App-Version": "1.2.3",
    });
  });

  it("surfaces authorization failures from a cached session", async () => {
    invokeMock.mockResolvedValue(proxyResponse(401, "denied"));

    await expect(fetchSpotifyPlaylist(ID)).rejects.toThrow("Spotify rejected the request (401)");
  });
});
