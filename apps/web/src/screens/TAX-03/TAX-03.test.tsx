// TAX-03 · Return › Intake (T-02-T19). One test per artboard (a, a2, b–f) on its fixture scenario,
// the read in the OpenAPI schema, and every filing, ignore, approval and discard as a person's
// click on its owner's route (which writes the audit row): nothing is sent until the click.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
} from "../../app-core/fixture-mode";
import { validateResponse } from "../../fixtures/schema-check";
import {
  DUPLICATE_VERSION,
  FELD_BINDER_ID,
  REQUEST,
  W2_CLAIRE,
} from "../../fixtures/scenarios/TAX-03";
import { ATTACHMENT, intakeFor } from "../../fixtures/seed/tax-intake";
import { newQueryClient } from "../../testing/support";
import { ReturnIntakePage } from ".";
import { COPY } from "./copy";
import { OPENS, OPEN_DOCUMENT, STATES, type Tax03State, scenarios } from "./scenarios";

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

interface Seen {
  calls: { method: string; path: string; body: unknown }[];
}

function show(state: Tax03State): Seen {
  const seen: Seen = { calls: [] };
  const scenario: Scenario = scenarios[state];
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <ReturnIntakePage returnId={OPENS[state]} initialDocument={OPEN_DOCUMENT[state] ?? null} />
    </QueryClientProvider>,
  );
  return seen;
}

const writes = (seen: Seen) => seen.calls.filter((c) => c.method !== "GET");

async function ready(): Promise<void> {
  await screen.findAllByText(/^2025 Form /);
}

