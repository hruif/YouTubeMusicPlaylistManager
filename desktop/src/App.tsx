import { useEffect, useMemo, useRef, useState } from "react";
import { openUrl } from "@tauri-apps/plugin-opener";
import {
  signIn,
  trySilentSignIn,
  signOut,
  getLibraryPlaylists,
  fetchTracksForPlaylists,
  combineFromCache,
  addVideos,
  removeVideos,
  createPlaylist,
  deletePlaylist,
  searchYouTubeMusicSongs,
  bestYoutubeMatch,
  type Playlist,
  type CombinedSong,
} from "./lib/ytmusic";
import { loadCache, saveCache, EMPTY_CACHE, type LibraryCache } from "./lib/cache";
import { fetchSpotifyPlaylist, type SpotifyTrack } from "./lib/spotify";
import "./App.css";

// Phase 1: read-only parity, cache-driven, polished. Virtualized song list, staleness, persisted
// selection/sort, search (Cmd+F), hide playlists, details with external links.

type SortKey = "title" | "artist" | "count";
const ROW_H = 30;
const STALE_MS = 7 * 24 * 3600 * 1000;

// --- small persisted UI state (selection/sort/filter) in localStorage (tiny, frequent writes) ---
type UiState = { selected: string[]; sortKey: SortKey; sortAsc: boolean; dupOnly: boolean };
const UI_KEY = "ytm.ui";
function loadUi(): UiState {
  const base: UiState = { selected: [], sortKey: "title", sortAsc: true, dupOnly: false };
  try {
    const raw = localStorage.getItem(UI_KEY);
    return raw ? { ...base, ...(JSON.parse(raw) as Partial<UiState>) } : base;
  } catch {
    return base;
  }
}

