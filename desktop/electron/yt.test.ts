import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Innertube } from "youtubei.js";
import { clearSession, getPlaylistTracks, removeRepeatedVideos, setSession } from "./yt";

const execute = vi.fn();

function song(videoId: string, setVideoId?: string, watchVideoId = videoId) {
  return {
    musicResponsiveListItemRenderer: {
      playlistItemData: { videoId, playlistSetVideoId: setVideoId },
      flexColumns: [{
        musicResponsiveListItemFlexColumnRenderer: {
          text: { runs: [{ text: videoId, navigationEndpoint: { watchEndpoint: { videoId: watchVideoId } } }] },
        },
      }],
    },
  };
}

function page(songs: ReturnType<typeof song>[], token?: string) {
  return {
    success: true,
    status_code: 200,
    data: {
      header: { musicEditablePlaylistDetailHeaderRenderer: { title: { simpleText: "check" } } },
      contents: {
        musicPlaylistShelfRenderer: {
          contents: [
            ...songs,
            ...(token ? [{ continuationItemRenderer: { continuationEndpoint: { continuationCommand: { token } } } }] : []),
          ],
        },
      },
    },
  };
}

const succeeded = { success: true, status_code: 200, data: { status: "STATUS_SUCCEEDED" } };

beforeEach(async () => {
  execute.mockReset();
  vi.spyOn(Innertube, "create").mockResolvedValue({ actions: { execute } } as unknown as Innertube);
  await setSession("");
});

afterEach(() => {
  clearSession();
  vi.restoreAllMocks();
});

describe("removeRepeatedVideos", () => {
  it("removes every extra copy across song pages and keeps the first copies in order", async () => {
    let songs = [song("A", "a1"), song("B", "b1"), song("A", "a2"), song("A", "a3"), song("B", "b2"), song("C", "c1")];
    execute.mockImplementation(async (endpoint: string, args: Record<string, unknown>) => {
      if (endpoint === "/browse") {
        return args.continuation ? page(songs.slice(2)) : page(songs.slice(0, 2), "more-songs");
      }
      expect(endpoint).toBe("browse/edit_playlist");
      const actions = args.actions as { action: string; setVideoId: string }[];
      expect(actions).toEqual([
        { action: "ACTION_REMOVE_VIDEO", setVideoId: "a2" },
        { action: "ACTION_REMOVE_VIDEO", setVideoId: "a3" },
        { action: "ACTION_REMOVE_VIDEO", setVideoId: "b2" },
      ]);
      const removed = new Set(actions.map((action) => action.setVideoId));
      songs = songs.filter((row) => !removed.has(row.musicResponsiveListItemRenderer.playlistItemData.playlistSetVideoId!));
      return succeeded;
    });

    expect(await removeRepeatedVideos("VLPLcheck", ["A", "B"])).toBe(3);
    expect(execute).toHaveBeenNthCalledWith(2, "/browse", {
      continuation: "more-songs", client: "YTMUSIC", parse: false,
    });
    expect(execute).toHaveBeenLastCalledWith("browse/edit_playlist", expect.objectContaining({
      playlistId: "PLcheck", client: "YTMUSIC", parse: false,
    }));
    // Read the simulated account again: the regression was an unchanged account behind a deduped UI.
    const result = await getPlaylistTracks("PLcheck");
    expect(result.tracks.map((track) => track.videoId)).toEqual(["A", "B", "C"]);
    expect(result).toMatchObject({ editable: true, title: "check" });
    expect(songs.map((row) => row.musicResponsiveListItemRenderer.playlistItemData.playlistSetVideoId)).toEqual(["a1", "b1", "c1"]);
  });

  it("uses the slot's song ID and leaves unconfirmed repeats and related suggestions alone", async () => {
    const first = page([song("A", "a1", "watch-A"), song("B", "b1")], "more-songs");
    const withRelated = {
      ...first,
      data: {
        ...first.data,
        related: { contents: [song("A", "related-a"), song("A", "related-a2")] },
        continuations: [{ nextContinuationData: { continuation: "related-songs" } }],
      },
    };
    execute.mockResolvedValueOnce(withRelated)
      .mockResolvedValueOnce(page([song("A", "a2", "watch-A"), song("B", "b2")]))
      .mockResolvedValueOnce(succeeded);

    expect(await removeRepeatedVideos("PLcheck", ["A"])).toBe(1);
    expect(execute).toHaveBeenLastCalledWith("browse/edit_playlist", expect.objectContaining({
      actions: [{ action: "ACTION_REMOVE_VIDEO", setVideoId: "a2" }],
    }));
  });

  it("ignores duplicate response rows for the same playlist entry", async () => {
    execute.mockResolvedValueOnce(page([song("A", "a1"), song("A", "a1"), song("A", "a2"), song("A", "a2")]))
      .mockResolvedValueOnce(succeeded);
    expect(await removeRepeatedVideos("PLcheck", ["A"])).toBe(1);
    expect(execute).toHaveBeenLastCalledWith("browse/edit_playlist", expect.objectContaining({
      actions: [{ action: "ACTION_REMOVE_VIDEO", setVideoId: "a2" }],
    }));
  });

  it("does not edit when the confirmed songs no longer repeat on YouTube", async () => {
    execute.mockResolvedValueOnce(page([song("A", "a1"), song("B", "b1")]));
    expect(await removeRepeatedVideos("PLcheck", ["A", "missing"])).toBe(0);
    expect(execute).toHaveBeenCalledTimes(1);
  });

  it("does not fetch or edit an empty selection", async () => {
    expect(await removeRepeatedVideos("PLcheck", [])).toBe(0);
    expect(execute).not.toHaveBeenCalled();
  });

  it("refuses the whole edit if an extra copy lacks its playlist entry ID", async () => {
    execute.mockResolvedValueOnce(page([song("A", "a1"), song("A", "a2"), song("A")]));
    await expect(removeRepeatedVideos("PLcheck", ["A"])).rejects.toThrow("details needed");
    expect(execute).toHaveBeenCalledTimes(1);
  });

  it("does not edit a partial playlist when a continuation fails", async () => {
    execute.mockResolvedValueOnce(page([song("A", "a1"), song("A", "a2")], "next"))
      .mockRejectedValueOnce(new Error("Offline"));
    await expect(removeRepeatedVideos("PLcheck", ["A"])).rejects.toThrow("Offline");
    expect(execute).toHaveBeenCalledTimes(2);
  });

  it("rejects a repeating continuation instead of treating a partial playlist as complete", async () => {
    execute.mockResolvedValueOnce(page([song("A", "a1")], "next"))
      .mockResolvedValueOnce(page([song("A", "a2")], "next"));
    await expect(removeRepeatedVideos("PLcheck", ["A"])).rejects.toThrow("complete playlist");
    expect(execute).toHaveBeenCalledTimes(2);
  });

  it.each([
    { success: false, status_code: 403, data: {} },
    { success: true, status_code: 200, data: { status: "STATUS_FAILED" } },
    { success: true, status_code: 200, data: {} },
  ])("does not report a rejected or unacknowledged edit as success: %j", async (response) => {
    execute.mockResolvedValueOnce(page([song("A", "a1"), song("A", "a2")]))
      .mockResolvedValueOnce(response);
    await expect(removeRepeatedVideos("PLcheck", ["A"])).rejects.toThrow("rejected");
  });
});
