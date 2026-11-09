// A-07-T28 / A-07-T29 remainder (DEC-3030): AUD-19's AUD-21 and AUD-22 chips open those letters
// inside the cockpit's Completion canvas, and Back closes them.
import { cleanup, fireEvent, screen } from "@testing-library/react";
import { type JSX, useState } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { aud21, COMPLETION_WORK_ITEM } from "../../fixtures/seed/audit-completion";
import { json, mockApi, renderRoutes } from "../../testing/support";
import {
  type CompletionLetter,
  type LettersMode,
  isCompletionLetter,
  useCompletionLetterCanvas,
} from "./completionLetters";

afterEach(cleanup);

function Host({ open, mode }: { open: CompletionLetter; mode?: LettersMode }): JSX.Element {
  const [letter, setLetter] = useState<CompletionLetter | null>(open);
  const canvas = useCompletionLetterCanvas(
    COMPLETION_WORK_ITEM,
    letter,
    () => {
      setLetter(null);
    },
    mode,
  );
  return canvas === null ? (
    <p>Completion Checklist</p>
  ) : (
    <section aria-label={canvas.title}>{canvas.children}</section>
  );
}

describe("AUD-02 completion letters", () => {
  it("only AUD-21 and AUD-22 open inside the cockpit", () => {
    expect(isCompletionLetter("AUD-21")).toBe(true);
    expect(isCompletionLetter("AUD-22")).toBe(true);
    expect(isCompletionLetter("AUD-20")).toBe(false);
  });

  it("AUD-22 opens on its E0 rows and Back closes it", async () => {
    mockApi({});
    renderRoutes([{ path: "/", component: () => <Host open="AUD-22" /> }]);
    expect(await screen.findByRole("region", { name: "Governance communications" })).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: "‹ Cockpit" }));
    expect(await screen.findByText("Completion Checklist")).toBeTruthy();
  });

  it("AUD-21 reads the representation letter through its route", async () => {
    mockApi({
      [`GET /v1/audits/${COMPLETION_WORK_ITEM}/representation-letter`]: () => json(aud21("a")),
    });
    renderRoutes([{ path: "/", component: () => <Host open="AUD-21" /> }]);
    expect(await screen.findByRole("region", { name: "Representation letter" })).toBeTruthy();
  });

  it("live: AUD-22 lists the server's communications and draws the selected letter", async () => {
    const row = {
      id: "c-1",
      kind: "planning_260" as const,
      standard: "AU-C 260",
      status: "draft" as const,
      channel: null,
      due_on: null,
      overdue: false,
      sent_at: null,
      acknowledged_at: null,
      acknowledged_by_body: null,
    };
    mockApi({
      [`GET /v1/audits/${COMPLETION_WORK_ITEM}/governance-communications`]: () =>
        json({ allowed_actions: [], items: [row], required_sent: 0, required_total: 2 }),
      [`GET /v1/audits/${COMPLETION_WORK_ITEM}/governance-communications/c-1`]: () =>
        json({
          row,
          sections: [
            {
              key: "scope_timing",
              title: "Planned scope and timing",
              text: "- Fieldwork in October",
              built_from: [],
              citations: [],
              human_edited: false,
            },
          ],
          version: 1,
          version_no: 1,
          content_hash: "a".repeat(64),
          watermark: "draft",
          allowed_actions: ["governance_comm.approve_send"],
        }),
    });
    renderRoutes([{ path: "/", component: () => <Host open="AUD-22" mode="live" /> }]);
    expect(await screen.findByText("Planned scope and timing")).toBeTruthy();
    expect(screen.getByText("- Fieldwork in October")).toBeTruthy();
    // Allowed by the server, but not bound here yet: no button that does nothing.
    expect(screen.queryByRole("button", { name: "Approve & send…" })).toBeNull();
    expect(document.querySelector("[data-screen='AUD-22'][data-live='true']")).not.toBeNull();
  });

  it("live: AUD-21 draws the server's paragraphs and signers, not the artboard's paper", async () => {
    mockApi({
      [`GET /v1/audits/${COMPLETION_WORK_ITEM}/representation-letter`]: () => json(aud21("a")),
    });
    renderRoutes([{ path: "/", component: () => <Host open="AUD-21" mode="live" /> }]);
    expect(await screen.findByRole("region", { name: "Representation letter" })).toBeTruthy();
    expect(await screen.findByText("General representations (AU-C 580)")).toBeTruthy();
    expect(screen.queryByText(/Brightwater Hale LLP/)).toBeNull();
  });

  it("live mode opens AUD-21 and AUD-22; off opens neither; AUD-23 reads the live report", () => {
    expect(isCompletionLetter("AUD-22", "live")).toBe(true);
    expect(isCompletionLetter("AUD-21", null)).toBe(false);
    expect(isCompletionLetter("AUD-23", null)).toBe(true); // A-07-T34
  });
});
