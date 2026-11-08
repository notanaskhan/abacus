// A-05-T58 (TASK-6214): EBP-07 in fixture mode. Row: "Typed form values render in #6A98E8, one
// matchId lights row and field together, and the empty state shows until Summit's draft arrives."
import { client } from "@abacus/api-client/client";
import { Matchable, MatchScope } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import type { JSX } from "react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { EBP07_DRAFT_VERSION, EBP07_WORK_ITEM } from "../../fixtures/seed/ebp07";
import { newQueryClient } from "../../testing/support";
import { type Form5500Tab, useForm5500Canvas } from "./Form5500";
import { type Ebp07State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

const FIELD = `ev:${EBP07_DRAFT_VERSION}#p2:1l`;

function Canvas({ tab, raised }: { tab: Form5500Tab; raised?: string[] }): JSX.Element {
  const canvas = useForm5500Canvas(EBP07_WORK_ITEM, {
    tab,
    onRemind: () => undefined,
    onRaise: (line) => raised?.push(line.line),
  });
  return (
    <MatchScope>
      <div data-test="state">{canvas.state?.kind}</div>
      <div data-test="actions">{canvas.actions}</div>
      {canvas.children}
      {/* The viewer's field region for line 1l(b): the same match id as the row. */}
      <Matchable id={FIELD as never} kind="region" as="div">
        16,812,400
      </Matchable>
    </MatchScope>
  );
}

function show(state: Ebp07State, tab: Form5500Tab = "schedule_h", raised?: string[]): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <Canvas tab={tab} {...(raised === undefined ? {} : { raised })} />
    </QueryClientProvider>,
  );
}

const drawn = (selector: string): Promise<HTMLElement> =>
  waitFor(
    () => {
      const found = document.querySelector<HTMLElement>(selector);
      expect(found).not.toBeNull();
      return found as HTMLElement;
    },
    { timeout: 6000 },
  );

describe("EBP-07", () => {
  it("a: the only differences are the 48,600 receivable, split 15,060 / 33,540", async () => {
    show("a");
    const net = await drawn("[data-line='1l']");
    expect(net.textContent).toContain("16,861,000");
    expect(net.textContent).toContain("16,812,400");
    expect(net.textContent).toContain("48,600");
    expect((await drawn("[data-line='1b(1)']")).textContent).toContain("15,060");
    expect((await drawn("[data-line='1b(2)']")).textContent).toContain("33,540");
    expect((await drawn("[data-line='2j']")).dataset.classification).toBe("tie");
    const items = document.querySelectorAll("[data-classification='reconciling_item']");
    expect(Array.from(items).map((r) => (r as HTMLElement).dataset.line)).toEqual([
      "1b(1)", "1b(2)", "1f", "1l", "2a(1)(A)", "2a(1)(B)", "2d", "2k",
    ]); // prettier-ignore
  });

  it("a: no $ in the statement table, and the form's values are the typed ink", async () => {
    show("a");
    const table = await drawn("[data-ebp07='schedule-h']");
    expect(table.textContent).not.toContain("$");
    const form = (await drawn("[data-line='1c(9)']")).querySelector("[data-col='form']");
    expect(form?.className).toContain("text-doc-typed");
    const fs = (await drawn("[data-line='1c(9)']")).querySelector("[data-col='fs']");
    expect(fs?.className).not.toContain("text-doc-typed");
  });

  it("a: one match id lights the row and the draft's field together", async () => {
    show("a");
    const row = await drawn("[data-line='1l']");
    expect(row.getAttribute("data-match")).toBe(FIELD);
    fireEvent.focus(row);
    const field = document.querySelector<HTMLElement>(`[data-match-kind='region']`);
    await waitFor(() => {
      expect(row.hasAttribute("data-lit")).toBe(true);
      expect(field?.hasAttribute("data-lit")).toBe(true);
    });
  });

  it("a: the Note 8 card reads the server's figures", async () => {
    show("a");
    const note = await drawn("[data-ebp07='note']");
    expect(note.textContent).toContain("16,861,000");
    expect(note.textContent).toContain("(48,600)");
    expect(note.textContent).toContain("2,583,900");
    expect(note.textContent).toContain("Send note to AUD-20");
  });

  it("b: Part IV 4a reads Yes · 33,540, consistent with EBP-04", async () => {
    show("b", "part_iv");
    const row = await drawn("[data-part-iv='4a']");
    expect(row.dataset.consistency).toBe("consistent");
    expect(row.textContent).toContain("Yes");
    expect(row.textContent).toContain("33,540");
    expect(row.querySelector("[data-evidence='EBP-04']")).not.toBeNull();
  });

  it("c: the 4i schedule totals 16,812,400 and the 4a schedule follows", async () => {
    show("c", "schedules");
    expect((await drawn("[data-held='total']")).textContent).toContain("16,812,400");
    const krs = await drawn("[data-held='KRS 500 Index Fund']");
    expect(krs.textContent).toContain("6,120,450");
    expect(krs.dataset.mark).toBe("*");
    expect(krs.textContent).toContain("**"); // cost omitted, participant-directed
    expect(
      document
        .querySelector("[data-held='Self-directed brokerage accounts (BrokerWindow)']")
        ?.getAttribute("data-mark"),
    ).toBe("");
    expect((await drawn("[data-held='total']")).hasAttribute("data-ties")).toBe(true);
    expect(document.body.textContent).toContain("* Party in interest");
    expect((await drawn("[data-ebp07='schedule-4a']")).textContent).toContain("line 4a");
  });

  it("d: the empty state shows until Summit's draft arrives", async () => {
    show("d");
    await waitFor(() => {
      expect(document.querySelector("[data-test='state']")?.textContent).toBe("empty");
    });
    expect(document.querySelector("[data-ebp07='schedule-h']")).toBeNull();
  });

  it("b: every line 4a to 4m; code checks 4a, the others read not checked", async () => {
    show("b", "part_iv");
    await drawn("[data-part-iv='4m']");
    expect(document.querySelectorAll("[data-part-iv]")).toHaveLength(13);
    expect((await drawn("[data-part-iv='4e']")).textContent).toContain("500,000");
    expect(
      (await drawn("[data-part-iv='4e']")).querySelector("[data-ebp07='not-checked']"),
    ).not.toBeNull();
  });

  it("e: 4a answered No is flagged inconsistent, with Raise exception…", async () => {
    const raised: string[] = [];
    show("e", "part_iv", raised);
    const row = await drawn("[data-part-iv='4a']");
    expect(row.dataset.consistency).toBe("inconsistent");
    expect(row.textContent).toContain("Inconsistent with the late-deposit finding (EBP-04)");
    const raise = Array.from(row.querySelectorAll("button")).find((b) =>
      b.textContent.includes("Raise exception"),
    );
    raise?.click();
    expect(raised).toEqual(["4a"]);
  });

  it("off: ebp.modules off draws C-20", async () => {
    show("off");
    await waitFor(() => {
      expect(document.querySelector("[data-test='state']")?.textContent).toBe("flag-off");
    });
  });
});
