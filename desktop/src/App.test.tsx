// @vitest-environment jsdom
// End-to-end behaviour of the real App against a fake Electron backend: every invoke() goes to
// `handlers`, so each test decides what "YouTube Music" answers.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

type Handler = (args: Record<string, unknown>) => unknown;
let handlers: Record<string, Handler> = {};
const invoke = vi.fn(async (cmd: string, args: Record<string, unknown> = {}) => {
  const h = handlers[cmd];
  if (!h) return null;
  return h(args);
});
const calls = (cmd: string) => invoke.mock.calls.filter(([c]) => c === cmd).map(([, a]) => a);

(globalThis as unknown as { electronAPI: unknown }).electronAPI = {
  isElectron: true,
  invoke,
  showWindow: async () => {},
  setBackgroundColor: async () => {},
  allowCloseAndQuit: async () => {},
  deferClose: async () => {},
  openExternal: async () => {},
  onCloseRequested: () => () => {},
  installUpdate: async () => false,
  onUpdateProgress: () => () => {},
  onTracksProgress: () => () => {},
};

const { default: App } = await import("./App");

const track = (videoId: string, title: string) => ({ videoId, title, artist: "Artist" });
const gym = [track("a", "Alpha"), track("b", "Bravo"), track("c", "Charlie"), track("d", "Delta")];

function signedIn() {
  handlers = {
    read_cache: () =>
      JSON.stringify({
        version: 2,
        playlists: [{ id: "gym", title: "Gym" }],
        tracksByPlaylist: { gym },
        updatedAt: { gym: Date.now() },
        shown: ["gym"],
        editable: ["gym"],
      }),
    try_silent_sign_in: () => ({ cookie_names: ["SID"] }),
    yt_account_info: () => ({ name: "Tester" }),
    yt_get_playlist_tracks: () => ({ tracks: gym, editable: true, title: "Gym" }),
  };
  localStorage.setItem("ytm.ui", JSON.stringify({ selected: ["gym"], autoRefreshOnLaunch: false, checkUpdates: false }));
}

async function renderApp() {
  render(<App />);
  await screen.findByText("Alpha");
}

beforeEach(() => {
  invoke.mockClear();
  handlers = {};
});

describe("sign-in", () => {
  it("shows a timed-out sign-in inline, without the IPC prefix, and offers Try again", async () => {
    handlers = {
      read_cache: () => null,
      try_silent_sign_in: () => null,
      sign_in_youtube_music: () => {
        throw new Error("Error invoking remote method 'invoke': Error: Sign-in timed out. Please try again.");
      },
    };
    render(<App />);
    await userEvent.click(await screen.findByRole("button", { name: "Sign in with Google" }));
    expect(await screen.findByText("Sign-in timed out. Please try again.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("errors", () => {
  it("shows a failed refresh in the header with Retry, which runs it again and clears the error", async () => {
    signedIn();
    await renderApp();
    handlers.yt_get_playlist_tracks = () => {
      throw new Error("Network down");
    };
    await userEvent.keyboard("{Meta>}r{/Meta}");
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Couldn't load “Gym”.");

    handlers.yt_get_playlist_tracks = () => ({ tracks: gym, editable: true, title: "Gym" });
    await userEvent.click(within(alert).getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    expect(calls("yt_get_playlist_tracks")).toHaveLength(2);
  });

  it("clears the error as soon as another action starts", async () => {
    signedIn();
    await renderApp();
    handlers.yt_get_playlist_tracks = () => {
      throw new Error("Network down");
    };
    await userEvent.keyboard("{Meta>}r{/Meta}");
    await screen.findByRole("alert");
    handlers.yt_get_playlist_tracks = () => new Promise(() => {}); // still running
    await userEvent.keyboard("{Meta>}r{/Meta}");
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
  });
});

describe("undo", () => {
  async function removeBravo() {
    signedIn();
    handlers.yt_remove_videos = (a) => a.videoIds;
    handlers.yt_restore_videos = () => true;
    await renderApp();
    await userEvent.click(screen.getByText("Bravo"));
    await userEvent.keyboard("{Delete}");
    await userEvent.click(await screen.findByRole("button", { name: "Confirm" }));
    await screen.findByRole("button", { name: "Undo" });
    expect(calls("yt_remove_videos")).toEqual([{ playlistId: "gym", videoIds: ["b"] }]);
  }

  it("⌘Z puts a removed song back in front of the song that followed it", async () => {
    await removeBravo();
    await userEvent.keyboard("{Meta>}z{/Meta}");
    await waitFor(() =>
      expect(calls("yt_restore_videos")).toEqual([{ playlistId: "gym", items: [{ videoId: "b", beforeVideoId: "c" }] }]),
    );
  });

  it("⌘Z inside a text field is left to the field", async () => {
    await removeBravo();
    await userEvent.click(screen.getByRole("searchbox", { name: "Search songs" }));
    await userEvent.keyboard("{Meta>}z{/Meta}");
    expect(calls("yt_restore_videos")).toHaveLength(0);
    expect(screen.getByRole("button", { name: "Undo" })).toBeInTheDocument();
  });

  it("undoing an add removes exactly the added songs", async () => {
    signedIn();
    handlers.read_cache = () =>
      JSON.stringify({
        version: 2,
        playlists: [{ id: "gym", title: "Gym" }, { id: "run", title: "Run" }],
        tracksByPlaylist: { gym, run: [track("a", "Alpha")] },
        updatedAt: { gym: Date.now(), run: Date.now() },
        shown: ["gym", "run"],
        editable: ["gym", "run"],
      });
    handlers.yt_remove_videos = (a) => a.videoIds;
    localStorage.setItem("ytm.ui", JSON.stringify({ selected: ["gym"], autoRefreshOnLaunch: false, checkUpdates: false }));
    await renderApp();
    await userEvent.keyboard("{Meta>}a{/Meta}"); // all four selected; "Alpha" is already in Run
    await userEvent.click(screen.getByRole("button", { name: /Add to/ }));
    const picker = await screen.findByRole("dialog", { name: /Add 4 songs to/ });
    await userEvent.click(within(picker).getByRole("button", { name: /Run/ }));
    expect(calls("yt_add_videos")).toEqual([{ playlistId: "run", videoIds: ["b", "c", "d"] }]);
    await userEvent.click(await screen.findByRole("button", { name: "Undo" }));
    await waitFor(() => expect(calls("yt_remove_videos")).toEqual([{ playlistId: "run", videoIds: ["b", "c", "d"] }]));
  });
});

describe("dialogs and keyboard", () => {
  it("a dialog ignores clicks on the dimmed backdrop and closes with Esc", async () => {
    signedIn();
    await renderApp();
    await userEvent.keyboard("{Meta>},{/Meta}");
    const dialog = await screen.findByRole("dialog", { name: "Settings" });
    await userEvent.click(dialog.parentElement!); // the backdrop
    await userEvent.click(dialog.parentElement!);
    expect(screen.getByRole("dialog", { name: "Settings" })).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("↓ moves through songs, ⇧↓ extends, Esc clears the selection", async () => {
    signedIn();
    await renderApp();
    await userEvent.keyboard("{ArrowDown}");
    expect(screen.getByRole("option", { name: /Alpha/ })).toHaveAttribute("aria-selected", "true");
    await userEvent.keyboard("{Shift>}{ArrowDown}{ArrowDown}{/Shift}");
    expect(screen.getByRole("toolbar", { name: "Selected songs" })).toHaveTextContent("3 selected");
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("toolbar", { name: "Selected songs" })).not.toBeInTheDocument();
  });
});
