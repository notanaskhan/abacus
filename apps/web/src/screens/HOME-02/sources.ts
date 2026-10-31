// A gate's class and its cited sources (I-01-T17, T18): the detail's evidence rows and the evidence
// pane's segments read the same list. A decision card's sources are its C4 citations grouped by
// evidence version (each with its first citation's match, so SHL-08 opens lit on it); an agent
// output's are its proposal's evidence rows. Sign-offs and approvals cite nothing of their own here.

import type { CitationV2Out, HumanGateOut } from "@abacus/api-client";
import { agentProposalOptions, listCitationsOptions } from "@abacus/api-client/query";
import { useQuery } from "@tanstack/react-query";

export type GateClass = "decision" | "sign_off" | "proposal" | "approval";

/** The gate's class (DF-25 kinds): a decision card, a sign-off, an agent output, or the rest. */
export function classOf(gate: HumanGateOut): GateClass {
  if (
    gate.kind === "decision" &&
    (gate.overlay === "decision_card" || gate.subject.type === "decision_card")
  ) {
    return "decision";
  }
  if (gate.kind === "sign_off_request") return "sign_off";
  if (gate.kind === "proposal") return "proposal";
  return "approval";
}

export interface GateSource {
  versionId: string;
  title: string;
  /** Citations into this source ("n citations"). */
  n: number;
  /** The first citation's match: the region SHL-08 lights on open. */
  matchId: string | null;
}

/** Citations grouped by source document, in first-cited order. */
export function groupSources(citations: readonly CitationV2Out[]): GateSource[] {
  const groups = new Map<string, GateSource>();
  for (const c of citations) {
    const versionId = c.source.evidence_version_id ?? c.source.id;
    const found = groups.get(versionId);
    if (found === undefined)
      groups.set(versionId, { versionId, title: c.title, n: 1, matchId: c.match_id });
    else found.n += 1;
  }
  return [...groups.values()];
}

/** The selected gate's cited sources (empty while loading, and for classes that cite nothing). */
export function useGateSources(gate: HumanGateOut | undefined): GateSource[] {
  const which = gate === undefined ? null : classOf(gate);
  const id = gate?.subject.id ?? "";
  const citations = useQuery({
    ...listCitationsOptions({ query: { anchor_type: "decision_card", anchor_id: id } }),
    enabled: which === "decision",
  });
  const proposal = useQuery({
    ...agentProposalOptions({ path: { ref: id } }),
    enabled: which === "proposal",
  });
  if (which === "decision") return groupSources(citations.data?.items ?? []);
  if (which === "proposal") {
    return (proposal.data?.evidence ?? []).map((e) => ({
      versionId: e.evidence_version_id,
      title: e.label,
      n: e.citation_count,
      matchId: null,
    }));
  }
  return [];
}