function relativeAge(ms?: number): string {
  if (!ms) return "never";
  const mins = Math.floor((Date.now() - ms) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// Virtualization: render only the rows in view. Uses a callback ref so the scroll/resize
// listeners attach when the container actually mounts (it's gated behind sign-in, so a plain
// useEffect([]) at mount would find no element and never wire up — leaving only the first page).
function useVirtual(count: number) {
  const [el, setEl] = useState<HTMLDivElement | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const [height, setHeight] = useState(0);
  useEffect(() => {
    if (!el) return;
    const onScroll = () => setScrollTop(el.scrollTop);
    el.addEventListener("scroll", onScroll, { passive: true });
    const ro = new ResizeObserver(() => setHeight(el.clientHeight));
    ro.observe(el);
    setHeight(el.clientHeight);
    setScrollTop(el.scrollTop);
    return () => {
      el.removeEventListener("scroll", onScroll);
      ro.disconnect();
    };
  }, [el]);
  const overscan = 10;
  const h = height || 600;
  const start = Math.max(0, Math.floor(scrollTop / ROW_H) - overscan);
  const end = Math.min(count, Math.ceil((scrollTop + h) / ROW_H) + overscan);
  return { ref: setEl, start, end };
}

function App() {
  const ui0 = useRef(loadUi()).current;
  const [status, setStatus] = useState("Starting…");
  const [busy, setBusy] = useState(false);
  const [signedIn, setSignedIn] = useState(false);
  const [cache, setCache] = useState<LibraryCache>({ ...EMPTY_CACHE });
  const [selected, setSelected] = useState<Set<string>>(() => new Set(ui0.selected));
  const [sortKey, setSortKey] = useState<SortKey>(ui0.sortKey);
  const [sortAsc, setSortAsc] = useState(ui0.sortAsc);
  const [dupOnly, setDupOnly] = useState(ui0.dupOnly);
  const [query, setQuery] = useState("");
  const [showManage, setShowManage] = useState(false);
  const [manageQuery, setManageQuery] = useState("");
  const [detail, setDetail] = useState<CombinedSong | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const [menu, setMenu] = useState<{ x: number; y: number; items: { label: string; onClick: () => void }[] } | null>(null);
  const [selectedSongs, setSelectedSongs] = useState<Set<string>>(new Set());
  const lastSongIndex = useRef<number | null>(null);
  const lastClick = useRef<{ id: string; t: number } | null>(null);
  const [addPicker, setAddPicker] = useState(false);
  const [addQuery, setAddQuery] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [removePicker, setRemovePicker] = useState(false);
  const [confirm, setConfirm] = useState<{ title: string; body: string; onConfirm: () => void } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Playlist | null>(null);
  const [deleteText, setDeleteText] = useState("");
  const [showDeleted, setShowDeleted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [spotifyOpen, setSpotifyOpen] = useState(false);
  const [spotifyUrl, setSpotifyUrl] = useState("");
  const [spotifyResult, setSpotifyResult] = useState<{ title: string; tracks: SpotifyTrack[] } | null>(null);
  const [spotifyLoading, setSpotifyLoading] = useState(false);
  const [spotifyProgress, setSpotifyProgress] = useState("");
  const [spotifyName, setSpotifyName] = useState("");
  const [transferResult, setTransferResult] = useState<{ name: string; matched: number; unmatched: SpotifyTrack[] } | null>(null);
  const [showUnmatched, setShowUnmatched] = useState<string | null>(null);

  // Report a failure: status line + a popup so it's obvious something went wrong.
  function fail(message: string) {
    setStatus(message);
    setError(message);
  }
  const errText = (err: unknown) => (err instanceof Error ? err.message : String(err));

  async function readSpotify() {
    setSpotifyResult(null);
    setSpotifyLoading(true);
    setSpotifyProgress("Connecting to Spotify…");
    try {
      const r = await fetchSpotifyPlaylist(spotifyUrl, (loaded, total) =>
        setSpotifyProgress(`Loaded ${loaded}/${total || "?"}…`),
      );
      setSpotifyResult(r);
      setSpotifyName(r.title);
      setSpotifyProgress(`${r.tracks.length} tracks`);
    } catch (err) {
      setSpotifyProgress("");
      fail(`Spotify import failed: ${errText(err)}`);
    } finally {
      setSpotifyLoading(false);
    }
  }

  const ytSearchUrl = (q: string) => `https://music.youtube.com/search?q=${encodeURIComponent(q)}`;

  // Transfer a read Spotify playlist to a new YouTube Music playlist: match each track conservatively,
  // create from confident matches, persist the unmatched ones for manual follow-up.
  async function transferSpotify() {
    if (!spotifyResult) return;
    const name = spotifyName.trim() || spotifyResult.title;
    const tracks = spotifyResult.tracks;
    setSpotifyOpen(false);
    setBusy(true);
    setStatus(`Matching 0/${tracks.length} on YouTube Music…`);
    try {
      const matches: ({ videoId: string; title: string; artist: string } | null)[] = new Array(tracks.length).fill(null);
      let cursor = 0;
      let done = 0;
      const worker = async (): Promise<void> => {
        while (cursor < tracks.length) {
          const i = cursor++;
          const t = tracks[i];
          try {
            const candidates = await searchYouTubeMusicSongs(`${t.title} ${t.artist}`.trim());
            const m = bestYoutubeMatch(candidates, t.title, t.artist);
            if (m) matches[i] = { videoId: m.videoId, title: t.title, artist: t.artist };
          } catch {
            /* leave unmatched */
          }
          done += 1;
          setStatus(`Matching ${done}/${tracks.length} on YouTube Music…`);
        }
      };
      await Promise.all(Array.from({ length: Math.min(4, tracks.length) }, () => worker()));

      const matchedIds: string[] = [];
      const matchedTracks: { videoId: string; title: string; artist: string }[] = [];
      const unmatched: SpotifyTrack[] = [];
      for (let i = 0; i < tracks.length; i += 1) {
        const m = matches[i];
        if (m) {
          matchedIds.push(m.videoId);
          matchedTracks.push(m);
        } else {
          unmatched.push(tracks[i]);
        }
      }
      if (matchedIds.length === 0) {
        fail("No songs could be confidently matched on YouTube Music.");
        return;
      }
      setStatus(`Creating “${name}” with ${matchedIds.length} songs…`);
      const newId = await createPlaylist(name, matchedIds);
      if (newId) {
        persist({
          ...cache,
          playlists: [{ id: newId, title: name }, ...cache.playlists],
          tracksByPlaylist: { ...cache.tracksByPlaylist, [newId]: matchedTracks },
          updatedAt: { ...cache.updatedAt, [newId]: Date.now() },
          editable: [...new Set([...cache.editable, newId])],
          unmatched: unmatched.length ? { ...cache.unmatched, [newId]: unmatched } : cache.unmatched,
        });
      } else {
        await refreshPlaylists(cache);
      }
      setTransferResult({ name, matched: matchedIds.length, unmatched });
      setStatus(`Transferred “${name}”: ${matchedIds.length} added, ${unmatched.length} unmatched`);
    } catch (err) {
      fail(`Transfer failed: ${errText(err)}`);
    } finally {
      setBusy(false);
    }
  }

  function persist(next: LibraryCache) {
    setCache(next);
    void saveCache(next);
  }

  const openSong = (videoId: string) => void openUrl(`https://music.youtube.com/watch?v=${videoId}`);
  const openPlaylist = (id: string) => void openUrl(`https://music.youtube.com/playlist?list=${id}`);
  function openMenu(e: React.MouseEvent, items: { label: string; onClick: () => void }[]) {
    e.preventDefault();
    e.stopPropagation();
    setMenu({ x: Math.min(e.clientX, window.innerWidth - 190), y: e.clientY, items });
  }

  // Suppress the WebView's default right-click menu (reload/inspect) so we can use our own;
  // any left-click dismisses an open context menu.
  useEffect(() => {
    const onCtx = (e: MouseEvent) => e.preventDefault();
    const onClick = () => setMenu(null);
    window.addEventListener("contextmenu", onCtx);
    window.addEventListener("click", onClick);
    return () => {
      window.removeEventListener("contextmenu", onCtx);
      window.removeEventListener("click", onClick);
    };
  }, []);

  // Persist UI state on change.
  useEffect(() => {
    try {
      localStorage.setItem(UI_KEY, JSON.stringify({ selected: [...selected], sortKey, sortAsc, dupOnly }));
    } catch {
      /* ignore */
    }
  }, [selected, sortKey, sortAsc, dupOnly]);

  // Cmd/Ctrl+F focuses the song search.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "f") {
        e.preventDefault();
        searchRef.current?.focus();
        searchRef.current?.select();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  async function refreshPlaylists(current: LibraryCache) {
    setBusy(true);
    setStatus("Refreshing playlist list…");
    try {
      const playlists = await getLibraryPlaylists();
      persist({ ...current, playlists });
      setStatus(`${playlists.length} playlists`);
    } catch (err) {
      fail(`Failed to refresh playlists: ${errText(err)}`);
    } finally {
      setBusy(false);
    }
  }

  const started = useRef(false);
  useEffect(() => {
    if (started.current) return; // guard React StrictMode's double-invoke in dev
    started.current = true;
    (async () => {
      const cached = await loadCache();
      setCache(cached);
      setStatus("Signing in…");
      try {
        const names = await trySilentSignIn();
        if (names) {
          setSignedIn(true);
          setStatus(`${cached.playlists.length} playlists (cached)`);
          if (cached.playlists.length === 0) await refreshPlaylists(cached);
        } else {
          setStatus("Not signed in");
        }
      } catch (err) {
        setStatus(`Sign-in failed: ${err instanceof Error ? err.message : String(err)}`);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const hidden = useMemo(() => new Set(cache.hidden), [cache.hidden]);
  const visiblePlaylists = useMemo(
    () => cache.playlists.filter((p) => !hidden.has(p.id)),
    [cache.playlists, hidden],
  );
  const titleToId = useMemo(() => {
    const m = new Map<string, string>();
    for (const p of cache.playlists) m.set(p.title, p.id);
    return m;
  }, [cache.playlists]);

  function isStale(id: string): boolean {
    const t = cache.updatedAt[id];
    return !cache.tracksByPlaylist[id] || !t || Date.now() - t > STALE_MS;
  }

  function toggleSelected(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function setPlaylistHidden(id: string, hide: boolean) {
    const next = new Set(cache.hidden);
    if (hide) next.add(id);
    else next.delete(id);
    persist({ ...cache, hidden: [...next] });
    if (hide)
      setSelected((prev) => {
        const s = new Set(prev);
        s.delete(id);
        return s;
      });
  }

  const selectedPlaylists = useMemo(
    () => cache.playlists.filter((p) => selected.has(p.id)),
    [cache.playlists, selected],
  );
  const stalePlaylists = useMemo(
    () => visiblePlaylists.filter((p) => isStale(p.id)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [visiblePlaylists, cache.updatedAt, cache.tracksByPlaylist],
  );

  async function runUpdate(list: Playlist[]) {
    if (list.length === 0) return;
    setBusy(true);
    setStatus(`Updating 0/${list.length}…`);
    try {
      const { tracksByPlaylist, editableIds, notFoundIds, failures } = await fetchTracksForPlaylists(
        list,
        4,
        (done, total) => setStatus(`Updating ${done}/${total}…`),
      );
      const now = Date.now();
      const updatedAt = { ...cache.updatedAt };
      for (const id of Object.keys(tracksByPlaylist)) updatedAt[id] = now;
      let next: LibraryCache = {
        ...cache,
        tracksByPlaylist: { ...cache.tracksByPlaylist, ...tracksByPlaylist },
        updatedAt,
        editable: [...new Set([...cache.editable, ...editableIds])],
      };

      // 404-prune: drop playlists YouTube reports as gone (deleted elsewhere), archiving their
      // cached songs so nothing is silently lost.
      if (notFoundIds.length) {
        const gone = new Set(notFoundIds);
        const tracks = { ...next.tracksByPlaylist };
        const upd = { ...next.updatedAt };
        const archived: LibraryCache["deleted"] = [];
        for (const id of notFoundIds) {
          const pl = cache.playlists.find((p) => p.id === id);
          const t = cache.tracksByPlaylist[id] ?? [];
          if (pl && t.length) archived.push({ id, title: pl.title, tracks: t, deletedAt: now });
          delete tracks[id];
          delete upd[id];
        }
        next = {
          ...next,
          playlists: next.playlists.filter((p) => !gone.has(p.id)),
          tracksByPlaylist: tracks,
          updatedAt: upd,
          hidden: next.hidden.filter((id) => !gone.has(id)),
          editable: next.editable.filter((id) => !gone.has(id)),
          deleted: [...archived, ...next.deleted].slice(0, 30),
        };
        setSelected((prev) => {
          const s = new Set(prev);
          for (const id of notFoundIds) s.delete(id);
          return s;
        });
      }

      persist(next);
      const n = Object.keys(tracksByPlaylist).length;
      const extras = [
        notFoundIds.length ? `removed ${notFoundIds.length} deleted` : "",
        failures.length ? `${failures.length} failed (retry)` : "",
      ].filter(Boolean);
      setStatus(`Updated ${n} playlist(s)${extras.length ? ` · ${extras.join(" · ")}` : ""}`);
    } catch (err) {
      fail(`Update failed: ${errText(err)}`);
    } finally {
      setBusy(false);
    }
  }

  const songs = useMemo(
    () => combineFromCache(selectedPlaylists, cache.tracksByPlaylist),
    [selectedPlaylists, cache.tracksByPlaylist],
  );

  const editable = useMemo(() => new Set(cache.editable), [cache.editable]);
  const selectedTracks = useMemo(
    () => songs.filter((s) => selectedSongs.has(s.videoId)),
    [songs, selectedSongs],
  );
  // Targets for "Add to playlist": the shown (non-hidden) playlists; ownership can't be reliably
  // detected up front, so editable-detected ones sort first and the add attempt reports rejection.
  const addTargets = useMemo(() => {
    const q = addQuery.trim().toLowerCase();
    return visiblePlaylists
      .filter((p) => p.title.toLowerCase().includes(q))
      .sort((a, b) => Number(editable.has(b.id)) - Number(editable.has(a.id)));
  }, [visiblePlaylists, editable, addQuery]);

  // Add the selected songs to a playlist you own — optimistic, reverting on error.
  async function addSelectedTo(target: Playlist) {
    setAddPicker(false);
    const existing = cache.tracksByPlaylist[target.id] ?? [];
    const have = new Set(existing.map((t) => t.videoId));
    const toAdd = selectedTracks
      .filter((t) => !have.has(t.videoId))
      .map(({ videoId, title, artist, thumb }) => ({ videoId, title, artist, thumb }));
    if (toAdd.length === 0) {
      setStatus(`All selected songs are already in ${target.title}`);
      return;
    }
    persist({
      ...cache,
      tracksByPlaylist: { ...cache.tracksByPlaylist, [target.id]: [...existing, ...toAdd] },
    });
    setBusy(true);
    setStatus(`Adding ${toAdd.length} to ${target.title}…`);
    try {
      await addVideos(target.id, toAdd.map((t) => t.videoId));
      setStatus(`Added ${toAdd.length} to ${target.title}`);
    } catch (err) {
      persist({ ...cache, tracksByPlaylist: { ...cache.tracksByPlaylist, [target.id]: existing } });
      fail(`Add failed: ${errText(err)}`);
    } finally {
      setBusy(false);
    }
  }

  // Create a new playlist from the selected songs.
  async function createFromSelection() {
    const name = newName.trim();
    if (!name) return;
    const tracks = selectedTracks.map(({ videoId, title, artist, thumb }) => ({ videoId, title, artist, thumb }));
    setCreateOpen(false);
    setNewName("");
    setBusy(true);
    setStatus(`Creating “${name}”…`);
    try {
      const newId = await createPlaylist(name, tracks.map((t) => t.videoId));
      if (newId) {
        persist({
          ...cache,
          playlists: [{ id: newId, title: name }, ...cache.playlists],
          tracksByPlaylist: { ...cache.tracksByPlaylist, [newId]: tracks },
          updatedAt: { ...cache.updatedAt, [newId]: Date.now() },
          editable: [...new Set([...cache.editable, newId])],
        });
        setStatus(`Created “${name}” with ${tracks.length} songs`);
      } else {
        setStatus(`Created “${name}” — refreshing list…`);
        await refreshPlaylists(cache);
      }
    } catch (err) {
      fail(`Create failed: ${errText(err)}`);
    } finally {
      setBusy(false);
    }
  }

  function confirmAction(title: string, body: string, onConfirm: () => void) {
    setConfirm({ title, body, onConfirm });
  }

  // Removal targets: the loaded (selected) playlists that contain ≥1 of the selected songs.
  const removeTargets = useMemo(() => {
    const sel = selectedSongs;
    return selectedPlaylists.filter((p) =>
      (cache.tracksByPlaylist[p.id] ?? []).some((t) => sel.has(t.videoId)),
    );
  }, [selectedPlaylists, selectedSongs, cache.tracksByPlaylist]);

  // Remove the selected songs from a playlist — confirm, optimistic, revert on error.
  function removeSelectedFrom(target: Playlist) {
    setRemovePicker(false);
    const existing = cache.tracksByPlaylist[target.id] ?? [];
    const ids = [...new Set(existing.filter((t) => selectedSongs.has(t.videoId)).map((t) => t.videoId))];
    if (ids.length === 0) return;
    confirmAction(
      `Remove ${ids.length} song(s) from “${target.title}”?`,
      "This removes them from the playlist on your YouTube Music account.",
      async () => {
        const remaining = existing.filter((t) => !selectedSongs.has(t.videoId));
        persist({ ...cache, tracksByPlaylist: { ...cache.tracksByPlaylist, [target.id]: remaining } });
        setBusy(true);
        setStatus(`Removing ${ids.length} from ${target.title}…`);
        try {
          await removeVideos(target.id, ids);
          setStatus(`Removed ${ids.length} from ${target.title}`);
        } catch (err) {
          persist({ ...cache, tracksByPlaylist: { ...cache.tracksByPlaylist, [target.id]: existing } });
          fail(`Remove failed: ${errText(err)}`);
        } finally {
          setBusy(false);
        }
      },
    );
  }

  // Delete a playlist (non-optimistic — don't drop local data unless YouTube confirms). Archives
  // the song list locally first so it can be recreated. Invoked from the hardened delete modal.
  async function doDelete(p: Playlist) {
    setDeleteTarget(null);
    setDeleteText("");
    setBusy(true);
    setStatus(`Deleting ${p.title}…`);
    try {
      await deletePlaylist(p.id);
      const tracks = cache.tracksByPlaylist[p.id] ?? [];
      const tracksByPlaylist = { ...cache.tracksByPlaylist };
      delete tracksByPlaylist[p.id];
      const updatedAt = { ...cache.updatedAt };
      delete updatedAt[p.id];
      const archived = { id: p.id, title: p.title, tracks, deletedAt: Date.now() };
      persist({
        ...cache,
        playlists: cache.playlists.filter((x) => x.id !== p.id),
        tracksByPlaylist,
        updatedAt,
        hidden: cache.hidden.filter((id) => id !== p.id),
        editable: cache.editable.filter((id) => id !== p.id),
        deleted: [archived, ...cache.deleted].slice(0, 30),
      });
      setSelected((prev) => {
        const s = new Set(prev);
        s.delete(p.id);
        return s;
      });
      setStatus(`Deleted ${p.title} (archived ${tracks.length} songs for recovery)`);
    } catch (err) {
      fail(`Delete failed: ${errText(err)}`);
    } finally {
      setBusy(false);
    }
  }

  // Recreate a deleted playlist from the local archive.
  async function recreateDeleted(d: { title: string; tracks: { videoId: string; title: string; artist: string; thumb?: string }[] }) {
    setShowDeleted(false);
    setBusy(true);
    setStatus(`Recreating “${d.title}”…`);
    try {
      const newId = await createPlaylist(d.title, d.tracks.map((t) => t.videoId));
      if (newId) {
        persist({
          ...cache,
          playlists: [{ id: newId, title: d.title }, ...cache.playlists],
          tracksByPlaylist: { ...cache.tracksByPlaylist, [newId]: d.tracks },
          updatedAt: { ...cache.updatedAt, [newId]: Date.now() },
          editable: [...new Set([...cache.editable, newId])],
        });
        setStatus(`Recreated “${d.title}” with ${d.tracks.length} songs`);
      } else {
        setStatus(`Recreated “${d.title}” — refreshing list…`);
        await refreshPlaylists(cache);
      }
    } catch (err) {
      fail(`Recreate failed: ${errText(err)}`);
    } finally {
      setBusy(false);
    }
  }

  // Remove repeated songs (same video appearing more than once) within one playlist, keeping one.
  function removeRepeats(p: Playlist) {
    const tracks = cache.tracksByPlaylist[p.id];
    if (!tracks) {
      setStatus(`Update “${p.title}” first to find repeats`);
      return;
    }
    const counts = new Map<string, number>();
    for (const t of tracks) counts.set(t.videoId, (counts.get(t.videoId) ?? 0) + 1);
    const repeated = [...counts.entries()].filter(([, c]) => c > 1).map(([id]) => id);
    if (repeated.length === 0) {
      setStatus(`No repeats in “${p.title}”`);
      return;
    }
    confirmAction(
      `Remove ${repeated.length} repeated song(s) in “${p.title}”?`,
      "Keeps one copy of each. Note: YouTube doesn't expose per-copy ids, so de-duplicated songs are re-added once and move to the end of the playlist.",
      async () => {
        const seen = new Set<string>();
        const deduped = tracks.filter((t) => (seen.has(t.videoId) ? false : (seen.add(t.videoId), true)));
        persist({ ...cache, tracksByPlaylist: { ...cache.tracksByPlaylist, [p.id]: deduped } });
        setBusy(true);
        setStatus(`Removing repeats in ${p.title}…`);
        try {
          await removeVideos(p.id, repeated); // removes ALL occurrences of each repeated id
          await addVideos(p.id, repeated); // add one of each back
          setStatus(`Removed repeats in ${p.title} (${repeated.length})`);
        } catch (err) {
          persist({ ...cache, tracksByPlaylist: { ...cache.tracksByPlaylist, [p.id]: tracks } });
          fail(`Remove repeats failed: ${errText(err)}`);
        } finally {
          setBusy(false);
        }
      },
    );
  }

  const visibleSongs = useMemo(() => {
    const q = query.trim().toLowerCase();
    let filtered = songs;
    if (q) filtered = filtered.filter((s) => s.title.toLowerCase().includes(q) || s.artist.toLowerCase().includes(q));
    if (dupOnly) filtered = filtered.filter((s) => s.playlists.length > 1);
    const copy = [...filtered];
    copy.sort((a, b) => {
      let cmp = 0;
      if (sortKey === "title") cmp = a.title.localeCompare(b.title);
      else if (sortKey === "artist") cmp = a.artist.localeCompare(b.artist);
      else cmp = a.playlists.length - b.playlists.length;
      return sortAsc ? cmp : -cmp;
    });
    return copy;
  }, [songs, query, dupOnly, sortKey, sortAsc]);

  const v = useVirtual(visibleSongs.length);

  function sortBy(key: SortKey) {
    if (sortKey === key) setSortAsc((a) => !a);
    else {
      setSortKey(key);
      setSortAsc(true);
    }
  }
  const arrow = (key: SortKey) => (sortKey === key ? (sortAsc ? " ▲" : " ▼") : "");

  // Song selection: plain click = select one; Cmd/Ctrl+click = toggle; Shift+click = range.
  // Double-click (same row, fast) opens details — detected manually so a click after closing a
  // modal can't be mis-counted as a double-click on a different row.
  function onSongClick(e: React.MouseEvent, index: number) {
    const song = visibleSongs[index];
    const id = song.videoId;
    const prev = lastClick.current;
    if (prev && prev.id === id && e.timeStamp - prev.t < 350) {
      lastClick.current = null;
      setDetail(song);
      return;
    }
    lastClick.current = { id, t: e.timeStamp };
    if (e.shiftKey && lastSongIndex.current !== null) {
      const [a, b] = [lastSongIndex.current, index].sort((x, y) => x - y);
      const range = new Set<string>();
      for (let i = a; i <= b; i++) range.add(visibleSongs[i].videoId);
      setSelectedSongs(range);
    } else if (e.metaKey || e.ctrlKey) {
      setSelectedSongs((prev) => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        return next;
      });
      lastSongIndex.current = index;
    } else {
      setSelectedSongs(new Set([id]));
      lastSongIndex.current = index;
    }
  }

  const uncachedSelected = selectedPlaylists.filter((p) => !cache.tracksByPlaylist[p.id]).length;
  const manageList = cache.playlists.filter((p) =>
    p.title.toLowerCase().includes(manageQuery.trim().toLowerCase()),
  );

  return (
    <main className="app">
      <header className="toolbar">
        <h1>YouTube Music Manager</h1>
        <span className="status">{status}</span>
        <span className="grow" />
        <span className="actions">
          {signedIn && cache.deleted.length > 0 && (
            <button disabled={busy} onClick={() => setShowDeleted(true)}>Recently deleted ({cache.deleted.length})</button>
          )}
          {signedIn && <button disabled={busy} onClick={() => { setSpotifyResult(null); setSpotifyProgress(""); setSpotifyOpen(true); }}>Import Spotify</button>}
          {signedIn && <button disabled={busy} onClick={() => setShowManage(true)}>Manage playlists</button>}
          {signedIn && <button disabled={busy} onClick={() => refreshPlaylists(cache)}>Refresh list</button>}
          {signedIn ? (
            <button
              disabled={busy}
              onClick={async () => {
                await signOut();
                setSignedIn(false);
                setSelected(new Set());
                setStatus("Signed out");
              }}
            >
              Sign out
            </button>
          ) : (
            <button
              className="primary"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await signIn();
                  setSignedIn(true);
                  setBusy(false);
                  if (cache.playlists.length === 0) await refreshPlaylists(cache);
                } catch (err) {
                  setStatus(`Sign-in failed: ${err instanceof Error ? err.message : String(err)}`);
                  setBusy(false);
                }
              }}
            >
              Sign in
            </button>
          )}
        </span>
      </header>

      {signedIn && (
        <div className="layout">
          <section className="sidebar">
            <div className="sidebar-head">
              <strong>Playlists ({visiblePlaylists.length})</strong>
              <button className="small" onClick={() => setSelected(new Set(visiblePlaylists.map((p) => p.id)))}>Select all</button>
              <button className="small" onClick={() => setSelected(new Set())}>Clear</button>
            </div>
            <div className="panel list">
              {visiblePlaylists.map((p) => {
                const tracks = cache.tracksByPlaylist[p.id];
                const stale = isStale(p.id);
                return (
                  <div
                    key={p.id}
                    className="pl-row"
                    onContextMenu={(e) =>
                      openMenu(e, [
                        { label: "Remove repeats", onClick: () => removeRepeats(p) },
                        ...(cache.unmatched[p.id]?.length
                          ? [{ label: `Unmatched from Spotify (${cache.unmatched[p.id].length})`, onClick: () => setShowUnmatched(p.id) }]
                          : []),
                        { label: "Hide from sidebar", onClick: () => setPlaylistHidden(p.id, true) },
                        { label: "Open in YouTube Music", onClick: () => openPlaylist(p.id) },
                        { label: "Delete playlist…", onClick: () => { setDeleteText(""); setDeleteTarget(p); } },
                      ])
                    }
                  >
                    <input type="checkbox" checked={selected.has(p.id)} onChange={() => toggleSelected(p.id)} />
                    <span className="pl-title" onClick={() => toggleSelected(p.id)}>{p.title}</span>
                    {stale && <span className={`dot ${tracks ? "stale" : "none"}`} title={tracks ? `Updated ${relativeAge(cache.updatedAt[p.id])}` : "Not cached"} />}
                    {tracks && <span className="pl-meta">{tracks.length}</span>}
                    <button className="pl-hide" title="Hide from sidebar" onClick={() => setPlaylistHidden(p.id, true)}>×</button>
                  </div>
                );
              })}
              {visiblePlaylists.length === 0 && <p className="empty">All playlists hidden — use “Manage playlists”.</p>}
            </div>
            <button disabled={busy || selectedPlaylists.length === 0} onClick={() => runUpdate(selectedPlaylists)}>
              Update {selectedPlaylists.length} selected{uncachedSelected ? ` (${uncachedSelected} new)` : ""}
            </button>
            {stalePlaylists.length > 0 && (
              <button disabled={busy} onClick={() => runUpdate(stalePlaylists)}>
                Update stale ({stalePlaylists.length})
              </button>
            )}
          </section>

          <section className="songpane">
            <div className="searchbar">
              <input ref={searchRef} className="search" placeholder="Search songs…  (⌘F)" value={query} onChange={(e) => setQuery(e.currentTarget.value)} />
              {query && <button className="small" onClick={() => setQuery("")}>clear</button>}
              <label className="toggle">
                <input type="checkbox" checked={dupOnly} onChange={(e) => setDupOnly(e.currentTarget.checked)} />
                in &gt;1 playlist
              </label>
              <span className="count">{visibleSongs.length} songs{selectedSongs.size ? ` · ${selectedSongs.size} selected` : ""}</span>
            </div>

            <div className="song-head">
              <div className="col" onClick={() => sortBy("title")}>Title{arrow("title")}</div>
              <div className="col" onClick={() => sortBy("artist")}>Artist{arrow("artist")}</div>
              <div className="col" onClick={() => sortBy("count")}>In playlists{arrow("count")}</div>
            </div>
            <div className="song-scroll" ref={v.ref}>
              {visibleSongs.length === 0 ? (
                <p className="empty">
                  {songs.length === 0
                    ? "Select playlists, then “Update” to fetch their songs (cached after that)."
                    : "No songs match."}
                </p>
              ) : (
                <div className="song-inner" style={{ height: visibleSongs.length * ROW_H }}>
                  {visibleSongs.slice(v.start, v.end).map((s, idx) => {
                    const i = v.start + idx;
                    return (
                      <div
                        key={s.videoId}
                        className={`song-row${i % 2 ? " zebra" : ""}${selectedSongs.has(s.videoId) ? " selected" : ""}`}
                        style={{ top: i * ROW_H }}
                        onClick={(e) => onSongClick(e, i)}
                        onContextMenu={(e) => {
                          let count = selectedSongs.size;
                          if (!selectedSongs.has(s.videoId)) {
                            setSelectedSongs(new Set([s.videoId]));
                            lastSongIndex.current = i;
                            count = 1;
                          }
                          openMenu(e, [
                            { label: `Add ${count} to playlist…`, onClick: () => setAddPicker(true) },
                            { label: `Remove ${count} from playlist…`, onClick: () => setRemovePicker(true) },
                            { label: `New playlist from ${count} song${count > 1 ? "s" : ""}…`, onClick: () => setCreateOpen(true) },
                            { label: "Open in YouTube Music", onClick: () => openSong(s.videoId) },
                            { label: "Details", onClick: () => setDetail(s) },
                          ]);
                        }}
                      >
                        <div className="cell title-cell">
                          {s.thumb ? <img className="thumb" src={s.thumb} loading="lazy" alt="" /> : <span className="thumb" />}
                          <span className="ttext">{s.title}</span>
                        </div>
                        <div className="cell muted">{s.artist}</div>
                        <div className="cell muted" title={s.playlists.join(", ")}>
                          {s.playlists.length === 1 ? s.playlists[0] : `${s.playlists.length} playlists`}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </section>
        </div>
      )}

      {showManage && (
        <Overlay title="Manage playlists" onClose={() => setShowManage(false)}>
          <p style={{ fontSize: 13, color: "var(--muted)", marginTop: 0 }}>
            Unchecked playlists are hidden from the main sidebar (still cached). {hidden.size} hidden.
          </p>
          <input
            placeholder="Filter…"
            value={manageQuery}
            onChange={(e) => setManageQuery(e.currentTarget.value)}
            style={{ width: "100%", marginBottom: 8 }}
          />
          <div className="panel" style={{ maxHeight: "50vh", overflow: "auto" }}>
            {manageList.map((p) => (
              <label key={p.id} className="pl-row">
                <input type="checkbox" checked={!hidden.has(p.id)} onChange={(e) => setPlaylistHidden(p.id, !e.currentTarget.checked)} />
                <span className="pl-title">{p.title}</span>
              </label>
            ))}
          </div>
        </Overlay>
      )}

      {detail && (
        <Overlay title={detail.title} onClose={() => setDetail(null)}>
          <p style={{ margin: "4px 0" }}><strong>Artist:</strong> {detail.artist || "—"}</p>
          <p style={{ margin: "4px 0", display: "flex", gap: 8, alignItems: "center" }}>
            <button className="small" onClick={() => openUrl(`https://music.youtube.com/watch?v=${detail.videoId}`)}>
              Open in YouTube Music
            </button>
            <code style={{ color: "var(--muted)" }}>{detail.videoId}</code>
          </p>
          <p style={{ margin: "10px 0 4px" }}><strong>In {detail.playlists.length} playlist(s):</strong></p>
          <ul style={{ margin: 0, paddingLeft: 18, maxHeight: "38vh", overflow: "auto" }}>
            {detail.playlists.map((name) => {
              const id = titleToId.get(name);
              return (
                <li key={name} style={{ marginBottom: 2 }}>
                  {name}
                  {id && (
                    <button
                      className="small"
                      style={{ marginLeft: 8 }}
                      onClick={() => openUrl(`https://music.youtube.com/playlist?list=${id}`)}
                    >
                      open
                    </button>
                  )}
                </li>
              );
            })}
          </ul>
        </Overlay>
      )}

      {addPicker && (
        <Overlay title={`Add ${selectedTracks.length} song(s) to…`} onClose={() => setAddPicker(false)}>
          <p style={{ color: "var(--muted)", fontSize: 12.5, marginTop: 0 }}>
            Pick a playlist you own. ✓ marks ones detected as editable; others are still allowed and
            will report an error if YouTube rejects the edit.
          </p>
          <input placeholder="Filter playlists…" value={addQuery} onChange={(e) => setAddQuery(e.currentTarget.value)} style={{ width: "100%", marginBottom: 8 }} />
          <div className="panel" style={{ maxHeight: "50vh", overflow: "auto" }}>
            {addTargets.map((p) => (
              <div key={p.id} className="pl-row" style={{ cursor: "pointer" }} onClick={() => addSelectedTo(p)}>
                {editable.has(p.id) && <span style={{ color: "var(--accent)" }}>✓</span>}
                <span className="pl-title">{p.title}</span>
                {cache.tracksByPlaylist[p.id] && <span className="pl-meta">{cache.tracksByPlaylist[p.id].length}</span>}
              </div>
            ))}
            {addTargets.length === 0 && <p className="empty">No matches.</p>}
          </div>
        </Overlay>
      )}

      {removePicker && (
        <Overlay title={`Remove ${selectedTracks.length} song(s) from…`} onClose={() => setRemovePicker(false)}>
          {removeTargets.length === 0 ? (
            <p className="empty">The selected songs aren’t in any of the loaded (selected) playlists.</p>
          ) : (
            <div className="panel" style={{ maxHeight: "50vh", overflow: "auto" }}>
              {removeTargets.map((p) => (
                <div key={p.id} className="pl-row" style={{ cursor: "pointer" }} onClick={() => removeSelectedFrom(p)}>
                  <span className="pl-title">{p.title}</span>
                  <span className="pl-meta">
                    {(cache.tracksByPlaylist[p.id] ?? []).filter((t) => selectedSongs.has(t.videoId)).length} selected
                  </span>
                </div>
              ))}
            </div>
          )}
        </Overlay>
      )}

      {confirm && (
        <Overlay title={confirm.title} onClose={() => setConfirm(null)}>
          <p style={{ fontSize: 13 }}>{confirm.body}</p>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button onClick={() => setConfirm(null)}>Cancel</button>
            <button
              className="primary"
              onClick={() => {
                const fn = confirm.onConfirm;
                setConfirm(null);
                fn();
              }}
            >
              Confirm
            </button>
          </div>
        </Overlay>
      )}

      {deleteTarget && (
        <Overlay
          title={`⚠️ Delete “${deleteTarget.title}”?`}
          onClose={() => {
            setDeleteTarget(null);
            setDeleteText("");
          }}
        >
          <p className="warn" style={{ fontSize: 13 }}>
            This permanently deletes the playlist from your YouTube Music account — it can’t be undone there.
          </p>
          <p style={{ fontSize: 13 }}>
            {cache.tracksByPlaylist[deleteTarget.id]
              ? `Contains ${cache.tracksByPlaylist[deleteTarget.id].length} songs — its song list will be archived locally so you can recreate it from “Recently deleted.”`
              : "It isn’t cached locally, so its song list can’t be archived — Update it first if you want recovery."}
          </p>
          <p style={{ fontSize: 13, margin: "10px 0 4px" }}>
            Type the playlist name <strong>{deleteTarget.title}</strong> to confirm:
          </p>
          <input
            autoFocus
            value={deleteText}
            placeholder={deleteTarget.title}
            onChange={(e) => setDeleteText(e.currentTarget.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                setDeleteTarget(null);
                setDeleteText("");
              }
            }}
            style={{ width: "100%", marginBottom: 10 }}
          />
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button className="primary" onClick={() => { setDeleteTarget(null); setDeleteText(""); }}>Cancel</button>
            <button className="danger" disabled={deleteText.trim() !== deleteTarget.title.trim()} onClick={() => doDelete(deleteTarget)}>
              Delete
            </button>
          </div>
        </Overlay>
      )}

      {showDeleted && (
        <Overlay title="Recently deleted playlists" onClose={() => setShowDeleted(false)}>
          <p style={{ fontSize: 12.5, color: "var(--muted)", marginTop: 0 }}>
            Local archive of song lists. “Recreate” makes a new playlist with the same songs.
          </p>
          {cache.deleted.length === 0 ? (
            <p className="empty">Nothing archived.</p>
          ) : (
            <div className="panel" style={{ maxHeight: "55vh", overflow: "auto" }}>
              {cache.deleted.map((d) => (
                <div key={`${d.id}-${d.deletedAt}`} className="pl-row">
                  <span className="pl-title">{d.title}</span>
                  <span className="pl-meta">{d.tracks.length} songs · {relativeAge(d.deletedAt)}</span>
                  <button className="small" onClick={() => recreateDeleted(d)}>Recreate</button>
                  <button
                    className="small"
                    onClick={() =>
                      persist({ ...cache, deleted: cache.deleted.filter((x) => !(x.id === d.id && x.deletedAt === d.deletedAt)) })
                    }
                  >
                    Forget
                  </button>
                </div>
              ))}
            </div>
          )}
        </Overlay>
      )}

      {createOpen && (
        <Overlay title={`New playlist from ${selectedTracks.length} song(s)`} onClose={() => setCreateOpen(false)}>
          <input
            autoFocus
            placeholder="Playlist name"
            value={newName}
            onChange={(e) => setNewName(e.currentTarget.value)}
            onKeyDown={(e) => e.key === "Enter" && createFromSelection()}
            style={{ width: "100%", marginBottom: 10 }}
          />
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button onClick={() => setCreateOpen(false)}>Cancel</button>
            <button className="primary" disabled={!newName.trim()} onClick={createFromSelection}>Create</button>
          </div>
        </Overlay>
      )}

      {spotifyOpen && (
        <Overlay title="Import a Spotify playlist" onClose={() => setSpotifyOpen(false)}>
          <p style={{ fontSize: 12.5, color: "var(--muted)", marginTop: 0 }}>
            Paste a public Spotify playlist link. (Unofficial Spotify access — it can occasionally
            break when Spotify changes their site; just try again or report it.)
          </p>
          <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
            <input
              style={{ flex: 1 }}
              placeholder="https://open.spotify.com/playlist/…"
              value={spotifyUrl}
              onChange={(e) => setSpotifyUrl(e.currentTarget.value)}
              onKeyDown={(e) => e.key === "Enter" && !spotifyLoading && readSpotify()}
            />
            <button className="primary" disabled={spotifyLoading || !spotifyUrl.trim()} onClick={readSpotify}>
              Read
            </button>
          </div>
          {spotifyProgress && <p style={{ fontSize: 13 }}>{spotifyProgress}</p>}
          {spotifyResult && (
            <>
              <p style={{ margin: "6px 0" }}>
                <strong>{spotifyResult.title}</strong> — {spotifyResult.tracks.length} tracks
              </p>
              <div className="panel" style={{ maxHeight: "40vh", overflow: "auto" }}>
                {spotifyResult.tracks.map((t, i) => (
                  <div key={i} className="pl-row">
                    <span className="pl-title">{t.title}</span>
                    <span className="pl-meta">{t.artist}</span>
                  </div>
                ))}
              </div>
              <div style={{ display: "flex", gap: 8, marginTop: 10, alignItems: "center" }}>
                <input style={{ flex: 1 }} placeholder="New YouTube playlist name" value={spotifyName} onChange={(e) => setSpotifyName(e.currentTarget.value)} />
                <button className="primary" disabled={busy || !spotifyName.trim()} onClick={transferSpotify}>
                  Transfer to YouTube Music
                </button>
              </div>
              <p style={{ fontSize: 12, color: "var(--muted)", marginTop: 6 }}>
                Only confident title+artist matches are added; the rest are listed afterwards to find manually.
              </p>
            </>
          )}
        </Overlay>
      )}

      {transferResult && (
        <Overlay title="Transfer complete" onClose={() => setTransferResult(null)}>
          <p>
            <strong>{transferResult.name}</strong>: {transferResult.matched} song(s) added to YouTube Music.
          </p>
          {transferResult.unmatched.length > 0 ? (
            <>
              <p style={{ marginTop: 8, fontSize: 13 }}>
                {transferResult.unmatched.length} couldn’t be confidently matched — search them manually:
              </p>
              <div className="panel" style={{ maxHeight: "40vh", overflow: "auto" }}>
                {transferResult.unmatched.map((t, i) => (
                  <div key={i} className="pl-row">
                    <span className="pl-title">{t.title}</span>
                    <span className="pl-meta">{t.artist}</span>
                    <button className="small" onClick={() => openUrl(ytSearchUrl(`${t.title} ${t.artist}`))}>search</button>
                  </div>
                ))}
              </div>
              <p style={{ fontSize: 12, color: "var(--muted)", marginTop: 6 }}>
                This list is saved — right-click the new playlist → “Unmatched from Spotify” to see it again.
              </p>
            </>
          ) : (
            <p style={{ color: "var(--muted)" }}>Everything matched. 🎉</p>
          )}
        </Overlay>
      )}

      {showUnmatched && (
        <Overlay title="Unmatched from Spotify" onClose={() => setShowUnmatched(null)}>
          <div className="panel" style={{ maxHeight: "50vh", overflow: "auto" }}>
            {(cache.unmatched[showUnmatched] ?? []).map((t, i) => (
              <div key={i} className="pl-row">
                <span className="pl-title">{t.title}</span>
                <span className="pl-meta">{t.artist}</span>
                <button className="small" onClick={() => openUrl(ytSearchUrl(`${t.title} ${t.artist}`))}>search</button>
              </div>
            ))}
          </div>
        </Overlay>
      )}

      {error && (
        <Overlay title="⚠️ Something went wrong" onClose={() => setError(null)}>
          <p className="warn" style={{ fontSize: 13, wordBreak: "break-word" }}>{error}</p>
          <div style={{ display: "flex", justifyContent: "flex-end" }}>
            <button className="primary" onClick={() => setError(null)}>OK</button>
          </div>
        </Overlay>
      )}

      {menu && (
        <div className="ctx-menu" style={{ left: menu.x, top: menu.y }} onClick={(e) => e.stopPropagation()}>
          {menu.items.map((it) => (
            <div
              key={it.label}
              className="ctx-item"
              onClick={() => {
                it.onClick();
                setMenu(null);
              }}
            >
              {it.label}
            </div>
          ))}
        </div>
      )}
    </main>
  );
}

function Overlay({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button onClick={onClose}>Close</button>
        </div>
        {children}
      </div>
    </div>
  );
}

export default App;
