// YouTube Music data layer for the Electron main process: the youtubei.js client + all read/write
// operations, ported from src/lib/ytmusic.ts. The renderer calls these via IPC.
//
// Networking: in Node there's no CORS or forbidden-header restriction, so the Rust proxy collapses
// into a direct fetch(). We still port tauriFetch's auth fix — youtubei.js computes SAPISIDHASH for
// the www.youtube.com origin, but YouTube Music (client "67") requests run on music.youtube.com, so
// we rewrite the URL and recompute the hash for that origin (else Google ignores the auth, yt_li=0).

import { Innertube, YTNodes } from "youtubei.js";

export type Playlist = { id: string; title: string };
export type Track = {
  videoId: string;
  title: string;
  artist: string;
  thumb?: string;
  album?: string;
  duration?: number; // seconds
};
export type MatchCandidate = { videoId: string; title: string; artist: string };

let client: Innertube | null = null;

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function textFromMusicValue(value: any): string {
  if (!value) return "";
  if (typeof value === "string") return value;
  if (typeof value.text === "string") return value.text;
  if (typeof value.simpleText === "string") return value.simpleText;
  if (Array.isArray(value.runs)) return value.runs.map((run: { text?: string }) => run.text ?? "").join("");
  return "";
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function flexColumnText(item: any, index: number): string {
  const parsedColumn = item?.flex_columns?.[index];
  const rawColumn = item?.flexColumns?.[index]?.musicResponsiveListItemFlexColumnRenderer;
  return textFromMusicValue(parsedColumn?.title ?? parsedColumn?.text ?? rawColumn?.text ?? rawColumn?.title);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function firstByKey(node: any, key: string): any | null {
  if (!node || typeof node !== "object") return null;
  if (Array.isArray(node)) {
    for (const child of node) {
      const found = firstByKey(child, key);
      if (found) return found;
    }
    return null;
  }
  if (node[key]) return node[key];
  for (const childKey in node) {
    const found = firstByKey(node[childKey], key);
    if (found) return found;
  }
  return null;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function collectVideoIds(node: any, into: string[] = []): string[] {
  if (!node || typeof node !== "object") return into;
  if (Array.isArray(node)) {
    for (const child of node) collectVideoIds(child, into);
    return into;
  }
  if (typeof node.videoId === "string") into.push(node.videoId);
  for (const key in node) collectVideoIds(node[key], into);
  return into;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function extractVideoId(item: any): string | undefined {
  return (
    item?.id ||
    item?.playlistItemData?.videoId ||
    item?.endpoint?.payload?.videoId ||
    item?.title?.endpoint?.payload?.videoId ||
    item?.flex_columns?.[0]?.title?.endpoint?.payload?.videoId ||
    item?.flexColumns?.[0]?.musicResponsiveListItemFlexColumnRenderer?.text?.runs?.[0]?.navigationEndpoint?.watchEndpoint?.videoId ||
    item?.flexColumns?.[0]?.musicResponsiveListItemFlexColumnRenderer?.text?.runs?.[0]?.endpoint?.payload?.videoId ||
    collectVideoIds(item)[0]
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function extractArtist(item: any): string {
  const artists =
    (item?.artists ?? []).map((a: { name?: string }) => a?.name).filter(Boolean).join(", ") ||
    (item?.authors ?? []).map((a: { name?: string }) => a?.name).filter(Boolean).join(", ");
  return (
    artists ||
    textFromMusicValue(item?.subtitle) ||
    flexColumnText(item, 1) ||
    ""
  );
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function extractThumb(item: any): string | undefined {
  const thumbs =
    item?.thumbnail?.contents ??
    item?.thumbnail?.musicThumbnailRenderer?.thumbnail?.thumbnails ??
    item?.thumbnail?.thumbnails ??
    item?.thumbnails ??
    [];
  return thumbs[0]?.url;
}

// "3:45" / "1:02:03" -> seconds; undefined when the text isn't a clock time.
export function parseDuration(text: string): number | undefined {
  if (!/^\d+(:\d{1,2}){1,2}$/.test(text.trim())) return undefined;
  return text
    .trim()
    .split(":")
    .reduce((total, part) => total * 60 + Number(part), 0);
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function extractDuration(item: any): number | undefined {
  if (typeof item?.duration?.seconds === "number" && item.duration.seconds > 0) return item.duration.seconds;
  const fixed =
    item?.fixed_columns?.[0]?.title ??
    item?.fixed_columns?.[0]?.text ??
    item?.fixedColumns?.[0]?.musicResponsiveListItemFixedColumnRenderer?.text;
  return parseDuration(textFromMusicValue(fixed) || textFromMusicValue(item?.duration));
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function extractAlbum(item: any): string | undefined {
  if (typeof item?.album?.name === "string" && item.album.name) return item.album.name;
  // Playlist rows put the album in the third flex column (title · artist · album).
  return flexColumnText(item, 2) || undefined;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function extractTrackFromPlaylistItem(rawItem: any): Track | null {
  const item = rawItem?.musicResponsiveListItemRenderer ?? rawItem;
  if (!item || item?.type === "ContinuationItem") return null;
  const videoId = extractVideoId(item);
  const title = textFromMusicValue(item?.title) || flexColumnText(item, 0) || item?.name || "";
  if (!videoId || !title) return null;
  const track: Track = { videoId, title, artist: extractArtist(item), thumb: extractThumb(item) };
  const album = extractAlbum(item);
  const duration = extractDuration(item);
  if (album) track.album = album;
  if (duration) track.duration = duration;
  return track;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function findPlaylistRowList(node: any): any[] | null {
  if (!node || typeof node !== "object") return null;
  if (Array.isArray(node)) {
    if (node.some((el) => el?.musicResponsiveListItemRenderer)) return node;
    for (const child of node) {
      const found = findPlaylistRowList(child);
      if (found) return found;
    }
    return null;
  }
  for (const key in node) {
    const found = findPlaylistRowList(node[key]);
    if (found) return found;
  }
  return null;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function collectPlaylistRows(root: any): any[] {
  return (findPlaylistRowList(root) ?? [])
    .map((item) => item?.musicResponsiveListItemRenderer)
    .filter(Boolean);
}

// The continuation token for the playlist songs specifically: the trailing continuation item in
// the same list as the song rows, not the page-level related/suggestions continuation.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function nextPlaylistSongsToken(root: any): string | null {
  let token: string | null = null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const visit = (node: any): void => {
    if (token || !node || typeof node !== "object") return;
    if (Array.isArray(node)) {
      if (node.some((el) => el?.musicResponsiveListItemRenderer)) {
        for (const el of node) {
          const t = el?.continuationItemRenderer?.continuationEndpoint?.continuationCommand?.token;
          if (t) { token = t; return; }
        }
      }
      for (const el of node) { visit(el); if (token) return; }
      return;
    }
    for (const key in node) { visit(node[key]); if (token) return; }
  };
  visit(root);
  return token;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function rawPlaylistTitle(root: any): string {
  const header =
    firstByKey(root, "musicResponsiveHeaderRenderer") ??
    firstByKey(root, "musicEditablePlaylistDetailHeaderRenderer") ??
    firstByKey(root, "musicDetailHeaderRenderer");
  return textFromMusicValue(header?.title);
}

// youtubei.js authenticates by reading the literal `SAPISID` cookie; on .youtube.com it's often only
// present as `__Secure-3PAPISID` (same value), so alias it when missing.
export function normalizeCookie(cookie: string): string {
  if (/(?:^|;\s*)SAPISID=/.test(cookie)) return cookie;
  const match = cookie.match(/(?:^|;\s*)__Secure-3PAPISID=([^;]+)/);
  return match ? `${cookie}; SAPISID=${match[1]}` : cookie;
}

function getCookieValue(cookieHeader: string | undefined, name: string): string | null {
  if (!cookieHeader) return null;
  for (const part of cookieHeader.split(";")) {
    const [cookieName, ...valueParts] = part.trim().split("=");
    if (cookieName === name) return valueParts.join("=");
  }
  return null;
}

async function sha1Hex(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-1", new TextEncoder().encode(value));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function isYouTubeHost(host: string): boolean {
  return /(^|\.)youtube\.com$/.test(host) || /(^|\.)google\.com$/.test(host);
}

function headersToObject(headers: HeadersInit | undefined): Record<string, string> {
  const out: Record<string, string> = {};
  if (!headers) return out;
  if (headers instanceof Headers) headers.forEach((value, key) => (out[key] = value));
  else if (Array.isArray(headers)) for (const [k, v] of headers) out[k] = v;
  else Object.assign(out, headers);
  return out;
}

async function applyAuthHeaders(headers: Record<string, string>, host: string): Promise<void> {
  if (!isYouTubeHost(host)) return;
  const isMusic = headers["x-youtube-client-name"] === "67";
  const origin = isMusic ? "https://music.youtube.com" : "https://www.youtube.com";
  if (isMusic) {
    const cookie = headers.cookie ?? headers.Cookie;
    const sapisid = getCookieValue(cookie, "SAPISID") ?? getCookieValue(cookie, "__Secure-3PAPISID");
    if (sapisid) {
      const timestamp = Math.floor(Date.now() / 1000);
      const hash = await sha1Hex(`${timestamp} ${sapisid} ${origin}`);
      headers.authorization = `SAPISIDHASH ${timestamp}_${hash}`;
      headers["x-goog-request-time"] = timestamp.toString();
    }
  }
  headers.origin = origin;
  headers["x-origin"] = origin;
  headers.referer = `${origin}/`;
}

function rewriteUrlForMusic(inputUrl: string, headers: Record<string, string>): string {
  const url = new URL(inputUrl);
  if (
    headers["x-youtube-client-name"] === "67" &&
    url.hostname === "www.youtube.com" &&
    url.pathname.startsWith("/youtubei/")
  ) {
    url.hostname = "music.youtube.com";
  }
  return url.toString();
}

// fetch() for youtubei.js: applies the auth fix, then hits the network directly (Node = no CORS).
async function electronFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const method = (init?.method ?? (input instanceof Request ? input.method : "GET")).toUpperCase();
  const headers = headersToObject(init?.headers ?? (input instanceof Request ? input.headers : undefined));
  const rawUrl = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
  const url = rewriteUrlForMusic(rawUrl, headers);
  await applyAuthHeaders(headers, new URL(url).hostname);

  let body: BodyInit | undefined = init?.body ?? undefined;
  if (body == null && input instanceof Request) {
    const buf = await input.clone().arrayBuffer();
    body = buf.byteLength ? buf : undefined;
  }
  return fetch(url, { method, headers, body });
}

async function createClient(cookie: string): Promise<void> {
  client = await Innertube.create({
    cookie: normalizeCookie(cookie),
    fetch: electronFetch,
    generate_session_locally: true,
    retrieve_player: false,
  });
}

function requireClient(): Innertube {
  if (!client) throw new Error("Not signed in yet.");
  return client;
}

export async function setSession(cookie: string): Promise<void> {
  await createClient(cookie);
}
export function clearSession(): void {
  client = null;
}

// ---- operations (ported verbatim from src/lib/ytmusic.ts) ----

function normalizePlaylistId(playlistId: string): string {
  const id = playlistId.trim();
  return id.startsWith("VL") ? id.slice(2) : id;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function isPlaylistEditable(playlist: any): boolean {
  if (playlist?.header?.type === "MusicEditablePlaylistDetailHeader") return true;
  if (firstByKey(playlist, "musicEditablePlaylistDetailHeaderRenderer")) return true;
  try {
    const found = playlist?.page?.contents_memo?.getType(YTNodes.MusicEditablePlaylistDetailHeader);
    return !!found?.length;
  } catch {
    return false;
  }
}

export async function getLibraryPlaylists(): Promise<Playlist[]> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let library: any = await requireClient().music.getLibrary();
  const filter: string | undefined = (library.filters as string[] | undefined)?.find((f) => /playlist/i.test(f));
  if (filter) {
    try {
      library = await library.applyFilter(filter);
    } catch {
      /* fall back to the unfiltered landing page */
    }
  }
  const out: Playlist[] = [];
  const seen = new Set<string>();
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const take = (nodes: any[] | undefined): void => {
    for (const node of nodes ?? []) {
      const t = node?.title;
      const title = typeof t === "string" ? t : t?.text;
      const raw = node?.endpoint?.payload?.browseId ?? node?.id;
      if (!raw) continue;
      const id = String(raw).replace(/^VL/, "");
      if (!id.startsWith("PL")) continue;
      if (seen.has(id)) continue;
      seen.add(id);
      out.push({ id, title: title ?? "(untitled)" });
    }
  };
  for (const section of (library.contents as unknown[] | undefined) ?? []) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const s = section as any;
    take(s?.items ?? s?.contents);
  }
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let cont: any = library;
  let guard = 0;
  while (cont?.has_continuation && guard++ < 25) {
    cont = await cont.getContinuation();
    const c = cont?.contents;
    take(c?.items ?? c?.contents);
  }
  return out;
}

// The header's song count ("1,234 songs"), so loading progress can be shown as a fraction. Best
// effort: undefined when the header has no recognisable count (e.g. another UI language).
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function rawPlaylistSongCount(root: any): number | undefined {
  const header =
    firstByKey(root, "musicResponsiveHeaderRenderer") ??
    firstByKey(root, "musicEditablePlaylistDetailHeaderRenderer") ??
    firstByKey(root, "musicDetailHeaderRenderer");
  if (!header) return undefined;
  const texts: string[] = [];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const collect = (node: any): void => {
    if (!node || typeof node !== "object") return;
    if (typeof node.text === "string") texts.push(node.text);
    // Skip the title: a playlist called "50 songs I love" isn't a count.
    for (const key in node) if (key !== "title") collect(node[key]);
  };
  collect(header);
  for (const text of texts) {
    const m = text.match(/^\s*([\d,.]+)\s+(?:songs?|tracks?|videos?)\b/i);
    if (m) return Number(m[1].replace(/[,.]/g, ""));
  }
  return undefined;
}

export type LoadProgress = (loaded: number, total: number | undefined) => void;

async function getPlaylistRows(playlistId: string, onProgress?: LoadProgress) {
  const actions = requireClient().actions as unknown as {
    execute(endpoint: string, args: Record<string, unknown>): Promise<{ data?: unknown }>;
  };
  const browseId = `VL${normalizePlaylistId(playlistId)}`;
  // Keep raw rows until the caller has finished: playlistItemData identifies individual copies.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const rows: any[] = [];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const take = (root: any): void => {
    rows.push(...collectPlaylistRows(root));
  };
  let res = await actions.execute("/browse", { browseId, client: "YTMUSIC", parse: false });
  const editable = isPlaylistEditable(res?.data);
  const title = rawPlaylistTitle(res?.data);
  const total = rawPlaylistSongCount(res?.data);
  take(res?.data);
  onProgress?.(rows.length, total);
  let token = nextPlaylistSongsToken(res?.data);
  const visited = new Set<string>();
  while (token) {
    if (visited.has(token) || visited.size >= 60) {
      throw new Error("Couldn't load the complete playlist. Please try again.");
    }
    visited.add(token);
    res = await actions.execute("/browse", { continuation: token, client: "YTMUSIC", parse: false });
    take(res?.data);
    onProgress?.(rows.length, total);
    token = nextPlaylistSongsToken(res?.data);
  }
  return { rows, editable, title };
}

export async function getPlaylistTracks(
  playlistId: string,
  onProgress?: LoadProgress,
): Promise<{ tracks: Track[]; editable: boolean; title: string }> {
  const { rows, editable, title } = await getPlaylistRows(playlistId, onProgress);
  const tracks = rows.map(extractTrackFromPlaylistItem).filter((track): track is Track => track !== null);
  return { tracks, editable, title };
}

// Remove only the extra playlist entries for the confirmed song IDs. A video ID identifies the
// song, while playlistSetVideoId identifies one copy; deleting one then re-adding it leaves the
// same number of repeats. Read every songs page before editing and keep the first entry in place.
export async function removeRepeatedVideos(playlistId: string, videoIds: string[]): Promise<number> {
  const pid = normalizePlaylistId(playlistId);
  const client = requireClient();
  const wanted = new Set(videoIds);
  if (!wanted.size) return 0;
  const { rows } = await getPlaylistRows(pid);
  const seenVideos = new Set<string>();
  const seenSlots = new Set<string>();
  const editActions: { action: "ACTION_REMOVE_VIDEO"; setVideoId: string }[] = [];
  for (const row of rows) {
    const videoId = extractVideoId(row);
    if (!videoId || !wanted.has(videoId)) continue;
    const setVideoId = row?.playlistItemData?.playlistSetVideoId;
    // A repeated response row for the same slot is not another copy of the song.
    if (typeof setVideoId === "string" && setVideoId) {
      if (seenSlots.has(setVideoId)) continue;
      seenSlots.add(setVideoId);
    }
    if (seenVideos.has(videoId)) {
      if (typeof setVideoId !== "string" || !setVideoId) {
        throw new Error("YouTube Music didn't provide the details needed to remove every repeat. Try refreshing or signing in again.");
      }
      editActions.push({ action: "ACTION_REMOVE_VIDEO", setVideoId });
    } else {
      seenVideos.add(videoId);
    }
  }
  if (!editActions.length) return 0;
  const endpoint = new YTNodes.NavigationEndpoint({ playlistEditEndpoint: { playlistId: pid, actions: editActions } });
  const response = await endpoint.call(client.actions, { client: "YTMUSIC", parse: false });
  if (!response.success || response.status_code >= 400 || response.data?.status !== "STATUS_SUCCEEDED") {
    throw new Error("YouTube Music rejected the repeat removal. Refresh the playlist and try again.");
  }
  return editActions.length;
}

export async function addVideos(playlistId: string, videoIds: string[]): Promise<void> {
  await requireClient().playlist.addVideos(normalizePlaylistId(playlistId), videoIds);
}

// Removing a song needs its "set-video-id" — the id of the song's slot in *this* playlist, distinct
// from the videoId. youtubei.js's own removeVideos finds it by paging the playlist through the
// REGULAR YouTube client, which doesn't reliably see YouTube Music items and throws "There are no
// continuations". Instead we page the playlist through the YTMUSIC client (the same view the user
// sees) and read each slot's set-video-id straight from the raw JSON's `playlistItemData`, then
// remove via the edit endpoint directly.
//
// Returns the videoIds actually removed (ones not found in the playlist are skipped).
export async function removeVideos(playlistId: string, videoIds: string[]): Promise<string[]> {
  const pid = normalizePlaylistId(playlistId);
  const client = requireClient();
  const browseId = `VL${pid}`;
  const wanted = new Set(videoIds);
  // Two tiers of videoId -> set-video-id, both keyed by the wanted song's id. We prefer a slot match
  // (the id stored in the playlist slot itself) and only fall back to a wide match (the id found
  // anywhere in the row, e.g. the watch endpoint) for songs the slot id didn't catch.
  const slotMatch = new Map<string, string>();
  const wideMatch = new Map<string, string>();
  const matchedCount = (): number =>
    [...wanted].filter((id) => slotMatch.has(id) || wideMatch.has(id)).length;

  const actions = client.actions as unknown as {
    execute(endpoint: string, args: Record<string, unknown>): Promise<{ data?: unknown }>;
  };

  // Collect every videoId string anywhere under a node (a playlist row references its song's id in
  // several places — the slot's playlistItemData, the watch endpoint, the menu — and which one our
  // displayed id came from varies for "song" vs "video" items, so we match against all of them).
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const collectVideoIds = (node: any, into: Set<string>): void => {
    if (!node || typeof node !== "object") return;
    if (Array.isArray(node)) {
      for (const child of node) collectVideoIds(child, into);
      return;
    }
    if (typeof node.videoId === "string") into.add(node.videoId);
    for (const key in node) collectVideoIds(node[key], into);
  };

  // Record set-video-ids for any wanted song among this page's playlist rows. Only true playlist
  // members carry a playlistSetVideoId, so unrelated "related songs" rows are skipped automatically.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const scanRows = (node: any): void => {
    if (!node || typeof node !== "object") return;
    if (Array.isArray(node)) {
      for (const child of node) scanRows(child);
      return;
    }
    const renderer = node.musicResponsiveListItemRenderer;
    const setVideoId = renderer?.playlistItemData?.playlistSetVideoId;
    if (renderer && setVideoId) {
      const slotId = renderer.playlistItemData?.videoId;
      if (typeof slotId === "string" && wanted.has(slotId) && !slotMatch.has(slotId)) {
        slotMatch.set(slotId, setVideoId);
      }
      const ids = new Set<string>();
      collectVideoIds(renderer, ids);
      for (const id of ids) if (wanted.has(id) && !wideMatch.has(id)) wideMatch.set(id, setVideoId);
    }
    for (const key in node) scanRows(node[key]);
  };

  // The continuation token for the PLAYLIST SONGS specifically: the trailing continuationItemRenderer
  // that sits in the same list as the song rows. Critically NOT the section list's nextContinuationData
  // (that paginates the "related songs" suggestions and derails us off the actual track list).
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const nextSongsToken = (root: any): string | null => {
    let token: string | null = null;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const visit = (node: any): void => {
      if (token || !node || typeof node !== "object") return;
      if (Array.isArray(node)) {
        // A list holding song rows: its trailing continuationItemRenderer is the songs continuation.
        if (node.some((el) => el?.musicResponsiveListItemRenderer)) {
          for (const el of node) {
            const t = el?.continuationItemRenderer?.continuationEndpoint?.continuationCommand?.token;
            if (t) { token = t; return; }
          }
        }
        for (const el of node) { visit(el); if (token) return; }
        return;
      }
      for (const key in node) { visit(node[key]); if (token) return; }
    };
    visit(root);
    return token;
  };

  let res = await actions.execute("/browse", { browseId, client: "YTMUSIC", parse: false });
  scanRows(res?.data);
  let token = nextSongsToken(res?.data);
  let guard = 0;
  while (token && matchedCount() < wanted.size && guard++ < 60) {
    res = await actions.execute("/browse", { continuation: token, client: "YTMUSIC", parse: false });
    scanRows(res?.data);
    const next = nextSongsToken(res?.data);
    if (next === token) break; // no forward progress — stop rather than loop forever
    token = next;
  }

  // Resolve each wanted song to its set-video-id, preferring the slot match over the wide one.
  const resolved = new Map<string, string>(); // videoId -> set-video-id
  for (const id of wanted) {
    const setVideoId = slotMatch.get(id) ?? wideMatch.get(id);
    if (setVideoId) resolved.set(id, setVideoId);
  }
  if (resolved.size === 0) {
    throw new Error("Couldn't find the selected song(s) in this playlist to remove.");
  }

  const editActions = [...new Set(resolved.values())].map((setVideoId) => ({
    action: "ACTION_REMOVE_VIDEO",
    setVideoId,
  }));
  const endpoint = new YTNodes.NavigationEndpoint({ playlistEditEndpoint: { playlistId: pid, actions: editActions } });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  await endpoint.call(client.actions as any);
  return [...resolved.keys()];
}

// Undo a removal: re-add the songs, then move each back in front of the song that followed it
// before it was removed (`beforeVideoId`; null = it was last, so the end is already right).
// Adding always appends, so the re-added copy is the last row with that videoId. Returns false if
// the songs came back but couldn't be moved into place (they're then at the end of the playlist).
export async function restoreVideos(
  playlistId: string,
  items: { videoId: string; beforeVideoId: string | null }[],
): Promise<boolean> {
  const pid = normalizePlaylistId(playlistId);
  if (!items.length) return true;
  await addVideos(pid, items.map((i) => i.videoId));
  const moves = items.filter((i) => i.beforeVideoId);
  if (!moves.length) return true;

  const { rows } = await getPlaylistRows(pid);
  const slots = rows
    .map((row) => ({ videoId: extractVideoId(row), setVideoId: row?.playlistItemData?.playlistSetVideoId }))
    .filter((s): s is { videoId: string; setVideoId: string } => !!s.videoId && typeof s.setVideoId === "string");
  const restoredIds = new Set(items.map((i) => i.videoId));
  const lastSlot = (videoId: string) => [...slots].reverse().find((s) => s.videoId === videoId)?.setVideoId;
  // The successor's own slot: its first copy that isn't one of the songs just re-added.
  const successorSlot = (videoId: string) =>
    slots.find((s) => s.videoId === videoId && !(restoredIds.has(videoId) && s.setVideoId === lastSlot(videoId)))?.setVideoId;

  const editActions: { action: "ACTION_MOVE_VIDEO_BEFORE"; setVideoId: string; movedSetVideoIdSuccessor: string }[] = [];
  for (const item of moves) {
    const moved = lastSlot(item.videoId);
    const successor = successorSlot(item.beforeVideoId!);
    if (!moved || !successor) return false;
    // In original order, so songs that shared a successor keep their relative order.
    editActions.push({ action: "ACTION_MOVE_VIDEO_BEFORE", setVideoId: moved, movedSetVideoIdSuccessor: successor });
  }
  const endpoint = new YTNodes.NavigationEndpoint({ playlistEditEndpoint: { playlistId: pid, actions: editActions } });
  const response = await endpoint.call(requireClient().actions, { client: "YTMUSIC", parse: false });
  return !!response.success && response.status_code < 400 && response.data?.status === "STATUS_SUCCEEDED";
}

export type PlaylistPrivacy = "PRIVATE" | "UNLISTED" | "PUBLIC";

export async function createPlaylist(
  title: string,
  videoIds: string[],
  privacy: PlaylistPrivacy = "PRIVATE",
): Promise<string | undefined> {
  // youtubei.js's playlist.create() always makes a PRIVATE playlist and exposes no privacy option.
  // For anything else we hit the raw /playlist/create endpoint with privacyStatus. Queues are
  // created UNLISTED so the link opens in any browser — even one signed into a different Google
  // account, or signed out — instead of a blank "private playlist" page. The proven helper stays
  // the path for PRIVATE so the common create/transfer flows are unchanged.
  if (privacy === "PRIVATE") {
    const res = await requireClient().playlist.create(title, videoIds);
    return res.playlist_id;
  }
  try {
    const actions = requireClient().actions as unknown as {
      execute(endpoint: string, args: Record<string, unknown>): Promise<{ data?: { playlistId?: string } }>;
    };
    const res = await actions.execute("/playlist/create", {
      title,
      videoIds,
      privacyStatus: privacy,
      parse: false,
    });
    if (res?.data?.playlistId) return res.data.playlistId;
    // Some responses may not surface the id where we expect — fall through to the proven helper.
    throw new Error("create returned no playlistId");
  } catch (err) {
    // If the raw privacy-aware create is ever rejected (e.g. the endpoint stops accepting the extra
    // field), don't break the feature — fall back to a standard (private) playlist so playback still
    // works. The only downside is the cross-account "blank page" case the unlisted setting avoids.
    console.warn(`Unlisted playlist create failed, falling back to private: ${err instanceof Error ? err.message : String(err)}`);
    const res = await requireClient().playlist.create(title, videoIds);
    return res.playlist_id;
  }
}

export async function deletePlaylist(playlistId: string): Promise<void> {
  const actions = requireClient().actions as unknown as {
    execute(endpoint: string, args: Record<string, unknown>): Promise<{ success: boolean; status_code: number }>;
  };
  let res: { success: boolean; status_code: number };
  try {
    res = await actions.execute("/playlist/delete", {
      playlistId: normalizePlaylistId(playlistId),
      parse: false,
    });
  } catch (err) {
    // A playlist that's already gone (deleted elsewhere) is the goal of "delete" — treat as success.
    const msg = err instanceof Error ? err.message : String(err);
    if (/\b404\b|not[\s_-]?found/i.test(msg)) return;
    throw err;
  }
  if (res?.status_code === 404) return; // already gone — done
  const ok = res?.success !== false && (res?.status_code === undefined || res.status_code < 400);
  if (!ok) throw new Error(`YouTube rejected the delete (success=${res?.success}, status=${res?.status_code})`);
}

export async function searchYouTubeMusicSongs(query: string): Promise<MatchCandidate[]> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const res: any = await requireClient().music.search(query, { type: "song" });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const items: any[] = res?.songs?.contents ?? res?.contents?.find?.((c: any) => c?.contents)?.contents ?? [];
  const out: MatchCandidate[] = [];
  for (const item of items) {
    const videoId = extractVideoId(item);
    const title = textFromMusicValue(item?.title) || flexColumnText(item, 0);
    if (!videoId || !title) continue;
    out.push({ videoId, title, artist: extractArtist(item) });
  }
  return out;
}

export type AccountInfo = { name: string; handle?: string };

export async function getAccountInfo(): Promise<AccountInfo> {
  const info = await requireClient().account.getInfo();
  const contents = info as unknown as {
    contents?: {
      contents?: Array<{
        is_selected?: boolean;
        account_name?: { text?: string };
        channel_handle?: { text?: string };
      }>;
    };
  };
  const items = contents?.contents?.contents ?? [];
  // YouTube can return several accounts (multi-login); pick the active one, not just the first.
  const item = items.find((a) => a?.is_selected) ?? items[0];
  const name = item?.account_name?.text?.trim() || "Signed in";
  const handle = item?.channel_handle?.text?.trim() || undefined;
  return { name, handle };
}
