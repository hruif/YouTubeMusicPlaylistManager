import { describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));
vi.mock("@tauri-apps/api/window", () => ({ getCurrentWindow: vi.fn() }));
vi.mock("@tauri-apps/api/webviewWindow", () => ({ getCurrentWebviewWindow: vi.fn() }));
vi.mock("@tauri-apps/plugin-opener", () => ({ openUrl: vi.fn() }));

const { cleanIpcError } = await import("./native");

describe("cleanIpcError", () => {
  it("strips Electron's remote-method prefix", () => {
    expect(cleanIpcError("Error invoking remote method 'invoke': Error: Sign-in timed out. Please try again.")).toBe(
      "Sign-in timed out. Please try again.",
    );
  });
  it("leaves other messages alone", () => {
    expect(cleanIpcError("Network down")).toBe("Network down");
  });
});
