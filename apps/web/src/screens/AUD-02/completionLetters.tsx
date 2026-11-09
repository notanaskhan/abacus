// A-07-T28 / A-07-T29 remainder (DEC-3030), A-07-T34: AUD-21, AUD-22 and AUD-23 inside the AUD-02 cockpit, opened from
// AUD-19's checklist (its "AUD-21" and "AUD-22" link chips) and closed by their Back. AUD-21 reads
// the representation letter through C11's route; AUD-22 draws the handoff's E0 rows (frame a) until
// A-07-T33 wires its live read. Every send, approve and remind stays the person's, bound later.
import { representationLetterOptions } from "@abacus/api-client/query";
import type { CockpitCanvas } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { lazy, Suspense } from "react";

// Fixture mode only (DEC-3030): both canvases still draw the E0 artboard's words, so a production
// build must not carry them (SPEC-048 AC-10). The compile-time flag drops the imports there; the
// chips keep going to the host until A-07-T33's live wiring. Loaded on first open (bundle budget).
// Inline so the production build folds it to false and drops both imports.
const FIXTURES = import.meta.env.MODE === "test" || import.meta.env.VITE_FIXTURES === "1";
const RepLetter = FIXTURES
  ? lazy(async () => ({ default: (await import("../AUD-21")).RepLetter }))
  : () => null;
const Governance = FIXTURES
  ? lazy(async () => ({ default: (await import("../AUD-22")).Governance }))
  : () => null;
// A-07-T34: AUD-23's report builder, opened from AUD-19's "AUD-23" chip: the canvas in fixture
// builds, the live report (`GET …/report`) everywhere else (S33 partials round, DEC-3137).
const ReportBuilder = FIXTURES
  ? lazy(async () => ({ default: (await import("../AUD-23")).ReportBuilder }))
  : () => null;
const LiveReport = lazy(async () => ({ default: (await import("../AUD-23")).LiveReport }));

/** The checklist link targets that open inside the cockpit. */
export type CompletionLetter = "AUD-21" | "AUD-22" | "AUD-23";

export function isCompletionLetter(target: string): target is CompletionLetter {
  return target === "AUD-23" || (FIXTURES && (target === "AUD-21" || target === "AUD-22"));
}

export function useCompletionLetterCanvas(
  workItemId: string,
  letter: CompletionLetter | null,
  onBack: () => void,
): CockpitCanvas | null {
  const rep = useQuery({
    ...representationLetterOptions({ path: { work_item_id: workItemId } }),
    enabled: letter === "AUD-21",
    retry: false,
  });
  if (letter === "AUD-23") {
    return {
      title: "Report builder",
      children: (
        <Suspense fallback={null}>
          {FIXTURES ? (
            <ReportBuilder frame="a" onBack={onBack} />
          ) : (
            <LiveReport workItemId={workItemId} onBack={onBack} />
          )}
        </Suspense>
      ),
    };
  }
  if (letter === "AUD-22") {
    return {
      title: "Governance communications",
      children: (
        <Suspense fallback={null}>
          <Governance frame="a" onBack={onBack} />
        </Suspense>
      ),
    };
  }
  if (letter === "AUD-21") {
    return {
      title: "Representation letter",
      ...(rep.isPending ? { state: { kind: "loading" } as const } : {}),
      children:
        rep.data === undefined ? null : (
          <Suspense fallback={null}>
            <RepLetter letter={rep.data} onBack={onBack} />
          </Suspense>
        ),
    };
  }
  return null;
}
