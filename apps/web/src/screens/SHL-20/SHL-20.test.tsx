// P-06-T22: SHL-20 a–f on their fixture scenarios through the generated client. Row acceptance:
// "Seven scenarios render (a–f here, BND-02 g in BND-02.test.tsx), feedback cannot be sent without
// a reason, and no confidence percentage appears anywhere." Plus the contract's: the anatomy, the
// flag reasons verbatim, the expected period, the counts, View → SHL-08, Return… with Wrong
// document preselected, the drafted follow-up the person sends, and nothing accepted, returned or
// sent by the screening itself.
import { client } from "@abacus/api-client/client";
import { Outlet, useRouterState } from "@tanstack/react-router";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { type JSX } from "react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
} from "../../app-core/fixture-mode";
import { decodeOverlays } from "../../app-core/overlays";
import { SCREENING_POLL_MS, pollWhileRunning } from "../../domain/screening";
import {
  FLAGGED_CARD,
  INVOICE_FLAG,
  PASSED_CARD,
  RUNNING_CARD,
  STATEMENT_FLAG,
  STATEMENT_VERSION,
} from "../../fixtures/seed/screening";
// Registers the `?ov=viewer` drawer, as the firm routes do.
import "../../routes/firm/viewer";
import { renderRoutes } from "../../testing/support";
import { SHL20 } from "./artboard";
import { STATES, type Shl20State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

/** Every route the screen called, as "METHOD /openapi/path". */
let calls: string[] = [];
let bodies: Record<string, unknown> = {};

function spied(scenario: Scenario): Scenario {
  const handlers: Record<string, FixtureHandler> = {};
  for (const [key, handler] of Object.entries(scenario.handlers)) {
    handlers[key] = (request) => {
      calls.push(key);
      bodies[key] = request.body;
      return handler(request);
    };
  }
  return { ...scenario, handlers };
}

function Root(): JSX.Element {
  const search = useRouterState({ select: (s) => s.location.search as Record<string, unknown> });
  return (
    <>
      <output data-testid="ov">{JSON.stringify(search["ov"] ?? null)}</output>
      <Outlet />
    </>
  );
}

function show(state: Shl20State): void {
  calls = [];
  bodies = {};
  restore = installFixtureMode(spied(scenarios[state]));
  renderRoutes([{ path: "/", component: () => <SHL20 state={state} /> }], { root: Root });
}

/** The card once its aggregate has loaded (a running card stays busy: c). */
async function card(): Promise<HTMLElement> {
  const found = await screen.findByRole("region", { name: "Evidence screening" });
  await waitFor(
    () => {
      expect(found.getAttribute("data-screening-card")).not.toBeNull();
      expect(
        found.querySelector("[data-verdict]") ?? found.textContent.includes("new files"),
      ).toBeTruthy();
    },
    { timeout: 4000 },
  );
  return found;
}

const WRITES = [
  "POST /v1/engagements/{engagement_id}/evidence-versions/{version_id}/decision/send-back",
  "POST /v1/follow-ups/{follow_up_id}/send",
  "POST /v1/engagements/{engagement_id}/request-items/{item_id}/screening/rerun",
  "POST /v1/screenings/{screening_result_id}/feedback",
];

describe("SHL-20 scenarios", () => {
  it("cover a–f, as Cole Hart", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f"]);
    for (const s of STATES) expect(scenarios[s].persona).toBe("cole-hart");
    expect(scenarios.a.clock).toBe("2026-09-26T10:14:00-05:00");
    expect(scenarios.b.clock).toBe("2026-09-26T10:16:00-05:00");
    expect(scenarios.c.clock).toBe("2026-09-28T09:05:00-05:00");
  });

  it("foot: 31 files − 2 flagged = 29; after the corrected files, 40 of 40", () => {
    expect(FLAGGED_CARD.files_total - FLAGGED_CARD.file_flags.length).toBe(
      FLAGGED_CARD.files_answering,
    );
    expect([PASSED_CARD.files_answering, PASSED_CARD.files_total]).toEqual([40, 40]);
    expect(RUNNING_CARD.running).toBe(true);
  });

  for (const state of STATES) {
    it(`${state}: renders, with no confidence percentage and no human-only verb on the card`, async () => {
      show(state);
      const found = await card();
      expect(document.body.textContent).not.toMatch(/\d\s*%|confidence/i);
      for (const b of Array.from(found.querySelectorAll("button"))) {
        expect(b.textContent).not.toMatch(/\b(Approve|Sign off|Release|Post|Decide|Accept)\b/);
      }
      if (state !== "b") {
        for (const write of WRITES) expect(calls).not.toContain(write);
      }
    });
  }
});

