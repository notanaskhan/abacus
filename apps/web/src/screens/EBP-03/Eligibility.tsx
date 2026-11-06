import type { EligibilitySampleRowOut } from "@abacus/api-client";
import {
  auditFindingCreateMutation,
  ebpEligibilitySampleOptions,
  ebpEligibilitySampleQueryKey,
  ebpTestMarkMutation,
} from "@abacus/api-client/query";
import {
  type CockpitCanvas,
  Button,
  Icon,
  PaneAction,
  Pill,
  StatusDisc,
  type ViewState,
  amount,
  cn,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useFlag } from "../../app-core/flags";
import { COPY } from "./copy";

// EBP-03 · Eligibility testing (A-05-T23; A-05 §3; the handoff spec): the AUD-02 cockpit's
// Testing › Eligibility Testing canvas over `GET …/ebp/eligibility/sample` (DEC-2225), A-03's 25
// sampled participants in order. The Dual-Source card sets census against PayGrid's HR record
// (a difference carries the amber corner and code's "No effect" note); the matrix shows each
// participant's masked date of birth, hire, code's entry date, the rate and the result: a ✓, the
// Flag with "Exception", "Needs human" with Mark no effect (a person's mark), or a spinner while
// the agent tests (C6 polled, rows revealed with a 70 ms client stagger). A row's click opens its
// PayGrid new-hire record in the viewer dock, never a Form I-9, and draws code's computation line.
// The Exceptions card states code's missed amounts; Raise exception… drafts an AUD-15 finding and
// Request opt-out forms opens SHL-14. Adopt (L1)… and Sign off… are the person's (SHL-12).

const POLL_MS = 1_000;
const STAGGER_MS = 70;
// The attribute a hire-date difference waits on (A-05-T22's `ebp_eligibility` grid).
const HIRE_DATE = "hire_date";
const CARD = "mx-[12px] mt-[12px] overflow-hidden rounded-card bg-card shadow-e1";
const HEAD = "flex h-[32px] items-center px-[12px] text-body font-medium hairline-b";
const TH = "h-[28px] bg-band-hd px-[8px] text-left text-th font-normal text-ink-2";
const TD = "h-[29px] truncate px-[8px] text-[12px]";

/** "2025-06-01" → "06/01/2025": the handoff's date grammar (no arithmetic). */
export function us(iso: string | null | undefined): string {
  if (iso == null) return "—";
  const [y, m, d] = iso.split("-");
  return `${m ?? ""}/${d ?? ""}/${y ?? ""}`;
}

function Chip({ children }: { children: string }): JSX.Element {
  return (
    <span className="rounded-[5px] bg-sel-bg px-[6px] py-[1px] inset-ring-[0.5px] inset-ring-stroke">
      {children}
    </span>
  );
}

function ResultCell({
  row,
  canMark,
  onMark,
}: {
  row: EligibilitySampleRowOut;
  canMark: boolean;
  onMark: () => void;
}): JSX.Element {
  switch (row.result) {
    case "exception":
      return (
        <span data-ebp03="exception" className="flex items-center gap-[4px]">
          <Icon name="flag" size={12} className="text-red" />
          <Pill variant="red-tint" size="micro">
            {COPY.exception}
          </Pill>
        </span>
      );
    case "needs_human":
      return (
        <span data-ebp03="needs-human" className="flex items-center gap-[6px]">
          <Pill variant="amber" size="micro">
            {COPY.needsHuman}
          </Pill>
          {canMark && (
            <Button variant="secondary" size="sm" onClick={onMark}>
              {COPY.markNoEffect}
            </Button>
          )}
        </span>
      );
    case "not_started":
      return (
        <span data-ebp03="testing" aria-label={COPY.testing}>
          <StatusDisc state="run" />
        </span>
      );
    default:
      return (
        <span data-ebp03="tick" className="text-ink-3" aria-label="✓">
          ✓
        </span>
      );
  }
}

