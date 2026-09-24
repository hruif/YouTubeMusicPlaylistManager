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

describe("restoreVideos", () => {
  it("re-adds the songs, then moves each re-added copy before its original successor, in order", async () => {
    // Before removal: A B C D. B and C were removed (successor of both: D). After re-adding: A D B C.
    execute.mockImplementation(async (endpoint: string) =>
      endpoint === "/browse" ? page([song("A", "a"), song("D", "d"), song("B", "b2"), song("C", "c2")]) : succeeded,
    );

    await expect(
      restoreVideos("VLPLcheck", [
        { videoId: "B", beforeVideoId: "D" },
        { videoId: "C", beforeVideoId: "D" },
      ]),
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

  it("only re-adds a song that was last (no successor, so no move)", async () => {
    await expect(restoreVideos("PLcheck", [{ videoId: "Z", beforeVideoId: null }])).resolves.toBe(true);
    expect(playlistAddVideos).toHaveBeenCalledWith("PLcheck", ["Z"]);
    expect(execute).not.toHaveBeenCalled();
  });

  it("moves the newly added copy, not an older copy of the same song", async () => {
    execute.mockImplementation(async (endpoint: string) =>
      endpoint === "/browse" ? page([song("A", "a1"), song("B", "b"), song("A", "a2")]) : succeeded,
    );
    await restoreVideos("PLcheck", [{ videoId: "A", beforeVideoId: "B" }]);
    expect(execute).toHaveBeenLastCalledWith(
      "browse/edit_playlist",
      expect.objectContaining({ actions: [{ action: "ACTION_MOVE_VIDEO_BEFORE", setVideoId: "a2", movedSetVideoIdSuccessor: "b" }] }),
    );
  });

  it("reports false when YouTube Music rejects the move (songs stay at the end)", async () => {
    execute.mockImplementation(async (endpoint: string) =>
      endpoint === "/browse" ? page([song("D", "d"), song("B", "b2")]) : { success: true, status_code: 200, data: { status: "STATUS_FAILED" } },
    );
    await expect(restoreVideos("PLcheck", [{ videoId: "B", beforeVideoId: "D" }])).resolves.toBe(false);
  });
});