describe("TAX-03 artboards", () => {
  it("covers a, a2 and b to f", () => {
    expect(STATES).toEqual(["a", "a2", "b", "c", "d", "e", "f"]);
  });

  it("every artboard's read is in the schema", () => {
    for (const v of ["a", "b", "c", "d", "e", "f"] as const) {
      expect(
        validateResponse("GET", "/v1/tax-returns/{return_id}/intake", intakeFor(v, OPENS.a)),
      ).toEqual([]);
    }
  });

  it("a: 5 of 7, the dependency banner, two 1095-C forms waiting and nothing filed", async () => {
    const seen = show("a");
    await ready();
    expect(await screen.findByText("5 of 7 requests satisfied")).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain(
      "Ridgeline 1065 K-1 is a draft — final pending Ridgeline partner approval",
    );
    expect(screen.getByText(COPY.draftK1)).toBeTruthy();
    expect(screen.getByText("final pending Ridgeline approval")).toBeTruthy();
    expect(screen.getByText(COPY.dock(2))).toBeTruthy();
    expect(screen.getByText("2024 ≠ 2025")).toBeTruthy();
    expect(screen.getByText(COPY.wrongYearSuggest)).toBeTruthy();
    // The agent's suggestion is agent text, and filing waits for the person.
    const suggestion = screen.getByText(/Accrued Agent suggests/);
    expect(suggestion.closest("[data-actor='agent']")).not.toBeNull();
    expect(
      screen.getByText("7 requests · 5 satisfied · 2 open · binder published Feb 3"),
    ).toBeTruthy();
    // The live poll: Claire's two files uploading, two attachments waiting.
    expect(await screen.findByText(COPY.uploading(2))).toBeTruthy();
    expect(screen.getByText(COPY.waiting(2))).toBeTruthy();
    expect(writes(seen)).toEqual([]);
  });

  it("a: File to request is the person's click on N-01's triage apply", async () => {
    const seen = show("a");
    await ready();
    fireEvent.click(await screen.findByRole("button", { name: COPY.fileTo }));
    await waitFor(() => {
      expect(writes(seen)).toHaveLength(1);
    });
    const [call] = writes(seen);
    expect(call?.path).toMatch(/\/v1\/inbox\/messages\/[^/]+\/triage\/apply$/);
    expect(call?.body).toMatchObject({
      decisions: [
        {
          attachment_id: ATTACHMENT.c2025,
          decision: "file",
          destination: { kind: "request", id: REQUEST.f1095c },
        },
      ],
    });
    const filed = COPY.filed("Feld_1095C_2025.pdf", "Form 1095-C From Mercer Hill Health");
    await waitFor(() => {
      expect(toastStore.list().some((t) => t.text === filed)).toBe(true);
    });
  });

  it("a: Ignore · wrong year sends the wrong_tax_year reason", async () => {
    const seen = show("a");
    await ready();
    fireEvent.click(await screen.findByRole("button", { name: COPY.ignoreWrongYear }));
    await waitFor(() => {
      expect(writes(seen)).toHaveLength(1);
    });
    expect(writes(seen)[0]?.body).toMatchObject({
      decisions: [
        { attachment_id: ATTACHMENT.c2024, decision: "ignore", reason_codes: ["wrong_tax_year"] },
      ],
    });
  });

  it("a2: the W-2 opens in the dock and Approve Document accepts its version", async () => {
    const seen = show("a2");
    await ready();
    const approve = await screen.findByRole("button", { name: COPY.approve });
    expect(
      screen.getByText(COPY.matchedTo("Income Sources", "2025 W-2 From Mercer Hill Health")),
    ).toBeTruthy();
    expect(writes(seen)).toEqual([]);
    fireEvent.click(approve);
    await waitFor(() => {
      expect(writes(seen)).toHaveLength(1);
    });
    expect(writes(seen)[0]?.path).toContain(`/evidence-versions/${W2_CLAIRE}/decision/accept`);
  });

  it("b: the 1095-C is received, Health & Medical is complete and the dock is empty", async () => {
    show("b");
    await ready();
    expect(await screen.findByText("6 of 7 requests satisfied")).toBeTruthy();
    expect(screen.getByText(COPY.dockEmpty)).toBeTruthy();
    const health = screen.getByRole("button", { name: /Health & Medical/ });
    expect(within(health).queryByText(/open/)).toBeNull();
  });

  it("c: marked done by Claire Feld, all seven satisfied, binder Complete", async () => {
    show("c");
    await ready();
    expect(await screen.findByText("7 of 7 requests satisfied")).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain(
      "Marked done by Claire Feld · Sep 15",
    );
    expect(screen.getByText(COPY.binderComplete)).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Intake" })).toBeTruthy();
  });

  it("d: the final K-1 replaces the draft and the banner is gone", async () => {
    show("d");
    await ready();
    expect(await screen.findByText(COPY.released("Sep 15"))).toBeTruthy();
    expect(screen.queryByText(COPY.draftK1)).toBeNull();
    expect(screen.queryByText(/K-1 is a draft/)).toBeNull();
  });

  it("e: the duplicate W-2 waits for a person's Discard duplicate", async () => {
    const seen = show("e");
    await ready();
    expect(await screen.findByText("Claire_Feld_2025_W2_MercerHill (1).pdf")).toBeTruthy();
    expect(screen.getByText(COPY.duplicate)).toBeTruthy();
    // The request row keeps naming the filed copy.
    expect(screen.getByText(/^Claire_Feld_2025_W2_MercerHill\.pdf/)).toBeTruthy();
    expect(writes(seen)).toEqual([]);
    fireEvent.click(screen.getByRole("button", { name: COPY.discardDuplicate }));
    await waitFor(() => {
      expect(writes(seen)).toHaveLength(1);
    });
    const [call] = writes(seen);
    expect(call?.path).toContain(
      `/request-items/${REQUEST.w2}/evidence-versions/${DUPLICATE_VERSION}/duplicate-resolution`,
    );
    expect(call?.body).toEqual({ decision: "discard_duplicate" });
  });

  it("f: Meera Shah's return has no binder yet", async () => {
    show("f");
    await ready();
    expect(await screen.findByText(COPY.noRequests)).toBeTruthy();
    expect(screen.getByText(COPY.noRequestsBody)).toBeTruthy();
    expect(screen.queryByText(COPY.unpublish)).toBeNull();
  });

  it("Unpublish binder asks first and sends only on confirm", async () => {
    const seen = show("a");
    await ready();
    fireEvent.click(await screen.findByRole("button", { name: COPY.unpublish }));
    expect(await screen.findByText(COPY.unpublishTitle)).toBeTruthy();
    expect(writes(seen)).toEqual([]);
    fireEvent.click(screen.getByRole("button", { name: COPY.unpublishConfirm }));
    await waitFor(() => {
      expect(writes(seen)).toHaveLength(1);
    });
    expect(writes(seen)[0]?.path).toBe(`/v1/binders/${FELD_BINDER_ID}/unpublish`);
  });
});
