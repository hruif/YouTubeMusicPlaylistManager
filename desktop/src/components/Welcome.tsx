export type SignInPhase = "booting" | "idle" | "waiting" | "failed";

// Signed-out screen. The line under the button always says what happens next: while waiting, where
// to finish signing in (Google's page opens in its own window); after a failure, what went wrong.
export function Welcome({ phase, error, onSignIn }: { phase: SignInPhase; error: string | null; onSignIn: () => void }) {
  return (
    <div className="welcome">
      <img className="welcome-icon" src="./icon.png" alt="" />
      <h2>YouTube Music Playlist Manager</h2>
      <p className="welcome-sub">Organize, clean up, and combine your playlists.</p>
      {phase === "booting" ? (
        <p className="welcome-note" role="status">Signing in…</p>
      ) : (
        <>
          <button className="primary big" disabled={phase === "waiting"} onClick={onSignIn}>
            {phase === "waiting" ? "Signing in…" : phase === "failed" ? "Try again" : "Sign in with Google"}
          </button>
          <p className={`welcome-note${phase === "failed" ? " warn" : ""}`} role="status" aria-live="polite">
            {phase === "waiting"
              ? "Finish signing in in the Google window that opened."
              : phase === "failed"
                ? error
                : "You sign in on Google’s own page. The app never stores your password."}
          </p>
        </>
      )}
    </div>
  );
}
