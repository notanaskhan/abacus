// BND-02 · Binder builder & tracker (P-06-T12). One test per artboard this task builds (a–f) on
// its fixture scenario, the spec's acceptance checklist for a–f, loading and error, the row
// actions against the C5 routes, "Preview as client", and the task's acceptance: "Six scenarios
// render, Eye off shows the internal-only helper, and polling stops while the tab is hidden."
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { act, cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { type JSX, useState } from "react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
  never,
} from "../../app-core/fixture-mode";
import { LIVE_POLL_MS } from "../../domain/requests";
import { renderRoutes } from "../../testing/support";
import { BND02, type BinderTab } from ".";
import { BINDERS, type Bnd02State, OPENS, STATES, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  toastStore.clear();
  vi.useRealTimers();
  setVisibility("visible");
});

interface Seen {
  calls: { method: string; path: string; body: unknown }[];
}

function install(scenario: Scenario, over: Record<string, FixtureHandler> = {}): Seen {
  const seen: Seen = { calls: [] };
  const handlers = Object.fromEntries(
    Object.entries({ ...scenario.handlers, ...over }).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  return seen;
}

function Harness({ state }: { state: Bnd02State }): JSX.Element {
  const [request, setRequest] = useState<string | null>(OPENS[state].request);
  const [tab, setTab] = useState<BinderTab>("requests");
  return (
    <BND02
      binderId={OPENS[state].binderId}
      request={request}
      onRequest={setRequest}
      tab={tab}
      onTab={setTab}
    />
  );
}

function show(state: Bnd02State, over: Record<string, FixtureHandler> = {}): Seen {
  const seen = install(scenarios[state], over);
  renderRoutes([{ path: "/", component: () => <Harness state={state} /> }]);
  return seen;
}

function rowOf(title: string): HTMLElement {
  const button = screen.getByRole("button", { name: title });
  const row = button.closest<HTMLElement>("[data-request]");
  if (row === null) throw new Error(`no row ${title}`);
  return row;
}

function dock(): HTMLElement {
  return screen.getByRole("region", { name: "Request dock" });
}

function liveCalls(seen: Seen): number {
  return seen.calls.filter((c) => c.path.endsWith("/live")).length;
}

function setVisibility(value: "visible" | "hidden"): void {
  Object.defineProperty(document, "visibilityState", { configurable: true, get: () => value });
  document.dispatchEvent(new Event("visibilitychange"));
}

async function openMenu(row: HTMLElement): Promise<HTMLElement> {
  const trigger = within(row).getByRole("button", { name: /actions$/ });
  trigger.focus();
  fireEvent.keyDown(trigger, { key: "ArrowDown" });
  return screen.findByRole("menu");
}

const PUBLISHED_A = "Published Feb 3 · 5 of 7 satisfied · 2 open";

describe("BND-02 artboards", () => {
  it("defines exactly the artboards P-06-T12 builds, as Kevin Osei at E0", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f"]);
    for (const s of STATES) {
      expect(scenarios[s].persona).toBe("kevin-osei");
      expect(scenarios[s].clock).toBe("2026-09-14T09:24:00-05:00");
    }
  });

  it("BND-02a default", async () => {
    show("a");
    expect(await screen.findByText(PUBLISHED_A)).toBeTruthy();
    expect(screen.getAllByText("2025 Binder").length).toBeGreaterThan(0);
    expect((await screen.findAllByText("Jonah & Claire Feld")).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "All Binders" })).toBeTruthy();
    expect(screen.getByText("Feb 3, 2026 · Kevin Osei")).toBeTruthy();
    expect(screen.getByText("2024 return (CCH Axcess)")).toBeTruthy();
    expect(screen.getByText("Claire Feld · Jonah Feld")).toBeTruthy();
    expect(screen.getByText("Not yet · 2 open")).toBeTruthy();
    expect(screen.getByText("1040 · prior-year")).toBeTruthy();
    // The dock opens on the Ridgeline K-1, the firm-provided draft.
    const k1 = rowOf("Schedule K-1 from Ridgeline Property Partners, LP");
    expect(within(k1).getByText("Draft K-1 · pre-release")).toBeTruthy();
    expect(
      within(dock()).getByText(
        "Brightwater Hale prepares this K-1 and adds it for you. Nothing to upload.",
      ),
    ).toBeTruthy();
    expect(await within(dock()).findByText("Ridgeline_2025_K-1_JonahFeld_DRAFT.pdf")).toBeTruthy();
    expect(await within(dock()).findByText("Kevin Osei")).toBeTruthy();
    // The live poll: the 1095-C waits in the Inbox, Claire is uploading the estimates.
    const aca = rowOf("Form 1095-C From Mercer Hill Health");
    expect(await within(aca).findByText("Waiting 2")).toBeTruthy();
    const est = rowOf(
      "2025 federal (1040-ES) and New York (IT-2105) estimated payment confirmations",
    );
    expect(within(est).getByText("Uploading 2 files…")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Unpublish…" })).toBeTruthy();
  });

  it("BND-02b draft roll-forward", async () => {
    show("b");
    expect(await screen.findByText("Draft · 7 requests from the 2025 return")).toBeTruthy();
    expect(screen.getAllByText("Not published")).toHaveLength(7);
    expect(
      screen.getAllByText("From 2025 return").filter((el) => el.closest("[data-request]")),
    ).toHaveLength(7);
    expect(screen.getByRole("button", { name: "Publish to client…" })).toBeTruthy();
    expect(screen.getAllByText("2026 Binder").length).toBeGreaterThan(0);
  });

  it("BND-02c complete", async () => {
    show("c");
    expect(
      await screen.findByText("Marked done by Claire Feld · Sep 15, 9:02 AM · 7 of 7"),
    ).toBeTruthy();
    expect(screen.getAllByText("Received ✓")).toHaveLength(6);
    expect(screen.getAllByText("Complete").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: "Unpublish…" })).toBeNull();
    expect(screen.queryByText("Requested")).toBeNull();
  });

  it("BND-02d overdue", async () => {
    show("d");
    expect(await screen.findByText("3 overdue")).toBeTruthy();
    expect(screen.getAllByText("Due Aug 31 · 14 days late")).toHaveLength(3);
    expect(screen.getByText("Published Jul 27 · 6 of 15 satisfied · 9 open")).toBeTruthy();
    expect(within(dock()).getByText("Send reminder for this request")).toBeTruthy();
  });

  it("BND-02d Send reminder… drafts the open items once, to Paul Thornbury, and Kevin sends", async () => {
    const seen = show("d");
    await screen.findByText("3 overdue");
    const send = await screen.findByRole("button", { name: "Send reminder…" });
    await waitFor(() => {
      expect((send as HTMLButtonElement).disabled).toBe(false);
    });
    fireEvent.click(send);
    const sheet = await screen.findByRole("dialog", { name: "Send follow-ups · 1" });
    expect(within(sheet).getByText("To Paul Thornbury")).toBeTruthy();
    expect(within(sheet).getByText("9 items, 3 overdue")).toBeTruthy();
    expect(within(sheet).getByText("+ 4 more open items listed once in the email")).toBeTruthy();
    expect(within(sheet).getAllByText("overdue")).toHaveLength(3);
    const drafted = seen.calls.find((c) => c.path === "/v1/follow-ups/drafts");
    expect((drafted?.body as { request_item_ids: string[] }).request_item_ids).toHaveLength(9);
    expect(seen.calls.some((c) => c.path === "/v1/follow-ups/send")).toBe(false);
    fireEvent.click(within(sheet).getByRole("button", { name: "Send 1 follow-up" }));
    await waitFor(() => {
      expect(toastStore.list()[0]?.text).toMatch(/^1 follow-up sent by /);
    });
    expect(toastStore.list()[0]?.action).toBe("Undo");
  });

  it("BND-02e ignored", async () => {
    show("e");
    expect(
      await screen.findByText("Published Jul 27 · 6 of 15 satisfied · 9 open (1 ignored)"),
    ).toBeTruthy();
    const ira = rowOf("2025 IRA contribution confirmations");
    expect(within(ira).getByText("Ignored")).toBeTruthy();
    expect(within(ira).getByText("Not applicable this year")).toBeTruthy();
    expect(within(dock()).getByRole("button", { name: "Waive (Not applicable)" })).toBeTruthy();
    expect(within(dock()).getByRole("button", { name: "Return to client…" })).toBeTruthy();
    const menu = await openMenu(ira);
    expect(within(menu).getByRole("menuitem", { name: "Return to client…" })).toBeTruthy();
    expect(within(menu).getByRole("menuitem", { name: "Waive (Not applicable)…" })).toBeTruthy();
  });

  it("BND-02f visibility off: Eye off shows the internal-only helper", async () => {
    show("f");
    await screen.findByText(PUBLISHED_A);
    const k1 = rowOf("Schedule K-1 from Ridgeline Property Partners, LP");
    expect(
      within(k1).getByText("Internal only — the client won't see this request."),
    ).toBeTruthy();
    const eye = within(k1).getByRole("button", { name: /hidden from client$/ });
    expect(eye.getAttribute("aria-pressed")).toBe("false");
    expect(
      within(dock())
        .getByRole("switch", { name: "Visible to client" })
        .getAttribute("aria-checked"),
    ).toBe("false");
    // Only the hidden row carries the helper.
    expect(screen.getAllByText("Internal only — the client won't see this request.")).toHaveLength(
      2,
    );
  });

  it("loading: the canvas waits on the record", async () => {
    show("a", { "GET /v1/binders/{binder_id}": () => never() });
    await waitFor(() => {
      expect(document.querySelector('[aria-busy="true"]')).not.toBeNull();
    });
    expect(screen.queryByText("2025 W-2 From Mercer Hill Health")).toBeNull();
  });

  it("error: a failed read offers a retry", async () => {
    show("a", { "GET /v1/binders/{binder_id}/requests": () => json({ detail: "boom" }, 500) });
    expect(await screen.findByRole("button", { name: /Try again|Retry/ })).toBeTruthy();
  });

  it("not allowed: a walled or unknown binder reads as not found", async () => {
    install(scenarios.a);
    renderRoutes([
      {
        path: "/",
        component: () => (
          <BND02
            binderId="00000000-0000-0000-0000-000000000000"
            request={null}
            onRequest={() => undefined}
            tab="requests"
            onTab={() => undefined}
          />
        ),
      },
    ]);
    expect(await screen.findByRole("button", { name: /Try again|Retry/ })).toBeTruthy();
    expect(screen.queryByText("Schedule K-1 from Ridgeline Property Partners, LP")).toBeNull();
  });
});

