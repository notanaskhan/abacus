import type {
  EngineSummaryLineOut,
  FilingRowOut,
  LadderStepOut,
  OverviewIssueOut,
  TaxReturnOverviewOut,
  TaxReturnRecordOut,
} from "@abacus/api-client";
import {
  firmMembersOptions,
  returnAssignMutation,
  returnOverviewOptions,
  returnRecordOptions,
} from "@abacus/api-client/query";
import {
  Button,
  DASH,
  EmptyState,
  GroupBand,
  Icon,
  type IconName,
  KvRowView,
  Menu,
  OverviewCard,
  Pill,
  RailRow,
  RecordCockpit,
  RecordHeader,
  Skeleton,
  StatusDisc,
  Tabsbar,
  Tag,
  type ToolbarProps,
  Tooltip,
  type ViewState,
  count,
  date as formatDate,
  status,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type ReactNode, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useFlag } from "../../app-core/flags";
import { useOpenHref, useOpenOverlay } from "../../app-core/open";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { hrefOf, ov, to } from "../../routes/to";
import { COPY } from "./copy";

// TAX-02 · Return › Overview (T-02-T14; docs/screens/TAX-02.md) on T2 RecordCockpit, without a
// dock: the `ReturnFrame` (subbar, tabsbar) over `GET /v1/tax-returns/{id}` and the overview over
// `/overview`. Every artboard is a data condition:
//
//   a  In review · Feld (banner, estimate, plan, issues, two-year)   b  Not started · Quintero
//   c  Gathering · Feld on Feb 3 (pro forma in place of the estimate) d  Prepared · Okonjo
//   e  Accepted · Feld on Sep 19                                      f  loading
//
// The pilot runs agents off: Run draft, Re-run draft… and the Assistant chip are drawn (disabled)
// only where PLANNED_VISIBLE and are absent in production, as is every tab and link whose screen is
// planned; the Checkpoints chip also shows where `review.checkpoints` is on and opens SHL-16, and
// Files opens the client's folder (FIL-01). Assign… is live (`POST …/assignments`); "Open in CCH
// Axcess" is the engine's deep link (never automation, DEC-49). An entity return (1065, 1120-S,
// 1041) takes the registry's entity wording; every form family opens here (DV-5).

const FORM_LABEL: Readonly<Record<TaxReturnRecordOut["row"]["form"], string>> = {
  "1040": "1040",
  "1041": "1041",
  "1065": "1065",
  "1120s": "1120-S",
  "1120": "1120",
  "990": "990",
  "706": "706",
  "709": "709",
  "1040x": "1040-X",
};
const ENTITY = new Set(["1065", "1120s", "1120", "990"]);
const DISC = { done: "done", in_progress: "half", not_started: "todo" } as const;
const RECORD_ICON: Readonly<Record<string, IconName>> = {
  client: "user-round",
  engagement: "briefcase",
  binder: "folder-open",
  files: "files",
  relationships: "network",
};
const FLAG: Readonly<Record<OverviewIssueOut["severity"], string>> = {
  high: "text-red",
  medium: "text-amber",
  low: "text-amber",
};
const CARD = "rounded-pane bg-card shadow-e1";

export type Tax02Tab = "overview" | "intake" | "review" | "issues" | "activity";

/** The return's state as the subbar words it (`subbar_*` contexts of the `return` object). */
function stateOf(row: TaxReturnRecordOut["row"]): {
  label: string;
  tone: ReturnType<typeof status>["variant"];
} {
  const level =
    row.review_level === null
      ? undefined
      : row.review_level.charAt(0).toUpperCase() + row.review_level.slice(1);
  const labelled = status("return", row.status, {
    context:
      row.status === "in_review"
        ? "subbar_rail_rows"
        : ENTITY.has(row.form)
          ? "subbar_entity_returns"
          : "subbar_1040_1041",
    ...(level === undefined ? {} : { vars: { level } }),
  });
  return {
    label: labelled.label,
    tone: status("return", row.status, { context: "subbar" }).variant,
  };
}

