// T-05-T66 (TASK-8024; T-05 §F13; SPEC-651 AC-13.1): whether an entity return's model-backed
// control may be offered, from `GET /v1/agents/capabilities`. A control the server would refuse is
// never offered: it renders disabled with its reason in words, never hidden behind an error, and
// the screen says the work is prepared without agents. While the capabilities load, nothing is
// offered (fail closed).

/** The capabilities the entity return screens call (T-05 §6). */
export const ENTITY_CAPABILITIES = {
  memo: "tax.memo_drafter",
  mapper: "tax.account_mapper",
  agreement: "tax.agreement_reader",
  fixRunner: "issues.fix_runner", // TXP-10's fix instructions (T-05-T66)
} as const;
export type EntityCapability = (typeof ENTITY_CAPABILITIES)[keyof typeof ENTITY_CAPABILITIES];

// The server's reason codes in words (ai_gateway boundary reasons; T-05-T03's undesigned copy).
const REASONS: Readonly<Record<string, string>> = {
  agent: "Accrued Agent is off for this firm. Prepare this by hand.",
  ai_paused: "Accrued Agent is paused for this firm. Prepare this by hand.",
  stage: "This agent is not cleared for your firm yet. Prepare this by hand.",
  consent_7216: "§7216 AI consent needed for this client before Accrued Agent can help.",
  tax_return_information: "§7216 AI consent needed for this client before Accrued Agent can help.",
  firm: "Accrued Agent is not set up for this firm. Prepare this by hand.",
};
const UNAVAILABLE = "Accrued Agent is unavailable right now. Prepare this by hand.";

export const PREPARED_WITHOUT_AGENTS = "Prepared without agents";

export interface AgentGate {
  /** True only when the capability answered available. */
  offered: boolean;
  /** The visible reason when not offered (null while loading or when offered). */
  reason: string | null;
  consent: boolean;
}

interface CapabilityRow {
  capability: string;
  available: boolean;
  reason?: string | null;
}

export function entityAgentGate(
  caps: { items?: readonly CapabilityRow[] } | undefined,
  capability: EntityCapability,
): AgentGate {
  if (caps === undefined) return { offered: false, reason: null, consent: false };
  const hit = caps.items?.find((c) => c.capability === capability);
  if (hit === undefined) return { offered: false, reason: UNAVAILABLE, consent: false };
  if (hit.available) return { offered: true, reason: null, consent: false };
  const code = hit.reason ?? "";
  return {
    offered: false,
    reason: REASONS[code] ?? UNAVAILABLE,
    consent: code === "consent_7216" || code === "tax_return_information",
  };
}
