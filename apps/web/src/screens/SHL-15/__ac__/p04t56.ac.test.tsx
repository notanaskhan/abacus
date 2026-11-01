// P-04-T56 (TASK-2806): the ADR-078 acceptance suite for the SHL-15 issue composer (P-04-T54) and
// the SHL-09 field provenance tray (P-04-T55), from P-04 §3 F6–F7. Row acceptance: "Tests written
// pass and fail if the internal note reaches the portal request." What it holds:
//
//   1  client wording never shows the internal note: the POR-04 send carries only the wording and
//      the contact, and no client-facing field is prefilled from the note
//   2  no propose-only checkbox on any fix-instruction sheet (DF-13, DEC-53)
//   3  an agent assignee cannot resolve: the agent's assignee element carries no control, and any
//      resolve-like control is a person's HumanAction
//   4  an edit needs a citation note (SHL-09): Save waits for a non-blank note, and the PUT carries it
//   5  Unsupported blocks field sign-off (SHL-09 e): disabled, and a click sends nothing
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import type { JSX } from "react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
} from "../../../app-core/fixture-mode";
import { SHL15 } from "../../../fixtures/seed/review";
import "../../../routes/firm/sheets";
import { newQueryClient } from "../../../testing/support";
import { ProvenanceTray } from "../../SHL-09";
import {
  DOCUMENTS,
  OPENS as SHL09_OPENS,
  type Shl09State,
  scenarios as shl09,
} from "../../SHL-09/scenarios";
import { BulkInstructionsSheet, FixInstructionsSheet, IssueFixDetail, NewIssueSheet } from "..";
import { OPENS, type Shl15State, scenarios as shl15 } from "../scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  toastStore.clear();
});

interface Call {
  method: string;
  path: string;
  body: unknown;
}

function mount(scenario: Scenario, view: () => JSX.Element): Call[] {
  const calls: Call[] = [];
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  const root = createRootRoute({ component: Outlet });
  const router = createRouter({
    routeTree: root.addChildren([
      createRoute({ getParentRoute: () => root, path: "/", component: view }),
    ]),
    history: createMemoryHistory({ initialEntries: ["/"] }),
  });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
  return calls;
}

function shl15View(state: Shl15State): () => JSX.Element {
  const open = OPENS[state];
  const none = (): undefined => undefined;
  return () => {
    if (open.mode === "fix" && state !== "ap" && state !== "app") {
      return <FixInstructionsSheet issueId={open.issueId} open onOpenChange={none} />;
    }
    if (open.mode === "fix" || open.mode === "explain") {
      return <IssueFixDetail issueId={open.issueId} />;
    }
    if (open.mode === "new") {
      return (
        <NewIssueSheet
          record={open.record}
          engagementId={open.engagementId}
          draft={open.draft}
          meta={open.meta}
          {...(open.context === undefined ? {} : { context: open.context })}
          open
          onOpenChange={none}
        />
      );
    }
    return (
      <BulkInstructionsSheet
        issueIds={open.ids}
        initialText={open.text}
        meta={open.meta}
        open
        onOpenChange={none}
      />
    );
  };
}

function shl09View(state: Shl09State): () => JSX.Element {
  const open = SHL09_OPENS[state];
  return () => (
    <ProvenanceTray
      field={{ type: open.type, id: open.id, fieldKey: open.fieldKey }}
      documents={DOCUMENTS}
    />
  );
}

const tray = (): Promise<HTMLElement> =>
  waitFor(
    () => {
      const t = document.querySelector<HTMLElement>("[data-shl09='tray']");
      if (t === null) throw new Error("no tray yet");
      return t;
    },
    { timeout: 6000 },
  );

