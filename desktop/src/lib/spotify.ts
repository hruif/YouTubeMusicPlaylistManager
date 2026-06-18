// Read a public Spotify playlist's tracks with no user setup, by replicating Spotify's web player
// (ported from the Python app's spotapi). Stages: home page -> web-player bundle (fetchPlaylist
// GraphQL hash) -> TOTP access token -> client token -> paginated GraphQL pathfinder query.
//
// This is an UNOFFICIAL, fragile path: Spotify periodically changes the TOTP secret, the bundle, or
// the GraphQL hash, which can break it. The rotating secret comes from a community-maintained list.
// Every failure throws a SpotifyError with a clear message; callers must treat breakage as expected
// and non-fatal (show it, abort the import — never crash the app).

import { invoke } from "@tauri-apps/api/core";

export class SpotifyError extends Error {}
export type SpotifyTrack = { title: string; artist: string };

const CHROME_UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36";
const SECRETS_URL =
  "https://code.thetadev.de/ThetaDev/spotify-secrets/raw/branch/main/secrets/secretDict.json";
const FALLBACK_SECRET = { version: "18", bytes: [70, 60, 33, 57, 92, 120, 90, 33, 32, 62, 62, 55, 126, 93, 66, 35, 108, 68] };

function bytesToB64(bytes: Uint8Array): string {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s);
}
function b64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) out[i] = bin.charCodeAt(i);
  return out;
}

type ProxyResult = { status: number; text: string; getHeader: (name: string) => string | undefined };

async function proxyRequest(
  method: string,
  url: string,
  headers: Record<string, string> = {},
  body?: string,
): Promise<ProxyResult> {
  const res = await invoke<{ status: number; headers: Record<string, string>; body_base64: string }>(
    "proxy_http_request",
    {
      input: {
        method,
        url,
        headers: { "User-Agent": CHROME_UA, ...headers },
        body_base64: body != null ? bytesToB64(new TextEncoder().encode(body)) : null,
      },
    },
  );
  const text = new TextDecoder().decode(b64ToBytes(res.body_base64));
  const lower: Record<string, string> = {};
  for (const k of Object.keys(res.headers)) lower[k.toLowerCase()] = res.headers[k];
  return { status: res.status, text, getHeader: (n) => lower[n.toLowerCase()] };
}

// TOTP (HMAC-SHA1, 30s, 6 digits). Key = UTF-8 of the transformed, community-maintained secret.
async function generateTotp(): Promise<{ totp: string; version: string }> {
  let version = FALLBACK_SECRET.version;
  let bytes = FALLBACK_SECRET.bytes;
  try {
    const r = await proxyRequest("GET", SECRETS_URL);
    if (r.status === 200) {
      const secrets = JSON.parse(r.text) as Record<string, number[]>;
      const latest = Object.keys(secrets)
        .map(Number)
        .filter((n) => !Number.isNaN(n))
        .sort((a, b) => b - a)[0];
      if (latest != null && Array.isArray(secrets[String(latest)])) {
        version = String(latest);
        bytes = secrets[String(latest)];
      }
    }
  } catch {
    /* fall back to the bundled secret */
  }
  const keyBytes = new TextEncoder().encode(bytes.map((e, t) => e ^ ((t % 33) + 9)).join(""));
  const counter = Math.floor(Date.now() / 1000 / 30);
  const counterBuf = new ArrayBuffer(8);
  const dv = new DataView(counterBuf);
  dv.setUint32(0, Math.floor(counter / 2 ** 32));
  dv.setUint32(4, counter >>> 0);
  const key = await crypto.subtle.importKey("raw", keyBytes, { name: "HMAC", hash: "SHA-1" }, false, ["sign"]);
  const sig = new Uint8Array(await crypto.subtle.sign("HMAC", key, counterBuf));
  const offset = sig[sig.length - 1] & 0xf;
  const code =
    ((sig[offset] & 0x7f) << 24) |
    ((sig[offset + 1] & 0xff) << 16) |
    ((sig[offset + 2] & 0xff) << 8) |
    (sig[offset + 3] & 0xff);
  return { totp: (code % 1_000_000).toString().padStart(6, "0"), version };
}

type Session = {
  token: string;
  clientToken: string;
  clientVersion: string;
  hash: string;
  createdAt: number;
};
let session: Session | null = null;
const SESSION_TTL = 25 * 60 * 1000;

