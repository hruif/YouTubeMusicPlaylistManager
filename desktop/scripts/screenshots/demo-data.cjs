// Made-up demo library for website screenshots (no real account data).
const palette = [
  ["#ff6b81", "#7b2ff7"], ["#f7971e", "#ffd200"], ["#00c6ff", "#0072ff"], ["#11998e", "#38ef7d"],
  ["#fc466b", "#3f5efb"], ["#f953c6", "#b91d73"], ["#4568dc", "#b06ab3"], ["#ee9ca7", "#ffdde1"],
  ["#43cea2", "#185a9d"], ["#ff5f6d", "#ffc371"], ["#654ea3", "#eaafc8"], ["#1d976c", "#93f9b9"],
];
// A small gradient square standing in for album art.
function art(i) {
  const [a, b] = palette[i % palette.length];
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${a}"/><stop offset="1" stop-color="${b}"/></linearGradient></defs><rect width="60" height="60" fill="url(#g)"/><circle cx="42" cy="18" r="9" fill="#fff" fill-opacity=".22"/></svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}
const songs = [
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
].map(([title, artist, album, duration], i) => ({ videoId: `demo${i}`, title, artist, album, duration, thumb: art(i) }));

const pick = (...idx) => idx.map((i) => songs[i]);
const tracksByPlaylist = {
  night: pick(0, 2, 7, 8, 9, 10, 14, 22, 26, 3, 23, 1),
  sunday: pick(1, 11, 17, 23, 24, 7, 3, 12, 30, 22, 29),
  gym: pick(5, 15, 16, 12, 3, 19, 4, 18, 13, 5),
  road: pick(20, 21, 28, 29, 30, 31, 1, 4, 13, 16, 18, 3),
  focus: pick(24, 25, 26, 22, 23, 9, 10),
  summer: pick(15, 16, 17, 3, 11, 13, 19, 27, 28),
};
const playlists = [
  { id: "night", title: "Late Night Drive" },
  { id: "sunday", title: "Sunday Morning" },
  { id: "gym", title: "Gym" },
  { id: "road", title: "Road Trip" },
  { id: "focus", title: "Focus" },
  { id: "summer", title: "Summer 2026" },
];
const now = Date.now();
module.exports = {
  cache: {
    version: 2,
    playlists,
    tracksByPlaylist,
    updatedAt: Object.fromEntries(playlists.map((p) => [p.id, now - 3600e3])),
    shown: playlists.map((p) => p.id),
    external: [],
    editable: playlists.map((p) => p.id),
    deleted: [],
    unmatched: {},
    customNames: {},
    removedSongs: {},
    tempPlaylists: [],
  },
};
