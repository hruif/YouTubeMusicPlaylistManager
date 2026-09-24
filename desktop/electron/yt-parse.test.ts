import { describe, expect, it } from "vitest";
import { extractTrackFromPlaylistItem, parseDuration, rawPlaylistSongCount } from "./yt";

function column(text: string) {
  return { musicResponsiveListItemFlexColumnRenderer: { text: { runs: [{ text }] } } };
}

describe("parseDuration", () => {
  it("parses m:ss and h:mm:ss", () => {
    expect(parseDuration("3:45")).toBe(225);
    expect(parseDuration("1:02:03")).toBe(3723);
  });
  it("rejects text that isn't a clock time", () => {
    expect(parseDuration("")).toBeUndefined();
    expect(parseDuration("Song")).toBeUndefined();
  });
});

describe("extractTrackFromPlaylistItem album and duration", () => {
  it("reads the album column and the fixed duration column of a raw playlist row", () => {
    const track = extractTrackFromPlaylistItem({
      musicResponsiveListItemRenderer: {
        playlistItemData: { videoId: "A" },
        flexColumns: [column("Title"), column("Artist"), column("Album")],
        fixedColumns: [{ musicResponsiveListItemFixedColumnRenderer: { text: { runs: [{ text: "4:05" }] } } }],
      },
    });
    expect(track).toMatchObject({ videoId: "A", title: "Title", artist: "Artist", album: "Album", duration: 245 });
  });

  it("reads youtubei.js parsed fields", () => {
    const track = extractTrackFromPlaylistItem({
      id: "B",
      title: "Parsed",
      artists: [{ name: "Someone" }],
      album: { name: "Record" },
      duration: { text: "2:00", seconds: 120 },
    });
    expect(track).toMatchObject({ album: "Record", duration: 120 });
  });

  it("omits album and duration when a row has neither", () => {
    const track = extractTrackFromPlaylistItem({
      musicResponsiveListItemRenderer: { playlistItemData: { videoId: "C" }, flexColumns: [column("Only title")] },
    });
    expect(track).not.toHaveProperty("album");
    expect(track).not.toHaveProperty("duration");
  });
});

describe("rawPlaylistSongCount", () => {
  it("reads the song count from the header subtitle", () => {
    const data = {
      header: {
        musicResponsiveHeaderRenderer: {
          title: { runs: [{ text: "50 songs I love" }] },
          secondSubtitle: { runs: [{ text: "1,234 songs" }, { text: " • " }, { text: "5+ hours" }] },
        },
      },
    };
    expect(rawPlaylistSongCount(data)).toBe(1234);
  });
  it("is undefined without a recognisable count", () => {
    expect(rawPlaylistSongCount({ header: { musicDetailHeaderRenderer: { title: { runs: [{ text: "Mix" }] } } } })).toBeUndefined();
    expect(rawPlaylistSongCount({})).toBeUndefined();
  });
});
