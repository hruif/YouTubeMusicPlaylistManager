// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { createRef } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SongPane } from "./SongPane";
import type { CombinedSong } from "../lib/ytmusic";

const songs: CombinedSong[] = [
  { videoId: "a", title: "Dreams", artist: "Fleetwood Mac", album: "Rumours", duration: 257, playlists: ["Gym"] },
  { videoId: "b", title: "Redbone", artist: "Childish Gambino", duration: 327, playlists: ["Gym", "Drive"] },
];

function pane(overrides: Partial<Parameters<typeof SongPane>[0]> = {}) {
  const props: Parameters<typeof SongPane>[0] = {
    searchRef: createRef<HTMLInputElement>(),
    query: "",
    onQueryChange: vi.fn(),
    filters: { duplicates: false, unavailable: false },
    onFiltersChange: vi.fn(),
    sortKey: "title",
    sortAsc: true,
    onSort: vi.fn(),
    songs,
    visibleSongs: songs,
    playlistNames: ["Gym", "Drive"],
    busy: false,
    activeIndex: null,
    selectedSongs: new Set(),
    customNames: {},
    replaceNames: false,
    onSongClick: vi.fn(),
    onSongContextMenu: vi.fn(),
    onRefresh: vi.fn(),
    onPlayAll: vi.fn(),
    onPlaySelected: vi.fn(),
    onAddSelected: vi.fn(),
    onRemoveSelected: vi.fn(),
    onNewPlaylist: vi.fn(),
    onClearSelection: vi.fn(),
    ...overrides,
  };
  render(<SongPane {...props} />);
  return props;
}

describe("SongPane", () => {
  it("with no playlist selected, shows the empty state and hides the column headers", () => {
    pane({ playlistNames: [], songs: [], visibleSongs: [] });
    expect(screen.getByText("Pick a playlist to see its songs")).toBeInTheDocument();
    expect(screen.queryByRole("toolbar")).not.toBeInTheDocument();
    expect(screen.getByRole("row", { hidden: true })).not.toBeVisible();
  });

  it("shows album and time columns", () => {
    pane();
    expect(screen.getByText("Rumours")).toBeInTheDocument();
    expect(screen.getByText("4:17")).toBeInTheDocument();
  });

  it("context bar: playlist summary with Refresh and Play all", async () => {
    const p = pane({ visibleSongs: songs.slice(0, 1) });
    expect(screen.getByText("Gym, Drive · 1 of 2 songs")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Refresh/ }));
    await userEvent.click(screen.getByRole("button", { name: /Play all/ }));
    expect(p.onRefresh).toHaveBeenCalled();
    expect(p.onPlayAll).toHaveBeenCalled();
  });

  it("context bar: switches to selection actions when songs are selected", async () => {
    const p = pane({ selectedSongs: new Set(["a", "b"]) });
    expect(screen.getByRole("toolbar", { name: "Selected songs" })).toHaveTextContent("2 selected");
    for (const [name, fn] of [
      [/Play/, p.onPlaySelected],
      [/Add to/, p.onAddSelected],
      [/Remove from/, p.onRemoveSelected],
      [/New playlist/, p.onNewPlaylist],
      ["Clear selection", p.onClearSelection],
    ] as const) {
      await userEvent.click(screen.getByRole("button", { name }));
      expect(fn).toHaveBeenCalled();
    }
  });

  it("sortable headers are buttons that report the sort direction", async () => {
    const p = pane({ sortKey: "duration", sortAsc: false });
    expect(screen.getByRole("columnheader", { name: /Time/ })).toHaveAttribute("aria-sort", "descending");
    expect(screen.getByRole("columnheader", { name: /Album/ })).toHaveAttribute("aria-sort", "none");
    await userEvent.click(screen.getByRole("button", { name: "Album" }));
    expect(p.onSort).toHaveBeenCalledWith("album");
  });

  it("offers to clear search and filters when nothing matches", async () => {
    const p = pane({ visibleSongs: [], query: "zzz" });
    await userEvent.click(screen.getByRole("button", { name: "Clear search and filters" }));
    expect(p.onQueryChange).toHaveBeenCalledWith("");
    expect(p.onFiltersChange).toHaveBeenCalledWith({ duplicates: false, unavailable: false });
  });
});