describe("BND-02 acceptance", () => {
  it("BND-02 acceptance: counts foot: 7 requests = 3 + 1 + 1 + 1 + 1; 5 satisfied and 2 open", async () => {
    show("a");
    await screen.findByText(PUBLISHED_A);
    const feld = BINDERS.feld.binder;
    const sizes = (feld.categories ?? [])
      .filter((c) => c.total_count > 0)
      .map((c) => c.total_count);
    expect(sizes).toEqual([3, 1, 1, 1, 1]);
    expect(feld.done_count).toBe(5);
    expect(feld.total_count).toBe(7);
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("5");
  });

  it("BND-02 acceptance: the rail uses the nine category names with olive ticks", async () => {
    show("a");
    await screen.findByText(PUBLISHED_A);
    const list = screen.getByRole("list", { name: "Categories" });
    const names = within(list)
      .getAllByRole("button")
      .map((b) => b.textContent);
    expect(names).toHaveLength(9);
    expect(names[1]).toContain("Income Sources");
    expect(names[3]).toContain("Health & Medical1 open");
    expect(within(list).getAllByRole("img", { name: "Done" })).toHaveLength(3);
  });

  it('BND-02 acceptance: "From 2024 return" appears on rows 1–6 only', async () => {
    show("a");
    await screen.findByText(PUBLISHED_A);
    expect(
      screen.getAllByText("From 2024 return").filter((el) => el.closest("[data-request]")),
    ).toHaveLength(6);
    const est = rowOf(
      "2025 federal (1040-ES) and New York (IT-2105) estimated payment confirmations",
    );
    expect(within(est).queryByText("From 2024 return")).toBeNull();
  });

  it("BND-02 acceptance: no digital-asset request exists", async () => {
    show("a");
    await screen.findByText(PUBLISHED_A);
    expect(screen.queryByText(/digital asset/i)).toBeNull();
  });

  it("BND-02 acceptance: the draft K-1 never reaches the client preview as a document", async () => {
    show("a");
    await screen.findByText(PUBLISHED_A);
    fireEvent.click(screen.getByRole("button", { name: "Preview as client" }));
    const sheet = await screen.findByRole("dialog", { name: "Preview as client" });
    expect(within(sheet).queryByText(/DRAFT\.pdf/)).toBeNull();
    expect(within(sheet).queryByText("Draft K-1 · pre-release")).toBeNull();
    expect(within(sheet).getByText("2025 W-2 From Mercer Hill Health")).toBeTruthy();
  });
});