export function useEligibilityCanvas(
  workItemId: string,
  {
    active,
    onDock,
    onRaise,
    onRequestOptOut,
    onSignOff,
  }: {
    active: boolean;
    /** The viewer dock on a row's HR record version. */
    onDock?: (versionId: string) => void;
    onRaise?: () => void;
    onRequestOptOut?: () => void;
    /** SHL-12 on the attribute test, at L1 (Adopt) or L2 (Sign off). */
    onSignOff?: (testId: string, level: "L1" | "L2") => void;
  },
): CockpitCanvas {
  const on = useFlag("ebp.modules") === true;
  const queryClient = useQueryClient();
  const path = { path: { work_item_id: workItemId } };
  const sample = useQuery({
    ...ebpEligibilitySampleOptions(path),
    enabled: active && on,
    refetchInterval: (q) =>
      (q.state.data?.rows ?? []).some((r) => r.result === "not_started") ? POLL_MS : false,
  });
  const mark = useMutation({
    ...ebpTestMarkMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ebpEligibilitySampleQueryKey(path) });
    },
  });
  // "Raise exception…": an AUD-15 draft finding on the paper, naming the sample's exceptions.
  const raise = useMutation({
    ...auditFindingCreateMutation(),
    onSuccess: () => {
      toast.show({ kind: "success", text: COPY.raised });
    },
    onError: () => {
      toast.show({ kind: "error", text: COPY.raiseFailed });
    },
  });
  const [chosen, setChosen] = useState<number | null>(null);

  let state: ViewState = { kind: "ready" };
  if (!on) state = { kind: "flag-off", flag: "ebp.modules" };
  else if (sample.isError) {
    const status = (sample.error as { status?: number } | null)?.status;
    state =
      status === 404
        ? { kind: "restricted", reason: "walled" }
        : { kind: "error", retry: () => void sample.refetch() };
  } else if (sample.data === undefined) state = { kind: "loading" };
  else if (sample.data.rows.length === 0) state = { kind: "empty" };

  const data = sample.data;
  const rows = data?.rows ?? [];
  const selected = rows.find((r) => r.position === (chosen ?? 1));
  const canMark = (data?.allowed_actions ?? []).includes("test.mark");
  const pending = rows.some((r) => r.result === "needs_human" || r.result === "not_started");
  const adopted = data?.prepared_by != null;
  const exceptions = rows.filter((r) => r.result === "exception");
  const pick = (row: EligibilitySampleRowOut): void => {
    setChosen(row.position);
    if (row.hr_record_version_id != null) onDock?.(row.hr_record_version_id);
  };

  return {
    title: COPY.title,
    well: true,
    state,
    empty: { title: COPY.empty, body: COPY.emptyBody },
    actions: (
      <>
        {data?.prepared_by != null && (
          <span
            data-chip="l1"
            className="rounded-full bg-green-tint px-[6px] text-micro text-green-ink"
          >
            {COPY.check(data.prepared_by)}
          </span>
        )}
        {data?.reviewed_by != null && (
          <span
            data-chip="l2"
            className="rounded-full bg-green-tint px-[6px] text-micro text-green-ink"
          >
            {COPY.check(data.reviewed_by)}
          </span>
        )}
        <PaneAction icon="pencil" label={COPY.edit} />
        <PaneAction
          label={COPY.signOff}
          disabled={!adopted || pending || data.reviewed_by != null}
          {...(adopted ? {} : { title: COPY.adoptFirst })}
          onClick={() => {
            if (data?.test_id != null) onSignOff?.(data.test_id, "L2");
          }}
        />
        <PaneAction icon="file" label={COPY.sourceDocs} />
      </>
    ),
    footer:
      data === undefined ? null : (
        <div className="flex items-center gap-[8px]">
          {!adopted && (
            <Button
              variant="primary"
              size="sm"
              disabled={pending}
              onClick={() => {
                if (data.test_id != null) onSignOff?.(data.test_id, "L1");
              }}
            >
              {COPY.adopt}
            </Button>
          )}
          <PaneAction label={COPY.citations(rows.length * 3)} />
          <PaneAction label={COPY.procedures} />
        </div>
      ),
    children:
      data === undefined ? null : (
        <div data-screen="EBP-03" className="pb-[12px]">
          <section data-ebp03="dual" aria-label={COPY.dual} className={CARD}>
            <h3 className={HEAD}>{COPY.dual}</h3>
            <table className="w-full table-fixed">
              <thead>
                <tr>
                  <th className={cn(TH, "w-[32px]")}>{COPY.columns.n}</th>
                  <th className={TH}>{COPY.columns.census}</th>
                  <th className={TH}>{COPY.columns.hr}</th>
                  <th className={TH}>{COPY.columns.dob}</th>
                  <th className={TH}>{COPY.columns.hire}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const differs = r.hr_hire !== null && r.hr_hire !== r.census_hire;
                  return (
                    <tr key={r.item_id} data-dual={r.position} className="hairline-t">
                      <td className={cn(TD, "text-ink-3")}>{r.position}</td>
                      <td className={TD}>{r.census_name}</td>
                      <td className={TD}>
                        {r.hr_first_name !== null && <Chip>{r.hr_first_name}</Chip>}
                      </td>
                      <td className={cn(TD, "text-ink-3")}>{r.dob_masked}</td>
                      <td className={TD}>
                        {us(r.census_hire)}
                        {differs && (
                          <span data-ebp03="hire-differs" className="ml-[6px]">
                            <Chip>{us(r.hr_hire)}</Chip>
                            <Icon
                              name="triangle-alert"
                              size={12}
                              className="ml-[4px] text-amber"
                            />
                          </span>
                        )}
                        {r.note !== null && (
                          <span className="block text-[11px] text-amber-ink">{r.note}</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>
          <section data-ebp03="matrix" aria-label={COPY.matrix} className={CARD}>
            <h3 className={HEAD}>{COPY.matrix}</h3>
            <table className="w-full table-fixed">
              <thead>
                <tr>
                  <th className={cn(TH, "w-[32px]")}>{COPY.columns.n}</th>
                  <th className={TH}>{COPY.columns.participant}</th>
                  <th className={TH}>{COPY.columns.dob}</th>
                  <th className={TH}>{COPY.columns.hire}</th>
                  <th className={TH}>{COPY.columns.entry}</th>
                  <th className={TH}>{COPY.columns.rate}</th>
                  <th className={TH}>{COPY.columns.result}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr
                    key={r.item_id}
                    data-row={r.position}
                    data-participant={r.census_name}
                    {...(selected?.position === r.position ? { "aria-selected": true } : {})}
                    onClick={() => {
                      pick(r);
                    }}
                    style={{ transitionDelay: `${String(i * STAGGER_MS)}ms` }}
                    className={cn(
                      "cursor-default transition-opacity hairline-t",
                      selected?.position === r.position && "bg-sel-bg font-medium",
                    )}
                  >
                    <td className={cn(TD, "text-ink-3")}>{r.position}</td>
                    <td className={TD}>{r.census_name}</td>
                    <td className={cn(TD, "text-ink-3")}>{r.dob_masked}</td>
                    <td className={TD}>{us(r.census_hire)}</td>
                    <td className={TD}>
                      <Chip>{us(r.entry_on)}</Chip>
                    </td>
                    <td className={TD}>{r.rate_label}</td>
                    <td className={TD}>
                      <ResultCell
                        row={r}
                        canMark={canMark}
                        onMark={() => {
                          if (data.test_id == null) return;
                          mark.mutate({
                            path: {
                              work_item_id: workItemId,
                              test_id: data.test_id,
                              item_id: r.item_id,
                              attribute: HIRE_DATE,
                            },
                            body: { result: "no_effect" },
                            headers: { "Idempotency-Key": crypto.randomUUID() },
                          });
                        }}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {selected !== undefined && selected.entry_on !== null && (
              <p
                data-ebp03="computation"
                className="px-[12px] py-[8px] text-[11.5px] text-ink-2 hairline-t"
              >
                {COPY.computation(
                  selected.eligible_on === null ? null : us(selected.eligible_on),
                  us(selected.entry_on),
                  selected.recordkeeper_entry_on === null
                    ? null
                    : us(selected.recordkeeper_entry_on),
                )}
              </p>
            )}
          </section>
          {exceptions.length > 0 && (
            <section data-ebp03="exceptions" className={CARD}>
              <h3 className={HEAD}>{COPY.exceptionsCard(exceptions.length)}</h3>
              <ul className="px-[12px] py-[8px] text-[12.5px] leading-[1.55]">
                {exceptions.map((r) => (
                  <li key={r.item_id}>
                    {COPY.missed(
                      r.census_name,
                      us(r.entry_on),
                      amount(r.missed_deferral ?? null, "money").text,
                      amount(r.missed_match ?? null, "money").text,
                    )}
                  </li>
                ))}
              </ul>
              <div className="flex items-center gap-[8px] px-[12px] pb-[12px]">
                <Button
                  variant="tonal"
                  size="sm"
                  disabled={
                    raise.isPending ||
                    raise.isSuccess ||
                    data.workpaper_id == null ||
                    !data.allowed_actions.includes("finding.create")
                  }
                  onClick={() => {
                    if (data.workpaper_id == null) return;
                    raise.mutate({
                      path: { work_item_id: workItemId },
                      body: {
                        title: COPY.findingTitle(exceptions.length),
                        kind: "compliance",
                        workpaper_id: data.workpaper_id,
                      },
                      headers: { "Idempotency-Key": crypto.randomUUID() },
                    });
                    onRaise?.();
                  }}
                >
                  {COPY.raise}
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  {...(onRequestOptOut === undefined ? {} : { onClick: onRequestOptOut })}
                >
                  {COPY.requestOptOut}
                </Button>
              </div>
            </section>
          )}
        </div>
      ),
  };
}
