// Demo library for the website's live demo and screenshots: real songs in made-up playlists (no
// account data).
import type { Playlist, Track } from "../lib/ytmusic";

const palette = [
  ["#ff6b81", "#7b2ff7"], ["#f7971e", "#ffd200"], ["#00c6ff", "#0072ff"], ["#11998e", "#38ef7d"],
  ["#fc466b", "#3f5efb"], ["#f953c6", "#b91d73"], ["#4568dc", "#b06ab3"], ["#ee9ca7", "#ffdde1"],
  ["#43cea2", "#185a9d"], ["#ff5f6d", "#ffc371"], ["#654ea3", "#eaafc8"], ["#1d976c", "#93f9b9"],
];

// A small gradient square standing in for album art.
function art(i: number): string {
  const [a, b] = palette[i % palette.length];
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${a}"/><stop offset="1" stop-color="${b}"/></linearGradient></defs><rect width="60" height="60" fill="url(#g)"/><circle cx="42" cy="18" r="9" fill="#fff" fill-opacity=".22"/></svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

// The real YouTube Music video ids (looked up with a YouTube Music song search, 2026-09-26), so
// playing from the demo opens the actual songs. Same order as the list below.
const VIDEO_IDS = [
  "7ID-1jzek4Y", "swJOIjjW69U", "k49I5m1J6Is", "XDjB9E3YtUE",
  "r78xfXZb_WU", "4D7u5KF7SP8", "iMr69JihnP4", "9cHbvRUALrc",
  "Fx3b85eDQvw", "4texipD7faM", "aiTXImcbhoY", "D-6FeedpTpg",
  "NMRhx71bGo4", "PvM79DJ2PmM", "x6QJPJO2w40", "J7p4bzqLvCw",
  "OsfAnsMY21M", "-JIazHCRk9A", "VHb_XIql_gU", "rymYToIEL9o",
  "HzdD8kbDzZA", "U4zA0xnBEJU", "m_npTC0Rvgg", "pvC5YD-IjL0",
  "WKU8DJzipW4", "eQ6--TNre9k", "xMV6l2y67rk", "Sr_gTknZooY",
  "B2mmDEv0OEk", "wuJIqmha2Hk", "YkLLcIKhJ64", "1UjLFMg18cY",
];

export const DEMO_SONGS: Track[] = (
  [
    ["Midnight City", "M83", "Hurry Up, We're Dreaming", 243],
    ["Dreams", "Fleetwood Mac", "Rumours", 257],
    ["Redbone", "Childish Gambino", "Awaken, My Love!", 327],
    ["Heat Waves", "Glass Animals", "Dreamland", 239],
    ["Electric Feel", "MGMT", "Oracular Spectacular", 229],
    ["Get Lucky", "Daft Punk", "Random Access Memories", 369],
    ["Motion Sickness", "Phoebe Bridgers", "Stranger in the Alps", 230],
    ["Pink + White", "Frank Ocean", "Blonde", 184],
    ["Nights", "Frank Ocean", "Blonde", 307],
    ["Retrograde", "James Blake", "Overgrown", 223],
    ["Tadow", "Masego & FKJ", "Tadow", 301],
    ["Sunflower", "Rex Orange County", "Sunflower", 252],
    ["Let It Happen", "Tame Impala", "Currents", 467],
    ["The Less I Know the Better", "Tame Impala", "Currents", 216],
    ["Ivy", "Frank Ocean", "Blonde", 249],
    ["Blinding Lights", "The Weeknd", "After Hours", 200],
    ["Levitating", "Dua Lipa", "Future Nostalgia", 203],
    ["Good Days", "SZA", "Good Days", 279],
    ["Kids", "MGMT", "Oracular Spectacular", 302],
    ["Borderline", "Tame Impala", "The Slow Rush", 237],
    ["Take On Me", "a-ha", "Hunting High and Low", 225],
    ["Everybody Wants to Rule the World", "Tears for Fears", "Songs from the Big Chair", 251],
    ["Space Song", "Beach House", "Depression Cherry", 320],
    ["Holocene", "Bon Iver", "Bon Iver, Bon Iver", 336],
    ["Clair de Lune", "Claude Debussy", "Suite bergamasque", 300],
    ["Weightless", "Marconi Union", "Weightless", 480],
    ["Intro", "The xx", "xx", 127],
    ["Lost in Yesterday", "Tame Impala", "The Slow Rush", 249],
    ["September", "Earth, Wind & Fire", "The Best of EWF Vol. 1", 215],
    ["Mr. Blue Sky", "Electric Light Orchestra", "Out of the Blue", 303],
    ["Dancing Queen", "ABBA", "Arrival", 231],
    ["Don't Stop Me Now", "Queen", "Jazz", 209],
  ] as const
).map(([title, artist, album, duration], i) => ({ videoId: VIDEO_IDS[i], title, artist, album, duration, thumb: art(i) }));

const pick = (...idx: number[]) => idx.map((i) => DEMO_SONGS[i]);

export const DEMO_PLAYLISTS: Playlist[] = [
  { id: "night", title: "Late Night Drive" },
  { id: "sunday", title: "Sunday Morning" },
  { id: "gym", title: "Gym" },
  { id: "road", title: "Road Trip" },
  { id: "focus", title: "Focus" },
  { id: "summer", title: "Summer 2026" },
];

// "Gym" lists Get Lucky twice, so "Repeated within a playlist" and Remove repeats have something to find.
export const DEMO_TRACKS: Record<string, Track[]> = {
  night: pick(0, 2, 7, 8, 9, 10, 14, 22, 26, 3, 23, 1),
  sunday: pick(1, 11, 17, 23, 24, 7, 3, 12, 30, 22, 29),
  gym: pick(5, 15, 16, 12, 3, 19, 4, 18, 13, 5),
  road: pick(20, 21, 28, 29, 30, 31, 1, 4, 13, 16, 18, 3),
  focus: pick(24, 25, 26, 22, 23, 9, 10),
  summer: pick(15, 16, 17, 3, 11, 13, 19, 27, 28),
};

// What the demo opens with: two playlists selected, no update checks or launch refreshes.
export const DEMO_UI = { selected: ["night", "sunday"], autoRefreshOnLaunch: false, checkUpdates: false };