describe("BND-02 rows and live poll", () => {
  it("the Eye toggle sends the visibility and the helper follows", async () => {
    const seen = show("a");
    await screen.findByText(PUBLISHED_A);
    const w2 = rowOf("2025 W-2 From Mercer Hill Health");
    fireEvent.click(within(w2).getByRole("button", { name: /visible to client$/ }));
    await waitFor(() => {
      const put = seen.calls.find((c) => c.method === "PUT");
      expect(put?.path).toMatch(/\/client-visibility$/);
      expect(put?.body).toEqual({ client_visible: false });
    });
    expect(
      await within(rowOf("2025 W-2 From Mercer Hill Health")).findByText(
        "Internal only — the client won't see this request.",
      ),
    ).toBeTruthy();
  });

  it("Delete is offered only for a never-sent Draft", async () => {
    show("a");
    await screen.findByText(PUBLISHED_A);
    const menu = await openMenu(rowOf("2025 W-2 From Mercer Hill Health"));
    expect(
      within(menu).getByRole("menuitem", { name: "Delete" }).getAttribute("aria-disabled"),
    ).toBe("true");
  });

  it("Return to client… asks for a note and sends it", async () => {
    const seen = show("e");
    await screen.findByText(/1 ignored/);
    fireEvent.click(within(dock()).getByRole("button", { name: "Return to client…" }));
    const dialog = await screen.findByRole("dialog", { name: "Return to client" });
    const send = within(dialog).getByRole("button", { name: "Return" });
    expect(send.hasAttribute("disabled")).toBe(true);
    fireEvent.change(within(dialog).getByRole("textbox"), {
      target: { value: "We still need these for 2025." },
    });
    fireEvent.click(send);
    await waitFor(() => {
      const post = seen.calls.find((c) => c.path.endsWith("/return-to-client"));
      expect(post?.body).toEqual({ note: "We still need these for 2025." });
    });
  });

  it("polling stops while the tab is hidden and resumes when it shows", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const seen = show("a");
    await screen.findByText(PUBLISHED_A);
    await waitFor(() => {
      expect(liveCalls(seen)).toBeGreaterThanOrEqual(1);
    });
    const first = liveCalls(seen);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(LIVE_POLL_MS + 100);
    });
    expect(liveCalls(seen)).toBeGreaterThan(first);
    act(() => {
      setVisibility("hidden");
    });
    const hidden = liveCalls(seen);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(LIVE_POLL_MS * 4);
    });
    expect(liveCalls(seen)).toBe(hidden);
    act(() => {
      setVisibility("visible");
    });
    await act(async () => {
      await vi.advanceTimersByTimeAsync(LIVE_POLL_MS + 100);
    });
    expect(liveCalls(seen)).toBeGreaterThan(hidden);
  });

  it("a Draft or complete binder is not polled", async () => {
    const seen = show("b");
    await screen.findByText("Draft · 7 requests from the 2025 return");
    expect(liveCalls(seen)).toBe(0);
  });

  it("no agent-owned control offers Approve, Sign off, Release, Send or Post", async () => {
    show("a");
    await screen.findByText(PUBLISHED_A);
    for (const word of [/^Approve/, /^Sign off/, /^Release/, /^Send$/, /^Post/]) {
      expect(screen.queryByRole("button", { name: word })).toBeNull();
    }
  });
});
