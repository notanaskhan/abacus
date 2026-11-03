import type { FindingRowOut, LateRemittanceOut } from "@abacus/api-client";
import {
  auditFindingOptions,
  auditFindingsOptions,
  ebpLateRemittancesOptions,
} from "@abacus/api-client/query";
import {
  EmptyState,
  ErrorState,
  type IssueGroup,
  type IssueItem,
  IssueQueue,
  Pill,
  QueueDetailLayout,
  SearchField,
  Skeleton,
  amount,
  cn,
  date,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useNow } from "../../app-core/clock";
import { COPY } from "./copy";
import { FindingDetail, FindingFooter } from "./Detail";

// AUD-15 · Findings register (A-06-T18; the handoff spec, docs/plan/epics/A-06.md §5): T9
// close-review inside the audit cockpit's Evaluation tabs. The 310 queue bands every finding by
// severity (Material weakness · Significant deficiency · Deficiency · Exception for resolution ·
// Misstatements), with search and Hide concluded; the 480 detail is the finding (Detail.tsx): its
// type, COSO component, the severity a person proposed and only the engagement partner concludes,
// Why This Was Surfaced, the evaluation, and the footer the viewer's role and the finding's state
// allow. The 576 evidence pane shows EBP-04's late remittance behind an EBP-04 finding; the
// detail's file chip lights its row in the source-match purple. Rows open the finding; nothing in
// the queue decides (INV-1). Data through the generated client only.

type Band = keyof typeof COPY.bands;
const ORDER: readonly Band[] = [
  "material_weakness",
  "significant_deficiency",
  "deficiency",
  "exception",
  "misstatements",
];

export function bandOf(f: FindingRowOut): Band {
  if (f.kind === "misstatement" || f.route === "converted_to_misstatement") return "misstatements";
  if (f.deficiency_status === "exception_for_resolution") return "exception";
  return f.severity_concluded ?? f.severity_proposed ?? "deficiency";
}

export function isConcluded(f: FindingRowOut): boolean {
  return f.deficiency_status === "concluded" || f.deficiency_status === "communicated";
}

function subOf(f: FindingRowOut): string {
  const band = bandOf(f);
  if (band === "misstatements") return f.workpaper_ref ?? "";
  const status = f.deficiency_status === null ? null : COPY.status[f.deficiency_status];
  const coso = f.coso_component === null ? null : COPY.coso[f.coso_component];
  const parts = band === "exception" ? [status, f.workpaper_ref] : [status, coso, f.workpaper_ref];
  return parts.filter((p) => p != null && p !== "").join(" · ");
}

function itemOf(f: FindingRowOut): IssueItem {
  const band = bandOf(f);
  const flag =
    band === "material_weakness" || band === "significant_deficiency"
      ? ("red" as const)
      : band === "misstatements"
        ? undefined
        : ("amber" as const);
  return {
    id: f.id,
    title: f.title,
    sub: subOf(f),
    ...(flag === undefined ? {} : { flag }),
  };
}

function groupsOf(rows: readonly FindingRowOut[]): IssueGroup[] {
  return ORDER.flatMap((band) => {
    const items = rows.filter((f) => bandOf(f) === band).map(itemOf);
    return items.length === 0
      ? []
      : [{ id: band, label: COPY.bands[band], count: String(items.length), items }];
  });
}

function matches(f: FindingRowOut, q: string): boolean {
  const needle = q.trim().toLowerCase();
  if (needle === "") return true;
  return [f.ref, f.title, f.workpaper_ref ?? ""].some((s) => s.toLowerCase().includes(needle));
}

/** The 576 evidence pane: EBP-04's late remittances behind the finding, the lit row in the
 * source-match purple, and the correction card. */
