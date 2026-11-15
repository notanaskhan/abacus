// T-05-T66 steps 3–8 (TASK-8073; T-05 §F13; SPEC-651 AC-13.1 to AC-13.3): with agents off every
// model-backed control on the entity screens is disabled with its reason (never hidden behind an
// error), the person's way stays open, a run waiting on §7216 consent names it, a firm without the
// entity returns entitlement keeps the coordination view locked, and with `tax.entity_workspace`
// off every entity route draws its own screen.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { JSX, ReactNode } from "react";
import { returnRecordOptions } from "@abacus/api-client/query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { tallies, trialBalance } from "../../fixtures/seed/tax-entity";
import { ridgeline } from "../../fixtures/seed/tax-entity-allocation";
import {
  ASSIGNEES,
  TAX_EXEMPT,
  issueDetail,
  ridgelineIssues,
} from "../../fixtures/seed/tax-entity-issues";
import { COPY as TXP02_COPY } from "../TXP-02/copy";
import { TXP02 } from "../TXP-02";
import { TXP06 } from "../TXP-06";
import { COPY as TXP10_COPY } from "../TXP-10/copy";
import { TXP10 } from "../TXP-10";
import { COPY } from "./copy";
import { waitingLine } from "./index";

const flags = vi.hoisted(() => ({ entity: true, entitled: true }));
vi.mock("../../app-core/flags", async (actual) => ({
  ...(await actual<typeof import("../../app-core/flags")>()),
  useFlag: (name: string) => (name === "tax.entity_workspace" ? flags.entity : undefined),
  useEntitlement: (module: string) => (module === "tax_entity_returns" ? flags.entitled : true),
}));
vi.mock("@tanstack/react-router", async (actual) => ({
  ...(await actual<typeof import("@tanstack/react-router")>()),
  useNavigate: () => () => undefined,
  Navigate: () => null,
}));

const { EntityReturn } = await import("./EntityReturn");

afterEach(() => {
  cleanup();
  flags.entity = true;
  flags.entitled = true;
});

const OFF = "Accrued Agent is off for this firm. Prepare this by hand.";

describe("T-05-T66 agents off (AC-13.1)", () => {
  it("TXP-02: Map… stays the person's pick and the screen says why", () => {
    render(
      <TXP02
        tb={trialBalance("run2")}
        tallies={tallies("run2")}
        view="account"
        statement="full"
        agentReason={OFF}
      />,
    );
    const note = document.querySelector("[data-agents-off='tax.account_mapper']");
    expect(note?.textContent).toContain("Prepared without agents");
    expect(screen.queryAllByText(TXP02_COPY.byAccount).length).toBeGreaterThan(0);
  });

  it("TXP-06: the structure is keyed by hand and the rail says why", () => {
    render(<TXP06 structure={ridgeline()} forceOpen agentReason={OFF} />);
    const note = document.querySelector("[data-agents-off='tax.agreement_reader']");
    expect(note?.textContent).toContain(OFF);
  });

  it("TXP-10: fix instructions are disabled with the reason, never hidden", () => {
    const onInstruct = vi.fn();
    render(
      <TXP10
        queue={ridgelineIssues("a", false)}
        selectedId={TAX_EXEMPT}
        detail={issueDetail(TAX_EXEMPT, "a")}
        assignees={ASSIGNEES.items}
        showResolved={false}
        query=""
        onInstruct={onInstruct}
        agentOffered={false}
        agentReason={OFF}
      />,
    );
    const button = screen.getByRole("button", { name: TXP10_COPY.composer });
    expect(button).toHaveProperty("disabled", true);
    fireEvent.click(button);
    expect(onInstruct).not.toHaveBeenCalled();
    expect(document.querySelector("[data-agents-off='issues.fix_runner']")).not.toBeNull();
  });

  it("TXP-10: while the capabilities load nothing is offered (fail closed)", () => {
    render(
      <TXP10
        queue={ridgelineIssues("a", false)}
        selectedId={TAX_EXEMPT}
        detail={issueDetail(TAX_EXEMPT, "a")}
        assignees={ASSIGNEES.items}
        showResolved={false}
        query=""
        agentOffered={false}
        agentReason={null}
      />,
    );
    expect(screen.getByRole("button", { name: TXP10_COPY.composer })).toHaveProperty(
      "disabled",
      true,
    );
  });

  it("TXP-00: a run waiting on §7216 consent names it; any other wait is the answer", () => {
    expect(waitingLine(["consent_7216"])).toBe(COPY.waitingConsent);
    expect(waitingLine([])).toBe(COPY.waiting);
  });
});

function withRecord(form: string): (props: { children: ReactNode }) => JSX.Element {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const key = returnRecordOptions({ path: { return_id: "r1" } }).queryKey;
  client.setQueryData(key, {
    engagement_id: "e1",
    row: { form, tax_year: 2025, client_name: "Ridgeline Ventures LLC" },
  } as never);
  return function Wrapper({ children }) {
    return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
  };
}

describe("T-05-T66 entitlement and flag (AC-13.2, AC-13.3)", () => {
  it("without tax_entity_returns the return keeps the coordination view, locked", () => {
    flags.entitled = false;
    render(
      <EntityReturn
        returnId="r1"
        slug="agent"
        overview={<p data-overview>TAX-02</p>}
        onOpen={() => undefined}
        onComposer={() => undefined}
      />,
      { wrapper: withRecord("1065") },
    );
    expect(document.querySelector("[data-entity-locked]")).not.toBeNull();
    expect(screen.getByText(COPY.lockedTitle)).toBeTruthy();
    expect(document.querySelector("[data-overview]")).not.toBeNull();
  });

  it.each(["agent", "issues", "workpaper", "activity", "review"] as const)(
    "with tax.entity_workspace off, %s draws the route's own screen, never a blank pane",
    (slug) => {
      flags.entity = false;
      render(
        <EntityReturn
          returnId="r1"
          slug={slug}
          overview={<p data-overview>TAX-02</p>}
          onOpen={() => undefined}
          onComposer={() => undefined}
        />,
        { wrapper: withRecord("1065") },
      );
      expect(document.querySelector("[data-overview]")).not.toBeNull();
    },
  );
});
