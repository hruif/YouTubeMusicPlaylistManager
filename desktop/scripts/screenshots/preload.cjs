// Stand-in for the app's Electron bridge: serves the demo library and accepts edits, so the real
// UI can be driven for screenshots without an account.
const { cache } = require("./demo-data.cjs");
window.electronAPI = {
  isElectron: true,
  invoke: async (cmd, args = {}) => {
    switch (cmd) {
      case "read_cache": return JSON.stringify(cache);
      case "try_silent_sign_in": return { cookie_names: ["SID"] };
      case "yt_account_info": return { name: "Demo" };
      case "yt_get_library": return cache.playlists;
      case "yt_remove_videos": return args.videoIds;
      default: return null;
    }
  },
  showWindow: async () => {}, setBackgroundColor: async () => {}, allowCloseAndQuit: async () => {},
  deferClose: async () => {}, openExternal: async () => {}, onCloseRequested: () => () => {},
  installUpdate: async () => false, onUpdateProgress: () => () => {}, onTracksProgress: () => () => {},
};
