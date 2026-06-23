// YouTube Music data layer for the Electron main process: the youtubei.js client + all read/write
// operations, ported from src/lib/ytmusic.ts. The renderer calls these via IPC.
//
// Networking: in Node there's no CORS or forbidden-header restriction, so the Rust proxy collapses
// into a direct fetch(). We still port tauriFetch's auth fix — youtubei.js computes SAPISIDHASH for
// the www.youtube.com origin, but YouTube Music (client "67") requests run on music.youtube.com, so
// we rewrite the URL and recompute the hash for that origin (else Google ignores the auth, yt_li=0).

import { Innertube, YTNodes } from "youtubei.js";

export type Playlist = { id: string; title: string };
export type Track = { videoId: string; title: string; artist: string; thumb?: string };
export type MatchCandidate = { videoId: string; title: string; artist: string };

let client: Innertube | null = null;

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

export async function getPlaylistTracks(
  playlistId: string,
): Promise<{ tracks: Track[]; editable: boolean; title: string }> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let playlist: any = await requireClient().music.getPlaylist(playlistId);
  const editable = isPlaylistEditable(playlist);
  const h = playlist?.header?.title;
  const title: string = (typeof h === "string" ? h : h?.text) ?? "";
  const out: Track[] = [];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const take = (items: any[] | undefined): void => {
    for (const item of items ?? []) {
      const videoId: string | undefined = item?.id;
      const t = typeof item?.title === "string" ? item.title : item?.title?.text;
      if (!videoId || !t) continue;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const artist =
        (item?.artists ?? []).map((a: any) => a?.name).filter(Boolean).join(", ") ||
        (typeof item?.subtitle === "string" ? item.subtitle : item?.subtitle?.text) ||
        "";
      const thumbs = item?.thumbnail?.contents ?? item?.thumbnails ?? [];
      const thumb: string | undefined = thumbs[0]?.url;
      out.push({ videoId, title: t, artist, thumb });
    }
  };
  take(playlist.items);
  let guard = 0;
  while (playlist?.has_continuation && guard++ < 50) {
    playlist = await playlist.getContinuation();
    take(playlist.items);
  }
  return { tracks: out, editable, title };
}

export async function addVideos(playlistId: string, videoIds: string[]): Promise<void> {
  await requireClient().playlist.addVideos(normalizePlaylistId(playlistId), videoIds);
}

export async function removeVideos(playlistId: string, videoIds: string[]): Promise<void> {
  await requireClient().playlist.removeVideos(normalizePlaylistId(playlistId), videoIds);
}

export async function createPlaylist(title: string, videoIds: string[]): Promise<string | undefined> {
  const res = await requireClient().playlist.create(title, videoIds);
  return res.playlist_id;
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
    const videoId: string | undefined = item?.id;
    const title = typeof item?.title === "string" ? item.title : item?.title?.text;
    if (!videoId || !title) continue;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const artist =
      (item?.artists ?? []).map((a: any) => a?.name).filter(Boolean).join(", ") ||
      (typeof item?.subtitle === "string" ? item.subtitle : item?.subtitle?.text) ||
      "";
    out.push({ videoId, title, artist });
  }
  return out;
}

export async function getAccountInfo(): Promise<string> {
  const info = await requireClient().account.getInfo();
  const contents = info as unknown as {
    contents?: { contents?: Array<{ account_name?: { text?: string } }> };
  };
  return contents?.contents?.contents?.[0]?.account_name?.text ?? "Signed in";
}