describe("1 · client wording never shows the internal note", () => {
  const NOTE = SHL15.b.internal_note;

  it("b: the POR-04 send carries only the wording and the contact", async () => {
    expect(NOTE).not.toBe("");
    const calls = mount(shl15.b, shl15View("b"));
    const sheet = await screen.findByRole("dialog");
    const send = await within(sheet).findByRole<HTMLButtonElement>("button", {
      name: "Create & send to client",
    });
    await waitFor(() => {
      expect(send.disabled).toBe(false);
    });
    fireEvent.click(send);
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/send-to-client"))).toBe(
        true,
      );
    });
    const sent = calls.find((c) => c.method === "POST" && c.path.endsWith("/send-to-client"));
    const body = JSON.stringify(sent?.body);
    // The whole note, and each of its sentences, stays out of what the client receives.
    expect(body).not.toContain(NOTE);
    for (const part of NOTE.split(/(?<=[.;])\s+/u).filter((p) => p.length > 12)) {
      expect(body).not.toContain(part);
    }
    expect(Object.keys(sent?.body as object)).not.toContain("internal_note");
  });

  it("b: the client wording field is not prefilled from the internal note", async () => {
    mount(shl15.b, shl15View("b"));
    const sheet = await screen.findByRole("dialog");
    await within(sheet).findByText("Client wording — what Dana sees");
    for (const box of within(sheet).queryAllByRole<HTMLTextAreaElement>("textbox")) {
      const label = box.getAttribute("aria-label") ?? box.labels[0]?.textContent ?? "";
      if (/client wording/iu.test(label)) expect(box.value).not.toContain(NOTE);
    }
  });
});

describe("2 · no propose-only checkbox (DF-13)", () => {
  it.each(["a", "e"] as const)(
    "%s: no checkbox and no 'Propose changes for my approval'",
    async (s) => {
      mount(shl15[s], shl15View(s));
      const sheet = await screen.findByRole("dialog");
      await waitFor(() => {
        expect(sheet.textContent).not.toBe("");
      });
      expect(within(sheet).queryByRole("checkbox")).toBeNull();
      expect(sheet.textContent).not.toMatch(/propose changes for my approval/iu);
    },
  );
});

describe("3 · an agent assignee cannot resolve", () => {
  it.each(["a", "ap", "app", "d"] as const)(
    "%s: the agent's assignee carries no control; resolve is only ever a HumanAction",
    async (s) => {
      mount(shl15[s], shl15View(s));
      await waitFor(
        () => {
          expect(document.querySelector("[data-actor='agent']")).not.toBeNull();
        },
        { timeout: 6000 },
      );
      for (const el of document.querySelectorAll<HTMLElement>("[data-actor='agent']")) {
        expect(within(el).queryAllByRole("button")).toEqual([]);
        expect(el.closest("button")).toBeNull();
      }
      for (const b of screen.queryAllByRole("button")) {
        if (/resolve/iu.test(b.textContent))
          expect(b.getAttribute("data-human-verb")).not.toBeNull();
      }
    },
  );
});

describe("4 · an edit needs a citation note (SHL-09)", () => {
  it("a: Save waits for a non-blank note, and the PUT carries it", async () => {
    const calls = mount(shl09.a, shl09View("a"));
    const t = await tray();
    fireEvent.click(within(t).getByRole("button", { name: "Edit value" }));
    const form = t.querySelector<HTMLElement>("[data-shl09='edit']") as HTMLElement;
    const save = within(form).getByRole<HTMLButtonElement>("button", { name: "Save" });
    const note = within(form).getByLabelText("Citation note (required)");
    expect(save.disabled).toBe(true);
    fireEvent.change(note, { target: { value: "   " } });
    expect(save.disabled).toBe(true);
    fireEvent.change(note, { target: { value: "Per the corrected 1099-INT, p. 4" } });
    expect(save.disabled).toBe(false);
    fireEvent.click(save);
    await waitFor(() => {
      expect(calls.some((c) => c.method === "PUT" && c.path.endsWith("/value"))).toBe(true);
    });
    const put = calls.find((c) => c.method === "PUT" && c.path.endsWith("/value"));
    expect((put?.body as { citation_note: string }).citation_note).toBe(
      "Per the corrected 1099-INT, p. 4",
    );
  });
});

describe("5 · Unsupported blocks field sign-off (SHL-09 e)", () => {
  it("e: Sign off field is disabled and a click sends no tick", async () => {
    const calls = mount(shl09.e, shl09View("e"));
    const t = await tray();
    const sign = within(t).getByRole<HTMLButtonElement>("button", { name: "Sign off field" });
    expect(sign.disabled).toBe(true);
    fireEvent.click(sign);
    expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/ticks"))).toBe(false);
  });
});
