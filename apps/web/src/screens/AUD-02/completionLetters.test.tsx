// A-07-T28 / A-07-T29 remainder (DEC-3030): AUD-19's AUD-21 and AUD-22 chips open those letters
// inside the cockpit's Completion canvas, and Back closes them.
import { cleanup, fireEvent, screen } from "@testing-library/react";
import { type JSX, useState } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { aud21, COMPLETION_WORK_ITEM } from "../../fixtures/seed/audit-completion";
import { json, mockApi, renderRoutes } from "../../testing/support";
import {
  type CompletionLetter,
  isCompletionLetter,
  useCompletionLetterCanvas,
} from "./completionLetters";

afterEach(cleanup);

function Host({ open }: { open: CompletionLetter }): JSX.Element {
  const [letter, setLetter] = useState<CompletionLetter | null>(open);
  const canvas = useCompletionLetterCanvas(COMPLETION_WORK_ITEM, letter, () => {
    setLetter(null);
  });
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
});
