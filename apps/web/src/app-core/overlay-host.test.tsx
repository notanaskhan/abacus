// F-05-T20: OverlayHost against a real router on memory history. A layer opens from the URL, a
// reload draws it again, Back closes it, Escape closes it with replace, and a second drawer takes
// the first one's place. The registry entries here are tests' own; the real ones are the screen
// epics'.
import { Button, Dialog, Drawer } from "@abacus/ui";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import {
  Outlet,
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import { type JSX } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it } from "vitest";
import { OverlayHost, useOverlays } from "./overlay-host";
import { clearOverlayRegistry, registerOverlay } from "./overlays";

beforeAll(() => {
  // What jsdom lacks and Radix's anchored layers read.
  const g = globalThis as { ResizeObserver?: unknown };
  g.ResizeObserver ??= class {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  };
});

beforeEach(() => {
  registerOverlay("request", {
    layer: "drawer",
    render: ({ ref, close }) => (
      <Drawer
        open
        onOpenChange={(o) => {
          if (!o) close();
        }}
        title={`Request ${ref.args.join(" ")}`}
      >
        <p>Composer</p>
      </Drawer>
    ),
  });
  registerOverlay("notifications", {
    layer: "drawer",
    render: ({ close }) => (
      <Drawer
        open
        onOpenChange={(o) => {
          if (!o) close();
        }}
        title="Notifications"
      >
        <p>Bell</p>
      </Drawer>
    ),
  });
  registerOverlay("signoff", {
    layer: "modal",
    render: ({ close }) => (
      <Dialog
        open
        onOpenChange={(o) => {
          if (!o) close();
        }}
        title="Sign off"
      >
        <p>Attest</p>
      </Dialog>
    ),
  });
});

afterEach(() => {
  cleanup();
  clearOverlayRegistry();
});

function Page(): JSX.Element {
  const { open } = useOverlays();
  return (
    <>
      <Button
        onClick={() => {
          open("request", "new");
        }}
      >
        New request
      </Button>
      <Button
        onClick={() => {
          open("notifications");
        }}
      >
        Bell
      </Button>
      <Button
        onClick={() => {
          open("signoff", "aje");
        }}
      >
        Sign off
      </Button>
    </>
  );
}

function mount(at = "/") {
  const root = createRootRoute({
    component: () => (
      <>
        <Outlet />
        <OverlayHost />
      </>
    ),
  });
  const index = createRoute({ getParentRoute: () => root, path: "/", component: Page });
  const history = createMemoryHistory({ initialEntries: [at] });
  const router = createRouter({ routeTree: root.addChildren([index]), history });
  render(<RouterProvider router={router} />);
  return { router, history };
}

const search = (history: ReturnType<typeof createMemoryHistory>): string =>
  history.location.search;

describe("OverlayHost", () => {
  it("draws nothing until the URL names a layer", async () => {
    mount();
    await screen.findByRole("button", { name: "New request" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("draws the layer a reloaded URL names", async () => {
    mount("/?ov=request%3Anew");
    expect(await screen.findByRole("dialog", { name: "Request new" })).toBeTruthy();
  });

  it("opens with a click, writes it to the URL, and Back closes it", async () => {
    const { history } = mount();
    fireEvent.click(await screen.findByRole("button", { name: "New request" }));
    await screen.findByRole("dialog", { name: "Request new" });
    expect(search(history)).toBe("?ov=request%3Anew");
    act(() => {
      history.back();
    });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
    expect(search(history)).toBe("");
  });

  it("closes on Escape and on the close button, replacing the entry rather than adding one", async () => {
    const { history } = mount();
    fireEvent.click(await screen.findByRole("button", { name: "New request" }));
    await screen.findByRole("dialog", { name: "Request new" });
    const length = history.length;
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
    expect(search(history)).toBe("");
    expect(history.length).toBe(length);

    fireEvent.click(screen.getByRole("button", { name: "New request" }));
    fireEvent.click(await screen.findByRole("button", { name: "Close" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
    expect(search(history)).toBe("");
  });

  it("never two drawers: a second drawer replaces the first in the URL and on the page", async () => {
    const { history } = mount();
    fireEvent.click(await screen.findByRole("button", { name: "New request" }));
    await screen.findByRole("dialog", { name: "Request new" });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "Bell", hidden: true }));
    });
    await screen.findByRole("dialog", { name: "Notifications" });
    expect(search(history)).toBe("?ov=notifications");
    expect(screen.queryByText("Request new", { selector: "h2" })).toBeNull();
  });

  it("stacks a modal over a drawer, and Escape closes only the modal", async () => {
    const { history } = mount();
    fireEvent.click(await screen.findByRole("button", { name: "New request" }));
    await screen.findByRole("dialog", { name: "Request new" });
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "Sign off", hidden: true }));
    });
    await screen.findByRole("dialog", { name: "Sign off" });
    expect(decodeURIComponent(search(history))).toContain("request:new");
    expect(decodeURIComponent(search(history))).toContain("signoff:aje");

    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "Sign off" })).toBeNull();
    });
    expect(screen.getByText("Request new", { selector: "h2" })).toBeTruthy();
    expect(search(history)).toBe("?ov=request%3Anew");
  });

  it("keeps the other search parameters when it opens and closes a layer", async () => {
    const { history } = mount("/?segment=open");
    fireEvent.click(await screen.findByRole("button", { name: "New request" }));
    await screen.findByRole("dialog", { name: "Request new" });
    expect(search(history)).toContain("segment=open");
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
    expect(search(history)).toContain("segment=open");
    expect(search(history)).not.toContain("ov=");
  });

  it("ignores a key the registry does not know", async () => {
    mount("/?ov=mystery%3A1");
    await screen.findByRole("button", { name: "New request" });
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
