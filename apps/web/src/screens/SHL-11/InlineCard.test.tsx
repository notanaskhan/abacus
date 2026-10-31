// SHL-11 e · the inline decision card (P-04-T52) on its fixture scenario, and the acceptance: "The
// inline card specimen matches SHL-11e and Open decision opens the sheet on the same card." The
// pixels are the visual suite's; here the content, the read-only options, the agent's tag and the
// `?ov=decision:<cardId>` layer the button opens, with the sheet drawing that card.
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, within } from "@testing-library/react";
import type { JSX } from "react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { useOverlays } from "../../app-core/overlay-host";
import "../../routes/firm/sheets"; // registers `decision` with the overlay registry
import { renderRoutes } from "../../testing/support";
import { DecisionInlineCard, DecisionSheet } from ".";
import { CARD_ID, scenarios } from "./scenarios";

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

function Dock(): JSX.Element {
  const { refs } = useOverlays();
  const layer = refs.find((r) => r.key === "decision");
  return (
    <>
      <DecisionInlineCard cardId={CARD_ID} />
      {layer?.args[0] !== undefined && (
        <DecisionSheet cardId={layer.args[0]} open onOpenChange={() => undefined} />
      )}
    </>
  );
}

describe("SHL-11 e · inline dock card", () => {
  it("e: the question, two compact read-only options and the agent's Recommended tag", async () => {
    restore = installFixtureMode(scenarios.e);
    renderRoutes([{ path: "/", component: () => <DecisionInlineCard cardId={CARD_ID} /> }]);
    const card = (await screen.findByText(QUESTION)).closest("[data-decision-inline]");
    expect(card?.getAttribute("data-decision-inline")).toBe("dock");
    expect(card?.className).toContain("w-[330px]");
    const options = within(card as HTMLElement).getAllByRole("listitem");
    expect(options.map((o) => o.textContent)).toEqual([
      "1.0% — $168,100",
      "1.5% — $252,200Recommended by Accrued Agent",
    ]);
    // Read-only: nothing to choose here, and nothing an agent could press to decide.
    expect(within(card as HTMLElement).queryAllByRole("radio")).toHaveLength(0);
    expect(screen.queryByRole("button", { name: /Decide/u })).toBeNull();
    expect(screen.getByRole("button", { name: "Open decision" })).toBeTruthy();
  });

  it("e: Open decision opens the sheet on the same card", async () => {
    restore = installFixtureMode(scenarios.e);
    renderRoutes([{ path: "/", component: Dock }]);
    fireEvent.click(await screen.findByRole("button", { name: "Open decision" }));
    const sheet = await screen.findByRole("dialog");
    expect(within(sheet).getByText(QUESTION)).toBeTruthy();
    expect(
      within(sheet).getByText(/Reserved to Engagement Partner · Margaret Okonkwo/u),
    ).toBeTruthy();
  });

  it("the chat variant (P-09) is the same card at the thread's width and calls its host", async () => {
    restore = installFixtureMode(scenarios.e);
    const onOpen = vi.fn();
    renderRoutes([
      {
        path: "/",
        component: () => <DecisionInlineCard cardId={CARD_ID} variant="chat" onOpen={onOpen} />,
      },
    ]);
    const card = (await screen.findByText(QUESTION)).closest("[data-decision-inline]");
    expect(card?.getAttribute("data-decision-inline")).toBe("chat");
    expect(card?.className).toContain("max-w-[520px]");
    fireEvent.click(screen.getByRole("button", { name: "Open decision" }));
    expect(onOpen).toHaveBeenCalledWith(CARD_ID);
  });

  it("a decided card shows the decision and no recommendation tag", async () => {
    restore = installFixtureMode(scenarios.c);
    renderRoutes([{ path: "/", component: () => <DecisionInlineCard cardId={CARD_ID} /> }]);
    await screen.findByText(QUESTION);
    expect(screen.getByText("Decided")).toBeTruthy();
    expect(document.querySelectorAll("[data-decided]")).toHaveLength(1);
    expect(screen.queryByText("Recommended")).toBeNull();
  });
});
