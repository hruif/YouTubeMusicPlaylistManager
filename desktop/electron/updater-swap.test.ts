import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { execFileSync } from "node:child_process";
import { chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";

vi.mock("electron", () => ({ app: { isPackaged: true, getPath: vi.fn() } }));

const { installTarget, swapScript } = await import("./updater");

describe("installTarget", () => {
  it("installs next to the current copy under the new build's name", () => {
    expect(installTarget("/Applications/YouTube Music Manager.app", "YouTube Music Playlist Manager.app")).toBe(
      "/Applications/YouTube Music Playlist Manager.app",
    );
  });
});

// Runs the real swap script against temp folders, with `open`/`xattr` stubbed out so nothing launches.
describe("swapScript", () => {
  let root: string;
  let log: string;
  const bundle = (p: string, marker: string) => {
    mkdirSync(p, { recursive: true });
    writeFileSync(path.join(p, "marker"), marker);
  };
  const run = (dest: string, target: string, src: string) => {
    const script = path.join(root, "swap.sh");
    writeFileSync(script, swapScript({ pid: 2 ** 22 + 7, newApp: src, dest, target }));
    execFileSync("/bin/bash", [script], { env: { PATH: `${path.join(root, "bin")}:/usr/bin:/bin` } });
  };

  beforeEach(() => {
    root = mkdtempSync(path.join(os.tmpdir(), "ytmpm-swap-"));
    log = path.join(root, "calls.log");
    mkdirSync(path.join(root, "bin"));
    for (const cmd of ["open", "xattr"]) {
      const stub = path.join(root, "bin", cmd);
      writeFileSync(stub, `#!/bin/bash\necho "${cmd} $*" >> "${log}"\n`);
      chmodSync(stub, 0o755);
    }
  });
  afterEach(() => rmSync(root, { recursive: true, force: true }));

  it("replaces a renamed install with the new name and removes the old copy", () => {
    const dest = path.join(root, "Apps", "Old Name.app");
    const target = path.join(root, "Apps", "New Name.app");
    const src = path.join(root, "extract", "New Name.app");
    bundle(dest, "old");
    bundle(src, "new");
    run(dest, target, src);
    expect(existsSync(dest)).toBe(false);
    expect(readFileSync(path.join(target, "marker"), "utf8")).toBe("new");
    expect(existsSync(`${dest}.bak`)).toBe(false);
    expect(readFileSync(log, "utf8")).toContain(`open ${target}`);
  });

  it("replaces in place when the name is unchanged", () => {
    const dest = path.join(root, "Apps", "Same.app");
    const src = path.join(root, "extract", "Same.app");
    bundle(dest, "old");
    bundle(src, "new");
    run(dest, dest, src);
    expect(readFileSync(path.join(dest, "marker"), "utf8")).toBe("new");
  });

  it("falls back to the old path rather than touching another app already at the new name", () => {
    const dest = path.join(root, "Apps", "Old Name.app");
    const target = path.join(root, "Apps", "New Name.app");
    const src = path.join(root, "extract", "New Name.app");
    bundle(dest, "old");
    bundle(target, "someone else's");
    bundle(src, "new");
    run(dest, target, src);
    expect(readFileSync(path.join(target, "marker"), "utf8")).toBe("someone else's");
    expect(readFileSync(path.join(dest, "marker"), "utf8")).toBe("new");
  });

  it("escapes paths with shell metacharacters", () => {
    const dest = path.join(root, "Apps", 'We"ird $name`.app');
    const src = path.join(root, "extract", "Same.app");
    bundle(dest, "old");
    bundle(src, "new");
    run(dest, dest, src);
    expect(readFileSync(path.join(dest, "marker"), "utf8")).toBe("new");
  });
});