describe("SHL-20a: flagged", () => {
  it("draws the C-34 anatomy with the expected period and the code-worded answers", async () => {
    show("a");
    const found = await card();
    expect(found.textContent).toContain("Sep 26, 10:12 AM");
    expect(found.querySelector("[data-verdict]")?.textContent).toBe("Flagged");
    expect(found.textContent).toContain(
      "Support for 40 subsequent disbursements (SURL) · expected period Jun 1 – Sep 18, 2026",
    );
    const checks = Array.from(found.querySelectorAll("[data-check]")).map((c) => c.textContent);
    expect(checks).toEqual([
      "Does this answer the request?29 of 31 files answer the request. 2 do not.",
      "Is it inside the expected period?All other files are dated inside Jun 1 – Sep 18, 2026.",
    ]);
    expect(found.querySelector("[data-provenance]")?.textContent).toBe(
      "Screened by Accrued Agent · screener@v3 · 2 s · instructions inside files are never followed",
    );
    expect(screen.getByRole("button", { name: "Screening · 2 flagged" })).toBeTruthy();
  });

  it("the flag reasons are the verified citations, verbatim, as agent text", async () => {
    show("a");
    const band = await screen.findByRole("region", { name: "Flagged files" });
    await waitFor(() => {
      expect(band.querySelectorAll('[data-actor="agent"]')).toHaveLength(2);
    });
    const reasons = Array.from(band.querySelectorAll('[data-actor="agent"]')).map(
      (r) => r.textContent,
    );
    expect(reasons).toEqual([STATEMENT_FLAG.quote, INVOICE_FLAG.quote]);
    expect(band.textContent).toContain("Granite Rock Logistics — August statement.pdf");
    expect(band.textContent).toContain("Invoice 40117.pdf");
  });

  it("View opens SHL-08 on the flagged file with its region lit", async () => {
    show("a");
    await card();
    const view = await screen.findByRole("button", {
      name: "View Granite Rock Logistics — August statement.pdf",
    });
    await waitFor(() => {
      expect(view.hasAttribute("disabled")).toBe(false);
    });
    fireEvent.click(view);
    await waitFor(() => {
      expect(screen.getByTestId("ov").textContent).not.toBe("null");
    });
    const [ref] = decodeOverlays(JSON.parse(screen.getByTestId("ov").textContent));
    expect(ref?.key).toBe("viewer");
    expect(ref?.args.slice(0, 2)).toEqual([STATEMENT_VERSION, STATEMENT_FLAG.match_id]);
  });

  it("Return… opens the dialog with Wrong document preselected and returns only on confirm", async () => {
    show("a");
    await card();
    fireEvent.click(
      screen.getByRole("button", {
        name: "Return… Granite Rock Logistics — August statement.pdf",
      }),
    );
    const dialog = await screen.findByRole("dialog", { name: "Return to client" });
    await waitFor(() => {
      expect(within(dialog).getByRole("radio", { name: "Wrong document" })).toBeTruthy();
    });
    expect(
      within(dialog).getByRole("radio", { name: "Wrong document" }).getAttribute("aria-checked"),
    ).toBe("true");
    expect(calls).not.toContain(WRITES[0]);
    fireEvent.click(within(dialog).getByRole("button", { name: "Return" }));
    await waitFor(() => {
      expect(calls).toContain(WRITES[0]);
    });
    expect(bodies[WRITES[0] ?? ""]).toEqual({ reason_code: "wrong_document" });
  });
});

describe("SHL-20b: the drafted follow-up", () => {
  it("opens the O3 sheet the platform drafted, and only the person's Send sends it", async () => {
    show("b");
    const sheet = await screen.findByRole("dialog", { name: "Follow-up to Luis Ferrante" });
    expect(sheet.textContent).toContain("POR-04 comment · SURL request");
    expect(sheet.textContent).toContain("Drafted by Accrued Agent · edit before sending");
    expect(sheet.textContent).toContain(
      "Returning: Granite Rock Logistics — August statement.pdf",
    );
    expect(sheet.textContent).toContain("Returning: Invoice 40117.pdf");
    expect(sheet.textContent).toContain(
      "Sends in the portal and by email. Both files show Returned.",
    );
    const body = within(sheet).getByRole<HTMLTextAreaElement>("textbox", {
      name: "Message to Luis Ferrante",
    });
    // DV-1: composed from the template's parts, never the handoff's per-payment model sentences.
    expect(body.value).not.toContain("please upload the invoice that payment settled");
    expect(body.value).toContain("Granite Rock Logistics — August statement.pdf · Wrong document");
    expect(calls).not.toContain(WRITES[1]);
    fireEvent.change(body, { target: { value: `${body.value}\nThanks.` } });
    fireEvent.click(within(sheet).getByRole("button", { name: "Send to Luis Ferrante" }));
    await waitFor(() => {
      expect(calls).toContain(WRITES[1]);
    });
    expect(calls).toContain("PATCH /v1/follow-ups/{follow_up_id}");
  });
});

