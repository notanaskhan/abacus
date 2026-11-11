// A-07-T28 / A-07-T29 remainder (DEC-3030), A-07-T34: AUD-21, AUD-22 and AUD-23 inside the AUD-02 cockpit, opened from
// AUD-19's checklist (its "AUD-21" and "AUD-22" link chips) and closed by their Back. AUD-21 reads
// the representation letter through C11's route; AUD-22 draws the handoff's E0 rows (frame a) until
// A-07-T33 wires its live read. Every send, approve and remind stays the person's, bound later.
import {
  governanceListOptions,
  governanceOptions,
  representationLetterOptions,
} from "@abacus/api-client/query";
import type { CockpitCanvas } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, lazy, Suspense, useState } from "react";
import { useFlag } from "../../app-core/flags";
import { RevealStepUp, useLiveArchive, useLiveRelease } from "../../domain/audits";

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

// A-07-T28/T29 remainder (DEC-3144): with `audits.letters` on, AUD-21 and AUD-22 open on the
// server's data through their live modules, which carry no artboard words.
const RepLetterLive = lazy(async () => ({
  default: (await import("../AUD-21/RepLetterLive")).RepLetterLive,
}));
const GovernanceLive = lazy(async () => ({
  default: (await import("../AUD-22/GovernanceLive")).GovernanceLive,
}));
// A-07-T47 (DEC-3303): AUD-24 and AUD-25 on the server's data, behind `audits.report_release` and
// `audits.archive`, polled every 10 s (2 s while the release or the lock runs).
const IssuanceLive = lazy(async () => ({
  default: (await import("../AUD-24/IssuanceLive")).IssuanceLive,
}));
const ArchiveLive = lazy(async () => ({
  default: (await import("../AUD-25/ArchiveLive")).ArchiveLive,
}));

function ReleaseHost({
  workItemId,
  onBack,
}: {
  workItemId: string;
  onBack: () => void;
}): JSX.Element | null {
  const { release, action } = useLiveRelease(workItemId);
  if (release.data === undefined) return null;
  return (
    <Suspense fallback={null}>
      <IssuanceLive
        release={release.data}
        running={action.running}
        problem={action.problem}
        onRelease={() => {
          void action.run();
        }}
        onBack={onBack}
      />
      <RevealStepUp open={action.stepUp} onOpenChange={action.setStepUp} />
    </Suspense>
  );
}

function ArchiveHost({
  workItemId,
  onBack,
}: {
  workItemId: string;
  onBack: () => void;
}): JSX.Element | null {
  const { archive, action } = useLiveArchive(workItemId);
  if (archive.data === undefined) return null;
  return (
    <Suspense fallback={null}>
      <ArchiveLive
        archive={archive.data}
        running={action.running}
        problem={action.problem}
        thenRollForward={action.thenRollForward}
        onThenRollForward={action.setThenRollForward}
        onLock={() => {
          void action.run();
        }}
        onBack={onBack}
      />
      <RevealStepUp open={action.stepUp} onOpenChange={action.setStepUp} />
    </Suspense>
  );
}

/** How the letters open here: the E0 frames (tests, fixture builds), live (`audits.letters`), or
 * not at all (the chips go to the host). */
export type LettersMode = "e0" | "live" | null;

export function useLettersMode(): LettersMode {
  const live = useFlag("audits.letters") === true;
  if (FIXTURES) return "e0";
  return live ? "live" : null;
}

/** The checklist link targets that open inside the cockpit. */
export type CompletionLetter = "AUD-21" | "AUD-22" | "AUD-23" | "AUD-24" | "AUD-25";

/** AUD-24 and AUD-25 open live with their flags (A-07-T47); fixture builds keep the host's. */
export function useReleaseArchiveLive(): { release: boolean; archive: boolean } {
  const release = useFlag("audits.report_release") === true;
  const archive = useFlag("audits.archive") === true;
  return { release: !FIXTURES && release, archive: !FIXTURES && archive };
}

export function isCompletionLetter(
  target: string,
  mode: LettersMode = FIXTURES ? "e0" : null,
  live: { release: boolean; archive: boolean } = { release: false, archive: false },
): target is CompletionLetter {
  // AUD-23 reads the live report (A-07-T34); AUD-21 and AUD-22 open in E0 or live mode (DEC-3144).
  if (target === "AUD-23") return true;
  if (target === "AUD-24") return live.release;
  if (target === "AUD-25") return live.archive;
  return mode !== null && (target === "AUD-21" || target === "AUD-22");
}

export function useCompletionLetterCanvas(
  workItemId: string,
  letter: CompletionLetter | null,
  onBack: () => void,
  mode: LettersMode = FIXTURES ? "e0" : null,
): CockpitCanvas | null {
  const path = { path: { work_item_id: workItemId } };
  const rep = useQuery({
    ...representationLetterOptions(path),
    enabled: letter === "AUD-21",
    retry: false,
  });
  const list = useQuery({
    ...governanceListOptions(path),
    enabled: mode === "live" && letter === "AUD-22",
    retry: false,
  });
  const [picked, setPicked] = useState<string | null>(null);
  const communication = picked ?? list.data?.items[0]?.id ?? null;
  const detail = useQuery({
    ...governanceOptions({
      path: { work_item_id: workItemId, communication_id: communication ?? "" },
    }),
    enabled: mode === "live" && letter === "AUD-22" && communication !== null,
    retry: false,
  });
  if (mode === "live" && letter === "AUD-22") {
    return {
      title: "Governance communications",
      ...(list.isPending ? { state: { kind: "loading" } as const } : {}),
      children:
        list.data === undefined ? null : (
          <Suspense fallback={null}>
            <GovernanceLive
              list={list.data}
              letter={detail.data}
              selected={communication}
              onSelect={setPicked}
              onBack={onBack}
            />
          </Suspense>
        ),
    };
  }
  if (mode === "live" && letter === "AUD-21") {
    return {
      title: "Representation letter",
      ...(rep.isPending ? { state: { kind: "loading" } as const } : {}),
      children:
        rep.data === undefined ? null : (
          <Suspense fallback={null}>
            <RepLetterLive letter={rep.data} onBack={onBack} />
          </Suspense>
        ),
    };
  }
  if (letter === "AUD-24") {
    return {
      title: "Issuance & release",
      children: <ReleaseHost workItemId={workItemId} onBack={onBack} />,
    };
  }
  if (letter === "AUD-25") {
    return {
      title: "Assembly & archive",
      children: <ArchiveHost workItemId={workItemId} onBack={onBack} />,
    };
  }
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
