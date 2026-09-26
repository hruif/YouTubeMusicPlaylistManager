import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  invoke,
  openExternal as openUrl,
  onCloseRequested,
  closeWindow,
  deferClose,
  isElectron,
  installUpdate,
  onUpdateProgress,
  onTracksProgress,
} from "./lib/native";
import {
  signIn,
  trySilentSignIn,
  signOut,
  getAccountInfo,
  getLibraryPlaylists,
  fetchTracksForPlaylists,
  combineFromCache,
  addVideos,
  removeVideos,
  removeRepeatedVideos,
  createPlaylist,
  deletePlaylist,
  getPlaylistTracks,
  getPlaylistTracksAfterRepeatRemoval,
  restoreVideos,
  parseYouTubePlaylistId,
  searchYouTubeMusicSongs,
  bestYoutubeMatch,
  type Playlist,
  type Track,
  type CombinedSong,
  type AccountInfo,
  type PlaylistPrivacy,
} from "./lib/ytmusic";
import { loadCache, saveCache, EMPTY_CACHE, type DeletedPlaylist, type LibraryCache } from "./lib/cache";
import type { SpotifyTrack } from "./lib/spotify";
import { checkForUpdate, checkForUpdateStrict, getCurrentVersion, type UpdateInfo } from "./lib/update";
import { STALE_MS } from "./lib/format";
import { DOUBLE_CLICK_MS } from "./hooks/useDoubleClick";
import { planRestore, repeatedWithinPlaylists, visibleSongsFor } from "./lib/songs";
import { applyTheme, loadUi, saveUi, type PlaylistSort, type SongFilters, type SortKey, type Theme } from "./lib/settings";
import { StatusArea, Toasts, type Progress, type Toast, type ToastAction } from "./components/Feedback";
import { HistoryMenu } from "./components/HistoryMenu";
import { GearIcon } from "./components/icons";
import { ContextMenu, menuAt, type MenuItem, type MenuState } from "./components/ContextMenu";
import { Welcome, type SignInPhase } from "./components/Welcome";
import { Sidebar } from "./components/Sidebar";
import { SongPane } from "./components/SongPane";
import { ConfirmDialog, ErrorDialog, ExitDialog, type ConfirmState } from "./components/dialogs/ConfirmDialog";
import { CreatePlaylistDialog } from "./components/dialogs/CreatePlaylistDialog";
import { DeletePlaylistDialog } from "./components/dialogs/DeletePlaylistDialog";
import { PlaylistPickerDialog } from "./components/dialogs/PlaylistPickerDialog";
import { ManagePlaylistsDialog } from "./components/dialogs/ManagePlaylistsDialog";
import { PlaylistInfoDialog } from "./components/dialogs/PlaylistInfoDialog";
import { SongDetailsDialog } from "./components/dialogs/SongDetailsDialog";
import { SpotifyImportDialog, TransferResultDialog, UnmatchedDialog } from "./components/dialogs/SpotifyDialogs";
import { RecentlyDeletedDialog, RemovedSongsDialog } from "./components/dialogs/ArchiveDialogs";
import { QueuesDialog } from "./components/dialogs/QueuesDialog";
import { SettingsDialog } from "./components/dialogs/SettingsDialog";
import "./App.css";

// A song's own fields, without the combined-view playlist membership.
const trackOf = ({ playlists: _playlists, ...track }: CombinedSong): Track => track;

