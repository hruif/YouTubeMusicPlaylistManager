import { describe, expect, it, vi } from "vitest";

vi.mock("electron", () => ({ app: { isPackaged: false, getAppPath: () => "/x", once: vi.fn(), removeListener: vi.fn() } }));

const { parseHelperResult } = await import("./auth");

describe("parseHelperResult", () => {
  it("returns the captured session from the last stdout line, ignoring AppKit noise", () => {
    const out = 'some AppKit log\n{"cookie":"SID=1","cookie_names":["SID"]}\n';
    expect(parseHelperResult(null, out)).toEqual({ cookie: "SID=1", cookie_names: ["SID"] });
  });

  it("returns null when the window was closed without signing in", () => {
    expect(parseHelperResult(null, "null\n")).toBeNull();
    expect(parseHelperResult(null, "not json")).toBeNull();
  });

  it("reports the timeout plainly instead of the raw command failure", () => {
    const err = Object.assign(new Error("Command failed: /path/login-helper"), { killed: true });
    expect(() => parseHelperResult(err, "")).toThrow("Sign-in timed out. Please try again.");
  });

  it("reports a crash with no output as an unexpected close", () => {
    expect(() => parseHelperResult(new Error("Command failed"), "")).toThrow("closed unexpectedly");
  });
});