function EvidencePane({
  workpaper,
  rows,
  lit,
}: {
  workpaper: string | null;
  rows: readonly LateRemittanceOut[];
  lit: string | null;
}): JSX.Element {
  const now = useNow();
  if (workpaper === null || rows.length === 0) {
    return (
      <div data-aud15="evidence" className="p-[16px] text-dense text-ink-3">
        {COPY.evidence.none}
      </div>
    );
  }
  const head = rows[0];
  return (
    <section data-aud15="evidence" aria-label={COPY.evidence.title(workpaper)}>
      <h3 className="flex h-[46px] items-center justify-center text-pane-title font-medium hairline-b">
        {COPY.evidence.title(workpaper)}
      </h3>
      <table className="w-full text-dense">
        <thead>
          <tr className="h-[30px] bg-band-hd text-th font-medium text-ink-2">
            <th className="px-[12px] text-left font-medium">{COPY.evidence.payDate}</th>
            <th className="text-left font-medium">{COPY.evidence.deposited}</th>
            <th className="text-left font-medium">{COPY.evidence.businessDays}</th>
            <th className="text-right font-medium">{COPY.evidence.deferrals}</th>
            <th className="px-[12px] text-left font-medium">{COPY.evidence.status}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.id}
              data-remittance={r.payroll_date}
              {...(lit === r.id ? { "data-lit": "" } : {})}
              className={cn(
                "h-[30px] hairline-t",
                lit === r.id && "bg-match-bg ring-1 ring-match-line ring-inset",
              )}
            >
              <td className="px-[12px]">{date(r.payroll_date, { now, withYear: true })}</td>
              <td>{date(r.deposited_on, { now, withYear: true })}</td>
              <td className="tabular-nums">{r.business_days}</td>
              <td className="text-right tabular-nums">{amount(r.amount, "cents").text}</td>
              <td className="px-[12px] font-medium text-red-ink">{COPY.evidence.late}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {head !== undefined && (
        <div
          data-aud15="correction"
          className="m-[12px] rounded-card bg-card shadow-e1"
          aria-label={COPY.evidence.correction}
        >
          <h4 className="px-[16px] py-[10px] text-body font-medium">{COPY.evidence.correction}</h4>
          {[
            [COPY.evidence.principal, amount(head.amount, "cents").text],
            [COPY.evidence.lostEarnings, amount(head.lost_earnings, "cents").text],
          ].map(([k, v]) => (
            <div key={k} className="flex h-[30px] items-center px-[16px] hairline-t">
              <span className="flex-1 text-ink-2">{k}</span>
              <span className="tabular-nums">{v}</span>
            </div>
          ))}
          <div className="flex h-[30px] items-center px-[16px] hairline-t">
            <span className="flex-1 text-ink-2">{COPY.evidence.correction}</span>
            <Pill variant="amber" size="state">
              {COPY.evidence.correctionState[head.status]}
            </Pill>
          </div>
        </div>
      )}
    </section>
  );
}

export function FindingsRegister({
  auditId,
  initialRef,
}: {
  auditId: string;
  /** The finding the screen opens selected (its ref, "F-07"); the first row otherwise. */
  initialRef?: string;
}): JSX.Element {
  const [q, setQ] = useState("");
  const [hide, setHide] = useState(false);
  const [chosen, setChosen] = useState<string | null>(null);
  const [lit, setLit] = useState<string | null>(null);
  const list = useQuery(auditFindingsOptions({ path: { work_item_id: auditId } }));
  const all = list.data?.items ?? [];
  const shown = all.filter((f) => matches(f, q) && !(hide && isConcluded(f)));
  const groups = groupsOf(shown);
  const order = groups.flatMap((g) => g.items);
  const fallback = all.find((f) => f.ref === initialRef)?.id ?? order[0]?.id ?? null;
  const selectedId = chosen ?? fallback;
  const selected = all.find((f) => f.id === selectedId);
  const detail = useQuery({
    ...auditFindingOptions({ path: { finding_id: selectedId ?? "" } }),
    enabled: selectedId !== null,
  });
  const ebp04 = selected?.workpaper_ref === "EBP-04";
  const late = useQuery({
    ...ebpLateRemittancesOptions({ path: { work_item_id: auditId } }),
    enabled: ebp04,
  });
  const remittances = ebp04 ? (late.data ?? []) : [];

  const queueBody = list.isError ? (
    <ErrorState noun={COPY.error} onRetry={() => void list.refetch()} />
  ) : list.data === undefined ? (
    <div aria-busy="true" className="flex flex-col gap-[10px] p-[12px]">
      {[0, 1, 2, 3].map((i) => (
        <Skeleton key={i} className="h-[44px] w-full" />
      ))}
    </div>
  ) : (
    <IssueQueue
      variant="severity"
      label={COPY.queue}
      groups={groups}
      selected={selectedId}
      onSelect={(item) => {
        setChosen(item.id);
        setLit(null);
      }}
    />
  );

  const detailBody =
    list.data !== undefined && all.length === 0 ? (
      <div data-aud15="empty" className="flex h-full items-center justify-center bg-shell">
        <EmptyState icon="flag" title={COPY.empty}>
          {COPY.emptyBody}
        </EmptyState>
      </div>
    ) : detail.data === undefined ? null : (
      <FindingDetail
        key={detail.data.finding.id}
        detail={detail.data}
        remittances={remittances}
        lit={lit}
        onLight={setLit}
      />
    );

  return (
    <div data-screen="AUD-15" className="flex min-h-0 flex-1 flex-col">
      <QueueDetailLayout
        preset="close-review"
        bare
        toolbar={{ nav: [], active: "Audits", firm: "" }}
        record={null}
        queue={{
          title: COPY.pane,
          left: <SearchField label={COPY.search} value={q} onChange={setQ} />,
          right: (
            <button
              type="button"
              aria-pressed={hide}
              onClick={() => {
                setHide((h) => !h);
              }}
              className="text-body text-ink-3 hover:text-ink"
            >
              {COPY.hideConcluded}
            </button>
          ),
          body: queueBody,
        }}
        detail={{
          body: detailBody,
          ...(detail.data === undefined || all.length === 0
            ? {}
            : {
                footer: <FindingFooter key={detail.data.finding.id} detail={detail.data} />,
              }),
        }}
        evidence={[
          <EvidencePane
            key="evidence"
            workpaper={selected?.workpaper_ref ?? null}
            rows={remittances}
            lit={lit}
          />,
        ]}
      />
    </div>
  );
}
