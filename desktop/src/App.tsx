import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  invoke,
  openExternal as openUrl,
  onCloseRequested,
  closeWindow,
  deferClose,
} from "./lib/native";
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
  getPlaylistTracks,
  parseYouTubePlaylistId,
  searchYouTubeMusicSongs,
  bestYoutubeMatch,
  type Playlist,
  type CombinedSong,
} from "./lib/ytmusic";
import { loadCache, saveCache, EMPTY_CACHE, type LibraryCache } from "./lib/cache";
import { fetchSpotifyPlaylist, type SpotifyTrack } from "./lib/spotify";
import { checkForUpdate } from "./lib/update";
import { STALE_MS, isUnavailableTitle, relativeAge } from "./lib/format";
import { Overlay } from "./components/Overlay";
import { SongList } from "./components/SongList";
import "./App.css";

// Phase 1: read-only parity, cache-driven, polished. Virtualized song list, staleness, persisted
// selection/sort, search (Cmd+F), hide playlists, details with external links.

type SortKey = "title" | "artist" | "count";

// --- small persisted UI state (selection/sort/filter) in localStorage (tiny, frequent writes) ---
type UiState = {
  selected: string[];
  sortKey: SortKey;
  sortAsc: boolean;
  dupOnly: boolean;
  unavailableOnly: boolean;
  replaceNames: boolean;
  autoDeleteQueues: boolean;
  checkUpdates: boolean;
  autoRefreshOnLaunch: boolean;
};
const UI_KEY = "ytm.ui";
function loadUi(): UiState {
  const base: UiState = {
    selected: [],
    sortKey: "title",
    sortAsc: true,
    dupOnly: false,
    unavailableOnly: false,
    replaceNames: false,
    autoDeleteQueues: false,
    checkUpdates: true,
    autoRefreshOnLaunch: true,
  };
  try {
    const raw = localStorage.getItem(UI_KEY);
    return raw ? { ...base, ...(JSON.parse(raw) as Partial<UiState>) } : base;
  } catch {
    return base;
  }
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
  const [unavailableOnly, setUnavailableOnly] = useState(ui0.unavailableOnly);
  const [query, setQuery] = useState("");
  const [showManage, setShowManage] = useState(false);
  const [manageQuery, setManageQuery] = useState("");
  const [detail, setDetail] = useState<CombinedSong | null>(null);
  const [customDraft, setCustomDraft] = useState("");
  const [detailAddTarget, setDetailAddTarget] = useState("");
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
  const [showRemoved, setShowRemoved] = useState<string | null>(null);
  const [showTemp, setShowTemp] = useState(false);
  const [addUrl, setAddUrl] = useState("");
  const [showSettings, setShowSettings] = useState(false);
  const [replaceNames, setReplaceNames] = useState(ui0.replaceNames);
  const [autoDeleteQueues, setAutoDeleteQueues] = useState(ui0.autoDeleteQueues);
  const [checkUpdates, setCheckUpdates] = useState(ui0.checkUpdates);
  const [autoRefreshOnLaunch, setAutoRefreshOnLaunch] = useState(ui0.autoRefreshOnLaunch);
  const [exitPrompt, setExitPrompt] = useState(false);
  const [update, setUpdate] = useState<{ version: string; url: string } | null>(null);
  // True until the initial silent sign-in settles, so the welcome screen shows "Signing in…" for a
  // returning user instead of flashing a "Sign in" prompt that immediately flips to their library.
  const [booting, setBooting] = useState(true);

  // Check for a newer release once on startup (best-effort), unless disabled in Settings.
  useEffect(() => {
    if (ui0.checkUpdates) void checkForUpdate().then(setUpdate);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
      const searchCache = new Map<string, Awaited<ReturnType<typeof searchYouTubeMusicSongs>>>();
      let cursor = 0;
      let done = 0;
      const worker = async (): Promise<void> => {
        while (cursor < tracks.length) {
          const i = cursor++;
          const t = tracks[i];
          const q = `${t.title} ${t.artist}`.trim();
          try {
            let candidates = searchCache.get(q);
            if (!candidates) {
              try {
                candidates = await searchYouTubeMusicSongs(q);
              } catch {
                candidates = await searchYouTubeMusicSongs(q); // one retry on a transient failure
              }
              searchCache.set(q, candidates);
            }
            const m = bestYoutubeMatch(candidates, t.title, t.artist);
            if (m) matches[i] = { videoId: m.videoId, title: t.title, artist: t.artist };
          } catch {
            /* leave unmatched */
          }
          done += 1;
          setStatus(`Matching ${done}/${tracks.length} on YouTube Music…`);
        }
      };
      await Promise.all(Array.from({ length: Math.min(6, tracks.length) }, () => worker()));

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
          ...cacheRef.current,
          playlists: [{ id: newId, title: name }, ...cacheRef.current.playlists],
          tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [newId]: matchedTracks },
          updatedAt: { ...cacheRef.current.updatedAt, [newId]: Date.now() },
          editable: [...new Set([...cacheRef.current.editable, newId])],
          unmatched: unmatched.length ? { ...cacheRef.current.unmatched, [newId]: unmatched } : cacheRef.current.unmatched,
        });
      } else {
        await refreshPlaylists();
      }
      setTransferResult({ name, matched: matchedIds.length, unmatched });
      setStatus(`Transferred “${name}”: ${matchedIds.length} added, ${unmatched.length} unmatched`);
    } catch (err) {
      fail(`Transfer failed: ${errText(err)}`);
    } finally {
      setBusy(false);
    }
  }

  // cacheRef always holds the latest cache, so async handlers can base a write on current state
  // (not a stale render snapshot) — otherwise a write after an await clobbers concurrent changes.
  const cacheRef = useRef(cache);
  useEffect(() => {
    cacheRef.current = cache;
  }, [cache]);
  // Debounced, atomic save (coalesces bursts; the Rust side writes temp+rename).
  useEffect(() => {
    const id = setTimeout(() => void saveCache(cache), 400);
    return () => clearTimeout(id);
  }, [cache]);
  function persist(next: LibraryCache) {
    cacheRef.current = next;
    setCache(next);
  }

  // On quit, offer to delete leftover queues (or auto-delete if enabled in Settings).
  const closingRef = useRef(false);
  const autoDeleteQueuesRef = useRef(autoDeleteQueues);
  autoDeleteQueuesRef.current = autoDeleteQueues;
  async function deleteAllTemp() {
    const remaining: typeof cacheRef.current.tempPlaylists = [];
    let failed = 0;
    for (const t of cacheRef.current.tempPlaylists) {
      try {
        await deletePlaylist(t.id);
      } catch {
        remaining.push(t); // keep the ones that failed so they're not lost
        failed += 1;
      }
    }
    // Persist the cleared list AND save it durably now — on the quit path the debounced save won't
    // fire before the app exits, which made deleted queues reappear as "leftover" next launch.
    const next = { ...cacheRef.current, tempPlaylists: remaining };
    persist(next);
    await saveCache(next);
    if (failed) setStatus(`Couldn't delete ${failed} queue(s) — they remain on your account.`);
  }
  useEffect(() => {
    // The window is held open until we call closeWindow() (Tauri: preventDefault+destroy; Electron:
    // main vetoes then we allow-close). So every path through the handler must end in closeWindow()
    // or a prompt.
    const unlisten = onCloseRequested(async () => {
      if (closingRef.current) return;
      if (cacheRef.current.tempPlaylists.length === 0) {
        closingRef.current = true;
        await closeWindow();
        return;
      }
      if (autoDeleteQueuesRef.current) {
        closingRef.current = true;
        await deferClose(); // deleting on the network may take longer than the force-quit timer
        await deleteAllTemp();
        await closeWindow();
      } else {
        await deferClose(); // we're asking the user — stop the shell's force-quit timer
        setExitPrompt(true);
      }
    });
    return () => unlisten();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function openDetails(s: CombinedSong) {
    setDetail(s);
    setCustomDraft(cacheRef.current.customNames[s.videoId] ?? "");
    setDetailAddTarget("");
  }
  // Stable indirection so the memoized-row callbacks don't depend on openDetails' identity.
  const openDetailsRef = useRef(openDetails);
  openDetailsRef.current = openDetails;
  function commitCustomName(videoId: string, value: string) {
    const v = value.trim();
    const next = { ...cache.customNames };
    if (v) next[videoId] = v;
    else delete next[videoId];
    persist({ ...cacheRef.current, customNames: next });
  }

  // "Play in YouTube Music": YouTube Music has no streaming API, so we recreate the workaround —
  // build a private temporary playlist from the songs and open it on music.youtube.com to play.
  // The temp playlist is tracked so it can be cleaned up later (Queues panel).
  async function playInYouTube(videoIds: string[], title: string) {
    if (videoIds.length === 0) return;
    setBusy(true);
    setStatus(`Building queue “${title}”…`);
    try {
      const newId = await createPlaylist(title, videoIds);
      if (newId) {
        persist({
          ...cacheRef.current,
          tempPlaylists: [{ id: newId, title, createdAt: Date.now() }, ...cacheRef.current.tempPlaylists].slice(0, 50),
        });
        await openPlaylist(newId);
        setStatus(`Opened “${title}” (${videoIds.length} songs) in YouTube Music`);
      } else {
        setStatus("Created the queue, but couldn't get its id to open it.");
      }
    } catch (err) {
      fail(`Couldn't build the queue: ${errText(err)}`);
    } finally {
      setBusy(false);
    }
  }

  function deleteTemp(id: string) {
    setBusy(true);
    setStatus("Deleting queue…");
    deletePlaylist(id)
      .then(() => {
        persist({ ...cacheRef.current, tempPlaylists: cacheRef.current.tempPlaylists.filter((t) => t.id !== id) });
        setStatus("Deleted queue");
      })
      .catch((err) => fail(`Couldn't delete the queue: ${errText(err)}`))
      .finally(() => setBusy(false));
  }

  async function doSignIn() {
    setBusy(true);
    setStatus("Signing in…");
    try {
      await signIn();
      setSignedIn(true);
      setBusy(false);
      if (cache.playlists.length === 0) await refreshPlaylists();
      else setStatus(`${cache.playlists.length} playlists`);
    } catch (err) {
      fail(`Sign-in failed: ${errText(err)}`);
      setBusy(false);
    }
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
      localStorage.setItem(
        UI_KEY,
        JSON.stringify({ selected: [...selected], sortKey, sortAsc, dupOnly, unavailableOnly, replaceNames, autoDeleteQueues, checkUpdates, autoRefreshOnLaunch }),
      );
    } catch {
      /* ignore */
    }
  }, [selected, sortKey, sortAsc, dupOnly, unavailableOnly, replaceNames, autoDeleteQueues, checkUpdates, autoRefreshOnLaunch]);

  // The shift-click range anchor indexes into visibleSongs; reset it when that ordering changes
  // (sort/filter/search) so a range isn't computed across two different orderings.
  useEffect(() => {
    lastSongIndex.current = null;
  }, [sortKey, sortAsc, query, dupOnly, unavailableOnly]);

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

  // Add any public YouTube/YT Music playlist by URL (not just your library) — added read-only
  // unless you happen to own it.
  async function addPublicPlaylist(input: string) {
    const id = parseYouTubePlaylistId(input);
    if (!id) {
      fail("Couldn't find a playlist id in that link.");
      return;
    }
    setShowManage(false);
    setAddUrl("");
    setBusy(true);
    setStatus("Loading playlist…");
    try {
      const { tracks, editable, title } = await getPlaylistTracks(id);
      const name = title || "Playlist";
      const c = cacheRef.current;
      persist({
        ...c,
        playlists: c.playlists.some((p) => p.id === id) ? c.playlists : [{ id, title: name }, ...c.playlists],
        tracksByPlaylist: { ...c.tracksByPlaylist, [id]: tracks },
        updatedAt: { ...c.updatedAt, [id]: Date.now() },
        editable: editable ? [...new Set([...c.editable, id])] : c.editable,
        // A playlist you explicitly add by URL should appear in the sidebar.
        shown: [...new Set([...c.shown, id])],
      });
      setSelected(new Set([id]));
      setStatus(`Added “${name}” (${tracks.length} songs)`);
    } catch (err) {
      fail(`Couldn't add that playlist: ${errText(err)}`);
    } finally {
      setBusy(false);
    }
  }

  async function refreshPlaylists() {
    setBusy(true);
    setStatus("Refreshing playlist list…");
    try {
      const playlists = await getLibraryPlaylists();
      // Just refresh the list. The sidebar is opt-in (cache.shown), so new playlists simply don't
      // appear until the user adds them via Manage — no hide bookkeeping needed.
      persist({ ...cacheRef.current, playlists });
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
          setStatus(
            `${cached.playlists.length} playlists (cached)` +
              (cached.tempPlaylists.length ? ` · ${cached.tempPlaylists.length} leftover queue(s) — see “Queues”` : ""),
          );
          // Auto-refresh the playlist list on launch (Settings; default on). The list fetch is
          // cheap (1-3 requests), and an empty cache always refreshes regardless.
          if (cached.playlists.length === 0 || ui0.autoRefreshOnLaunch) await refreshPlaylists();
        } else {
          setStatus("Not signed in");
        }
      } catch (err) {
        setStatus(`Sign-in failed: ${err instanceof Error ? err.message : String(err)}`);
      } finally {
        setBooting(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // The sidebar is opt-in: it shows only playlists the user has added (cache.shown), defaulting to
  // none. Adding playlists you want is friendlier than pruning a full list.
  const shown = useMemo(() => new Set(cache.shown), [cache.shown]);
  const visiblePlaylists = useMemo(
    () => cache.playlists.filter((p) => shown.has(p.id)),
    [cache.playlists, shown],
  );

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

  // Add/remove a playlist from the sidebar (opt-in). Removing also deselects it.
  function setPlaylistShown(id: string, show: boolean) {
    const next = new Set(cache.shown);
    if (show) next.add(id);
    else next.delete(id);
    persist({ ...cacheRef.current, shown: [...next] });
    if (!show)
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
      const updatedAt = { ...cacheRef.current.updatedAt };
      for (const id of Object.keys(tracksByPlaylist)) updatedAt[id] = now;

      // Archive songs that vanished from a playlist (present before, absent in the fresh fetch).
      // Guard: skip on first fetch (no prior) or an empty fetch (likely a hiccup), so we never wipe.
      const removedSongs = { ...cacheRef.current.removedSongs };
      let removedCount = 0;
      for (const id of Object.keys(tracksByPlaylist)) {
        const fresh = tracksByPlaylist[id];
        const old = cacheRef.current.tracksByPlaylist[id];
        if (!old || fresh.length === 0) continue;
        const freshIds = new Set(fresh.map((t) => t.videoId));
        const gone = old.filter((o) => !freshIds.has(o.videoId));
        if (gone.length === 0) continue;
        const existing = removedSongs[id] ?? [];
        const seen = new Set(existing.map((r) => `${r.title}|${r.artist}`));
        const additions = gone
          .filter((g) => !seen.has(`${g.title}|${g.artist}`))
          .map((g) => ({ title: g.title, artist: g.artist, removedAt: now }));
        if (additions.length) {
          removedSongs[id] = [...additions, ...existing].slice(0, 500);
          removedCount += additions.length;
        }
      }

      let next: LibraryCache = {
        ...cacheRef.current,
        tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, ...tracksByPlaylist },
        updatedAt,
        editable: [...new Set([...cacheRef.current.editable, ...editableIds])],
        removedSongs,
      };

      // 404-prune: drop playlists YouTube reports as gone (deleted elsewhere), archiving their
      // cached songs so nothing is silently lost.
      if (notFoundIds.length) {
        const gone = new Set(notFoundIds);
        const tracks = { ...next.tracksByPlaylist };
        const upd = { ...next.updatedAt };
        const archived: LibraryCache["deleted"] = [];
        for (const id of notFoundIds) {
          const pl = cacheRef.current.playlists.find((p) => p.id === id);
          const t = cacheRef.current.tracksByPlaylist[id] ?? [];
          if (pl && t.length) archived.push({ id, title: pl.title, tracks: t, deletedAt: now });
          delete tracks[id];
          delete upd[id];
        }
        next = {
          ...next,
          playlists: next.playlists.filter((p) => !gone.has(p.id)),
          tracksByPlaylist: tracks,
          updatedAt: upd,
          shown: next.shown.filter((id) => !gone.has(id)),
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
        removedCount ? `archived ${removedCount} removed song(s)` : "",
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

  // Auto-load songs for a selected playlist the first time it's opened (fetch-once-on-demand).
  // `autoTried` caps each playlist at one automatic attempt per session so a retryable network
  // failure — which never lands in the cache — can't spin the effect into an infinite refetch loop.
  // A manual "Refresh selected" is the explicit retry / re-pull for stale or changed data.
  const autoTried = useRef<Set<string>>(new Set());
  useEffect(() => {
    if (!signedIn || busy) return;
    const missing = selectedPlaylists.filter(
      (p) => !cache.tracksByPlaylist[p.id] && !autoTried.current.has(p.id),
    );
    if (missing.length) {
      missing.forEach((p) => autoTried.current.add(p.id));
      void runUpdate(missing);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedPlaylists, signedIn, busy]);

  const editable = useMemo(() => new Set(cache.editable), [cache.editable]);
  const selectedTracks = useMemo(
    () => songs.filter((s) => selectedSongs.has(s.videoId)),
    [songs, selectedSongs],
  );
  // Targets for "Add to playlist": the playlists shown in the sidebar; ownership can't be reliably
  // detected up front, so editable-detected ones sort first and the add attempt reports rejection.
  // Only playlists in the sidebar that we can actually modify (owned) — no point listing read-only
  // ones you can't add to.
  const addTargets = useMemo(() => {
    const q = addQuery.trim().toLowerCase();
    return visiblePlaylists.filter((p) => editable.has(p.id) && p.title.toLowerCase().includes(q));
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
      ...cacheRef.current,
      tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [target.id]: [...existing, ...toAdd] },
    });
    setBusy(true);
    setStatus(`Adding ${toAdd.length} to ${target.title}…`);
    try {
      await addVideos(target.id, toAdd.map((t) => t.videoId));
      setStatus(`Added ${toAdd.length} to ${target.title}`);
    } catch (err) {
      persist({ ...cacheRef.current, tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [target.id]: existing } });
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
          ...cacheRef.current,
          playlists: [{ id: newId, title: name }, ...cacheRef.current.playlists],
          tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [newId]: tracks },
          updatedAt: { ...cacheRef.current.updatedAt, [newId]: Date.now() },
          editable: [...new Set([...cacheRef.current.editable, newId])],
        });
        setStatus(`Created “${name}” with ${tracks.length} songs`);
      } else {
        setStatus(`Created “${name}” — refreshing list…`);
        await refreshPlaylists();
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
        persist({ ...cacheRef.current, tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [target.id]: remaining } });
        setBusy(true);
        setStatus(`Removing ${ids.length} from ${target.title}…`);
        try {
          await removeVideos(target.id, ids);
          setStatus(`Removed ${ids.length} from ${target.title}`);
        } catch (err) {
          persist({ ...cacheRef.current, tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [target.id]: existing } });
          fail(`Remove failed: ${errText(err)}`);
        } finally {
          setBusy(false);
        }
      },
    );
  }

  // Add/remove a single song to/from one playlist — the quick edits offered in the Details screen.
  // Optimistic with revert-on-error, mirroring the multi-select add/remove flows.
  async function addOneTo(song: CombinedSong, target: Playlist) {
    const existing = cacheRef.current.tracksByPlaylist[target.id] ?? [];
    if (existing.some((t) => t.videoId === song.videoId)) {
      setStatus(`Already in “${target.title}”`);
      return;
    }
    const track = { videoId: song.videoId, title: song.title, artist: song.artist, thumb: song.thumb };
    persist({ ...cacheRef.current, tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [target.id]: [...existing, track] } });
    setBusy(true);
    setStatus(`Adding to “${target.title}”…`);
    try {
      await addVideos(target.id, [song.videoId]);
      setStatus(`Added to “${target.title}”`);
    } catch (err) {
      persist({ ...cacheRef.current, tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [target.id]: existing } });
      fail(`Add failed: ${errText(err)}`);
    } finally {
      setBusy(false);
    }
  }
  function removeOneFrom(song: CombinedSong, target: Playlist) {
    const existing = cacheRef.current.tracksByPlaylist[target.id] ?? [];
    if (!existing.some((t) => t.videoId === song.videoId)) return;
    confirmAction(
      `Remove from “${target.title}”?`,
      `Removes “${song.title}” from this playlist on your YouTube Music account.`,
      async () => {
        const remaining = existing.filter((t) => t.videoId !== song.videoId);
        persist({ ...cacheRef.current, tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [target.id]: remaining } });
        setBusy(true);
        setStatus(`Removing from “${target.title}”…`);
        try {
          await removeVideos(target.id, [song.videoId]);
          setStatus(`Removed from “${target.title}”`);
        } catch (err) {
          persist({ ...cacheRef.current, tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [target.id]: existing } });
          fail(`Remove failed: ${errText(err)}`);
        } finally {
          setBusy(false);
        }
      },
    );
  }
  // Live (cache-derived) playlist membership for the open Details song, and the playlists it could be
  // added to — recomputed from the cache so the Details screen updates as you add/remove.
  const detailMembership = useMemo(
    () =>
      detail
        ? cache.playlists.filter((p) => (cache.tracksByPlaylist[p.id] ?? []).some((t) => t.videoId === detail.videoId))
        : [],
    [detail, cache.playlists, cache.tracksByPlaylist],
  );
  const detailAddTargets = useMemo(() => {
    if (!detail) return [];
    const inIds = new Set(detailMembership.map((p) => p.id));
    // Only sidebar playlists we can modify (owned) that the song isn't already in.
    return visiblePlaylists.filter((p) => editable.has(p.id) && !inIds.has(p.id));
  }, [detail, detailMembership, visiblePlaylists, editable]);

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
        ...cacheRef.current,
        playlists: cacheRef.current.playlists.filter((x) => x.id !== p.id),
        tracksByPlaylist,
        updatedAt,
        shown: cacheRef.current.shown.filter((id) => id !== p.id),
        editable: cacheRef.current.editable.filter((id) => id !== p.id),
        deleted: [archived, ...cacheRef.current.deleted].slice(0, 30),
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
          ...cacheRef.current,
          playlists: [{ id: newId, title: d.title }, ...cacheRef.current.playlists],
          tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [newId]: d.tracks },
          updatedAt: { ...cacheRef.current.updatedAt, [newId]: Date.now() },
          editable: [...new Set([...cacheRef.current.editable, newId])],
        });
        setStatus(`Recreated “${d.title}” with ${d.tracks.length} songs`);
      } else {
        setStatus(`Recreated “${d.title}” — refreshing list…`);
        await refreshPlaylists();
      }
    } catch (err) {
      fail(`Recreate failed: ${errText(err)}`);
    } finally {
      setBusy(false);
    }
  }

  // Export a playlist's tracks to a CSV (native save dialog). Fetches the songs on demand if they
  // aren't cached yet, so it works straight from Manage playlists without loading them first.
  async function exportPlaylist(p: Playlist) {
    let tracks = cache.tracksByPlaylist[p.id];
    if (!tracks) {
      setBusy(true);
      setStatus(`Loading “${p.title}” to export…`);
      try {
        const r = await getPlaylistTracks(p.id);
        tracks = r.tracks;
        persist({
          ...cacheRef.current,
          tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [p.id]: r.tracks },
          updatedAt: { ...cacheRef.current.updatedAt, [p.id]: Date.now() },
        });
      } catch (err) {
        fail(`Export failed: ${errText(err)}`);
        return;
      } finally {
        setBusy(false);
      }
    }
    if (!tracks || tracks.length === 0) {
      setStatus(`“${p.title}” has no songs to export`);
      return;
    }
    const esc = (v: string) => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
    const rows = [
      "Title,Artist,Video ID",
      ...tracks.map((t) => [t.title, t.artist, t.videoId].map((x) => esc(x || "")).join(",")),
    ];
    try {
      const saved = await invoke<boolean>("export_text_file", {
        defaultName: `${p.title}.csv`,
        contents: rows.join("\n"),
      });
      setStatus(saved ? `Exported “${p.title}” (${tracks.length} songs)` : "Export cancelled");
    } catch (err) {
      fail(`Export failed: ${errText(err)}`);
    }
  }

  // Remove repeated songs (same video appearing more than once) within one playlist, keeping one.
  function removeRepeats(p: Playlist) {
    const tracks = cache.tracksByPlaylist[p.id];
    if (!tracks) {
      setStatus(`Load songs for “${p.title}” first to find repeats`);
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
        persist({ ...cacheRef.current, tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [p.id]: deduped } });
        setBusy(true);
        setStatus(`Removing repeats in ${p.title}…`);
        let removed = false;
        try {
          await removeVideos(p.id, repeated); // removes ALL occurrences of each repeated id
          removed = true;
          await addVideos(p.id, repeated); // add one of each back
          setStatus(`Removed repeats in ${p.title} (${repeated.length})`);
        } catch (err) {
          if (removed) {
            // All copies were removed on YouTube but re-adding one failed → those songs are now
            // GONE on the account; reflect that (don't revert to showing repeats) and tell the user.
            const repSet = new Set(repeated);
            persist({
              ...cacheRef.current,
              tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [p.id]: tracks.filter((t) => !repSet.has(t.videoId)) },
            });
            fail(`Removed repeats in “${p.title}”, but re-adding one copy failed — those ${repeated.length} song(s) are now gone; re-add them. ${errText(err)}`);
          } else {
            persist({ ...cacheRef.current, tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [p.id]: tracks } });
            fail(`Remove repeats failed: ${errText(err)}`);
          }
        } finally {
          setBusy(false);
        }
      },
    );
  }

  const visibleSongs = useMemo(() => {
    const q = query.trim().toLowerCase();
    let filtered = songs;
    if (q)
      filtered = filtered.filter(
        (s) =>
          s.title.toLowerCase().includes(q) ||
          s.artist.toLowerCase().includes(q) ||
          (cache.customNames[s.videoId]?.toLowerCase().includes(q) ?? false),
      );
    if (dupOnly) filtered = filtered.filter((s) => s.playlists.length > 1);
    if (unavailableOnly) filtered = filtered.filter((s) => isUnavailableTitle(s.title));
    const copy = [...filtered];
    copy.sort((a, b) => {
      let cmp = 0;
      if (sortKey === "title") cmp = a.title.localeCompare(b.title);
      else if (sortKey === "artist") cmp = a.artist.localeCompare(b.artist);
      else cmp = a.playlists.length - b.playlists.length;
      return sortAsc ? cmp : -cmp;
    });
    return copy;
  }, [songs, query, dupOnly, unavailableOnly, sortKey, sortAsc, cache.customNames]);


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
  // Stable (useCallback) so the memoized SongRow only re-renders when visibleSongs/selection change.
  const onSongClick = useCallback(
    (e: React.MouseEvent, index: number) => {
      const song = visibleSongs[index];
      const id = song.videoId;
      const prev = lastClick.current;
      if (prev && prev.id === id && e.timeStamp - prev.t < 350) {
        lastClick.current = null;
        openDetailsRef.current(song);
        return;
      }
      lastClick.current = { id, t: e.timeStamp };
      if (e.shiftKey && lastSongIndex.current !== null) {
        const [a, b] = [lastSongIndex.current, index].sort((x, y) => x - y);
        const range = new Set<string>();
        for (let i = a; i <= b; i++) range.add(visibleSongs[i].videoId);
        setSelectedSongs(range);
      } else if (e.metaKey || e.ctrlKey) {
        setSelectedSongs((p) => {
          const next = new Set(p);
          if (next.has(id)) next.delete(id);
          else next.add(id);
          return next;
        });
        lastSongIndex.current = index;
      } else {
        setSelectedSongs(new Set([id]));
        lastSongIndex.current = index;
      }
    },
    [visibleSongs],
  );

  const onSongContextMenu = useCallback(
    (e: React.MouseEvent, index: number) => {
      const s = visibleSongs[index];
      const ids = selectedSongs.has(s.videoId) ? [...selectedSongs] : [s.videoId];
      const count = ids.length;
      if (!selectedSongs.has(s.videoId)) {
        setSelectedSongs(new Set([s.videoId]));
        lastSongIndex.current = index;
      }
      openMenu(e, [
        { label: `Play ${count} in YouTube Music`, onClick: () => playInYouTube(ids, `▶ Queue — ${count} song${count > 1 ? "s" : ""}`) },
        { label: `Add ${count} to playlist…`, onClick: () => setAddPicker(true) },
        { label: `Remove ${count} from playlist…`, onClick: () => setRemovePicker(true) },
        { label: `New playlist from ${count} song${count > 1 ? "s" : ""}…`, onClick: () => setCreateOpen(true) },
        { label: "Set custom name…", onClick: () => openDetailsRef.current(s) },
        { label: "Open in YouTube Music", onClick: () => openSong(s.videoId) },
        { label: "Details", onClick: () => openDetailsRef.current(s) },
      ]);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [visibleSongs, selectedSongs],
  );

  const manageList = cache.playlists.filter((p) =>
    p.title.toLowerCase().includes(manageQuery.trim().toLowerCase()),
  );

  return (
    <main className="app">
      {update && (
        <div className="update-bar">
          <span>A newer version ({update.version}) is available.</span>
          <button className="small" onClick={() => openUrl(update.url)}>Download</button>
          <button className="small" onClick={() => setUpdate(null)}>Dismiss</button>
        </div>
      )}
      <header className="toolbar">
        <h1>YouTube Music Manager</h1>
        <span className="status">{status}</span>
        <span className="grow" />
        <span className="actions">
          {signedIn && cache.deleted.length > 0 && (
            <button disabled={busy} onClick={() => setShowDeleted(true)}>Recently deleted ({cache.deleted.length})</button>
          )}
          {signedIn && cache.tempPlaylists.length > 0 && (
            <button disabled={busy} onClick={() => setShowTemp(true)}>Queues ({cache.tempPlaylists.length})</button>
          )}
          {signedIn && <button disabled={busy} onClick={() => setShowManage(true)}>Manage playlists</button>}
          {signedIn && <button disabled={busy} onClick={() => setShowSettings(true)} title="Settings">⚙</button>}
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
                        { label: "Export to CSV…", onClick: () => exportPlaylist(p) },
                        ...(cache.removedSongs[p.id]?.length
                          ? [{ label: `Removed songs (${cache.removedSongs[p.id].length})`, onClick: () => setShowRemoved(p.id) }]
                          : []),
                        ...(cache.unmatched[p.id]?.length
                          ? [{ label: `Unmatched from Spotify (${cache.unmatched[p.id].length})`, onClick: () => setShowUnmatched(p.id) }]
                          : []),
                        { label: "Remove from sidebar", onClick: () => setPlaylistShown(p.id, false) },
                        { label: "Open in YouTube Music", onClick: () => openPlaylist(p.id) },
                      ])
                    }
                  >
                    <input type="checkbox" checked={selected.has(p.id)} onChange={() => toggleSelected(p.id)} />
                    <span className="pl-title" onClick={() => toggleSelected(p.id)}>{p.title}</span>
                    {stale && <span className={`dot ${tracks ? "stale" : "none"}`} title={tracks ? `Updated ${relativeAge(cache.updatedAt[p.id])}` : "Not cached"} />}
                    {tracks && <span className="pl-meta">{tracks.length}</span>}
                    <button className="pl-hide" title="Remove from sidebar" onClick={() => setPlaylistShown(p.id, false)}>×</button>
                  </div>
                );
              })}
              {visiblePlaylists.length === 0 && (
                <div className="empty" style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-start" }}>
                  <span>No playlists added yet. Add the ones you want to work with.</span>
                  <button className="small" onClick={() => setShowManage(true)}>Manage playlists</button>
                </div>
              )}
            </div>
            <button
              disabled={busy || selectedPlaylists.length === 0}
              title="Re-pull the latest songs for the selected playlists (e.g. after editing them elsewhere). Songs load automatically the first time you select a playlist."
              onClick={() => runUpdate(selectedPlaylists)}
            >
              Refresh playlists{selectedPlaylists.length ? ` (${selectedPlaylists.length})` : ""}
            </button>
            <button
              disabled={busy || songs.length === 0}
              title="Make a temporary playlist from these songs and open it on music.youtube.com to play"
              onClick={() =>
                playInYouTube(
                  songs.map((s) => s.videoId),
                  `▶ ${selectedPlaylists.map((p) => p.title).join(", ").slice(0, 80) || "Queue"}`,
                )
              }
            >
              ▶ Play {songs.length} in YouTube Music
            </button>
          </section>

          <section className="songpane">
            <div className="searchbar">
              <input spellCheck={false} autoCorrect="off" autoCapitalize="off" ref={searchRef} className="search" placeholder="Search songs…  (⌘F)" value={query} onChange={(e) => setQuery(e.currentTarget.value)} />
              {query && <button className="small" onClick={() => setQuery("")}>clear</button>}
              <label className="toggle">
                <input type="checkbox" checked={dupOnly} onChange={(e) => setDupOnly(e.currentTarget.checked)} />
                in &gt;1 playlist
              </label>
              <label className="toggle" title="Songs with a deleted/private/unavailable placeholder title (best-effort)">
                <input type="checkbox" checked={unavailableOnly} onChange={(e) => setUnavailableOnly(e.currentTarget.checked)} />
                unavailable
              </label>
              <span className="count">{visibleSongs.length} songs{selectedSongs.size ? ` · ${selectedSongs.size} selected` : ""}</span>
            </div>

            <div className="song-head">
              <div className="col" onClick={() => sortBy("title")}>Title{arrow("title")}</div>
              <div className="col" onClick={() => sortBy("artist")}>Artist{arrow("artist")}</div>
              <div className="col" onClick={() => sortBy("count")}>In playlists{arrow("count")}</div>
            </div>
            <SongList
              songs={visibleSongs}
              emptyMessage={
                songs.length === 0
                  ? "Select a playlist to load its songs (cached after the first time)."
                  : "No songs match."
              }
              selectedSongs={selectedSongs}
              customNames={cache.customNames}
              replaceNames={replaceNames}
              onSongClick={onSongClick}
              onSongContextMenu={onSongContextMenu}
            />
          </section>
        </div>
      )}

      {!signedIn && (
        <div className="welcome">
          <img className="welcome-icon" src="/icon.png" alt="" onError={(e) => (e.currentTarget.style.display = "none")} />
          <h2>YouTube Music Manager</h2>
          <p className="welcome-sub">Manage your YouTube Music playlists, and import from Spotify.</p>
          {booting ? (
            <p className="status" style={{ minHeight: 18, fontSize: 15 }}>Signing in…</p>
          ) : (
            <>
              <button className="primary big" disabled={busy} onClick={doSignIn}>
                {busy ? "Signing in…" : "Sign in to YouTube Music"}
              </button>
              <p className="status" style={{ minHeight: 18 }}>{status}</p>
            </>
          )}
        </div>
      )}

      {showManage && (
        <Overlay title="Manage playlists" onClose={() => setShowManage(false)}>
          <p style={{ fontSize: 13, fontWeight: 600, margin: "0 0 6px" }}>Add a playlist</p>
          <p style={{ fontSize: 12.5, color: "var(--muted)", margin: "0 0 6px" }}>
            Paste any public YouTube / YouTube Music playlist link (or its id). It's added read-only
            unless you own it.
          </p>
          <div style={{ display: "flex", gap: 8 }}>
            <input
              spellCheck={false}
              autoCorrect="off"
              autoCapitalize="off"
              style={{ flex: 1 }}
              placeholder="https://music.youtube.com/playlist?list=…"
              value={addUrl}
              onChange={(e) => setAddUrl(e.currentTarget.value)}
              onKeyDown={(e) => e.key === "Enter" && addUrl.trim() && addPublicPlaylist(addUrl)}
            />
            <button className="primary" disabled={busy || !addUrl.trim()} onClick={() => addPublicPlaylist(addUrl)}>Add</button>
            <button
              disabled={busy}
              onClick={() => { setShowManage(false); setSpotifyResult(null); setSpotifyProgress(""); setSpotifyOpen(true); }}
            >
              Import from Spotify
            </button>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: 8, margin: "16px 0 6px", borderTop: "1px solid var(--border-subtle)", paddingTop: 14 }}>
            <span style={{ fontSize: 13, fontWeight: 600, flex: 1 }}>Your playlists</span>
            <button
              className="small"
              disabled={busy}
              title="Re-fetch the list of playlists from your YouTube Music account (e.g. after creating or deleting one elsewhere)"
              onClick={() => refreshPlaylists()}
            >
              Refresh list
            </button>
          </div>
          <p style={{ fontSize: 12.5, color: "var(--muted)", marginTop: 0 }}>
            Check the playlists you want in the sidebar. Right-click one for export, open, or delete.
            {` ${shown.size} of ${cache.playlists.length} shown.`}
          </p>
          <input spellCheck={false} autoCorrect="off" autoCapitalize="off"
            placeholder="Filter…"
            value={manageQuery}
            onChange={(e) => setManageQuery(e.currentTarget.value)}
            style={{ width: "100%", marginBottom: 8 }}
          />
          <div className="panel" style={{ maxHeight: "50vh", overflow: "auto" }}>
            {manageList.map((p) => (
              <label
                key={p.id}
                className="pl-row"
                onContextMenu={(e) =>
                  openMenu(e, [
                    { label: "Export to CSV…", onClick: () => exportPlaylist(p) },
                    { label: "Open in YouTube Music", onClick: () => openPlaylist(p.id) },
                    { label: "Delete playlist…", onClick: () => { setDeleteText(""); setDeleteTarget(p); } },
                  ])
                }
              >
                <input type="checkbox" checked={shown.has(p.id)} onChange={(e) => setPlaylistShown(p.id, e.currentTarget.checked)} />
                <span className="pl-title">{p.title}</span>
              </label>
            ))}
          </div>
        </Overlay>
      )}

      {detail && (
        <Overlay title={detail.title} onClose={() => setDetail(null)}>
          <p style={{ margin: "4px 0" }}><strong>Artist:</strong> {detail.artist || "—"}</p>
          <p style={{ margin: "8px 0 4px" }}><strong>Custom name</strong> (local, searchable):</p>
          <div style={{ display: "flex", gap: 8 }}>
            <input spellCheck={false} autoCorrect="off" autoCapitalize="off"
              style={{ flex: 1 }}
              placeholder="Your own name for this song…"
              value={customDraft}
              onChange={(e) => setCustomDraft(e.currentTarget.value)}
              onKeyDown={(e) => e.key === "Enter" && commitCustomName(detail.videoId, customDraft)}
            />
            <button className="primary" onClick={() => commitCustomName(detail.videoId, customDraft)}>Save</button>
            {customDraft && <button onClick={() => { setCustomDraft(""); commitCustomName(detail.videoId, ""); }}>Clear</button>}
          </div>
          <p style={{ margin: "4px 0", display: "flex", gap: 8, alignItems: "center" }}>
            <button className="small" onClick={() => openUrl(`https://music.youtube.com/watch?v=${detail.videoId}`)}>
              Open in YouTube Music
            </button>
            <code style={{ color: "var(--muted)" }}>{detail.videoId}</code>
          </p>
          <p style={{ margin: "12px 0 4px" }}><strong>In {detailMembership.length} loaded playlist(s):</strong></p>
          <div className="panel" style={{ maxHeight: "32vh", overflow: "auto" }}>
            {detailMembership.length === 0 ? (
              <p className="empty" style={{ padding: 10 }}>Not in any loaded playlist.</p>
            ) : (
              detailMembership.map((p) => (
                <div key={p.id} className="pl-row">
                  <span className="pl-title">{p.title}{editable.has(p.id) ? "" : " (read-only)"}</span>
                  <button className="small" onClick={() => openUrl(`https://music.youtube.com/playlist?list=${p.id}`)}>open</button>
                  {editable.has(p.id) && (
                    <button className="small danger" disabled={busy} onClick={() => removeOneFrom(detail, p)}>remove</button>
                  )}
                </div>
              ))
            )}
          </div>
          <p style={{ margin: "12px 0 4px" }}><strong>Add to a playlist:</strong></p>
          <div style={{ display: "flex", gap: 8 }}>
            <select
              style={{ flex: 1 }}
              value={detailAddTarget}
              onChange={(e) => setDetailAddTarget(e.currentTarget.value)}
            >
              <option value="">{detailAddTargets.length ? "Choose a playlist…" : "No editable sidebar playlists"}</option>
              {detailAddTargets.map((p) => (
                <option key={p.id} value={p.id}>{p.title}</option>
              ))}
            </select>
            <button
              className="primary"
              disabled={busy || !detailAddTarget}
              onClick={() => {
                const target = detailAddTargets.find((p) => p.id === detailAddTarget);
                if (target) addOneTo(detail, target);
                setDetailAddTarget("");
              }}
            >
              Add
            </button>
          </div>
        </Overlay>
      )}

      {addPicker && (
        <Overlay title={`Add ${selectedTracks.length} song(s) to…`} onClose={() => setAddPicker(false)}>
          <p style={{ color: "var(--muted)", fontSize: 12.5, marginTop: 0 }}>
            Pick one of your editable playlists from the sidebar.
          </p>
          <input spellCheck={false} autoCorrect="off" autoCapitalize="off" placeholder="Filter playlists…" value={addQuery} onChange={(e) => setAddQuery(e.currentTarget.value)} style={{ width: "100%", marginBottom: 8 }} />
          <div className="panel" style={{ maxHeight: "50vh", overflow: "auto" }}>
            {addTargets.map((p) => (
              <div key={p.id} className="pl-row" style={{ cursor: "pointer" }} onClick={() => addSelectedTo(p)}>
                <span className="pl-title">{p.title}</span>
                {cache.tracksByPlaylist[p.id] && <span className="pl-meta">{cache.tracksByPlaylist[p.id].length}</span>}
              </div>
            ))}
            {addTargets.length === 0 && <p className="empty">No editable playlists in the sidebar. Add some via Manage playlists.</p>}
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
              : "It isn’t cached locally, so its song list can’t be archived — load its songs first if you want recovery."}
          </p>
          <p style={{ fontSize: 13, margin: "10px 0 4px" }}>
            Type the playlist name <strong>{deleteTarget.title}</strong> to confirm:
          </p>
          <input spellCheck={false} autoCorrect="off" autoCapitalize="off"
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
                      persist({ ...cacheRef.current, deleted: cacheRef.current.deleted.filter((x) => !(x.id === d.id && x.deletedAt === d.deletedAt)) })
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
          <input spellCheck={false} autoCorrect="off" autoCapitalize="off"
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
            <input spellCheck={false} autoCorrect="off" autoCapitalize="off"
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
                <input spellCheck={false} autoCorrect="off" autoCapitalize="off" style={{ flex: 1 }} placeholder="New YouTube playlist name" value={spotifyName} onChange={(e) => setSpotifyName(e.currentTarget.value)} />
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

      {showRemoved && (
        <Overlay title="Removed songs (archived on update)" onClose={() => setShowRemoved(null)}>
          <p style={{ fontSize: 12.5, color: "var(--muted)", marginTop: 0 }}>
            Songs that disappeared from this playlist (deleted/taken down). The link is gone, but the
            title/artist are kept so you can find a replacement.
          </p>
          <div className="panel" style={{ maxHeight: "50vh", overflow: "auto" }}>
            {(cache.removedSongs[showRemoved] ?? []).map((t, i) => (
              <div key={i} className="pl-row">
                <span className="pl-title">{t.title}</span>
                <span className="pl-meta">{t.artist} · {relativeAge(t.removedAt)}</span>
                <button className="small" onClick={() => openUrl(ytSearchUrl(`${t.title} ${t.artist}`))}>search</button>
              </div>
            ))}
          </div>
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

      {showSettings && (
        <Overlay title="Settings" onClose={() => setShowSettings(false)}>
          <label className="setting">
            <input type="checkbox" checked={replaceNames} onChange={(e) => setReplaceNames(e.currentTarget.checked)} />
            Replace real titles with custom names (otherwise show both)
          </label>
          <label className="setting">
            <input type="checkbox" checked={autoDeleteQueues} onChange={(e) => setAutoDeleteQueues(e.currentTarget.checked)} />
            Delete leftover queues automatically when I quit
          </label>
          <label className="setting">
            <input type="checkbox" checked={autoRefreshOnLaunch} onChange={(e) => setAutoRefreshOnLaunch(e.currentTarget.checked)} />
            Refresh the playlist list automatically on launch
          </label>
          <label className="setting">
            <input type="checkbox" checked={checkUpdates} onChange={(e) => setCheckUpdates(e.currentTarget.checked)} />
            Check for updates on startup
          </label>
          <div style={{ borderTop: "1px solid var(--border-subtle)", marginTop: 12, paddingTop: 12, display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 13 }}>Signed in to YouTube Music</span>
            <span style={{ flex: 1 }} />
            <button
              className="danger"
              disabled={busy}
              onClick={async () => {
                setShowSettings(false);
                await signOut();
                setSignedIn(false);
                setSelected(new Set());
                setStatus("Signed out");
              }}
            >
              Sign out
            </button>
          </div>
          <p style={{ fontSize: 12, color: "var(--muted)", marginTop: 12, display: "flex", gap: 8, alignItems: "center" }}>
            YouTube Music Manager (beta)
            <button className="small" onClick={() => openUrl("https://github.com/hruif/YouTubeMusicPlaylistManager")}>Source</button>
          </p>
        </Overlay>
      )}

      {showTemp && (
        <Overlay title="Temporary playlists (queues)" onClose={() => setShowTemp(false)}>
          <p style={{ fontSize: 12.5, color: "var(--muted)", marginTop: 0 }}>
            Private playlists created by “Play in YouTube Music”. They live on your account until you
            delete them here.
          </p>
          {cache.tempPlaylists.length === 0 ? (
            <p className="empty">No queues.</p>
          ) : (
            <>
              <div className="panel" style={{ maxHeight: "50vh", overflow: "auto" }}>
                {cache.tempPlaylists.map((t) => (
                  <div key={t.id} className="pl-row">
                    <span className="pl-title">{t.title}</span>
                    <span className="pl-meta">{relativeAge(t.createdAt)}</span>
                    <button className="small" onClick={() => openPlaylist(t.id)}>open</button>
                    <button className="small" disabled={busy} onClick={() => deleteTemp(t.id)}>delete</button>
                  </div>
                ))}
              </div>
              <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
                <button
                  className="danger"
                  disabled={busy}
                  onClick={() =>
                    confirmAction(
                      `Delete all ${cache.tempPlaylists.length} queues?`,
                      "Permanently deletes every temporary playlist from your YouTube Music account.",
                      async () => {
                        setBusy(true);
                        const ids = cacheRef.current.tempPlaylists.map((t) => t.id);
                        let remaining = [...cacheRef.current.tempPlaylists];
                        for (const id of ids) {
                          try {
                            await deletePlaylist(id);
                            remaining = remaining.filter((t) => t.id !== id);
                            persist({ ...cacheRef.current, tempPlaylists: remaining });
                          } catch {
                            /* keep it in the list to retry */
                          }
                        }
                        setBusy(false);
                        setStatus(`Deleted ${ids.length - remaining.length} queue(s)`);
                      },
                    )
                  }
                >
                  Delete all
                </button>
              </div>
            </>
          )}
        </Overlay>
      )}

      {exitPrompt && (
        <Overlay title="Leftover queues" onClose={() => setExitPrompt(false)}>
          <p style={{ fontSize: 13 }}>
            You have {cache.tempPlaylists.length} temporary “Play in YouTube Music” queue(s) on your
            account. Delete them before closing?
          </p>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button onClick={() => setExitPrompt(false)}>Cancel</button>
            <button
              onClick={async () => {
                closingRef.current = true;
                await closeWindow();
              }}
            >
              Keep &amp; close
            </button>
            <button
              className="danger"
              onClick={async () => {
                closingRef.current = true;
                setExitPrompt(false);
                await deleteAllTemp();
                await closeWindow();
              }}
            >
              Delete &amp; close
            </button>
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

export default App;