function amount(v: EngineSummaryLineOut["amount"]): string {
  return v === null ? DASH : count(v);
}

/** A planned link's affordance: its "Opens …" hint where planned screens are drawn, else nothing. */
function Planned({ hint, children }: { hint: string; children: ReactNode }): JSX.Element | null {
  if (!PLANNED_VISIBLE) return null;
  return (
    <Tooltip content={hint}>
      <span className="inline-flex">{children}</span>
    </Tooltip>
  );
}

function Band({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  const [open, setOpen] = useState(true);
  return (
    <>
      <GroupBand
        title={title}
        open={open}
        onToggle={() => {
          setOpen((o) => !o);
        }}
      />
      {open && children}
    </>
  );
}

function TeamRow({ step }: { step: LadderStepOut }): JSX.Element {
  const label = step.step == null ? step.role : COPY.ladder[step.step];
  const row = (
    <div className="flex min-h-[38px] items-start gap-[10px] px-[12px] py-[6px] hairline-b">
      <span className="mt-[2px]">
        <StatusDisc state={DISC[step.state ?? "not_started"]} />
      </span>
      <span className="flex min-w-0 flex-col">
        <span className="text-dense text-ink">{label}</span>
        <span className="truncate text-meta text-ink-3">
          {step.note ?? step.person?.name ?? COPY.notAssigned}
        </span>
        {step.blocked_by != null && (
          <span className="text-meta text-amber-ink">{COPY.blockedBy(step.blocked_by)}</span>
        )}
      </span>
    </div>
  );
  return PLANNED_VISIBLE ? (
    <Tooltip content={COPY.hints.signoff(label)}>
      <div>{row}</div>
    </Tooltip>
  ) : (
    row
  );
}

function FilingRow({ row }: { row: FilingRowOut }): JSX.Element {
  if (row.key === "consents") {
    return (
      <div className="flex min-h-[33px] items-start justify-between gap-[10px] px-[12px] py-[7px] hairline-b">
        <span className="text-dense text-ink-2">{COPY.filing.consents}</span>
        <span className="flex flex-col items-end gap-[2px]">
          {row.pill != null && (
            <Pill variant="green" size="sm">
              {row.pill}
            </Pill>
          )}
          {row.detail != null && <span className="text-meta text-ink-3">{row.detail}</span>}
        </span>
      </div>
    );
  }
  return <KvRowView row={{ id: row.key, label: COPY.filing[row.key], value: row.value }} />;
}

function Rail({
  record,
  overview,
}: {
  record: TaxReturnRecordOut;
  overview: TaxReturnOverviewOut | undefined;
}): JSX.Element {
  const { row } = record;
  const state = stateOf(row);
  const open = useOpenHref();
  // The record links whose screens are built: Files opens the client's folder in FIL-01
  // (`/files/$clientId`, the screen's client route).
  const hrefs: Readonly<Record<string, string>> = {
    files: `${hrefOf(to.FIL01())}/${encodeURIComponent(row.client_id)}`,
  };
  return (
    <section aria-label={COPY.rail} className="pane flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="flex h-(--pane-hd-h) flex-none items-center justify-center bg-card hairline-b">
        <h2 className="text-pane font-medium tracking-[-0.012em]">{COPY.rail}</h2>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        <OverviewCard
          icon="file-text"
          title={COPY.formTitle(row.tax_year, FORM_LABEL[row.form])}
          sub={
            record.card_detail == null
              ? row.client_name
              : `${row.client_name} · ${record.card_detail}`
          }
          state={state.label}
        />
        {overview === undefined ? (
          <div className="flex flex-col gap-[8px] p-[12px]">
            <Skeleton className="h-[12px] w-[60%]" />
            <Skeleton className="h-[12px] w-[80%]" />
            <Skeleton className="h-[12px] w-[70%]" />
          </div>
        ) : (
          <>
            {(overview.record_links ?? []).length > 0 && (
              <Band title={COPY.bands.record}>
                {(overview.record_links ?? []).map((link) => {
                  const href = hrefs[link.key];
                  const r = (
                    <RailRow
                      link={{
                        id: link.key,
                        icon: RECORD_ICON[link.key] ?? "file-text",
                        title: COPY.record[link.key],
                        sub: link.sub,
                      }}
                      {...(href === undefined
                        ? {}
                        : {
                            onOpen: () => {
                              open(href);
                            },
                          })}
                    />
                  );
                  return PLANNED_VISIBLE ? (
                    <Tooltip key={link.key} content={COPY.hints[link.key]}>
                      <div>{r}</div>
                    </Tooltip>
                  ) : (
                    <div key={link.key}>{r}</div>
                  );
                })}
              </Band>
            )}
            {overview.ladder.length > 0 && (
              <Band title={COPY.bands.team}>
                {overview.ladder.map((step, i) => (
                  <TeamRow key={step.step ?? `${step.role}-${String(i)}`} step={step} />
                ))}
              </Band>
            )}
            {(overview.filing ?? []).length > 0 && (
              <Band title={COPY.bands.filing}>
                {(overview.filing ?? []).map((f) => (
                  <FilingRow key={f.key} row={f} />
                ))}
              </Band>
            )}
          </>
        )}
      </div>
    </section>
  );
}

function Banner({
  overview,
  now,
}: {
  overview: TaxReturnOverviewOut;
  now: Date;
}): JSX.Element | null {
  const dep = overview.k1_dependencies.find((k) => k.blocking === true);
  if (dep === undefined) return null;
  const label = dep.source_label ?? dep.issuer_name;
  return (
    <div
      role="status"
      className="col-span-2 flex min-h-[36px] items-center gap-[8px] rounded-nested bg-amber-tint px-[12px] py-[8px] text-dense font-medium text-amber-ink"
    >
      <Icon name="triangle-alert" size={14} />
      <span className="flex-1">
        {COPY.banner(
          label,
          dep.issuer_name,
          dep.short_name ?? dep.issuer_name,
          dep.source_due_on == null ? "" : formatDate(dep.source_due_on, { now }),
        )}
      </span>
      <Planned hint={COPY.hints.source}>
        <span className="text-ink">
          {COPY.openSource(label)} <span className="text-ink-3">→</span>
        </span>
      </Planned>
    </div>
  );
}

function Pipeline({ overview }: { overview: TaxReturnOverviewOut }): JSX.Element | null {
  const steps = overview.pipeline ?? [];
  if (steps.length === 0) return null;
  return (
    <section
      aria-label="Pipeline"
      className={`col-span-2 flex items-start gap-[12px] p-[14px] ${CARD}`}
    >
      {steps.map((s, i) => (
        <div key={s.step} className="flex flex-1 items-start gap-[10px]">
          <StatusDisc state={DISC[s.state]} size={17} />
          <span className="flex min-w-0 flex-col">
            <span className="text-section font-medium">{COPY.pipeline[s.step]}</span>
            <span className="text-meta text-ink-3">{s.sub}</span>
          </span>
          {i < steps.length - 1 && (
            <span aria-hidden="true" className="mt-[10px] h-px w-[40px] flex-none bg-rule" />
          )}
        </div>
      ))}
    </section>
  );
}

function CardHead({ children }: { children: ReactNode }): JSX.Element {
  return <h3 className="px-[14px] py-[12px] text-section font-medium hairline-b">{children}</h3>;
}

function Estimate({ overview, now }: { overview: TaxReturnOverviewOut; now: Date }): JSX.Element {
  const proForma = overview.pro_forma ?? [];
  if (proForma.length > 0) {
    return (
      <section aria-label={overview.pro_forma_label ?? COPY.estimate} className={CARD}>
        <CardHead>{overview.pro_forma_label}</CardHead>
        {proForma.map((r) => (
          <KvRowView key={r.label} row={{ id: r.label, label: r.label, value: r.value }} />
        ))}
      </section>
    );
  }
  const lines = overview.engine_summary;
  const title =
    lines.length > 0 && overview.engine_synced_on != null
      ? COPY.estimateFrom(formatDate(overview.engine_synced_on, { now }))
      : COPY.estimate;
  return (
    <section aria-label={COPY.estimate} className={CARD}>
      <CardHead>{title}</CardHead>
      {lines.length === 0 ? (
        <p className="px-[14px] py-[14px] text-dense text-ink-2">{COPY.noEstimate}</p>
      ) : (
        <table className="w-full text-cell tabular-nums">
          <tbody>
            {lines.map((l) => (
              <tr
                key={l.line_key}
                data-total={l.total ?? undefined}
                className={
                  l.total === "grand"
                    ? "border-t-[3px] border-double border-rule font-medium"
                    : l.total === "total"
                      ? "border-t border-rule font-medium"
                      : undefined
                }
              >
                <td className="w-[120px] px-[14px] py-[5px] align-top text-meta text-ink-3">
                  {l.line_ref}
                </td>
                <td
                  className={`py-[5px] align-top ${l.indent === true ? "pl-[20px] text-ink-2" : ""}`}
                >
                  {l.label}
                  {l.note != null && (
                    <span className="mt-[2px] flex items-center gap-[4px] text-meta text-amber-ink">
                      <Icon name="flag" size={12} />
                      {l.note}
                    </span>
                  )}
                </td>
                <td
                  className={`px-[14px] py-[5px] text-right align-top ${l.amount == null ? "text-ink-4" : ""}`}
                >
                  {amount(l.amount)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {overview.engine_footnote != null && lines.length > 0 && (
        <p className="px-[14px] py-[10px] text-meta text-ink-3 hairline-t">
          {overview.engine_footnote}
        </p>
      )}
    </section>
  );
}

function Plan({ overview }: { overview: TaxReturnOverviewOut }): JSX.Element | null {
  const rows = overview.plan ?? [];
  const k1s = overview.k1_classifications ?? [];
  if (rows.length === 0 && k1s.length === 0 && overview.carryforwards == null) return null;
  return (
    <section aria-label={COPY.plan} className={CARD}>
      <CardHead>{COPY.plan}</CardHead>
      {rows.map((r) => (
        <div
          key={r.label}
          className="flex min-h-[34px] items-start gap-[10px] px-[14px] py-[7px] hairline-b"
        >
          <span className="mt-[1px]">
            <StatusDisc state={DISC[r.state]} />
          </span>
          <span className="flex flex-col">
            <span className="text-dense">{r.label}</span>
            {r.detail != null && <span className="text-meta text-ink-3">{r.detail}</span>}
          </span>
        </div>
      ))}
      {k1s.length > 0 && (
        <>
          <p className="bg-band-hd px-[14px] py-[7px] text-dense text-ink-2 hairline-b">
            {COPY.k1Classifications}
          </p>
          {k1s.map((k) => (
            <div
              key={k.issuer_name}
              className="flex flex-col gap-[6px] px-[14px] py-[10px] hairline-b"
            >
              <span className="text-dense">{k.issuer_name}</span>
              <span className="flex flex-wrap gap-[6px]">
                {k.tags.map((t) => (
                  <Tag key={t}>{t}</Tag>
                ))}
                {k.pill != null && (
                  <Pill variant={k.pill_tone === "green" ? "green-tint" : "amber"} size="sm">
                    {k.pill}
                  </Pill>
                )}
              </span>
            </div>
          ))}
        </>
      )}
      {overview.carryforwards != null && (
        <>
          <p className="bg-band-hd px-[14px] py-[7px] text-dense text-ink-2 hairline-b">
            {COPY.carryforwards}
          </p>
          <p className="px-[14px] py-[10px] text-dense text-ink-2">{overview.carryforwards}</p>
        </>
      )}
    </section>
  );
}

function Issues({ overview }: { overview: TaxReturnOverviewOut }): JSX.Element {
  const rows = overview.issues ?? [];
  return (
    <section aria-label={COPY.issues(overview.open_issues)} className={CARD}>
      <CardHead>{COPY.issues(overview.open_issues)}</CardHead>
      {rows.length === 0 ? (
        <p className="px-[14px] py-[12px] text-dense text-ink-2 hairline-b">{COPY.noIssues}</p>
      ) : (
        rows.map((r) => (
          <div
            key={r.id}
            className="flex min-h-[40px] items-start gap-[8px] px-[14px] py-[7px] hairline-b"
          >
            <span className={`mt-[2px] ${FLAG[r.severity]}`}>
              <Icon name="flag" size={12} />
            </span>
            <span className="flex flex-col">
              <span className="text-dense">{r.title}</span>
              <span
                className={`text-meta ${r.kind === "action_required" ? "text-amber-ink" : "text-ink-3"}`}
              >
                {COPY.issueKind[r.kind]}
              </span>
            </span>
          </div>
        ))
      )}
      <div className="px-[14px] py-[10px]">
        <Planned hint={COPY.hints.issue}>
          <span className="text-dense font-medium">
            {COPY.openIssues} <span className="text-ink-3">→</span>
          </span>
        </Planned>
      </div>
    </section>
  );
}

function TwoYear({ overview }: { overview: TaxReturnOverviewOut }): JSX.Element | null {
  const rows = overview.two_year ?? [];
  if (rows.length === 0) return null;
  return (
    <section aria-label={COPY.twoYear} className={CARD}>
      <CardHead>{COPY.twoYear}</CardHead>
      {rows.map((r) => (
        <div
          key={r.key}
          className="flex items-baseline justify-between gap-[8px] px-[14px] py-[8px] hairline-b"
        >
          <span className="text-dense text-ink-2">{COPY.twoYearRows[r.key]}</span>
          <span className="flex items-baseline gap-[6px]">
            <span className="text-body font-medium tabular-nums">
              {count(r.prior)} → {count(r.current)}
            </span>
            {r.change_pct != null && (
              <span className="text-meta text-ink-3 tabular-nums">
                ({r.change_pct.startsWith("-") ? `−${r.change_pct.slice(1)}` : `+${r.change_pct}`}
                %)
              </span>
            )}
          </span>
        </div>
      ))}
      <div className="px-[14px] py-[10px]">
        <Planned hint={COPY.hints.twoYear}>
          <span className="text-dense font-medium">
            {COPY.openTwoYear} <span className="text-ink-3">→</span>
          </span>
        </Planned>
      </div>
    </section>
  );
}

function Body({
  record,
  overview,
  now,
}: {
  record: TaxReturnRecordOut;
  overview: TaxReturnOverviewOut;
  now: Date;
}): JSX.Element {
  if (record.row.status === "not_started") {
    return (
      <div className="flex min-h-0 flex-1 flex-col gap-[12px]">
        <Pipeline overview={overview} />
        <EmptyState
          icon="sparkles"
          title={COPY.noDraftTitle}
          {...(PLANNED_VISIBLE
            ? {
                action: (
                  <Button
                    variant="primary"
                    size="sm"
                    icon="sparkles"
                    disabled
                    title={COPY.binderNotPublished}
                  >
                    {COPY.runDraft}
                  </Button>
                ),
              }
            : {})}
        >
          {COPY.noDraftBody}
        </EmptyState>
      </div>
    );
  }
  const plan = <Plan overview={overview} />;
  const twoYear = <TwoYear overview={overview} />;
  return (
    <div className="grid grid-cols-[minmax(0,612fr)_minmax(0,388fr)] content-start gap-[12px]">
      <Banner overview={overview} now={now} />
      <Pipeline overview={overview} />
      <div className="flex min-w-0 flex-col gap-[12px]">
        <Estimate overview={overview} now={now} />
        <Issues overview={overview} />
      </div>
      <div className="flex min-w-0 flex-col gap-[12px]">
        {plan}
        {twoYear}
      </div>
    </div>
  );
}

function AssignMenu({ record }: { record: TaxReturnRecordOut }): JSX.Element {
  const members = useQuery(firmMembersOptions());
  const queryClient = useQueryClient();
  const assign = useMutation(returnAssignMutation());
  const [role, setRole] = useState<"preparer" | "reviewer" | "signer" | null>(null);
  const roles = (["preparer", "reviewer", "signer"] as const).map((r) => ({
    label: COPY.assignRoles[r],
    onSelect: () => {
      setRole(r);
    },
    opensDialog: true,
  }));
  return (
    <>
      <Menu
        label={COPY.actions.assign}
        align="end"
        trigger={
          <Button variant="secondary" size="sm" icon="user-plus" loading={assign.isPending}>
            {COPY.actions.assign}
          </Button>
        }
        sections={[roles]}
      />
      <Menu
        label={role === null ? COPY.actions.assign : COPY.assignRoles[role]}
        align="end"
        open={role !== null}
        onOpenChange={(open) => {
          if (!open) setRole(null);
        }}
        trigger={<span aria-hidden="true" className="block h-0 w-0" />}
        sections={[
          (members.data ?? []).map((m) => ({
            label: m.display_name,
            onSelect: () => {
              if (role === null) return;
              assign.mutate(
                {
                  path: { return_id: record.row.id },
                  body: { role, user_id: m.user_id },
                },
                {
                  onSuccess: () => {
                    toast.show({ kind: "success", text: COPY.assigned(m.display_name) });
                    void queryClient.invalidateQueries();
                  },
                  onError: () => {
                    toast.show({ kind: "error", text: COPY.assignFailed });
                  },
                },
              );
              setRole(null);
            },
          })),
        ]}
      />
    </>
  );
}

function Actions({ record }: { record: TaxReturnRecordOut }): JSX.Element {
  const { row } = record;
  const url = record.engine_url ?? null;
  const safe = url !== null && url.startsWith("https://");
  return (
    <span className="flex items-center gap-[8px]">
      {PLANNED_VISIBLE && (row.status === "accepted" || row.status === "filed") && (
        <Button variant="secondary" size="sm" icon="send" disabled title={COPY.hints.delivery}>
          {COPY.actions.openDelivery}
        </Button>
      )}
      {record.allowed_actions.includes("tax_return.assign") && <AssignMenu record={record} />}
      {PLANNED_VISIBLE &&
        row.status !== "not_started" &&
        row.status !== "gathering" &&
        row.status !== "accepted" && (
          <Button variant="secondary" size="sm" icon="sparkles" disabled title={COPY.rerunConfirm}>
            {COPY.actions.rerun}
          </Button>
        )}
      {safe ? (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex h-[29px] items-center gap-[6px] rounded-pill bg-card px-[11px] text-body text-ink shadow-e1 hover:bg-nested"
        >
          <Icon name="external-link" size={14} />
          {COPY.actions.openEngine}
        </a>
      ) : (
        <Button variant="secondary" size="sm" icon="external-link" disabled>
          {COPY.actions.openEngine}
        </Button>
      )}
    </span>
  );
}

export interface TAX02Props {
  returnId: string;
  tab?: Tax02Tab;
  onTab?: (tab: Tax02Tab) => void;
  /** The gallery's frame: the firm toolbar drawn inside the window. */
  toolbar?: ToolbarProps;
  frame?: boolean;
}

export function TAX02({
  returnId,
  tab = "overview",
  onTab,
  toolbar,
  frame = false,
}: TAX02Props): JSX.Element {
  const now = useNow();
  const openOverlay = useOpenOverlay();
  // The Checkpoints chip opens SHL-16 over the return where `review.checkpoints` is on.
  const checkpointsOn = useFlag("review.checkpoints") === true;
  const record = useQuery(returnRecordOptions({ path: { return_id: returnId } }));
  const overview = useQuery(returnOverviewOptions({ path: { return_id: returnId } }));
  const data = record.data;

  const state: ViewState = record.isError
    ? {
        kind: "error",
        retry: () => {
          void record.refetch();
          void overview.refetch();
        },
      }
    : data === undefined || overview.data === undefined
      ? { kind: "loading" }
      : { kind: "ready" };

  const subbar =
    data === undefined ? (
      <RecordHeader title="" checkpoints={false} sync={null} assistant={false} />
    ) : (
      (() => {
        const s = stateOf(data.row);
        return (
          <RecordHeader
            title={COPY.formTitle(data.row.tax_year, FORM_LABEL[data.row.form])}
            context={data.row.client_name}
            state={s.label}
            {...(s.tone === null ? {} : { stateTone: s.tone })}
            checkpoints={PLANNED_VISIBLE || checkpointsOn}
            onCheckpoints={() => {
              openOverlay(ov.SHL16("tax_return", returnId));
            }}
            sync={data.row.sync}
            onSync={() => {
              openOverlay(ov.TAX09(returnId)); // TAX-09: the return's engine sync (DEC-1288)
            }}
            {...(overview.data?.engine_synced_on == null
              ? {}
              : { syncDate: formatDate(overview.data.engine_synced_on, { now }) })}
            assistant={PLANNED_VISIBLE}
          />
        );
      })()
    );

  const counts = new Map((data?.tabs ?? []).map((t) => [t.tab, t.count]));
  const option = (key: Tax02Tab, live: boolean) => {
    const n = counts.get(key);
    return {
      label: COPY.tabs[key],
      ...(n == null || n === 0 ? {} : { count: n }),
      ...(key === "issues" ? { bad: true } : {}),
      ...(live ? {} : { disabled: true }),
    };
  };
  // The Intake, Review, Issues and Activity tabs open TAX-03, TAX-05, TAX-06 and TAX-07, all
  // planned: drawn disabled where planned screens are, absent in production.
  const tabs = (
    <Tabsbar
      label={COPY.tabs.label}
      options={[
        option("overview", true),
        ...(PLANNED_VISIBLE
          ? (["intake", "review", "issues", "activity"] as const).map((k) => option(k, false))
          : []),
      ]}
      active={COPY.tabs[tab === "overview" ? "overview" : tab]}
      onChange={(label) => {
        const key = (Object.keys(COPY.tabs) as (keyof typeof COPY.tabs)[]).find(
          (k) => k !== "label" && COPY.tabs[k] === label,
        );
        if (key !== undefined && key !== "label") onTab?.(key);
      }}
    />
  );

  const rail =
    data === undefined ? (
      <section aria-label={COPY.rail} className="pane flex min-h-0 flex-1 flex-col">
        <div className="flex h-(--pane-hd-h) flex-none items-center justify-center bg-card hairline-b">
          <h2 className="text-pane font-medium tracking-[-0.012em]">{COPY.rail}</h2>
        </div>
        <div className="flex flex-col gap-[10px] p-[12px]">
          <Skeleton className="h-[150px]" />
          <Skeleton className="h-[12px] w-[70%]" />
          <Skeleton className="h-[12px] w-[85%]" />
          <Skeleton className="h-[12px] w-[60%]" />
        </div>
      </section>
    ) : (
      <Rail record={data} overview={overview.data} />
    );

  return (
    <div data-screen="TAX-02" className="flex min-h-0 flex-1 flex-col">
      <RecordCockpit
        {...(toolbar === undefined ? {} : { toolbar })}
        frame={frame}
        {...(frame ? { height: 860 } : {})}
        header={subbar}
        tabs={tabs}
        rail={rail}
        canvas={{
          title: COPY.canvas,
          well: true,
          state,
          ...(data === undefined ? {} : { actions: <Actions record={data} /> }),
          children:
            data === undefined || overview.data === undefined ? null : (
              <Body record={data} overview={overview.data} now={now} />
            ),
        }}
      />
    </div>
  );
}

/** The screen with its own tab state: the gallery's artboard and the tests' host. */
export function ReturnOverviewPage(props: Omit<TAX02Props, "tab" | "onTab">): JSX.Element {
  const [tab, setTab] = useState<Tax02Tab>("overview");
  return <TAX02 {...props} tab={tab} onTab={setTab} />;
}