function App() {
  const ui0 = useRef(loadUi()).current;
  const [progress, setProgress] = useState<Progress | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [loading, setLoading] = useState<Record<string, { loaded: number; total?: number }>>({}); // per-playlist song loading
  const [busy, setBusy] = useState(false);
  const [signedIn, setSignedIn] = useState(false);
  const [signInPhase, setSignInPhase] = useState<SignInPhase>("booting");
  const [signInError, setSignInError] = useState<string | null>(null);
  const [account, setAccount] = useState<AccountInfo | null>(null);
  const [cache, setCache] = useState<LibraryCache>({ ...EMPTY_CACHE });
  const [selected, setSelected] = useState<Set<string>>(() => new Set(ui0.selected));
  const [sortKey, setSortKey] = useState<SortKey>(ui0.sortKey);
  const [sortAsc, setSortAsc] = useState(ui0.sortAsc);
  const [filters, setFilters] = useState<SongFilters>(ui0.filters);
  const [query, setQuery] = useState("");
  const [showManage, setShowManage] = useState(false);
  const [detail, setDetail] = useState<CombinedSong | null>(null);
  const [playlistDetail, setPlaylistDetail] = useState<Playlist | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const [menu, setMenu] = useState<MenuState | null>(null);
  const [selectedSongs, setSelectedSongs] = useState<Set<string>>(new Set());
  const [activeIndex, setActiveIndex] = useState<number | null>(null); // keyboard cursor in visibleSongs
  // Refs updated every render so the once-mounted keydown listener sees current state.
  const keyHandlerRef = useRef<(e: KeyboardEvent) => void>(() => {});
  const lastSongIndex = useRef<number | null>(null);
  const lastClick = useRef<{ id: string; t: number } | null>(null);
  const [addPicker, setAddPicker] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [removePicker, setRemovePicker] = useState(false);
  const [confirm, setConfirm] = useState<ConfirmState | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Playlist | null>(null);
  const [showDeleted, setShowDeleted] = useState(false);
  const [error, setError] = useState<{ message: string; retry?: () => void } | null>(null);
  const [errorDetails, setErrorDetails] = useState(false);
  const [spotifyOpen, setSpotifyOpen] = useState(false);
  const [transferResult, setTransferResult] = useState<{ name: string; matched: number; unmatched: SpotifyTrack[] } | null>(null);
  const [showUnmatched, setShowUnmatched] = useState<string | null>(null);
  const [showRemoved, setShowRemoved] = useState<string | null>(null);
  const [showTemp, setShowTemp] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [replaceNames, setReplaceNames] = useState(ui0.replaceNames);
  const [autoDeleteQueues, setAutoDeleteQueues] = useState(ui0.autoDeleteQueues);
  const [checkUpdates, setCheckUpdates] = useState(ui0.checkUpdates);
  const [autoRefreshOnLaunch, setAutoRefreshOnLaunch] = useState(ui0.autoRefreshOnLaunch);
  const [queuePrivacy, setQueuePrivacy] = useState<PlaylistPrivacy>(ui0.queuePrivacy);
  const [playlistSort, setPlaylistSort] = useState<PlaylistSort>(ui0.playlistSort);
  const [theme, setTheme] = useState<Theme>(ui0.theme);
  const [exitPrompt, setExitPrompt] = useState(false);
  const [update, setUpdate] = useState<UpdateInfo | null>(null);
  const [checkingForUpdates, setCheckingForUpdates] = useState(false);
  const [updateCheckMessage, setUpdateCheckMessage] = useState<string | null>(null);
  // In-place install progress: null = idle, otherwise a status string ("Downloading… 42%").
  const [installingUpdate, setInstallingUpdate] = useState<string | null>(null);
  const currentVersion = getCurrentVersion();

  // Check for a newer release once on startup (best-effort), unless disabled in Settings.
  useEffect(() => {
    if (ui0.checkUpdates) void checkForUpdate().then(setUpdate);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Feedback, in three kinds:
  // - progress: what's running now (header, with a bar when the amount of work is known);
  // - notify: the outcome of something you did (a toast that fades on its own);
  // - fail: an error. It stays in the header, with Retry when the action can safely be repeated,
  //   until you dismiss it or start something else (see the busy effect below).
  function showProgress(label: string, done?: number, total?: number) {
    setProgress({ label, done, total });
  }
  const toastId = useRef(0);
  function notify(message: string, action?: ToastAction): number {
    const id = ++toastId.current;
    setToasts((prev) => [...prev.slice(-2), { id, message, action }]);
    return id;
  }
  function dismissToast(id: number) {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    if (undoRef.current?.toastId === id) undoRef.current = null;
  }
  function fail(message: string, retry?: () => void) {
    setError({ message, retry });
  }
  // Starting new work clears the last error (it was about the previous action) and, once the work
  // finishes, the progress readout.
  useEffect(() => {
    if (busy) setError(null);
    else setProgress(null);
  }, [busy]);
  const errText = (err: unknown) => (err instanceof Error ? err.message : String(err));

  async function checkUpdatesNow() {
    setCheckingForUpdates(true);
    setUpdateCheckMessage("Checking for updates...");
    try {
      const next = await checkForUpdateStrict();
      setUpdate(next);
      setUpdateCheckMessage(
        next
          ? canInstallInPlace(next)
            ? `Version ${next.version} is available — "Update & restart" installs it in place.`
            : `Version ${next.version} is available. Download the update, then replace the installed app.`
          : `You are up to date on version ${currentVersion}.`,
      );
    } catch (err) {
      setUpdateCheckMessage(`Could not check for updates: ${errText(err)}`);
    } finally {
      setCheckingForUpdates(false);
    }
  }

  // In-place install is available only in the packaged Electron app and only for releases that ship
  // the zipped-.app asset (older releases have just the .dmg → manual download).
  const canInstallInPlace = (u: UpdateInfo | null): u is UpdateInfo & { zipUrl: string } =>
    isElectron && !!u?.zipUrl;

  async function installInPlace() {
    if (!canInstallInPlace(update) || installingUpdate !== null) return;
    setInstallingUpdate("Starting…");
    const off = onUpdateProgress((pct) =>
      setInstallingUpdate(pct < 100 ? `Downloading… ${pct}%` : "Installing, the app will restart…"),
    );
    try {
      // Resolves as the app is quitting to swap the bundle and relaunch; if it returns without
      // quitting, something is off — surface it and let the user fall back to a manual download.
      await installUpdate(update.zipUrl);
    } catch (err) {
      off();
      setInstallingUpdate(null);
      fail(`Update failed: ${errText(err)}. You can download it manually instead.`);
    }
  }

  const ytSearchUrl = (q: string) => `https://music.youtube.com/search?q=${encodeURIComponent(q)}`;

  // Transfer a read Spotify playlist to a new YouTube Music playlist: match each track conservatively,
  // create from confident matches, persist the unmatched ones for manual follow-up.
  async function transferSpotify(name: string, tracks: SpotifyTrack[]) {
    setSpotifyOpen(false);
    setBusy(true);
    showProgress("Matching songs on YouTube Music", 0, tracks.length);
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
          showProgress("Matching songs on YouTube Music", done, tracks.length);
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
      showProgress(`Creating “${name}” with ${matchedIds.length} songs`);
      const newId = await createPlaylist(name, matchedIds);
      if (newId) {
        persist({
          ...cacheRef.current,
          playlists: [{ id: newId, title: name }, ...cacheRef.current.playlists],
          tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [newId]: matchedTracks },
          updatedAt: { ...cacheRef.current.updatedAt, [newId]: Date.now() },
          editable: [...new Set([...cacheRef.current.editable, newId])],
          shown: [...new Set([...cacheRef.current.shown, newId])], // a playlist you just made should show
          unmatched: unmatched.length ? { ...cacheRef.current.unmatched, [newId]: unmatched } : cacheRef.current.unmatched,
        });
      } else {
        await refreshPlaylists();
      }
      setTransferResult({ name, matched: matchedIds.length, unmatched });
      notify(`Transferred “${name}”: ${matchedIds.length} added, ${unmatched.length} unmatched`);
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
    if (failed) fail(`Couldn't delete ${failed} queue${failed === 1 ? "" : "s"}. They're still on your account.`);
  }
  // Changes are saved to disk a moment after they happen (debounced), so a quit right after a
  // change would lose it. Every way out saves first.
  async function saveAndClose() {
    await saveCache(cacheRef.current).catch(() => {});
    await closeWindow();
  }
  const saveAndCloseRef = useRef(saveAndClose);
  saveAndCloseRef.current = saveAndClose;
  useEffect(() => {
    // The window is held open until we call closeWindow() (Tauri: preventDefault+destroy; Electron:
    // main vetoes then we allow-close). So every path through the handler must end in closeWindow()
    // or a prompt.
    const unlisten = onCloseRequested(async () => {
      if (closingRef.current) return;
      if (cacheRef.current.tempPlaylists.length === 0) {
        closingRef.current = true;
        await saveAndCloseRef.current();
        return;
      }
      if (autoDeleteQueuesRef.current) {
        closingRef.current = true;
        await deferClose(); // deleting on the network may take longer than the force-quit timer
        await deleteAllTemp();
        await saveAndCloseRef.current();
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
  }
  // Stable indirection so the memoized-row callbacks don't depend on openDetails' identity.
  const openDetailsRef = useRef(openDetails);
  openDetailsRef.current = openDetails;
  function commitCustomName(videoId: string, value: string) {
    const v = value.trim();
    const next = { ...cacheRef.current.customNames };
    if (v) next[videoId] = v;
    else delete next[videoId];
    persist({ ...cacheRef.current, customNames: next });
  }

  // "Play in YouTube Music": YouTube Music has no streaming API, so we recreate the workaround —
  // build a temporary playlist from the songs and open it on music.youtube.com to play. Its privacy
  // follows the "Queue visibility" setting (default UNLISTED): unlisted/public links open even when
  // the user's browser is signed into a different Google account than the app, or signed out, whereas
  // a private queue shows a blank page there. The temp playlist is tracked for cleanup (Queues panel).
  async function playInYouTube(videoIds: string[], title: string) {
    if (videoIds.length === 0) return;
    // A single song needs no queue — just open the song directly.
    if (videoIds.length === 1) {
      openSong(videoIds[0]);
      return;
    }
    setBusy(true);
    showProgress(`Building queue “${title}”`);
    try {
      const newId = await createPlaylist(title, videoIds, queuePrivacy);
      if (newId) {
        const c = cacheRef.current;
        persist({
          ...c,
          // A queue is a real (owned) playlist, so put it in the master list immediately — the
          // Queues panel just *marks* which playlists are queues (tempPlaylists), rather than being a
          // parallel list. It's kept out of the sidebar (not in `shown`) and out of Manage (tempIds).
          playlists: c.playlists.some((p) => p.id === newId) ? c.playlists : [{ id: newId, title }, ...c.playlists],
          editable: [...new Set([...c.editable, newId])],
          tempPlaylists: [{ id: newId, title, createdAt: Date.now() }, ...c.tempPlaylists].slice(0, 50),
        });
        // YouTube needs a moment to index a brand-new playlist; opening immediately often shows a
        // blank page. A short wait makes the opened page actually show the songs.
        showProgress(`Building queue “${title}”`);
        await new Promise((r) => setTimeout(r, 1500));
        await openPlaylist(newId);
        notify(`Opened “${title}” (${videoIds.length} songs) in YouTube Music`);
      } else {
        fail("Created the queue, but couldn't open it. Find it under Queues.");
      }
    } catch (err) {
      fail(`Couldn't build the queue: ${errText(err)}`);
    } finally {
      setBusy(false);
    }
  }

  function deleteTemp(id: string) {
    setBusy(true);
    showProgress("Deleting queue");
    deletePlaylist(id)
      .then(() => {
        persist({ ...cacheRef.current, tempPlaylists: cacheRef.current.tempPlaylists.filter((t) => t.id !== id) });
        notify("Deleted queue");
      })
      .catch((err) => fail(`Couldn't delete the queue: ${errText(err)}`, () => deleteTemp(id)))
      .finally(() => setBusy(false));
  }

  // Remove a playlist from the app entirely (no YouTube call) — for playlists you don't own (can't
  // delete), e.g. URL-added public ones. Purges all local traces, including any archived removed/
  // unmatched songs keyed by its id.
  function removeFromCache(id: string) {
    const c = cacheRef.current;
    const tracksByPlaylist = { ...c.tracksByPlaylist };
    delete tracksByPlaylist[id];
    const updatedAt = { ...c.updatedAt };
    delete updatedAt[id];
    const removedSongs = { ...c.removedSongs };
    delete removedSongs[id];
    const unmatched = { ...c.unmatched };
    delete unmatched[id];
    persist({
      ...c,
      tempPlaylists: c.tempPlaylists.filter((t) => t.id !== id),
      playlists: c.playlists.filter((p) => p.id !== id),
      shown: c.shown.filter((x) => x !== id),
      external: c.external.filter((x) => x !== id),
      editable: c.editable.filter((x) => x !== id),
      tracksByPlaylist,
      updatedAt,
      removedSongs,
      unmatched,
    });
    setSelected((prev) => {
      const s = new Set(prev);
      s.delete(id);
      return s;
    });
    notify("Removed from your list");
  }

  // Interactive sign-in. Progress and failure show inline on the welcome screen, not in a popup.
  async function doSignIn() {
    setSignInPhase("waiting");
    setSignInError(null);
    try {
      await signIn();
      setSignedIn(true);
      setSignInPhase("idle");
      void getAccountInfo().then(setAccount).catch(() => setAccount(null));
      if (cacheRef.current.playlists.length === 0) await refreshPlaylists();

    } catch (err) {
      setSignInError(errText(err));
      setSignInPhase("failed");
    }
  }

  const openSong = (videoId: string) => void openUrl(`https://music.youtube.com/watch?v=${videoId}`);
  const openPlaylist = (id: string) => void openUrl(`https://music.youtube.com/playlist?list=${id}`);
  function openMenu(e: React.MouseEvent, items: MenuItem[]) {
    e.preventDefault();
    e.stopPropagation();
    setMenu(menuAt(e, items));
  }

  function openPlaylistDetailFromRow(e: React.MouseEvent, playlist: Playlist) {
    const target = e.target as HTMLElement;
    if (target.closest("button,input,select")) return;
    setPlaylistDetail(playlist);
  }

  function playlistMenuItems(playlist: Playlist, location: "sidebar" | "manage") {
    const removedCount = cache.removedSongs[playlist.id]?.length ?? 0;
    const unmatchedCount = cache.unmatched[playlist.id]?.length ?? 0;
    return [
      { label: "Playlist details", onClick: () => setPlaylistDetail(playlist) },
      { label: "Export to CSV…", onClick: () => exportPlaylist(playlist) },
      ...(location === "sidebar" ? [{ label: "Remove repeats", onClick: () => removeRepeats(playlist) }] : []),
      ...(removedCount ? [{ label: `Removed songs (${removedCount})`, onClick: () => setShowRemoved(playlist.id) }] : []),
      ...(unmatchedCount ? [{ label: `Unmatched from Spotify (${unmatchedCount})`, onClick: () => setShowUnmatched(playlist.id) }] : []),
      location === "sidebar"
        ? { label: "Remove from sidebar", onClick: () => setPlaylistShown(playlist.id, false) }
        : shown.has(playlist.id)
          ? { label: "Remove from sidebar", onClick: () => setPlaylistShown(playlist.id, false) }
          : { label: "Show in sidebar", onClick: () => setPlaylistShown(playlist.id, true) },
      { label: "Open in YouTube Music", onClick: () => openPlaylist(playlist.id) },
      ...(location === "manage"
        ? [
            cache.external.includes(playlist.id)
              ? { label: "Remove from list", onClick: () => removeFromCache(playlist.id) }
              : { label: "Delete playlist…", onClick: () => setDeleteTarget(playlist) },
          ]
        : []),
    ];
  }

  // Suppress the WebView's default right-click menu (reload/inspect) so we can use our own. Dismissal
  // is handled by the menu's own full-screen backdrop (see the render), so a dismiss click is
  // consumed there and can't also trigger the thing underneath it.
  useEffect(() => {
    const onCtx = (e: MouseEvent) => e.preventDefault();
    window.addEventListener("contextmenu", onCtx);
    return () => window.removeEventListener("contextmenu", onCtx);
  }, []);

  // Persist UI state on change.
  useEffect(() => {
    saveUi({ selected: [...selected], sortKey, sortAsc, filters, replaceNames, autoDeleteQueues, checkUpdates, autoRefreshOnLaunch, playlistSort, queuePrivacy, theme });
  }, [selected, sortKey, sortAsc, filters, replaceNames, autoDeleteQueues, checkUpdates, autoRefreshOnLaunch, playlistSort, queuePrivacy, theme]);
  useEffect(() => applyTheme(theme), [theme]);

  // The shift-click range anchor indexes into visibleSongs; reset it when that ordering changes
  // (sort/filter/search) so a range isn't computed across two different orderings.
  useEffect(() => {
    lastSongIndex.current = null;
    setActiveIndex(null);
  }, [sortKey, sortAsc, query, filters]);

  // Per-page loading progress for the sidebar's pies. Only playlists runUpdate is loading are
  // tracked, so other fetches (export, repeat checks) don't flash a pie.
  useEffect(
    () =>
      onTracksProgress(({ playlistId, loaded, total }) =>
        setLoading((prev) => (prev[playlistId] ? { ...prev, [playlistId]: { loaded, total } } : prev)),
      ),
    [],
  );

  // Keyboard shortcuts (listed in Settings). The listener mounts once and calls keyHandlerRef,
  // which is reassigned every render so it always sees current state.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => keyHandlerRef.current(e);
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
    setBusy(true);
    showProgress("Loading playlist");
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
        // A playlist you explicitly add by URL should appear in the sidebar, and be marked external
        // so a library refresh (which only returns YOUR playlists) doesn't wipe it.
        shown: [...new Set([...c.shown, id])],
        external: [...new Set([...c.external, id])],
      });
      setSelected(new Set([id]));
      notify(`Added “${name}” (${tracks.length} songs)`);
    } catch (err) {
      fail(`Couldn't add that playlist: ${errText(err)}`, () => addPublicPlaylist(input));
    } finally {
      setBusy(false);
    }
  }

  // `announce`: confirm with a toast (a user-requested refresh), vs. silent (launch, sign-in).
  async function refreshPlaylists(announce = false) {
    setBusy(true);
    showProgress("Refreshing playlist list");
    try {
      const library = await getLibraryPlaylists();
      const c = cacheRef.current; // latest, AFTER the await
      const libraryIds = new Set(library.map((p) => p.id));
      // getLibraryPlaylists only returns YOUR library, so re-append URL-added (external) playlists
      // that aren't in it — otherwise a refresh would silently drop them. Drop external markers that
      // are now in the library (e.g. you saved/created it since).
      const externalPlaylists = c.playlists.filter((p) => c.external.includes(p.id) && !libraryIds.has(p.id));
      const playlists = [...library, ...externalPlaylists];
      const liveIds = new Set(playlists.map((p) => p.id));
      // The sidebar is opt-in (cache.shown), so new playlists don't appear until added via Manage.
      // Queues are a *view* over real playlists, so reconcile them here: drop any queue whose
      // playlist no longer exists. A grace window protects a just-created queue the library landing
      // hasn't caught up to yet (eventual consistency).
      const grace = Date.now() - 120_000;
      persist({
        ...c,
        playlists,
        external: c.external.filter((id) => liveIds.has(id)),
        tempPlaylists: c.tempPlaylists.filter((t) => liveIds.has(t.id) || t.createdAt > grace),
      });
      if (announce) notify(`Found ${playlists.length} playlists`);
    } catch (err) {
      fail(`Couldn't refresh your playlists: ${errText(err)}`, () => refreshPlaylists(announce));
    } finally {
      setBusy(false);
    }
  }

  const started = useRef(false);
  useEffect(() => {
    if (started.current) return; // guard React StrictMode's double-invoke in dev
    started.current = true;
    (async () => {
      const { cache: cached, migrated } = await loadCache();
      setCache(cached);
      try {
        const names = await trySilentSignIn();
        if (names) {
          setSignedIn(true);
          setSignInPhase("idle");
          void getAccountInfo().then(setAccount).catch(() => setAccount(null));
          if (cached.tempPlaylists.length)
            notify(`${cached.tempPlaylists.length} leftover queue${cached.tempPlaylists.length === 1 ? "" : "s"} from last time. Find ${cached.tempPlaylists.length === 1 ? "it" : "them"} under the clock button.`);
          // Auto-refresh the playlist list on launch (Settings; default on). The list fetch is
          // cheap (1-3 requests); an empty cache, or a one-time post-update cache migration (which
          // cleared the cached tracks), always refreshes regardless of the setting.
          if (cached.playlists.length === 0 || ui0.autoRefreshOnLaunch || migrated) {
            await refreshPlaylists();
            // Launch top-up: fetch tracks for sidebar (shown) playlists whose cache is missing or
            // stale, so song counts are present on open instead of an empty "not cached" dot.
            // Deliberately conservative — sidebar-only, stale-only, low concurrency, and no timer
            // (no background polling) — to keep API traffic, and the app's ToS exposure, minimal.
            const c = cacheRef.current;
            const cutoff = Date.now() - STALE_MS;
            const staleShown = c.shown
              .map((id) => c.playlists.find((p) => p.id === id))
              .filter((p): p is Playlist => !!p && (!c.tracksByPlaylist[p.id] || !c.updatedAt[p.id] || c.updatedAt[p.id] < cutoff));
            if (staleShown.length) {
              staleShown.forEach((p) => autoTried.current.add(p.id));
              // Fire-and-forget: let boot finish and the signed-in UI show immediately; the top-up
              // runs in the background (runUpdate owns its own busy/status and error handling).
              void runUpdate(staleShown, 2);
            }
          }
        } else {
          setSignInPhase("idle");
        }
      } catch (err) {
        setSignInError(`Couldn't sign in automatically: ${errText(err)}`);
        setSignInPhase("failed");
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Stable playlist ordering (the library fetch order is unstable across refreshes). Default by name.
  const sortPlaylists = useCallback(
    (list: Playlist[]): Playlist[] => {
      const copy = [...list];
      if (playlistSort === "updated") {
        copy.sort((a, b) => (cache.updatedAt[b.id] ?? 0) - (cache.updatedAt[a.id] ?? 0));
      } else if (playlistSort === "count") {
        copy.sort((a, b) => (cache.tracksByPlaylist[b.id]?.length ?? 0) - (cache.tracksByPlaylist[a.id]?.length ?? 0));
      } else {
        copy.sort((a, b) => a.title.localeCompare(b.title));
      }
      return copy;
    },
    [playlistSort, cache.updatedAt, cache.tracksByPlaylist],
  );

  // The sidebar is opt-in: it shows only playlists the user has added (cache.shown), defaulting to
  // none. Adding playlists you want is friendlier than pruning a full list.
  const shown = useMemo(() => new Set(cache.shown), [cache.shown]);
  const visiblePlaylists = useMemo(
    () => sortPlaylists(cache.playlists.filter((p) => shown.has(p.id))),
    [cache.playlists, shown, sortPlaylists],
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

  // `announce`: confirm with a toast (an explicit refresh), vs. silent (auto-loading on select).
  async function runUpdate(list: Playlist[], concurrency = 4, announce = false) {
    if (list.length === 0) return;
    setBusy(true);
    showProgress("Loading songs", 0, list.length);
    setLoading((prev) => {
      const next = { ...prev };
      for (const p of list) next[p.id] = next[p.id] ?? { loaded: 0 };
      return next;
    });
    try {
      const { tracksByPlaylist, editableIds, notFoundIds, failures } = await fetchTracksForPlaylists(
        list,
        concurrency,
        (done, total, playlist) => {
          showProgress("Loading songs", done, total);
          setLoading((prev) => {
            const next = { ...prev };
            delete next[playlist.id];
            return next;
          });
        },
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
          .map((g) => ({ videoId: g.videoId, title: g.title, artist: g.artist, removedAt: now }));
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
        const removed = { ...next.removedSongs };
        const unm = { ...next.unmatched };
        const archived: LibraryCache["deleted"] = [];
        for (const id of notFoundIds) {
          const pl = cacheRef.current.playlists.find((p) => p.id === id);
          const t = cacheRef.current.tracksByPlaylist[id] ?? [];
          if (pl && t.length) archived.push({ id, title: pl.title, tracks: t, deletedAt: now });
          delete tracks[id];
          delete upd[id];
          delete removed[id];
          delete unm[id];
        }
        next = {
          ...next,
          playlists: next.playlists.filter((p) => !gone.has(p.id)),
          tracksByPlaylist: tracks,
          updatedAt: upd,
          removedSongs: removed,
          unmatched: unm,
          shown: next.shown.filter((id) => !gone.has(id)),
          external: next.external.filter((id) => !gone.has(id)),
          editable: next.editable.filter((id) => !gone.has(id)),
          tempPlaylists: next.tempPlaylists.filter((t) => !gone.has(t.id)),
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
        notFoundIds.length ? `${notFoundIds.length} deleted elsewhere` : "",
        removedCount ? `${removedCount} song${removedCount === 1 ? "" : "s"} removed since last time` : "",
      ].filter(Boolean);
      if (failures.length) {
        fail(
          `Couldn't load ${failures.length === 1 ? `“${failures[0].title}”` : `${failures.length} playlists`}.`,
          () => runUpdate(failures, concurrency, announce),
        );
      } else if (announce || extras.length) {
        notify(`Refreshed ${n} playlist${n === 1 ? "" : "s"}${extras.length ? ` · ${extras.join(" · ")}` : ""}`);
      }
    } catch (err) {
      fail(`Couldn't load songs: ${errText(err)}`, () => runUpdate(list, concurrency, announce));
    } finally {
      setLoading((prev) => {
        const next = { ...prev };
        for (const p of list) delete next[p.id];
        return next;
      });
      setBusy(false);
    }
  }

  const songs = useMemo(
    () => combineFromCache(selectedPlaylists, cache.tracksByPlaylist),
    [selectedPlaylists, cache.tracksByPlaylist],
  );

  // Keep the song selection in sync with the songs that actually exist. Deselecting a playlist or a
  // refresh can drop songs out of the list, and a lingering selection of gone songs is confusing.
  // (Pruned against `songs`, not the search-filtered view, so typing a filter doesn't deselect.)
  useEffect(() => {
    setSelectedSongs((prev) => {
      if (prev.size === 0) return prev;
      const present = new Set(songs.map((s) => s.videoId));
      const next = new Set([...prev].filter((id) => present.has(id)));
      return next.size === prev.size ? prev : next;
    });
  }, [songs]);

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

  // Closing "Manage playlists" loads tracks for any sidebar playlist that's never been fetched, so
  // its song count shows immediately instead of an empty "not cached" dot. Deferred to window-close
  // (rather than firing on each checkbox) so toggling a playlist on and back off — a misclick —
  // never triggers a fetch. autoTried caps each playlist at one automatic attempt per session.
  function closeManage() {
    setShowManage(false);
    const c = cacheRef.current;
    const toLoad = c.shown
      .map((id) => c.playlists.find((p) => p.id === id))
      .filter((p): p is Playlist => !!p && !c.tracksByPlaylist[p.id] && !autoTried.current.has(p.id));
    if (toLoad.length) {
      toLoad.forEach((p) => autoTried.current.add(p.id));
      void runUpdate(toLoad, 2);
    }
  }

  const editable = useMemo(() => new Set(cache.editable), [cache.editable]);
  const selectedTracks = useMemo(
    () => songs.filter((s) => selectedSongs.has(s.videoId)),
    [songs, selectedSongs],
  );
  // Targets for "Add to playlist": the playlists shown in the sidebar; ownership can't be reliably
  // detected up front, so editable-detected ones sort first and the add attempt reports rejection.
  // Only playlists in the sidebar that we can actually modify (owned) — no point listing read-only
  // ones you can't add to.
  const addTargets = useMemo(
    () => visiblePlaylists.filter((p) => editable.has(p.id)),
    [visiblePlaylists, editable],
  );

  // Add the selected songs to a playlist you own — optimistic, reverting on error.
  async function addSelectedTo(target: Playlist) {
    setAddPicker(false);
    const existing = cache.tracksByPlaylist[target.id] ?? [];
    const have = new Set(existing.map((t) => t.videoId));
    const toAdd = selectedTracks
      .filter((t) => !have.has(t.videoId))
      .map(trackOf);
    if (toAdd.length === 0) {
      notify(`All selected songs are already in ${target.title}`);
      return;
    }
    persist({
      ...cacheRef.current,
      tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [target.id]: [...existing, ...toAdd] },
    });
    setBusy(true);
    showProgress(`Adding ${toAdd.length} to ${target.title}`);
    try {
      await addVideos(target.id, toAdd.map((t) => t.videoId));
      // Adding a song back un-removes it: drop it from this playlist's "recently removed" archive.
      const addedIds = new Set(toAdd.map((t) => t.videoId));
      const prevRemoved = cacheRef.current.removedSongs[target.id] ?? [];
      const newRemoved = prevRemoved.filter((t) => !(t.videoId && addedIds.has(t.videoId)));
      if (newRemoved.length !== prevRemoved.length) {
        persist({
          ...cacheRef.current,
          removedSongs: { ...cacheRef.current.removedSongs, [target.id]: newRemoved },
        });
      }
      notifyWithUndo(`Added ${toAdd.length} to ${target.title}`, () => undoAdd(target, toAdd.map((t) => t.videoId)));
    } catch (err) {
      persist({ ...cacheRef.current, tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [target.id]: existing } });
      fail(`Add failed: ${errText(err)}`);
    } finally {
      setBusy(false);
    }
  }

  // Create a new playlist from the selected songs.
  async function createFromSelection(name: string) {
    const tracks = selectedTracks.map(trackOf);
    setCreateOpen(false);
    setBusy(true);
    showProgress(`Creating “${name}”`);
    try {
      const newId = await createPlaylist(name, tracks.map((t) => t.videoId));
      if (newId) {
        persist({
          ...cacheRef.current,
          playlists: [{ id: newId, title: name }, ...cacheRef.current.playlists],
          tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [newId]: tracks },
          updatedAt: { ...cacheRef.current.updatedAt, [newId]: Date.now() },
          editable: [...new Set([...cacheRef.current.editable, newId])],
          shown: [...new Set([...cacheRef.current.shown, newId])], // a playlist you just made should show
        });
        notify(`Created “${name}” with ${tracks.length} songs`);
      } else {
        showProgress(`Created “${name}” — refreshing list`);
        await refreshPlaylists();
      }
    } catch (err) {
      fail(`Create failed: ${errText(err)}`);
    } finally {
      setBusy(false);
    }
  }

  // ---- Undo for song edits ----
  // Offered only in the result toast, and by ⌘Z while that toast is showing: once it fades, the
  // chance to undo is gone (Removed songs and Recently deleted remain for later recovery).
  const undoRef = useRef<{ toastId: number; run: () => void } | null>(null);
  const busyRef = useRef(busy);
  busyRef.current = busy;
  function notifyWithUndo(message: string, run: () => void) {
    const id = notify(message, { label: "Undo", run });
    undoRef.current = { toastId: id, run };
  }
  function runUndo() {
    const undo = undoRef.current;
    if (!undo) return;
    dismissToast(undo.toastId);
    undo.run();
  }

  // Undo an add: remove exactly the songs that were added (they weren't in the playlist before).
  async function undoAdd(target: Playlist, videoIds: string[]) {
    if (busyRef.current) return fail("Wait for the current action to finish, then try again.");
    setBusy(true);
    showProgress(`Undoing add to ${target.title}`);
    try {
      const removed = new Set(await removeVideos(target.id, videoIds));
      const cur = cacheRef.current.tracksByPlaylist[target.id] ?? [];
      persist({
        ...cacheRef.current,
        tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [target.id]: cur.filter((t) => !removed.has(t.videoId)) },
      });
      notify(`Took ${removed.size} back out of ${target.title}`);
    } catch (err) {
      fail(`Couldn't undo: ${errText(err)}`);
    } finally {
      setBusy(false);
    }
  }

  // Undo a removal: put the songs back where they were. `before` is the playlist as it was before
  // the removal; each song goes back in front of the song that followed it then.
  async function undoRemove(target: Playlist, videoIds: string[], before: Track[]) {
    if (busyRef.current) return fail("Wait for the current action to finish, then try again.");
    const removed = new Set(videoIds);
    const items = planRestore(videoIds, before);
    setBusy(true);
    showProgress(`Putting songs back in ${target.title}`);
    try {
      const inPlace = await restoreVideos(target.id, items);
      // Re-read the playlist so the cache shows what YouTube Music actually has now.
      const { tracks } = await getPlaylistTracks(target.id);
      const archive = (cacheRef.current.removedSongs[target.id] ?? []).filter((r) => !(r.videoId && removed.has(r.videoId)));
      persist({
        ...cacheRef.current,
        tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [target.id]: tracks },
        updatedAt: { ...cacheRef.current.updatedAt, [target.id]: Date.now() },
        removedSongs: { ...cacheRef.current.removedSongs, [target.id]: archive },
      });
      notify(
        inPlace
          ? `Put ${items.length} back in ${target.title}`
          : `Put ${items.length} back in ${target.title}, but at the end of the playlist`,
      );
    } catch (err) {
      fail(`Couldn't undo: ${errText(err)}. Refresh the playlist to see where it stands.`);
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
      `Remove ${ids.length} song${ids.length === 1 ? "" : "s"} from “${target.title}”?`,
      "This removes them from the playlist on your YouTube Music account.",
      async () => {
        setBusy(true);
        showProgress(`Removing ${ids.length} from ${target.title}`);
        try {
          // Non-optimistic: update the cache to what was ACTUALLY removed (some songs may be
          // un-removable), then archive those into the playlist's "recently removed" list.
          const removedIds = new Set(await removeVideos(target.id, ids));
          const cur = cacheRef.current.tracksByPlaylist[target.id] ?? existing;
          const removed = cur.filter((t) => removedIds.has(t.videoId));
          const remaining = cur.filter((t) => !removedIds.has(t.videoId));
          const now = Date.now();
          const prevRemoved = cacheRef.current.removedSongs[target.id] ?? [];
          const seen = new Set(prevRemoved.map((r) => `${r.title}|${r.artist}`));
          const additions = removed
            .filter((g) => !seen.has(`${g.title}|${g.artist}`))
            .map((g) => ({ videoId: g.videoId, title: g.title, artist: g.artist, removedAt: now }));
          persist({
            ...cacheRef.current,
            tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [target.id]: remaining },
            removedSongs: { ...cacheRef.current.removedSongs, [target.id]: [...additions, ...prevRemoved].slice(0, 500) },
          });
          notifyWithUndo(
            removedIds.size < ids.length
              ? `Removed ${removedIds.size} of ${ids.length} from ${target.title} (some couldn't be removed)`
              : `Removed ${removedIds.size} from ${target.title}`,
            () => undoRemove(target, [...removedIds], cur),
          );
        } catch (err) {
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
      notify(`Already in “${target.title}”`);
      return;
    }
    const track = trackOf(song);
    persist({ ...cacheRef.current, tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [target.id]: [...existing, track] } });
    setBusy(true);
    showProgress(`Adding to “${target.title}”`);
    try {
      await addVideos(target.id, [song.videoId]);
      notifyWithUndo(`Added to “${target.title}”`, () => undoAdd(target, [song.videoId]));
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
        showProgress(`Removing from “${target.title}”`);
        try {
          await removeVideos(target.id, [song.videoId]);
          notifyWithUndo(`Removed from “${target.title}”`, () => undoRemove(target, [song.videoId], existing));
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
    setBusy(true);
    showProgress(`Deleting ${p.title}`);
    try {
      await deletePlaylist(p.id);
      const tracks = cache.tracksByPlaylist[p.id] ?? [];
      const tracksByPlaylist = { ...cache.tracksByPlaylist };
      delete tracksByPlaylist[p.id];
      const updatedAt = { ...cache.updatedAt };
      delete updatedAt[p.id];
      const removedSongs = { ...cacheRef.current.removedSongs };
      delete removedSongs[p.id];
      const unmatched = { ...cacheRef.current.unmatched };
      delete unmatched[p.id];
      const archived = { id: p.id, title: p.title, tracks, deletedAt: Date.now() };
      persist({
        ...cacheRef.current,
        playlists: cacheRef.current.playlists.filter((x) => x.id !== p.id),
        tracksByPlaylist,
        updatedAt,
        removedSongs,
        unmatched,
        shown: cacheRef.current.shown.filter((id) => id !== p.id),
        external: cacheRef.current.external.filter((id) => id !== p.id),
        editable: cacheRef.current.editable.filter((id) => id !== p.id),
        tempPlaylists: cacheRef.current.tempPlaylists.filter((t) => t.id !== p.id),
        deleted: [archived, ...cacheRef.current.deleted].slice(0, 30),
      });
      setSelected((prev) => {
        const s = new Set(prev);
        s.delete(p.id);
        return s;
      });
      notify(`Deleted “${p.title}”. You can recreate it from Recently deleted.`);
    } catch (err) {
      fail(`Delete failed: ${errText(err)}`);
    } finally {
      setBusy(false);
    }
  }

  // Recreate a deleted playlist from the local archive.
  async function recreateDeleted(d: DeletedPlaylist) {
    setShowDeleted(false);
    setBusy(true);
    showProgress(`Recreating “${d.title}”`);
    try {
      const newId = await createPlaylist(d.title, d.tracks.map((t) => t.videoId));
      if (newId) {
        persist({
          ...cacheRef.current,
          playlists: [{ id: newId, title: d.title }, ...cacheRef.current.playlists],
          tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [newId]: d.tracks },
          updatedAt: { ...cacheRef.current.updatedAt, [newId]: Date.now() },
          editable: [...new Set([...cacheRef.current.editable, newId])],
          shown: [...new Set([...cacheRef.current.shown, newId])], // a playlist you just made should show
        });
        notify(`Recreated “${d.title}” with ${d.tracks.length} songs`);
      } else {
        showProgress(`Recreated “${d.title}” — refreshing list`);
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
      showProgress(`Loading “${p.title}” to export`);
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
      notify(`“${p.title}” has no songs to export`);
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
      if (saved) notify(`Exported “${p.title}” (${tracks.length} songs)`);
    } catch (err) {
      fail(`Export failed: ${errText(err)}`);
    }
  }

  // Remove repeated songs (same video appearing more than once) within one playlist, keeping one.
  async function removeRepeats(p: Playlist) {
    if (busy) return;
    // Read YouTube first: older versions could hide repeats in the cache without removing them.
    const refreshTracks = async (removedVideoIds?: string[]) => {
      const { tracks } = removedVideoIds
        ? await getPlaylistTracksAfterRepeatRemoval(p.id, removedVideoIds)
        : await getPlaylistTracks(p.id);
      persist({
        ...cacheRef.current,
        tracksByPlaylist: { ...cacheRef.current.tracksByPlaylist, [p.id]: tracks },
        updatedAt: { ...cacheRef.current.updatedAt, [p.id]: Date.now() },
      });
      return tracks;
    };
    setBusy(true);
    showProgress(`Checking repeats in “${p.title}”`);
    let tracks: Track[];
    try {
      tracks = await refreshTracks();
    } catch (err) {
      fail(`Couldn't check repeats: ${errText(err)}`, () => removeRepeats(p));
      return;
    } finally {
      setBusy(false);
    }
    const counts = new Map<string, number>();
    for (const t of tracks) counts.set(t.videoId, (counts.get(t.videoId) ?? 0) + 1);
    const repeated = [...counts.entries()].filter(([, c]) => c > 1).map(([id]) => id);
    const extraCount = repeated.reduce((total, id) => total + counts.get(id)! - 1, 0);
    if (repeated.length === 0) {
      notify(`No repeats in “${p.title}”`);
      return;
    }
    confirmAction(
      `Remove ${extraCount} extra ${extraCount === 1 ? "copy" : "copies"} in “${p.title}”?`,
      "Keeps one copy of each song.\nNote: The first copy stays in its original position on YouTube Music.",
      async () => {
        setBusy(true);
        showProgress(`Removing repeats in ${p.title}`);
        try {
          const removedCount = await removeRepeatedVideos(p.id, repeated);
          const currentTracks = await refreshTracks(repeated);
          const remainingCounts = new Map<string, number>();
          for (const t of currentTracks) remainingCounts.set(t.videoId, (remainingCounts.get(t.videoId) ?? 0) + 1);
          const remaining = repeated.reduce((total, id) => total + Math.max(0, (remainingCounts.get(id) ?? 0) - 1), 0);
          if (remaining > 0) {
            fail(`YouTube Music still shows ${remaining} extra ${remaining === 1 ? "copy" : "copies"} in “${p.title}”. The playlist has been refreshed; try removing repeats again.`);
          } else {
            notify(`Removed ${removedCount} extra ${removedCount === 1 ? "copy" : "copies"} in ${p.title}`);
          }
        } catch (err) {
          // A failed request can still have applied some edits. Refresh the actual account state,
          // or invalidate the snapshot so the cache cannot falsely show a successful cleanup.
          let refreshError = "";
          try {
            await refreshTracks();
          } catch {
            const tracksByPlaylist = { ...cacheRef.current.tracksByPlaylist };
            const updatedAt = { ...cacheRef.current.updatedAt };
            delete tracksByPlaylist[p.id];
            delete updatedAt[p.id];
            persist({
              ...cacheRef.current,
              tracksByPlaylist,
              updatedAt,
            });
            refreshError = " Couldn't refresh the playlist; update it to see its current songs.";
          }
          fail(`Couldn't complete repeat removal: ${errText(err)}${refreshError}`);
        } finally {
          setBusy(false);
        }
      },
    );
  }

  const repeated = useMemo(
    () => repeatedWithinPlaylists(selectedPlaylists, cache.tracksByPlaylist),
    [selectedPlaylists, cache.tracksByPlaylist],
  );
  const visibleSongs = useMemo(
    () =>
      visibleSongsFor(songs, {
        query,
        filters,
        sortKey,
        sortAsc,
        customNames: cache.customNames,
        playlistCount: selectedPlaylists.length,
        repeated,
      }),
    [songs, query, filters, sortKey, sortAsc, cache.customNames, selectedPlaylists.length, repeated],
  );

  // Any modal open? Song shortcuts are suppressed while one is, so they can't act in the background.
  const anyModalOpen =
    !!menu || errorDetails || !!confirm || !!deleteTarget || exitPrompt || !!detail || !!playlistDetail || addPicker || removePicker ||
    createOpen || !!showUnmatched || !!showRemoved || spotifyOpen || !!transferResult || showTemp || showDeleted || showSettings || showManage;

  // Esc: dismiss the most-nested overlay (returns true if it closed something).
  function closeTopmost(): boolean {
    if (menu) return setMenu(null), true;
    if (errorDetails) return setErrorDetails(false), true;
    if (confirm) return setConfirm(null), true; // cancel — Esc never confirms a destructive action
    if (deleteTarget) return setDeleteTarget(null), true;
    if (exitPrompt) return setExitPrompt(false), true;
    if (detail) return setDetail(null), true;
    if (playlistDetail) return setPlaylistDetail(null), true;
    if (addPicker) return setAddPicker(false), true;
    if (removePicker) return setRemovePicker(false), true;
    if (createOpen) return setCreateOpen(false), true;
    if (showUnmatched) return setShowUnmatched(null), true;
    if (showRemoved) return setShowRemoved(null), true;
    if (transferResult) return setTransferResult(null), true;
    if (spotifyOpen) return setSpotifyOpen(false), true;
    if (showTemp) return setShowTemp(false), true;
    if (showDeleted) return setShowDeleted(false), true;
    if (showSettings) return setShowSettings(false), true;
    if (showManage) return closeManage(), true;
    if (error) return setError(null), true;
    return false;
  }

  // Delete/Backspace: remove the selected songs. One source playlist → remove directly (with the
  // usual confirm); several → open the picker to choose.
  function deleteSelected() {
    if (selectedSongs.size === 0) return;
    if (removeTargets.length === 1) removeSelectedFrom(removeTargets[0]);
    else if (removeTargets.length > 1) setRemovePicker(true);
  }

  // ↑/↓ move the keyboard cursor through the song list and select that song; with Shift, extend the
  // selection from the anchor (the same anchor Shift+click uses).
  function moveCursor(delta: number, extend: boolean) {
    if (visibleSongs.length === 0) return;
    const from = activeIndex ?? lastSongIndex.current;
    const next = from === null ? (delta > 0 ? 0 : visibleSongs.length - 1) : Math.min(visibleSongs.length - 1, Math.max(0, from + delta));
    setActiveIndex(next);
    if (extend && lastSongIndex.current !== null) {
      const [a, b] = [lastSongIndex.current, next].sort((x, y) => x - y);
      setSelectedSongs(new Set(visibleSongs.slice(a, b + 1).map((s) => s.videoId)));
    } else {
      setSelectedSongs(new Set([visibleSongs[next].videoId]));
      lastSongIndex.current = next;
    }
  }

  // Keyboard shortcuts (the list shown in Settings lives in SettingsDialog's SHORTCUTS).
  keyHandlerRef.current = (e: KeyboardEvent) => {
    const mod = e.metaKey || e.ctrlKey;
    const key = e.key.toLowerCase();
    if (e.key === "Escape") {
      // Esc works even while typing: close the topmost overlay, else clear the song selection.
      if (closeTopmost()) e.preventDefault();
      else if (signedIn && selectedSongs.size > 0) {
        e.preventDefault();
        setSelectedSongs(new Set());
        setActiveIndex(null);
      }
      return;
    }
    if (!signedIn || anyModalOpen) return;
    if (mod && key === ",") {
      e.preventDefault();
      setShowSettings(true);
      return;
    }
    if (mod && key === "f") {
      e.preventDefault();
      searchRef.current?.focus();
      searchRef.current?.select();
      return;
    }
    if (mod && key === "z" && !e.shiftKey && undoRef.current) {
      const el = document.activeElement as HTMLElement | null;
      // Inside a text field, ⌘Z belongs to the field.
      if (!(el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA"))) {
        e.preventDefault();
        runUndo();
        return;
      }
    }
    if (mod && key === "r") {
      e.preventDefault();
      if (!busy && selectedPlaylists.length) void runUpdate(selectedPlaylists, 4, true);
      return;
    }
    const el = document.activeElement as HTMLElement | null;
    const typing = !!el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable);
    if (typing) return;
    // Let a focused button handle its own Enter/Space.
    const onControl = !!el?.closest("button, a, summary");
    if (mod && key === "a") {
      e.preventDefault();
      setSelectedSongs(new Set(visibleSongs.map((s) => s.videoId)));
    } else if (e.key === "Delete" || e.key === "Backspace") {
      e.preventDefault();
      deleteSelected();
    } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      moveCursor(e.key === "ArrowDown" ? 1 : -1, e.shiftKey);
    } else if (e.key === "Enter" && !onControl && activeIndex !== null && visibleSongs[activeIndex]) {
      e.preventDefault();
      openDetails(visibleSongs[activeIndex]);
    }
  };

  function sortBy(key: SortKey) {
    if (sortKey === key) setSortAsc((a) => !a);
    else {
      setSortKey(key);
      setSortAsc(true);
    }
  }

  // Song selection: plain click = select one; Cmd/Ctrl+click = toggle; Shift+click = range.
  // Double-click (same row, fast) opens details — detected manually so a click after closing a
  // modal can't be mis-counted as a double-click on a different row.
  // Stable (useCallback) so the memoized SongRow only re-renders when visibleSongs/selection change.
  const onSongClick = useCallback(
    (e: React.MouseEvent, index: number) => {
      const song = visibleSongs[index];
      const id = song.videoId;
      const prev = lastClick.current;
      if (prev && prev.id === id && e.timeStamp - prev.t < DOUBLE_CLICK_MS) {
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
        setActiveIndex(index);
        setSelectedSongs((p) => {
          const next = new Set(p);
          if (next.has(id)) next.delete(id);
          else next.add(id);
          return next;
        });
        lastSongIndex.current = index;
      } else {
        setActiveIndex(index);
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
      const many = count > 1;
      const n = many ? `${count} ` : ""; // "5 " when multiple, "" for a single song
      openMenu(e, [
        // For a single song "Open in YouTube Music" below already covers it — only offer the queue
        // (which creates a temp playlist) when there's more than one.
        ...(many ? [{ label: `Play ${count} in YouTube Music`, onClick: () => playInYouTube(ids, `▶ Queue — ${count} songs`) }] : []),
        { label: `Add ${n}to playlist…`, onClick: () => setAddPicker(true) },
        { label: `Remove ${n}from playlist…`, onClick: () => setRemovePicker(true) },
        { label: many ? `New playlist from ${count} songs…` : "New playlist from this song…", onClick: () => setCreateOpen(true) },
        { label: "Set custom name…", onClick: () => openDetailsRef.current(s) },
        { label: "Open in YouTube Music", onClick: () => openSong(s.videoId) },
        { label: "Details", onClick: () => openDetailsRef.current(s) },
      ]);
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [visibleSongs, selectedSongs],
  );

  // Queue playlists are real (private) playlists, so the library fetch returns them — but they're
  // managed in Queues, not here, so keep them out of the Manage list.
  const tempIds = useMemo(() => new Set(cache.tempPlaylists.map((t) => t.id)), [cache.tempPlaylists]);
  // Live title from the master playlist list, so the Queues panel is a view over it (the marker's
  // stored title is only a fallback for the brief window before a refresh confirms the playlist).
  const titleById = useMemo(() => new Map(cache.playlists.map((p) => [p.id, p.title])), [cache.playlists]);
  const manageList = useMemo(
    () => sortPlaylists(cache.playlists.filter((p) => !tempIds.has(p.id))),
    [cache.playlists, tempIds, sortPlaylists],
  );

  async function signOutNow() {
    setShowSettings(false);
    await signOut();
    setSignedIn(false);
    setSignInPhase("idle");
    setAccount(null);
    // Wipe local state so the next account (or sign-in) starts clean — otherwise the previous
    // account's playlists/tracks linger in memory and get re-saved to disk.
    persist({ ...EMPTY_CACHE });
    setSelected(new Set());
    setSelectedSongs(new Set());
    autoTried.current = new Set();
  }

  function deleteAllQueues() {
    confirmAction(
      `Delete all ${cache.tempPlaylists.length} queues?`,
      "Permanently deletes every temporary playlist from your YouTube Music account.",
      async () => {
        setBusy(true);
        const ids = cacheRef.current.tempPlaylists.map((t) => t.id);
        const failed = new Set<string>();
        for (const id of ids) {
          try {
            await deletePlaylist(id);
          } catch {
            failed.add(id); // keep it in the list to retry
          }
        }
        // Persist once at the end, off the latest cache, keeping only the failures.
        persist({
          ...cacheRef.current,
          tempPlaylists: cacheRef.current.tempPlaylists.filter((t) => failed.has(t.id)),
        });
        setBusy(false);
        notify(`Deleted ${ids.length - failed.size} queue(s)`);
      },
    );
  }

  const searchSong = (t: { title: string; artist: string }) => void openUrl(ytSearchUrl(`${t.title} ${t.artist}`));
  const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;

  return (
    <main className="app">
      {update && (
        <div className="update-bar" role="status">
          {installingUpdate !== null ? (
            <span>{installingUpdate}</span>
          ) : (
            <>
              <span>Version {update.version} is available.</span>
              {canInstallInPlace(update) && <button className="small" onClick={installInPlace}>Update &amp; restart</button>}
              <button className="small" onClick={() => openUrl(update.url)}>
                {canInstallInPlace(update) ? "Download manually" : "Download update"}
              </button>
              <button className="small" onClick={() => setUpdate(null)}>Dismiss</button>
            </>
          )}
        </div>
      )}

      {signedIn ? (
        <>
          <header className="toolbar">
            <h1>YouTube Music Playlist Manager</h1>
            <StatusArea
              progress={busy ? progress : null}
              error={error}
              onRetry={() => {
                const retry = error?.retry;
                setError(null);
                retry?.();
              }}
              onDetails={() => setErrorDetails(true)}
              onDismiss={() => setError(null)}
            />
            <span className="grow" />
            <span className="actions">
              <button disabled={busy} onClick={() => setShowManage(true)}>Manage playlists</button>
              <HistoryMenu
                queueCount={cache.tempPlaylists.length}
                deletedCount={cache.deleted.length}
                disabled={busy}
                onQueues={() => setShowTemp(true)}
                onDeleted={() => setShowDeleted(true)}
              />
              <button className="icon-only" disabled={busy} onClick={() => setShowSettings(true)} aria-label="Settings" title="Settings (⌘,)">
                <GearIcon />
              </button>
            </span>
          </header>

          <div className="layout">
            <Sidebar
              playlists={visiblePlaylists}
              tracksByPlaylist={cache.tracksByPlaylist}
              updatedAt={cache.updatedAt}
              selected={selected}
              playlistSort={playlistSort}
              loading={loading}
              isStale={isStale}
              onSortChange={setPlaylistSort}
              onSelectAll={() => setSelected(new Set(visiblePlaylists.map((p) => p.id)))}
              onClear={() => setSelected(new Set())}
              onToggle={toggleSelected}
              onHide={(id) => setPlaylistShown(id, false)}
              onOpenDetails={openPlaylistDetailFromRow}
              onContextMenu={(e, p) => openMenu(e, playlistMenuItems(p, "sidebar"))}
              onManage={() => setShowManage(true)}
            />
            <SongPane
              searchRef={searchRef}
              query={query}
              onQueryChange={setQuery}
              filters={filters}
              onFiltersChange={setFilters}
              sortKey={sortKey}
              sortAsc={sortAsc}
              onSort={sortBy}
              songs={songs}
              visibleSongs={visibleSongs}
              playlistNames={selectedPlaylists.map((p) => p.title)}
              busy={busy}
              activeIndex={activeIndex}
              selectedSongs={selectedSongs}
              customNames={cache.customNames}
              replaceNames={replaceNames}
              onSongClick={onSongClick}
              onSongContextMenu={onSongContextMenu}
              onRefresh={() => runUpdate(selectedPlaylists, 4, true)}
              onPlayAll={() =>
                playInYouTube(
                  songs.map((s) => s.videoId),
                  `▶ ${selectedPlaylists.map((p) => p.title).join(", ").slice(0, 80) || "Queue"}`,
                )
              }
              onPlaySelected={() => playInYouTube([...selectedSongs], `▶ Queue — ${selectedSongs.size} songs`)}
              onAddSelected={() => setAddPicker(true)}
              onRemoveSelected={() => setRemovePicker(true)}
              onNewPlaylist={() => setCreateOpen(true)}
              onClearSelection={() => {
                setSelectedSongs(new Set());
                setActiveIndex(null);
              }}
            />
          </div>
        </>
      ) : (
        <Welcome phase={signInPhase} error={signInError} onSignIn={doSignIn} />
      )}

      {showManage && (
        <ManagePlaylistsDialog
          playlists={manageList}
          totalCount={cache.playlists.length}
          shown={shown}
          busy={busy}
          playlistSort={playlistSort}
          onSortChange={setPlaylistSort}
          onSetShown={setPlaylistShown}
          onAddByUrl={addPublicPlaylist}
          onRefreshList={() => refreshPlaylists()}
          onImportSpotify={() => {
            setShowManage(false);
            setSpotifyOpen(true);
          }}
          onOpenDetails={openPlaylistDetailFromRow}
          onContextMenu={(e, p) => openMenu(e, playlistMenuItems(p, "manage"))}
          onClose={closeManage}
        />
      )}

      {playlistDetail && (() => {
        const p = cache.playlists.find((x) => x.id === playlistDetail.id) ?? playlistDetail;
        const inSidebar = shown.has(p.id);
        return (
          <PlaylistInfoDialog
            playlist={p}
            tracks={cache.tracksByPlaylist[p.id]}
            updatedAt={cache.updatedAt[p.id]}
            removedCount={cache.removedSongs[p.id]?.length ?? 0}
            unmatchedCount={cache.unmatched[p.id]?.length ?? 0}
            owned={editable.has(p.id)}
            external={cache.external.includes(p.id)}
            inSidebar={inSidebar}
            queueCreatedAt={cache.tempPlaylists.find((t) => t.id === p.id)?.createdAt}
            busy={busy}
            onOpen={() => openPlaylist(p.id)}
            onExport={() => exportPlaylist(p)}
            onToggleSidebar={() => setPlaylistShown(p.id, !inSidebar)}
            onRemoveRepeats={() => removeRepeats(p)}
            onShowRemoved={() => setShowRemoved(p.id)}
            onShowUnmatched={() => setShowUnmatched(p.id)}
            onClose={() => setPlaylistDetail(null)}
          />
        );
      })()}

      {detail && (
        <SongDetailsDialog
          key={detail.videoId}
          song={detail}
          customName={cache.customNames[detail.videoId] ?? ""}
          membership={detailMembership}
          addTargets={detailAddTargets}
          editable={editable}
          busy={busy}
          onSaveCustomName={(name) => commitCustomName(detail.videoId, name)}
          onOpenSong={() => openSong(detail.videoId)}
          onOpenPlaylist={openPlaylist}
          onRemoveFrom={(p) => removeOneFrom(detail, p)}
          onAddTo={(p) => addOneTo(detail, p)}
          onClose={() => setDetail(null)}
        />
      )}

      {addPicker && (
        <PlaylistPickerDialog
          title={`Add ${plural(selectedTracks.length, "song")} to…`}
          playlists={addTargets}
          filterable
          emptyText="None of your sidebar playlists can be edited. Add playlists you own via Manage playlists."
          meta={(p) => (cache.tracksByPlaylist[p.id] ? String(cache.tracksByPlaylist[p.id].length) : null)}
          onPick={addSelectedTo}
          onClose={() => setAddPicker(false)}
        />
      )}

      {removePicker && (
        <PlaylistPickerDialog
          title={`Remove ${plural(selectedTracks.length, "song")} from…`}
          playlists={removeTargets}
          filterable={false}
          emptyText="The selected songs aren’t in any of the selected playlists."
          meta={(p) => `${(cache.tracksByPlaylist[p.id] ?? []).filter((t) => selectedSongs.has(t.videoId)).length} selected`}
          onPick={removeSelectedFrom}
          onClose={() => setRemovePicker(false)}
        />
      )}

      {confirm && <ConfirmDialog confirm={confirm} onClose={() => setConfirm(null)} />}

      {deleteTarget && (
        <DeletePlaylistDialog
          playlist={deleteTarget}
          cachedCount={cache.tracksByPlaylist[deleteTarget.id]?.length}
          onDelete={() => doDelete(deleteTarget)}
          onClose={() => setDeleteTarget(null)}
        />
      )}

      {showDeleted && (
        <RecentlyDeletedDialog
          deleted={cache.deleted}
          busy={busy}
          onRecreate={recreateDeleted}
          onForget={(d) =>
            persist({ ...cacheRef.current, deleted: cacheRef.current.deleted.filter((x) => !(x.id === d.id && x.deletedAt === d.deletedAt)) })
          }
          onClose={() => setShowDeleted(false)}
        />
      )}

      {createOpen && (
        <CreatePlaylistDialog
          songCount={selectedTracks.length}
          busy={busy}
          onCreate={createFromSelection}
          onClose={() => setCreateOpen(false)}
        />
      )}

      {spotifyOpen && (
        <SpotifyImportDialog
          busy={busy}
          onOpenUrl={(url) => void openUrl(url)}
          onFail={fail}
          onTransfer={transferSpotify}
          onClose={() => setSpotifyOpen(false)}
        />
      )}

      {transferResult && (
        <TransferResultDialog result={transferResult} onSearch={searchSong} onClose={() => setTransferResult(null)} />
      )}

      {showRemoved && (
        <RemovedSongsDialog
          songs={cache.removedSongs[showRemoved] ?? []}
          onOpenSong={openSong}
          onSearch={searchSong}
          onClose={() => setShowRemoved(null)}
        />
      )}

      {showUnmatched && (
        <UnmatchedDialog tracks={cache.unmatched[showUnmatched] ?? []} onSearch={searchSong} onClose={() => setShowUnmatched(null)} />
      )}

      {showSettings && (
        <SettingsDialog
          currentVersion={currentVersion}
          checkingForUpdates={checkingForUpdates}
          updateCheckMessage={updateCheckMessage}
          canInstall={canInstallInPlace(update)}
          hasUpdate={!!update}
          installingUpdate={installingUpdate}
          account={account}
          busy={busy}
          checkUpdates={checkUpdates}
          replaceNames={replaceNames}
          autoDeleteQueues={autoDeleteQueues}
          autoRefreshOnLaunch={autoRefreshOnLaunch}
          queuePrivacy={queuePrivacy}
          theme={theme}
          onCheckUpdates={checkUpdatesNow}
          onInstall={installInPlace}
          onDownload={() => update && openUrl(update.url)}
          onChange={(patch) => {
            if (patch.checkUpdates !== undefined) setCheckUpdates(patch.checkUpdates);
            if (patch.replaceNames !== undefined) setReplaceNames(patch.replaceNames);
            if (patch.autoDeleteQueues !== undefined) setAutoDeleteQueues(patch.autoDeleteQueues);
            if (patch.autoRefreshOnLaunch !== undefined) setAutoRefreshOnLaunch(patch.autoRefreshOnLaunch);
            if (patch.queuePrivacy !== undefined) setQueuePrivacy(patch.queuePrivacy);
            if (patch.theme !== undefined) setTheme(patch.theme);
          }}
          onSignOut={signOutNow}
          onOpenSource={() => openUrl("https://github.com/hruif/YouTubeMusicPlaylistManager")}
          onClose={() => setShowSettings(false)}
        />
      )}

      {showTemp && (
        <QueuesDialog
          queues={cache.tempPlaylists}
          titleById={titleById}
          busy={busy}
          onOpen={openPlaylist}
          onDelete={deleteTemp}
          onDeleteAll={deleteAllQueues}
          onClose={() => setShowTemp(false)}
        />
      )}

      {exitPrompt && (
        <ExitDialog
          queueCount={cache.tempPlaylists.length}
          onCancel={() => setExitPrompt(false)}
          onKeep={async () => {
            closingRef.current = true;
            await saveAndClose();
          }}
          onDelete={async () => {
            closingRef.current = true;
            setExitPrompt(false);
            await deleteAllTemp();
            await saveAndClose();
          }}
        />
      )}

      {error && errorDetails && <ErrorDialog message={error.message} onClose={() => setErrorDetails(false)} />}

      <Toasts toasts={toasts} onExpire={dismissToast} />

      {menu && <ContextMenu menu={menu} onClose={() => setMenu(null)} />}
    </main>
  );
}

export default App;
