import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Innertube } from "youtubei.js";
import { clearSession, restoreVideos, setSession } from "./yt";

const execute = vi.fn();
const playlistAddVideos = vi.fn();

function song(videoId: string, setVideoId: string) {
  return {
    musicResponsiveListItemRenderer: {
      playlistItemData: { videoId, playlistSetVideoId: setVideoId },
      flexColumns: [{ musicResponsiveListItemFlexColumnRenderer: { text: { runs: [{ text: videoId }] } } }],
    },
  };
}

function page(songs: ReturnType<typeof song>[]) {
  return {
    success: true,
    status_code: 200,
    data: {
      header: { musicEditablePlaylistDetailHeaderRenderer: { title: { simpleText: "check" } } },
      contents: { musicPlaylistShelfRenderer: { contents: songs } },
    },
  };
}

const succeeded = { success: true, status_code: 200, data: { status: "STATUS_SUCCEEDED" } };

beforeEach(async () => {
  execute.mockReset();
  playlistAddVideos.mockReset().mockResolvedValue(undefined);
  vi.spyOn(Innertube, "create").mockResolvedValue({
    actions: { execute },
    playlist: { addVideos: playlistAddVideos },
  } as unknown as Innertube);
  await setSession("");
});

afterEach(() => {
  clearSession();
  vi.restoreAllMocks();
});

// Answers /browse with each page in turn (repeating the last), and edits with `edit`.
function browseSequence(pages: ReturnType<typeof song>[][], edit: unknown = succeeded) {
  let n = 0;
  execute.mockImplementation(async (endpoint: string) => {
    if (endpoint !== "/browse") return edit;
    return page(pages[Math.min(n++, pages.length - 1)]);
  });
}
const moveCalls = () => execute.mock.calls.filter(([e]) => e === "browse/edit_playlist").map(([, a]) => (a as { actions: unknown }).actions);

describe("restoreVideos", () => {
  it("re-adds the songs, then moves each new entry before its original successor, in order", async () => {
    // Before removal: A B C D. B and C were removed (successor of both: D). After re-adding: A D B C.
    browseSequence([
      [song("A", "a"), song("D", "d")],
      [song("A", "a"), song("D", "d"), song("B", "b2"), song("C", "c2")],
    ]);
    await expect(
      restoreVideos("VLPLcheck", [
        { videoId: "B", beforeVideoId: "D" },
        { videoId: "C", beforeVideoId: "D" },
      ], 0),
    ).resolves.toBe(true);

    expect(playlistAddVideos).toHaveBeenCalledWith("PLcheck", ["B", "C"]);
    expect(execute).toHaveBeenLastCalledWith(
      "browse/edit_playlist",
      expect.objectContaining({
        playlistId: "PLcheck",
        actions: [
          { action: "ACTION_MOVE_VIDEO_BEFORE", setVideoId: "b2", movedSetVideoIdSuccessor: "d" },
          { action: "ACTION_MOVE_VIDEO_BEFORE", setVideoId: "c2", movedSetVideoIdSuccessor: "d" },
        ],
      }),
    );
  });

  it("waits for YouTube Music to list the new entries before moving them", async () => {
    browseSequence([
      [song("A", "a"), song("D", "d")], // before
      [song("A", "a"), song("D", "d")], // right after the add: not listed yet
      [song("A", "a"), song("D", "d"), song("B", "b2")],
    ]);
    await expect(restoreVideos("PLcheck", [{ videoId: "B", beforeVideoId: "D" }], 0)).resolves.toBe(true);
    expect(moveCalls()).toEqual([[{ action: "ACTION_MOVE_VIDEO_BEFORE", setVideoId: "b2", movedSetVideoIdSuccessor: "d" }]]);
  });

  it("gives up (songs stay at the end) if the new entries never show up", async () => {
    browseSequence([[song("A", "a"), song("D", "d")]]);
    await expect(restoreVideos("PLcheck", [{ videoId: "B", beforeVideoId: "D" }], 0)).resolves.toBe(false);
    expect(moveCalls()).toEqual([]);
  });

  it("only re-adds a song that was last (no successor, so no reads or moves)", async () => {
    await expect(restoreVideos("PLcheck", [{ videoId: "Z", beforeVideoId: null }], 0)).resolves.toBe(true);
    expect(playlistAddVideos).toHaveBeenCalledWith("PLcheck", ["Z"]);
    expect(execute).not.toHaveBeenCalled();
  });

  it("moves the newly added copy, not a copy that was already there", async () => {
    browseSequence([
      [song("A", "a1"), song("B", "b")],
      [song("A", "a1"), song("B", "b"), song("A", "a3")],
    ]);
    await restoreVideos("PLcheck", [{ videoId: "A", beforeVideoId: "B" }], 0);
    expect(moveCalls()).toEqual([[{ action: "ACTION_MOVE_VIDEO_BEFORE", setVideoId: "a3", movedSetVideoIdSuccessor: "b" }]]);
  });

  it("reports false when YouTube Music rejects the move (songs stay at the end)", async () => {
    browseSequence(
      [[song("D", "d")], [song("D", "d"), song("B", "b2")]],
      { success: true, status_code: 200, data: { status: "STATUS_FAILED" } },
    );
    await expect(restoreVideos("PLcheck", [{ videoId: "B", beforeVideoId: "D" }], 0)).resolves.toBe(false);
  });
});
