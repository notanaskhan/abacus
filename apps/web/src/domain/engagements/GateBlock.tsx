import type { EngagementGateOut } from "@abacus/api-client";
import { DEFAULT_TZ, StatusDisc, date, status } from "@abacus/ui";
import type { JSX } from "react";

// The gate rows of an engagement (C1 v1.1; blueprint §3.3.2; ENG-02 b): one row per registered
// gate provider, in order. A gate reads met (olive ✓), blocked (amber triangle) or not started
// (ring); its line is the gate payload in words: who met it and when, the blocker's decision, or
// "Not started". The handoff's sentences ("Continuance approved by MO · May 28") need facts the
// gate payload does not carry yet (docs/screens/ENG-02.md, Deviations).

export const GATE_NAMES: Readonly<Record<EngagementGateOut["gate"], string>> = {
  G1: "Accept",
  G2: "Independent",
  G3: "Contracted",
  G4: "Planned",
  G5: "Reviewed",
  G6: "EQR",
  G7: "Represented",
  G8: "Released",
  G9: "Archived",
};

/** The role a blocker's decision waits on, from its reason code ("partner_decision"). */
function roleOf(reason: string): string | null {
  const m = /^([a-z]+)_decision$/.exec(reason);
  return m?.[1] ?? null;
}

export interface GateBlockProps {
  gates: readonly EngagementGateOut[];
  /** Initials by user id, for "MO · May 28". */
  initials: ReadonlyMap<string, string>;
  /** The G3 line's signers ("Dana Kowalski and MO"), when the letter is signed. */
  signers?: string;
  now: Date;
  tz?: string;
}

export function gateLine(
  gate: EngagementGateOut,
  initials: ReadonlyMap<string, string>,
  now: Date,
  tz: string,
  signers?: string,
): string {
  const when = gate.met_at == null ? null : date(gate.met_at, { now, tz });
  if (gate.met) {
    if (gate.gate === "G3" && signers !== undefined && when !== null) {
      return status("letter_record", "signed", {
        context: "gate_row",
        vars: { signers, date: when },
      }).label;
    }
    const who = gate.met_by_user_id == null ? null : (initials.get(gate.met_by_user_id) ?? null);
    return [who, when].filter((p): p is string => p !== null).join(" · ");
  }
  const blocker = gate.blockers?.[0];
  if (blocker !== undefined) {
    const role = roleOf(blocker.reason_code);
    if (role !== null) {
      return status("audit_section", "blocked_on_decision", { vars: { role } }).label;
    }
  }
  return status("audit_section", "not_started").label;
}

export function GateBlock({
  gates,
  initials,
  signers,
  now,
  tz = DEFAULT_TZ,
}: GateBlockProps): JSX.Element {
  return (
    <ul aria-label="Gates" className="flex flex-col">
      {gates.map((g) => {
        const blocked = !g.met && (g.blockers?.length ?? 0) > 0;
        return (
          <li
            key={g.gate}
            data-gate={g.gate}
            data-met={g.met ? "met" : blocked ? "blocked" : "not-started"}
            className="flex items-center gap-[10px] bg-card pt-[8px] pr-[12px] pb-[9px] pl-[13px] hairline-t"
          >
            <StatusDisc state={g.met ? "done" : blocked ? "warn" : "todo"} size={17} />
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="text-body">{`${g.gate} ${GATE_NAMES[g.gate]}`}</span>
              <span className="text-meta text-ink-3">
                {gateLine(g, initials, now, tz, signers)}
              </span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}
