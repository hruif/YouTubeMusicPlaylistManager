// Cache schema version. Bump when a change to how tracks are parsed/stored means existing cached
// data must be re-fetched to be correct (old parsed rows can't be transformed in place — they have
// to be re-pulled with the current parser). loadCache() (./cache) drops the cached tracks on any upgrade.
// History: v1 forces a re-fetch so the 0.3.1 artist-fallback parse reaches caches written earlier;
// v2 re-fetches to pick up album and duration.
export const CACHE_VERSION = 2;