async function getSession(): Promise<Session> {
  if (session && Date.now() - session.createdAt < SESSION_TTL) return session;

  // 1. Home page → web-player bundle URL, client version, device id (sp_t cookie).
  const home = await proxyRequest("GET", "https://open.spotify.com");
  if (home.status !== 200) throw new SpotifyError(`Spotify home page returned ${home.status}`);
  const deviceId = (home.getHeader("set-cookie")?.match(/sp_t=([^;\s]+)/) ?? [])[1] ?? "";
  const html = home.text;
  const jsPack = [...html.matchAll(/<script[^>]+src="([^"]+\.js)"/g)]
    .map((m) => m[1])
    .find((u) => /web-player\/web-player.*\.js$/.test(u));
  if (!jsPack) throw new SpotifyError("Couldn't locate the Spotify web-player bundle (their site changed).");
  let clientVersion = "";
  try {
    const cfg = (html.split('<script id="appServerConfig" type="text/plain">')[1] ?? "").split("</script>")[0];
    clientVersion = JSON.parse(new TextDecoder().decode(b64ToBytes(cfg))).clientVersion ?? "";
  } catch {
    /* non-fatal */
  }

  // 2. fetchPlaylist GraphQL hash from the bundle.
  const js = await proxyRequest("GET", jsPack);
  const hash = js.text.match(/"fetchPlaylist","query","([0-9a-f]+)"/)?.[1];
  if (!hash) throw new SpotifyError("Couldn't find Spotify's playlist query hash (their web player changed).");

  // 3. Anonymous access token (TOTP).
  const { totp, version } = await generateTotp();
  const tokRes = await proxyRequest(
    "GET",
    `https://open.spotify.com/api/token?reason=init&productType=web-player&totp=${totp}&totpVer=${version}&totpServer=${totp}`,
  );
  let token = "";
  let clientId = "";
  try {
    const t = JSON.parse(tokRes.text);
    token = t.accessToken;
    clientId = t.clientId;
  } catch {
    /* handled below */
  }
  if (!token) throw new SpotifyError("Couldn't get a Spotify access token (the token method may have changed).");

  // 4. Client token.
  const ctBody = JSON.stringify({
    client_data: {
      client_version: clientVersion,
      client_id: clientId,
      js_sdk_data: {
        device_brand: "unknown",
        device_model: "unknown",
        os: "windows",
        os_version: "NT 10.0",
        device_id: deviceId,
        device_type: "computer",
      },
    },
  });
  const ctRes = await proxyRequest(
    "POST",
    "https://clienttoken.spotify.com/v1/clienttoken",
    { "Content-Type": "application/json", Accept: "application/json" },
    ctBody,
  );
  let clientToken = "";
  try {
    clientToken = JSON.parse(ctRes.text)?.granted_token?.token ?? "";
  } catch {
    /* handled below */
  }
  if (!clientToken) throw new SpotifyError("Couldn't get a Spotify client token.");

  session = { token, clientToken, clientVersion, hash, createdAt: Date.now() };
  return session;
}

export function parseSpotifyPlaylistId(input: string): string | null {
  const m = input.match(/playlist[/:]([A-Za-z0-9]+)/);
  if (m) return m[1];
  const t = input.trim();
  return /^[A-Za-z0-9]{22}$/.test(t) ? t : null;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function pathfinderPage(s: Session, id: string, offset: number, limit: number): Promise<any> {
  const variables = encodeURIComponent(
    JSON.stringify({ uri: `spotify:playlist:${id}`, offset, limit, enableWatchFeedEntrypoint: false }),
  );
  const extensions = encodeURIComponent(JSON.stringify({ persistedQuery: { version: 1, sha256Hash: s.hash } }));
  const res = await proxyRequest(
    "GET",
    `https://api-partner.spotify.com/pathfinder/v1/query?operationName=fetchPlaylist&variables=${variables}&extensions=${extensions}`,
    { Authorization: `Bearer ${s.token}`, "Client-Token": s.clientToken, "Spotify-App-Version": s.clientVersion },
  );
  if (res.status === 401 || res.status === 403) {
    session = null; // force a fresh session next time
    throw new SpotifyError(`Spotify rejected the request (${res.status}) — try again.`);
  }
  if (res.status !== 200) throw new SpotifyError(`Spotify playlist query returned ${res.status}.`);
  try {
    return JSON.parse(res.text);
  } catch {
    throw new SpotifyError("Spotify returned an unreadable response.");
  }
}

/** Fetch a public Spotify playlist's title + full track list (paginated). */
export async function fetchSpotifyPlaylist(
  input: string,
  onProgress?: (loaded: number, total: number) => void,
): Promise<{ title: string; tracks: SpotifyTrack[] }> {
  const id = parseSpotifyPlaylistId(input);
  if (!id) throw new SpotifyError("That doesn't look like a Spotify playlist link or ID.");
  const s = await getSession();

  const LIMIT = 100;
  const tracks: SpotifyTrack[] = [];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const collect = (content: any) => {
    for (const item of content?.items ?? []) {
      const d = item?.itemV2?.data;
      const title: string | undefined = d?.name;
      if (!title) continue;
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const artist = (d?.artists?.items ?? []).map((a: any) => a?.profile?.name).filter(Boolean).join(", ");
      tracks.push({ title, artist });
    }
  };

  const first = await pathfinderPage(s, id, 0, LIMIT);
  const pv = first?.data?.playlistV2;
  if (!pv || pv.__typename === "NotFound") throw new SpotifyError("Playlist not found, private, or unavailable.");
  const title: string = pv?.name ?? "Spotify playlist";
  const total: number = pv?.content?.totalCount ?? 0;
  collect(pv.content);
  onProgress?.(tracks.length, total);

  let offset = LIMIT;
  while (offset < total) {
    const page = await pathfinderPage(s, id, offset, LIMIT);
    collect(page?.data?.playlistV2?.content);
    onProgress?.(tracks.length, total);
    offset += LIMIT;
  }
  return { title, tracks };
}
