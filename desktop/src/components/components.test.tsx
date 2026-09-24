// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Overlay } from "./Overlay";
import { FilterMenu } from "./FilterMenu";
import { StatusArea, Toasts } from "./Feedback";
import { Sidebar } from "./Sidebar";
import { HistoryMenu } from "./HistoryMenu";
import { Welcome } from "./Welcome";

describe("Overlay", () => {
  it("closes only from its Close button, never from a click on the backdrop", async () => {
    const onClose = vi.fn();
    const { container } = render(<Overlay title="Info" onClose={onClose}><p>body</p></Overlay>);
    await userEvent.click(container.querySelector(".overlay")!);
    await userEvent.click(container.querySelector(".overlay")!);
    expect(onClose).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("is a labelled modal dialog that takes focus and keeps Tab inside", async () => {
    render(
      <Overlay title="Rename" onClose={() => {}}>
        <input aria-label="Name" />
        <button>Save</button>
      </Overlay>,
    );
    expect(screen.getByRole("dialog", { name: "Rename" })).toHaveAttribute("aria-modal", "true");
    expect(screen.getByLabelText("Name")).toHaveFocus();
    await userEvent.tab(); // Save
    await userEvent.tab(); // wraps to Close (first focusable)
    expect(screen.getByRole("button", { name: "Close" })).toHaveFocus();
  });
});

describe("FilterMenu", () => {
  it("toggles filters and shows how many are on", async () => {
    const onChange = vi.fn();
    const { rerender } = render(<FilterMenu filters={{ duplicates: false, unavailable: false }} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: "Filter" }));
    await userEvent.click(screen.getByLabelText("Unavailable"));
    expect(onChange).toHaveBeenCalledWith({ duplicates: false, unavailable: true });
    rerender(<FilterMenu filters={{ duplicates: true, unavailable: true }} onChange={onChange} />);
    expect(screen.getByRole("button", { name: "Filter · 2" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(onChange).toHaveBeenLastCalledWith({ duplicates: false, unavailable: false });
  });

  it("Esc closes the popover without reaching the window's handler", async () => {
    const onWindowKey = vi.fn();
    window.addEventListener("keydown", onWindowKey);
    render(<FilterMenu filters={{ duplicates: false, unavailable: false }} onChange={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: "Filter" }));
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByLabelText("Unavailable")).not.toBeInTheDocument();
    expect(onWindowKey.mock.calls.some(([e]) => e.key === "Escape")).toBe(false);
    window.removeEventListener("keydown", onWindowKey);
  });
});

describe("StatusArea", () => {
  const noop = () => {};

  it("shows an error with Retry and Dismiss, and the full message on click", async () => {
    const onRetry = vi.fn();
    const onDetails = vi.fn();
    const onDismiss = vi.fn();
    render(
      <StatusArea progress={null} error={{ message: "Couldn't load “Gym”.", retry: noop }} onRetry={onRetry} onDetails={onDetails} onDismiss={onDismiss} />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Couldn't load “Gym”.");
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    await userEvent.click(screen.getByRole("button", { name: "Dismiss error" }));
    await userEvent.click(screen.getByText("Couldn't load “Gym”."));
    expect([onRetry, onDismiss, onDetails].map((f) => f.mock.calls.length)).toEqual([1, 1, 1]);
  });

  it("offers no Retry when the action can't safely be repeated", () => {
    render(<StatusArea progress={null} error={{ message: "Remove failed" }} onRetry={noop} onDetails={noop} onDismiss={noop} />);
    expect(screen.queryByRole("button", { name: "Retry" })).not.toBeInTheDocument();
  });

  it("shows progress as a count and bar when the total is known, a spinner otherwise", () => {
    const { container, rerender } = render(
      <StatusArea progress={{ label: "Loading songs", done: 1, total: 4 }} error={null} onRetry={noop} onDetails={noop} onDismiss={noop} />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Loading songs 1/4");
    expect(container.querySelector<HTMLElement>(".progress-bar i")!.style.width).toBe("25%");
    rerender(<StatusArea progress={{ label: "Deleting queue" }} error={null} onRetry={noop} onDetails={noop} onDismiss={noop} />);
    expect(container.querySelector(".spinner")).toBeInTheDocument();
  });
});

describe("Toasts", () => {
  it("expire on their own, later when they carry an action, and pause while hovered", () => {
    vi.useFakeTimers();
    const onExpire = vi.fn();
    render(
      <Toasts
        toasts={[
          { id: 1, message: "Exported" },
          { id: 2, message: "Removed 2", action: { label: "Undo", run: () => {} } },
        ]}
        onExpire={onExpire}
      />,
    );
    act(() => vi.advanceTimersByTime(4100));
    expect(onExpire.mock.calls.map(([id]) => id)).toEqual([1]);
    fireEvent.mouseEnter(screen.getByText("Removed 2").parentElement!);
    act(() => vi.advanceTimersByTime(10_000));
    expect(onExpire).not.toHaveBeenCalledWith(2);
    fireEvent.mouseLeave(screen.getByText("Removed 2").parentElement!);
    act(() => vi.advanceTimersByTime(8100));
    expect(onExpire).toHaveBeenCalledWith(2);
    vi.useRealTimers();
  });

  it("runs the action and dismisses the toast", async () => {
    const run = vi.fn();
    const onExpire = vi.fn();
    render(<Toasts toasts={[{ id: 3, message: "Removed", action: { label: "Undo", run } }]} onExpire={onExpire} />);
    await userEvent.click(screen.getByRole("button", { name: "Undo" }));
    expect(run).toHaveBeenCalledOnce();
    expect(onExpire).toHaveBeenCalledWith(3);
  });
});

describe("Sidebar", () => {
  const base = {
    playlists: [{ id: "a", title: "Gym" }, { id: "b", title: "Road Trip" }],
    tracksByPlaylist: { a: [{ videoId: "v", title: "t", artist: "" }] },
    updatedAt: { a: Date.now() },
    playlistSort: "name" as const,
    isStale: () => false,
    onSortChange: () => {},
    onToggle: () => {},
    onHide: () => {},
    onOpenDetails: () => {},
    onContextMenu: () => {},
    onManage: () => {},
  };

  it("has one Select all / Clear button that flips once everything is selected", async () => {
    const onSelectAll = vi.fn();
    const onClear = vi.fn();
    const { rerender } = render(<Sidebar {...base} loading={{}} selected={new Set(["a"])} onSelectAll={onSelectAll} onClear={onClear} />);
    await userEvent.click(screen.getByRole("button", { name: "Select all" }));
    expect(onSelectAll).toHaveBeenCalled();
    rerender(<Sidebar {...base} loading={{}} selected={new Set(["a", "b"])} onSelectAll={onSelectAll} onClear={onClear} />);
    await userEvent.click(screen.getByRole("button", { name: "Clear" }));
    expect(onClear).toHaveBeenCalled();
  });

  it("shows a loading pie in place of the song count", () => {
    render(<Sidebar {...base} loading={{ a: { loaded: 100, total: 400 } }} selected={new Set()} onSelectAll={() => {}} onClear={() => {}} />);
    expect(screen.getByRole("img", { name: "Loading 100 of 400 songs" })).toBeInTheDocument();
    expect(screen.queryByText("1")).not.toBeInTheDocument();
  });
});

describe("HistoryMenu", () => {
  it("shows a dot only when there's something in it, and opens Queues / Recently deleted", async () => {
    const onQueues = vi.fn();
    const { rerender } = render(<HistoryMenu queueCount={0} deletedCount={0} disabled={false} onQueues={onQueues} onDeleted={() => {}} />);
    expect(screen.getByRole("button", { name: "Queues and recently deleted" })).not.toHaveClass("has-dot");
    rerender(<HistoryMenu queueCount={2} deletedCount={0} disabled={false} onQueues={onQueues} onDeleted={() => {}} />);
    const button = screen.getByRole("button", { name: /Queues and recently deleted/ });
    expect(button).toHaveClass("has-dot");
    await userEvent.click(button);
    await userEvent.click(screen.getByRole("menuitem", { name: /Queues/ }));
    expect(onQueues).toHaveBeenCalled();
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });
});

describe("Welcome", () => {
  it("says what happens next in each sign-in phase", () => {
    const { rerender } = render(<Welcome phase="idle" error={null} onSignIn={() => {}} />);
    expect(screen.getByRole("button", { name: "Sign in with Google" })).toBeEnabled();
    rerender(<Welcome phase="waiting" error={null} onSignIn={() => {}} />);
    expect(screen.getByRole("button", { name: "Signing in…" })).toBeDisabled();
    expect(screen.getByText(/Google window that opened/)).toBeInTheDocument();
    rerender(<Welcome phase="failed" error="Sign-in timed out. Please try again." onSignIn={() => {}} />);
    expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled();
    expect(screen.getByText("Sign-in timed out. Please try again.")).toBeInTheDocument();
    rerender(<Welcome phase="booting" error={null} onSignIn={() => {}} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
