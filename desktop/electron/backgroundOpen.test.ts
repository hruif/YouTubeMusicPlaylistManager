import { describe, expect, it } from "vitest";
import { browserFamily, explainFailure, openTabScript, permissionCheckScript, unsupportedReason } from "./backgroundOpen";

describe("browserFamily", () => {
  it("knows the browsers that can add tabs over AppleScript", () => {
    expect(browserFamily("Google Chrome")).toBe("chromium");
    expect(browserFamily("Brave Browser")).toBe("chromium");
    expect(browserFamily("Arc")).toBe("chromium");
    expect(browserFamily("Safari")).toBe("safari");
    expect(browserFamily("Firefox")).toBeNull();
    expect(browserFamily("")).toBeNull();
  });
});

describe("openTabScript", () => {
  it("adds a tab without activating the browser, taking the URL as an argument", () => {
    const script = openTabScript("Google Chrome", "chromium");
    expect(script).toContain('tell application "Google Chrome"');
    expect(script).toContain("set theURL to item 1 of argv");
    expect(script).toContain("make new tab with properties {URL:theURL}");
    expect(script).not.toMatch(/activate/);
  });

  it("uses Safari's own terms for Safari", () => {
    const script = openTabScript("Safari", "safari");
    expect(script).toContain("set current tab to (make new tab with properties {URL:theURL})");
    expect(script).toContain("make new document with properties {URL:theURL}");
  });
});

describe("permissionCheckScript", () => {
  it("only talks to the browser if it's already running, so it never launches it", () => {
    expect(permissionCheckScript("Safari")).toMatch(/^if application "Safari" is running then/);
  });
});

describe("messages", () => {
  it("explains a denied permission and where to change it", () => {
    expect(explainFailure("Google Chrome", "execution error: Not authorized to send Apple events to Google Chrome. (-1743)")).toMatch(
      /Permission to control Google Chrome wasn't given.*Privacy & Security → Automation/,
    );
  });

  it("names the browser when it can't do background tabs", () => {
    expect(unsupportedReason("Firefox", true)).toMatch(/^Firefox can't open tabs in the background, so it opened normally\./);
    expect(unsupportedReason("Firefox", false)).not.toMatch(/opened normally/);
  });
});
