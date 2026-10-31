// ac-test-author: notanaskhan (ADR-078 independent suite, built in the S21 solo lane)
// P-04-T53 (TASK-2609; P-04 §3 SHL-11; the handoff's SHL-11 spec; INV-1, ADR-005): the SHL-11 UI
// from its spec and the C3 contract, through the screen's public exports and its fixture frames.
// The row's acceptance: "Tests written in notanaskhan's session pass and fail if any persona other
// than the reserved person can select an option." Covered: reserved-person radios only, rationale
// required, decided read-only with name and time, superseded struck, agent wording never as the
// decider, and the inline card (e) read-only for everyone.
import type { DecisionCardOut } from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode } from "../../../app-core/fixture-mode";
import { SHL11 } from "../../../fixtures/seed/review";
import { renderRoutes } from "../../../testing/support";
import { DecisionInlineCard, DecisionSheet } from "..";
import { CARD_ID, type Shl11State, scenarios } from "../scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

const QUESTION = "Which planning materiality should the Northwind PY2025 audit use?";
const RESERVED = "margaret-okonkwo";
// Everyone in the seed who is not the card's reserved Engagement Partner, and the agent's own run.
const OTHERS = [
  "hannah-leclerc",
  "marcus-delaney",
  "ana-cruz",
  "daniel-reyes",
  "samuel-ito",
  "thomas-whitcombe",
  "grace-holloway",
] as const;
const CARD_ROUTE = "GET /v1/decision-cards/{card_id}";

/** The card as C3 answers it to `persona`: `decision.decide` only for the reserved person. */
function servedTo(persona: string, frame: DecisionCardOut = SHL11.a): DecisionCardOut {
  const actions = frame.card.allowed_actions.filter((a) => a !== "decision.decide");
  return {
    ...frame,
    card: {
      ...frame.card,
      allowed_actions: persona === RESERVED ? [...actions, "decision.decide"] : actions,
    },
  };
}

function sheet(state: Shl11State, persona?: string, card?: DecisionCardOut): void {
  const scenario = scenarios[state];
  const handlers: Record<string, FixtureHandler> =
    card === undefined
      ? scenario.handlers
      : {
          ...scenario.handlers,
          [CARD_ROUTE]: () =>
            new Response(JSON.stringify(card), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            }),
        };
  restore = installFixtureMode(
    { ...scenario, handlers },
    persona === undefined ? {} : { persona },
  );
  renderRoutes([
    {
      path: "/",
      component: () => <DecisionSheet cardId={CARD_ID} open onOpenChange={() => undefined} />,
    },
  ]);
}

const radios = (): HTMLButtonElement[] => screen.queryAllByRole<HTMLButtonElement>("radio");
const selectable = (r: HTMLButtonElement): boolean =>
  !r.disabled && r.getAttribute("aria-disabled") !== "true";

describe("reserved-person radios only", () => {
  it("test_ac1_the_reserved_person_can_select_an_option", async () => {
    sheet("a", RESERVED, servedTo(RESERVED));
    await screen.findByText(QUESTION);
    expect(radios().length).toBeGreaterThan(1);
    expect(radios().every(selectable)).toBe(true);
    const option = screen.getByRole<HTMLButtonElement>("radio", { name: "1.5% — $252,200" });
    fireEvent.click(option);
    expect(option.getAttribute("aria-checked")).toBe("true");
  });

  it.each(OTHERS)("test_ac1_%s_can_select_no_option", async (persona) => {
    sheet("a", persona, servedTo(persona));
    await screen.findByText(QUESTION);
    expect(radios().length).toBeGreaterThan(1);
    for (const radio of radios()) {
      expect(selectable(radio)).toBe(false);
      fireEvent.click(radio);
      expect(radio.getAttribute("aria-checked")).toBe("false");
    }
    expect(screen.queryByRole("button", { name: /^Decide/u })).toBeNull();
    expect(screen.queryByLabelText("Rationale (required)")).toBeNull();
  });

  it("test_ac1_the_screen_never_infers_the_right_to_decide_from_who_is_signed_in", async () => {
    // Margaret signed in, but C3 does not offer her the decide action on this card: no choice.
    sheet("a", RESERVED, servedTo("someone-else"));
    await screen.findByText(QUESTION);
    expect(radios().some(selectable)).toBe(false);
  });

  it("test_ac1_the_inline_card_lets_no_one_choose_not_even_the_reserved_person", async () => {
    restore = installFixtureMode(scenarios.e, { persona: RESERVED });
    renderRoutes([{ path: "/", component: () => <DecisionInlineCard cardId={CARD_ID} /> }]);
    await screen.findByText(QUESTION);
    expect(radios()).toHaveLength(0);
    expect(screen.queryByRole("button", { name: /^Decide/u })).toBeNull();
    expect(screen.getByRole("button", { name: "Open decision" })).toBeTruthy();
  });
});

