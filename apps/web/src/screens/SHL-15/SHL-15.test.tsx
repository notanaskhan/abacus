// SHL-15 · Issue composer & fix instructions (P-04-T54). Acceptance: "SHL-15b sends only the client
// wording to POR-04, the propose-only checkbox is absent, and a-prime, a-double-prime and d render
// from scripted fixtures." Plus a's suggestion and scope, the agents-off state (409
// `fix_runner_unavailable`), c's Issues count and e's bulk instruction.
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
import { type FixtureHandler, installFixtureMode } from "../../app-core/fixture-mode";
import { BULK_IDS, BULK_TEXT } from "../../fixtures/seed/issues-shl15";
import { DANA, INSTRUCTIONS, SUGGESTION, WORDING, k1 } from "../../fixtures/seed/review";
import "../../routes/firm/sheets"; // registers the `?ov=` keys (Accept opens `approve`)
import { newQueryClient } from "../../testing/support";
import { BulkInstructionsSheet, FixInstructionsSheet, IssueFixDetail, NewIssueSheet } from ".";
import { OPENS, STATES, type Shl15State, scenarios } from "./scenarios";

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
  headers: Headers | undefined;
}

function show(state: Shl15State): { calls: Call[]; search: () => Record<string, unknown> } {
  const calls: Call[] = [];
  const scenario = scenarios[state];
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({
          method: request.method,
          path: request.path,
          body: request.body,
          headers: request.headers,
        });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  const open = OPENS[state];
  const none = (): undefined => undefined;
  const view = (): JSX.Element => {
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
  return { calls, search: () => router.state.location.search as Record<string, unknown> };
}

const posts = (calls: Call[], path: RegExp): Call[] =>
  calls.filter((c) => c.method === "POST" && path.test(c.path));

describe("SHL-15", () => {
  it("builds a, a′, a″, b, c, d, e and the agents-off state", () => {
    expect(STATES).toEqual(["a", "ap", "app", "b", "c", "d", "e", "agents_off"]);
  });

  it("a: the issue card, the suggestion through AgentText, Use suggestion, the scope; no propose-only checkbox (DF-13)", async () => {
    const { calls } = show("a");
    expect(await screen.findByText("Issue 3 of 4")).toBeTruthy();
    const sheet = await screen.findByRole("dialog");
    expect(
      within(sheet).getByText("Source K-1 box 18A 'Tax-exempt interest' is not on the worksheet"),
    ).toBeTruthy();
    expect(sheet.textContent).toContain("Missing information");
    expect(sheet.querySelector('[data-link="file"]')?.textContent).toContain(
      "Ridgeline_2025_K1_JonahFeld_DRAFT.pdf",
    );
    const suggestion = within(sheet).getByRole("region", { name: "Suggested by Accrued Agent" });
    expect(suggestion.querySelector('[data-actor="agent"]')?.textContent).toBe(SUGGESTION);
    // DF-13: no "Propose changes for my approval" control anywhere.
    expect(within(sheet).queryByRole("checkbox")).toBeNull();
    expect(sheet.textContent).not.toContain("Propose changes for my approval");
    await waitFor(() => {
      expect(
        within(sheet).getByRole("radio", {
          name: "All 2 Missing information issues on this return",
        }),
      ).toBeTruthy();
    });
    fireEvent.click(within(sheet).getByRole("button", { name: "Use suggestion" }));
    const editor = within(sheet).getByLabelText<HTMLTextAreaElement>("Instructions");
    expect(editor.value).toBe(SUGGESTION);
    fireEvent.change(editor, { target: { value: INSTRUCTIONS } });
    fireEvent.click(within(sheet).getByRole("button", { name: "Set Fix Instructions" }));
    await waitFor(() => {
      expect(posts(calls, /fix-instructions$/u)).toHaveLength(1);
    });
    expect(posts(calls, /fix-instructions$/u)[0]?.body).toEqual({
      seen_version: 1,
      text: INSTRUCTIONS,
      scope: "this_issue",
    });
  });

  it("agents off: the 409 fix_runner_unavailable shows the agents-off state", async () => {
    show("agents_off");
    const sheet = await screen.findByRole("dialog");
    fireEvent.click(await within(sheet).findByRole("button", { name: "Use suggestion" }));
    fireEvent.click(within(sheet).getByRole("button", { name: "Set Fix Instructions" }));
    await waitFor(() => {
      expect(sheet.querySelector('[data-shl15="agents-off"]')).not.toBeNull();
    });
    expect(
      within(sheet).getByRole<HTMLButtonElement>("button", { name: "Set Fix Instructions" })
        .disabled,
    ).toBe(true);
  });

  it("b: Create & send to client sends only the client wording, with an Idempotency-Key", async () => {
    const { calls } = show("b");
    const sheet = await screen.findByRole("dialog");
    expect(sheet.textContent).toContain("EBP-04 · Northwind");
    expect(await within(sheet).findByText("Client wording — what Dana sees")).toBeTruthy();
    expect(sheet.textContent).toContain(
      "Sends as a request in Dana's portal (POR-04). Internal notes stay internal.",
    );
    const send = await within(sheet).findByRole("button", { name: "Create & send to client" });
    await waitFor(() => {
      expect((send as HTMLButtonElement).disabled).toBe(false);
    });
    fireEvent.click(send);
    await waitFor(() => {
      expect(posts(calls, /send-to-client$/u)).toHaveLength(1);
    });
    const created = posts(calls, /^\/v1\/issues$/u)[0]?.body as Record<string, unknown>;
    expect(created.kind).toBe("waiting_on_client");
    expect(created.internal_note).toContain("EPCRS");
    const sent = posts(calls, /send-to-client$/u)[0];
    // Only the client wording and the contact reach the client: never the internal note.
    expect(Object.keys(sent?.body as object).sort()).toEqual([
      "client_wording",
      "contact_id",
      "seen_version",
    ]);
    expect((sent?.body as { client_wording: string }).client_wording).toBe(WORDING);
    expect((sent?.body as { contact_id: string }).contact_id).toBe(DANA);
    expect(JSON.stringify(sent?.body)).not.toContain("EPCRS");
    expect(sent?.headers?.get("Idempotency-Key")).toMatch(/^[0-9a-f-]{36}$/u);
  });

  it("c: a field flag's Review point; the Issues count reads Feld 4 → 5", async () => {
    const { calls } = show("c");
    const sheet = await screen.findByRole("dialog");
    expect(await within(sheet).findByText("Feld Issues 4 → 5")).toBeTruthy();
    expect(sheet.querySelector('[data-link="form_field"]')?.textContent).toContain(
      "Ridgeline K-1 box 5 → Form 1040 line 2b",
    );
    expect(within(sheet).queryByRole("button", { name: "Create & send to client" })).toBeNull();
    fireEvent.click(within(sheet).getByRole("button", { name: "Create issue" }));
    await waitFor(() => {
      expect(posts(calls, /^\/v1\/issues$/u)).toHaveLength(1);
    });
    expect((posts(calls, /^\/v1\/issues$/u)[0]?.body as { kind: string }).kind).toBe(
      "review_point",
    );
  });

  it("e: one instruction for the 2 Missing information issues, scope locked", async () => {
    const { calls } = show("e");
    const sheet = await screen.findByRole("dialog");
    expect(sheet.textContent).toContain("Instructions for 2 issues");
    await waitFor(() => {
      expect(sheet.textContent).toContain("2025 estimated payment confirmations are missing");
    });
    expect(sheet.textContent).toContain("Applies to the 2 selected issues only");
    fireEvent.click(within(sheet).getByRole("button", { name: "Set Fix Instructions for 2" }));
    await waitFor(() => {
      expect(posts(calls, /fix-instructions:bulk$/u)).toHaveLength(1);
    });
    const body = posts(calls, /fix-instructions:bulk$/u)[0]?.body as {
      issues: { issue_id: string }[];
      text: string;
    };
    expect(body.issues.map((i) => i.issue_id)).toEqual([...BULK_IDS]);
    expect(body.text).toBe(BULK_TEXT);
  });

  it("a′: In progress — agent fixing, with the run row", async () => {
    show("ap");
    expect(await screen.findByText("In progress — agent fixing")).toBeTruthy();
    expect(document.querySelector('[data-shl15="run"]')?.textContent).toContain(
      "Adding 1,550 to Form 1040 line 2a",
    );
  });

  it("a″: the proposed values as ghosts; Accept opens SHL-10 on the proposal", async () => {
    const { search } = show("app");
    await waitFor(() => {
      expect(document.querySelectorAll("[data-ghost]")).toHaveLength(2);
    });
    expect(screen.getByText("Proposed 2 changes for your approval")).toBeTruthy();
    const accept = screen.getByRole("button", { name: "Accept" });
    fireEvent.click(accept);
    await waitFor(() => {
      expect(search().ov).toBe(`approve:${k1.ref}`);
    });
  });

  it("d: the explanation is read-only agent text with its three citations", async () => {
    show("d");
    const block = await screen.findByRole("region", { name: "Explanation" });
    expect(block.querySelector('[data-actor="agent"]')?.textContent).toContain(
      "New York adds interest on other states' bonds back on IT-201 line 20",
    );
    expect([...block.querySelectorAll("[data-citation]")].map((c) => c.textContent)).toEqual([
      "K-1 box 18A",
      "K-1 statement p. 3",
      "IT-201 instructions, line 20",
    ]);
    expect(within(block).queryAllByRole("button")).toEqual([]);
  });
});