describe("SHL-20c and d: rerun and passed", () => {
  it("c: the spinner line, skeleton answers and a disabled footer, polled every 2 s", async () => {
    show("c");
    const found = await screen.findByRole("region", { name: "Evidence screening" });
    await waitFor(() => {
      expect(found.textContent).toContain("Screening 2 new files…");
    });
    expect(found.querySelectorAll('[data-check-verdict="running"]')).toHaveLength(2);
    expect(
      within(found).getByRole("button", { name: "Draft follow-up" }).hasAttribute("disabled"),
    ).toBe(true);
    expect(within(found).getByRole("button", { name: "Rerun" }).hasAttribute("disabled")).toBe(
      true,
    );
    expect(SCREENING_POLL_MS).toBe(2000);
    expect(pollWhileRunning(RUNNING_CARD)).toBe(2000);
    expect(pollWhileRunning(PASSED_CARD)).toBe(false);
  });

  it("d: Passed, 40 of 40 payments supported, no flagged band, the chip reads passed", async () => {
    show("d");
    const found = await card();
    expect(found.querySelector("[data-verdict]")?.textContent).toBe("Passed");
    expect(found.querySelector("[data-screening-summary]")?.textContent).toBe(
      "40 of 40 payments supported",
    );
    expect(within(found).queryByRole("region", { name: "Flagged files" })).toBeNull();
    expect(within(found).queryByRole("button", { name: "Draft follow-up" })).toBeNull();
    expect(screen.getByRole("button", { name: "Screening · passed" })).toBeTruthy();
  });

  it("Rerun asks the server to screen again (a)", async () => {
    show("a");
    const found = await card();
    fireEvent.click(within(found).getByRole("button", { name: "Rerun" }));
    await waitFor(() => {
      expect(calls).toContain(WRITES[2]);
    });
  });
});

describe("SHL-20e: not screened", () => {
  it("reads the one line, with Screen now and Link to request… held off", async () => {
    show("e");
    const found = await screen.findByRole("region", { name: "Evidence screening" });
    expect(found.querySelector("[data-verdict]")?.textContent).toBe("Not screened");
    expect(found.textContent).toContain(
      "Screening has not run on this file. It runs once the file is linked to a request.",
    );
    expect(
      within(found).getByRole("button", { name: "Screen now" }).hasAttribute("disabled"),
    ).toBe(true);
    expect(
      within(found).getByRole("button", { name: "Link to request…" }).hasAttribute("disabled"),
    ).toBe(true);
    expect(document.body.textContent).toContain("FRF-30418.pdf");
  });
});

describe("SHL-20f: feedback", () => {
  it("Send feedback stays disabled until a reason is chosen, then records it", async () => {
    show("f");
    await card();
    const send = await screen.findByRole("button", { name: "Send feedback" });
    expect(send.hasAttribute("disabled")).toBe(true);
    fireEvent.click(send);
    expect(calls).not.toContain(WRITES[3]);
    fireEvent.click(screen.getByRole("radio", { name: "Wrong request match" }));
    expect(send.hasAttribute("disabled")).toBe(false);
    fireEvent.click(send);
    await waitFor(() => {
      expect(calls).toContain(WRITES[3]);
    });
    expect(bodies[WRITES[3] ?? ""]).toEqual({ thumb: "down", reason_code: "wrong_request_match" });
    await waitFor(() => {
      expect(document.querySelector("[data-provenance]")?.textContent).toContain(
        "Feedback sent · Wrong request match",
      );
    });
  });

  it("the server refuses a thumbs-down without a reason too", async () => {
    show("f");
    const handler = scenarios.f.handlers["POST /v1/screenings/{screening_result_id}/feedback"];
    const answer = await handler?.({
      method: "POST",
      path: "",
      params: { screening_result_id: FLAGGED_CARD.screening_result_id ?? "" },
      query: new URLSearchParams(),
      body: { thumb: "down" },
      persona: "cole-hart",
    });
    expect(answer?.status).toBe(422);
  });
});