describe("rationale required", () => {
  it("test_ac2_decide_waits_for_an_option_and_a_rationale", async () => {
    sheet("a", RESERVED, servedTo(RESERVED));
    const decide = await screen.findByRole<HTMLButtonElement>(
      "button",
      { name: /^Decide/u },
      { timeout: 10_000 },
    );
    expect(decide.disabled).toBe(true);
    fireEvent.click(screen.getByRole("radio", { name: "1.0% — $168,100" }));
    expect(decide.disabled).toBe(true);
    const rationale = screen.getByLabelText("Rationale (required)");
    fireEvent.change(rationale, { target: { value: "   " } });
    expect(decide.disabled).toBe(true); // blank is no rationale
    fireEvent.change(rationale, { target: { value: "Lower risk tolerance this year." } });
    expect(decide.disabled).toBe(false);
    fireEvent.change(rationale, { target: { value: "" } });
    expect(decide.disabled).toBe(true);
  });

  it("test_ac2_a_rationale_without_an_option_does_not_enable_decide", async () => {
    sheet("a", RESERVED, servedTo(RESERVED));
    const decide = await screen.findByRole<HTMLButtonElement>(
      "button",
      { name: /^Decide/u },
      { timeout: 10_000 },
    );
    fireEvent.change(screen.getByLabelText("Rationale (required)"), {
      target: { value: "A reason with no option chosen." },
    });
    expect(decide.disabled).toBe(true);
  });
});

describe("decided read-only with name and time", () => {
  it("test_ac3_a_decided_card_names_the_person_and_time_and_offers_no_choice", async () => {
    sheet("c", RESERVED);
    expect(await screen.findByText("Decided")).toBeTruthy();
    const line = document.querySelector("[data-decision-line]")?.textContent ?? "";
    expect(line).toContain("Margaret Okonkwo");
    expect(line).toMatch(/\d{1,2}:\d{2}\s?(AM|PM)/u);
    expect(radios()).toHaveLength(0);
    expect(screen.queryByRole("button", { name: /^Decide/u })).toBeNull();
    expect(screen.queryByRole("textbox")).toBeNull(); // the rationale reads as text
  });

  it("test_ac3_the_decided_inline_card_shows_the_decision_read_only", async () => {
    restore = installFixtureMode(scenarios.c, { persona: RESERVED });
    renderRoutes([{ path: "/", component: () => <DecisionInlineCard cardId={CARD_ID} /> }]);
    await screen.findByText(QUESTION);
    expect(screen.getByText("Decided")).toBeTruthy();
    expect(radios()).toHaveLength(0);
  });
});

describe("superseded struck", () => {
  it("test_ac4_a_superseded_decision_says_so_and_its_values_are_struck", async () => {
    sheet("h", RESERVED);
    expect(await screen.findByText(/^Superseded by v\d+$/u)).toBeTruthy();
    const line = document.querySelector("[data-decision-line]");
    expect(line).not.toBeNull();
    expect(line?.className).toContain("line-through");
    expect(screen.queryByText("Decided")).toBeNull(); // superseded is not the current decision
    expect(radios()).toHaveLength(0);
  });
});

describe("agent wording never as the decider", () => {
  const DECIDER = [
    /Accrued Agent decided/iu,
    /decided by Accrued Agent/iu,
    /Agent decided/iu,
    /the agent (chose|selected|approved)/iu,
    /\bI (decided|chose|selected)\b/iu,
  ];

  it.each(["a", "b", "c", "d", "f", "g", "h"] as const)(
    "test_ac5_frame_%s_never_words_the_agent_as_the_decider",
    async (state) => {
      sheet(state);
      await screen.findByRole("dialog");
      await screen.findByText((_, el) => el?.tagName === "H3");
      const text = document.body.textContent;
      for (const words of DECIDER) expect(text).not.toMatch(words);
    },
  );

  it("test_ac5_the_recommendation_is_a_tag_on_an_option_not_a_choice", async () => {
    sheet("a", "hannah-leclerc", servedTo("hannah-leclerc"));
    await screen.findByText(QUESTION);
    expect(screen.getByText("Recommended by Accrued Agent")).toBeTruthy();
    expect(radios().some((r) => r.getAttribute("aria-checked") === "true")).toBe(false);
  });

  it("test_ac5_history_names_a_person_for_the_decision_and_the_agent_only_for_the_proposal", async () => {
    sheet("d", RESERVED);
    await screen.findByText(QUESTION);
    const rows = [...document.querySelectorAll("[data-history]")].map((r) => r.textContent);
    const decided = rows.filter((r) => /decided by/u.test(r));
    expect(decided.length).toBeGreaterThan(0);
    for (const row of decided) expect(row).not.toMatch(/Agent/u);
    for (const row of rows.filter((r) => /Accrued Agent/u.test(r))) {
      expect(row).toMatch(/proposed by Accrued Agent/u);
    }
  });

  it("test_ac5_the_inline_card_attributes_the_tag_to_the_agent_for_screen_readers", async () => {
    restore = installFixtureMode(scenarios.e);
    renderRoutes([{ path: "/", component: () => <DecisionInlineCard cardId={CARD_ID} /> }]);
    const card = (await screen.findByText(QUESTION)).closest("section") as HTMLElement;
    expect(within(card).getByText(/by Accrued Agent/u)).toBeTruthy();
  });
});
