// A fetch() implementation for youtubei.js that routes every request through the Rust
// `proxy_http_request` command, so the session cookies are attached server-side (the app's own
// tauri:// origin can't send youtube.com cookies cross-site).
//
// Adapted from JustAnotherMusicClient's tauriFetch (Apache-2.0); see ../../NOTICE.
//
// youtubei.js self-computes the SAPISIDHASH Authorization header for the default (www.youtube.com)
// origin, which covers writes. For YouTube Music requests (client name "67") the request must use
// the music.youtube.com origin, so we rewrite the URL and recompute the hash for that origin.

import { invoke } from "@tauri-apps/api/core";

type ProxyHttpResponse = {
  status: number;
  headers: Record<string, string>;
  body_base64: string;
};

function toBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i += 1) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function fromBase64(base64: string): Uint8Array {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

// Read headers without dropping `Cookie`. youtubei.js builds a standalone Headers (guard "none"),
// so iterating it preserves Cookie; a plain object/array is preserved as-is too.
function headersToObject(headers: HeadersInit | undefined): Record<string, string> {
  const out: Record<string, string> = {};
  if (!headers) return out;
  if (headers instanceof Headers) {
    headers.forEach((value, key) => {
      out[key] = value;
    });
  } else if (Array.isArray(headers)) {
    for (const [key, value] of headers) out[key] = value;
  } else {
    Object.assign(out, headers);
  }
  return out;
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

async function applyMusicCookieAuth(headers: Record<string, string>): Promise<void> {
  if (headers["x-youtube-client-name"] !== "67") return;
  const origin = "https://music.youtube.com";
  const cookie = headers.cookie ?? headers.Cookie;
  const sapisid =
    getCookieValue(cookie, "SAPISID") ?? getCookieValue(cookie, "__Secure-3PAPISID");
  if (sapisid) {
    const timestamp = Math.floor(Date.now() / 1000);
    const hash = await sha1Hex(`${timestamp} ${sapisid} ${origin}`);
    headers.authorization = `SAPISIDHASH ${timestamp}_${hash}`;
    headers["x-goog-request-time"] = timestamp.toString();
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

async function bodyToBase64(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<string | undefined> {
  let body: BodyInit | null | undefined = init?.body;
  if (body == null && input instanceof Request) {
    const buffer = await input.clone().arrayBuffer();
    return buffer.byteLength ? toBase64(new Uint8Array(buffer)) : undefined;
  }
  if (body == null) return undefined;
  if (typeof body === "string") return toBase64(new TextEncoder().encode(body));
  if (body instanceof ArrayBuffer) return toBase64(new Uint8Array(body));
  if (ArrayBuffer.isView(body)) {
    return toBase64(new Uint8Array(body.buffer, body.byteOffset, body.byteLength));
  }
  if (body instanceof Blob) return toBase64(new Uint8Array(await body.arrayBuffer()));
  return toBase64(new TextEncoder().encode(String(body)));
}

export async function tauriFetch(
  input: RequestInfo | URL,
  init?: RequestInit,
): Promise<Response> {
  const method = (
    init?.method ?? (input instanceof Request ? input.method : "GET")
  ).toUpperCase();

  const headers = headersToObject(
    init?.headers ?? (input instanceof Request ? input.headers : undefined),
  );
  await applyMusicCookieAuth(headers);

  const rawUrl =
    typeof input === "string"
      ? input
      : input instanceof URL
        ? input.toString()
        : input.url;
  const url = rewriteUrlForMusic(rawUrl, headers);

  const body_base64 = await bodyToBase64(input, init);

  const response = await invoke<ProxyHttpResponse>("proxy_http_request", {
    input: { method, url, headers, body_base64: body_base64 ?? null },
  });

  return new Response(fromBase64(response.body_base64), {
    status: response.status,
    headers: response.headers,
  });
}
