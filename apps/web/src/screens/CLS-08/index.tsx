// CLS-08 Close › Deliverables (C-02-T23; handoff CLS-08 a-g; docs/screens/CLS-08.md; SPEC-701) on
// the T10 DocumentOnWell: the structure pane (package toggles, the SSARS question, the route rows,
// preconditions and release) and the paper pane (the statements, one page each, the legend on
// every page when the route carries one). Figures are the package read's, never computed here:
// lines without accounts are the server's subtotals. Toggling a section renumbers the pages; the
// edit goes to the server as a new version. Release is a Partner's, through its own dialog (C-02's
// release task); this screen never writes a figure.
import type { DeliveryPackageOut, DeliveryStatementLineOut } from "@abacus/api-client";
import { packageEditMutation, packageOptions } from "@abacus/api-client/query";
import {
  type ClauseVM,
  DocumentOnWell,
  type KvSheetVM,
  Pill,
  Skeleton,
  amount,
  cn,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { COPY as C } from "./copy";

const SECTIONS = [
  "balance_sheet",
  "income_statement",
  "cash_flows",
  "commentary",
  "reconciliation_summary",
] as const;
type Section = (typeof SECTIONS)[number];
const FIRM_ONLY: ReadonlySet<Section> = new Set(["reconciliation_summary"]);
const GRAND: ReadonlySet<string> = new Set([
  "total_assets",
  "total_liabilities_and_equity",
  "net_income",
]);

function Cell({ v, dollar }: { v: string | null | undefined; dollar: boolean }): JSX.Element {
  const f = amount(v ?? "", dollar ? "money" : "cents");
  return (
    <td className={cn("px-[6px] text-right tabular-nums", f.tone === "neg" && "text-red")}>
      {f.text}
    </td>
  );
}

function Statement({
  lines,
  prior,
}: {
  lines: readonly DeliveryStatementLineOut[];
  prior: boolean;
}): JSX.Element {
  return (
    <table className="w-full text-[12px]">
      <tbody>
        {lines.map((ln, i) => {
          const subtotal = (ln.account_refs ?? []).length === 0;
          const grand = GRAND.has(ln.key);
          const dollar = i === 0 || grand;
          return (
            <tr
              key={ln.key}
              data-line={ln.key}
              className={cn(
                "h-[22px]",
                subtotal && "font-medium hairline-t",
                grand && "border-b-[3px] border-double border-ink",
              )}
            >
              <td className="pr-[8px]">{ln.label}</td>
              <Cell v={ln.amount} dollar={dollar} />
              {prior ? <Cell v={ln.prior} dollar={dollar} /> : null}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function Page({
  n,
  of,
  legend,
  children,
}: {
  n: number;
  of: number;
  legend: string | null | undefined;
  children: JSX.Element;
}): JSX.Element {
  return (
    <section
      aria-label={C.statements.page(n, of)}
      className="mx-auto flex w-[600px] flex-col gap-[10px] rounded-[12px] bg-card px-[24px] pt-[20px] pb-[24px] shadow-e2"
    >
      {children}
      <footer className="flex flex-col items-center gap-[2px] pt-[8px]">
        {legend ? <span className="text-[11px] font-medium text-ink">{legend}</span> : null}
        <span className="text-[11px] text-ink-3">{C.statements.page(n, of)}</span>
      </footer>
    </section>
  );
}

function Heading({ title, sub }: { title: string; sub: string }): JSX.Element {
  return (
    <header className="flex flex-col items-center">
      <span className="text-[13.5px] font-medium">{C.statements.company}</span>
      <span className="text-[12px]">{title}</span>
      <span className="text-[12px] text-ink-2">{sub}</span>
    </header>
  );
}

function structure(
  pkg: DeliveryPackageOut,
  on: ReadonlySet<Section>,
  periodEnd: string,
): { clauses: ClauseVM[]; after: KvSheetVM[] } {
  const clauses: ClauseVM[] = SECTIONS.map((s) => ({
    id: s,
    label: C.sections[s] ?? s,
    on: on.has(s),
    ...(FIRM_ONLY.has(s) ? { reason: C.firmOnly } : {}),
  }));
  const route = C.basis.routes[pkg.route] ?? pkg.route;
  const basis: KvSheetVM = {
    crumb: C.basis.title,
    sections: [
      {
        title: C.basis.question,
        rows: [
          {
            key: C.basis.question,
            value: pkg.cas_answer ? C.basis.yes : C.basis.no,
            linkId: "cas",
          },
          { key: C.basis.periodEnd, value: periodEnd },
          { key: C.basis.adoption, value: C.basis.notAdopted, linkId: "KNW-04" },
          { key: C.basis.route, value: route },
          {
            key: C.basis.legend,
            value:
              pkg.legend === null || pkg.legend === undefined
                ? null
                : C.basis.legendEach(pkg.legend),
          },
          { key: C.basis.report, value: C.basis.none },
        ],
      },
    ],
  };
  const reasons = pkg.preconditions.map((p) =>
    p.blocker === "accounts_unreconciled"
      ? C.preconditions.accounts_unreconciled(p.done ?? 0, p.of ?? 0)
      : p.blocker === "issues_open"
        ? C.preconditions.issues_open(p.done ?? 0)
        : C.preconditions.entries_unposted,
  );
  const preconditions: KvSheetVM = {
    crumb: C.preconditions.title,
    sections: [
      {
        title: C.preconditions.title,
        rows:
          reasons.length === 0
            ? [{ key: C.preconditions.allMet, value: "✓" }]
            : reasons.map((r) => ({ key: r, value: "!" })),
      },
    ],
  };
  return { clauses, after: [basis, preconditions] };
}

export interface CLS08Props {
  closeId: string;
  periodEnd?: string;
  /** The rail's toolbar is the shell's; the artboard draws the panes alone. */
  bare?: boolean;
}

export function CLS08({
  closeId,
  periodEnd = "Aug 31, 2026",
  bare = true,
}: CLS08Props): JSX.Element {
  const path = { close_id: closeId };
  const qc = useQueryClient();
  const pkg = useQuery({ ...packageOptions({ path }), retry: false });
  const edit = useMutation({
    ...packageEditMutation(),
    onSuccess: () => qc.invalidateQueries({ queryKey: packageOptions({ path }).queryKey }),
  });
  const [local, setLocal] = useState<ReadonlySet<Section> | null>(null);
  if (pkg.data === undefined)
    return <Skeleton aria-label={C.drafting} className="h-[700px] w-full" />;
  const data = pkg.data;
  const on: ReadonlySet<Section> = local ?? new Set(data.sections as Section[]);
  const released = data.status === "released" || data.status === "approved_by_client";
  const drafting = data.status === "drafting";
  const pages = (["balance_sheet", "income_statement"] as const).filter((s) => on.has(s));
  const { clauses, after } = structure(data, on, periodEnd);
  return (
    <div data-screen="CLS-08" className="flex flex-col gap-[8px]">
      {released ? (
        <Pill variant="green-tint" size="sm" check>
          {data.status === "approved_by_client" ? C.status.approved : C.status.released}
        </Pill>
      ) : null}
      <DocumentOnWell
        bare={bare}
        record={null}
        toolbar={{} as never}
        copy={{
          edit: C.edit,
          regenerate: C.regenerate,
          drafting: C.drafting,
          rendering: C.drafting,
          watermark: C.watermark,
          variables: "",
        }}
        document={{
          status: drafting ? "drafting" : released ? "approved" : "draft",
          variant: "paper",
          structure: { kind: "clauses", clauses, variables: [], after },
          title: C.title,
          watermark: !released,
          actions: { edit: !released, regenerate: !released },
        }}
        onToggleSection={(id, value) => {
          const next = new Set(on);
          if (value) next.add(id as Section);
          else next.delete(id as Section);
          setLocal(next);
          edit.mutate({
            path,
            body: {
              sections: [...next] as never,
              cas_answer: data.cas_answer,
              expected_version: data.version,
            },
          });
        }}
        onOpenLink={(link) => {
          if (link !== "cas" || released) return;
          edit.mutate({
            path,
            body: {
              sections: [...on] as never,
              cas_answer: !data.cas_answer,
              expected_version: data.version,
            },
          });
        }}
      >
        {drafting ? (
          <div className="flex flex-col gap-[14px]">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="mx-auto h-[220px] w-[600px]" />
            ))}
          </div>
        ) : (
          <div className="flex flex-col gap-[14px]" data-pages={pages.length}>
            {pages.map((s, i) =>
              s === "balance_sheet" ? (
                <Page key={s} n={i + 1} of={pages.length} legend={data.legend}>
                  <>
                    <Heading
                      title={C.statements.balanceSheet}
                      sub={C.statements.balanceSheetDate}
                    />
                    <Statement lines={data.balance_sheet ?? []} prior={false} />
                  </>
                </Page>
              ) : (
                <Page key={s} n={i + 1} of={pages.length} legend={data.legend}>
                  <>
                    <Heading
                      title={C.statements.incomeStatement}
                      sub={C.statements.incomePeriod}
                    />
                    <Statement lines={data.income_statement ?? []} prior />
                  </>
                </Page>
              ),
            )}
          </div>
        )}
      </DocumentOnWell>
    </div>
  );
}
