// assertInvariants, UI layer (F-04-T21; F-04.30; ch. 04 §9.5): what a journey step's page must
// never show, checked after every step. The data-layer half (audit events by actor kind, from
// `_matrix.py`) is F-04-T30's `abacus_tools.harness.invariants`; so are the injected-violation
// self-tests. Every failure names the step and the invariant.
//
//   INV-1 the agent never decides: no approve, accept, sign-off, release, send, post, decide or
//         adopt control sits on an agent-owned element (`data-actor="agent"`, AgentText and a
//         suggested AgentFilledMarker value);
//   INV-2 an agent-set value shows a verified citation or "Uncited", and an "Uncited" value's
//         human gate is disabled;
//   INV-3 walls hold: a walled persona's page names no walled client and no copy reveals a hidden
//         count (DEC-43); probes of walled records answer 404;
//   INV-4 portal scopes hold: a portal persona's page names nothing outside its scopes, never says
//         "Accrued" (DEC-01), and probes of out-of-scope records answer 404;
//   INV-5 attribution: nothing reads that the Accrued Agent approved, accepted, signed, released,
//         sent, posted, decided or adopted.
import { expect, type Page } from "@playwright/test";
import type { PersonaAdapter } from "./adapters";
import type { Persona } from "./personas";

export interface InvariantContext {
  /** The journey step, for the failure message: "J02 step 4: publish the binder". */
  step: string;
  persona: Persona;
  /** Names this persona must not see on any page (another client's binder, a walled record). */
  outOfScope?: readonly string[];
  /** API paths this persona must get 404 for (a walled record, another client's binder). */
  probes?: readonly string[];
  /** The project's adapter, which runs the probes; probes are skipped where it has no API. */
  adapter?: PersonaAdapter;
}

/** The human-only verbs (plan 04 rule 9; F-05 H1; inv.spec.ts). */
export const HUMAN_VERBS = [
  "Approve",
  "Accept",
  "Sign off",
  "Release",
  "Send",
  "Post",
  "Decide",
  "Adopt",
] as const;

/** INV-5: the Agent as the one who decided. */
export const AGENT_APPROVER =
  /\b(Approved|Accepted|Signed off|Released|Sent|Posted|Decided|Adopted|Waived|Rejected|Confirmed) by (the )?Accrued Agent\b/i;

/** INV-3: copy that reveals a hidden count (DEC-43). */
export const HIDDEN_COUNT = [
  /\b\d+\s+(hidden|walled)\b/i,
  /\bhidden by (an? )?(ethical )?wall\b/i,
];

interface PageFacts {
  agentVerbs: string[];
  uncitedAgentValues: string[];
  openUncitedGates: string[];
  text: string;
}

async function factsOf(page: Page): Promise<PageFacts> {
  return page.evaluate(
    (verbs) => {
      const verb = new RegExp(`^(${verbs.join("|")})\\b`, "i");
      const nameOf = (el: Element): string =>
        (el.getAttribute("aria-label") ?? el.textContent).trim().replace(/\s+/g, " ");
      const controls = [
        ...document.querySelectorAll(
          'button, a[href], [role="button"], [role="menuitem"], [role="link"]',
        ),
      ];
      const agentVerbs = controls
        .filter((el) => verb.test(nameOf(el)) && el.closest('[data-actor="agent"]') !== null)
        .map(nameOf);

      const holderOf = (el: Element): Element =>
        el.closest('tr, li, [role="row"], [data-row], section, [role="dialog"]') ??
        el.parentElement ??
        el;
      const verified = (holder: Element): boolean =>
        [...holder.querySelectorAll("button, [role='button']")].some((b) =>
          /^Open the source at /.test(nameOf(b)),
        );
      const uncited = (holder: Element): boolean => /\bUncited\b/.test(holder.textContent);
      const values = [...document.querySelectorAll('[data-actor="agent"][data-filled]')];
      const uncitedAgentValues = values
        .filter((v) => {
          const holder = holderOf(v);
          return !verified(holder) && !uncited(holder);
        })
        .map(nameOf);
      const openUncitedGates = values
        .map(holderOf)
        .filter((holder) => uncited(holder) && !verified(holder))
        .flatMap((holder) =>
          [...holder.querySelectorAll<HTMLButtonElement>("[data-human-verb]")]
            .filter((b) => !b.disabled && b.getAttribute("aria-disabled") !== "true")
            .map(nameOf),
        );
      return {
        agentVerbs,
        uncitedAgentValues,
        openUncitedGates,
        text: document.body.innerText,
      };
    },
    HUMAN_VERBS as unknown as string[],
  );
}

/** The invariants a page breaks, as "INV-n: …" lines (empty when it holds). Exported for the
 * harness's own tests. */
export function violations(
  facts: PageFacts,
  ctx: InvariantContext,
  probeStatuses: ReadonlyMap<string, number>,
): string[] {
  const out: string[] = [];
  for (const v of facts.agentVerbs) out.push(`INV-1: "${v}" sits on an agent-owned element`);
  for (const v of facts.uncitedAgentValues) {
    out.push(`INV-2: agent-set value "${v}" has no verified citation and does not say Uncited`);
  }
  for (const v of facts.openUncitedGates) {
    out.push(`INV-2: "${v}" is enabled on an Uncited agent-set value`);
  }
  const walled = ctx.persona.walledFrom ?? [];
  for (const name of walled) {
    if (facts.text.includes(name)) out.push(`INV-3: ${ctx.persona.name} sees walled "${name}"`);
  }
  for (const pattern of HIDDEN_COUNT) {
    const m = pattern.exec(facts.text);
    if (m !== null) out.push(`INV-3: copy reveals a hidden count: "${m[0]}"`);
  }
  const portal = ctx.persona.kind !== "staff";
  for (const name of ctx.outOfScope ?? []) {
    if (facts.text.includes(name)) {
      out.push(`${portal ? "INV-4" : "INV-3"}: ${ctx.persona.name} sees out-of-scope "${name}"`);
    }
  }
  if (portal && /\bAccrued\b/.test(facts.text)) {
    out.push(`INV-4: the portal shows "Accrued" to ${ctx.persona.name} (DEC-01)`);
  }
  for (const [path, status] of probeStatuses) {
    if (status !== 404) {
      out.push(
        `${portal ? "INV-4" : "INV-3"}: ${path} answered ${String(status)} to ${ctx.persona.name}, not 404`,
      );
    }
  }
  const approver = AGENT_APPROVER.exec(facts.text);
  if (approver !== null) out.push(`INV-5: "${approver[0]}"`);
  return out;
}

/** INV-1 to INV-5 on the page as it stands after `ctx.step`. */
export async function assertInvariants(page: Page, ctx: InvariantContext): Promise<void> {
  const facts = await factsOf(page);
  const statuses = new Map<string, number>();
  for (const path of ctx.probes ?? []) {
    const status = (await ctx.adapter?.probe(page, path)) ?? null;
    if (status !== null) statuses.set(path, status);
  }
  expect(violations(facts, ctx, statuses), `${ctx.step}: invariants`).toEqual([]);
}
