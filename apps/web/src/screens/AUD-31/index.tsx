import type {
  AccountMappingOut,
  FsLineOptionOut,
  GroupSubtotalOut,
  MappingSetOut,
  MappingSetSummaryOut,
} from "@abacus/api-client";
import {
  accountMappingEditMutation,
  groupingCatalogueOptions,
  groupingLinesOptions,
  mappingConfirmMutation,
  mappingRunOptions,
  mappingSetOptions,
  mappingSetQueryKey,
  mappingSetsOptions,
  mappingSetsQueryKey,
} from "@abacus/api-client/query";
import {
  type Actor,
  Button,
  ConfirmDialog,
  HumanAction,
  Icon,
  MappingTable,
  type MappingTableGroup,
  type MappingTableRow,
  Menu,
  type MenuItem,
  Pill,
  TallyStrip,
  type TallyItem,
  type ViewState,
  ViewStateBody,
  amount,
  cn,
  date as formatDate,
  time,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useFlag } from "../../app-core/flags";
import { useOpenOverlay } from "../../app-core/open";
import { useSession } from "../../app-core/session";
import { ov } from "../../routes/to";
import { COPY } from "./copy";

// AUD-31 · Trial balance mapping (A-03-T12; docs/screens/AUD-31.md; the AUD-31 handoff, f and the
// composed a′–e′), single entity: the T3 two-pane Focus layout, a 490 source-file pane beside the
// 876 mapping pane on the new L2 MappingTable kit, over C9 v2 (`mapping-sets`, `group_by=fs_line`).
//
// - Focus row: "‹ Cockpit" and the entity and year centred (no entity segmented for one entity).
// - Source file: the ledger snapshot's account row lit in the match purple for the selected
//   mapping row (the read-only snapshot the mapping reads; SourceViewer row lighting).
// - Mapping: header pill (n need review · Confirmed <date> · Changed after sign-off), Edit,
//   Sign off… (SHL-12, a HumanAction) and Source Docs; the TallyStrip (MAPPED, NEED REVIEW, the
//   methods when the server names them, TB BALANCED with a tie pill); the run line without the
//   atom (DV-B1); the confirmed (d′) and stale (e′) banners; the table: NEEDS REVIEW band, then
//   MAPPED by grouping › FS line with the server's subtotals; Change ⌄ is the O1 picker grouped
//   by class with Recently used. No Accept, no Request changes…, no reasoning line: there are no
//   suggestions without the TB mapper (DV-B2).
// - Footer: "Confirm and continue" asks "Adopt n mappings (k edited) and mark the mapping
//   Prepared?" and posts the content hash seen; once confirmed, "Open TB & leadsheets ›".
// - b′: while the rules run, the body is the importing card, polling the run.
//
// Every figure is the server's: the screen formats, it never sums. Behind `ledger.tb_mapping`.

export interface AUD31Props {
  engagementId: string;
  /** "‹ Cockpit" and "Open TB & leadsheets ›" (the hosts' routes; planned in fixtures). */
  onCockpit?: () => void;
  onOpenTb?: () => void;
  /** The cockpit's Source Docs (AUD-03). */
  onSourceDocs?: () => void;
  height?: number;
}

const RUN_POLL_MS = 2_000;

function useActor(): Actor {
  const session = useSession();
  return session.user === null
    ? { kind: "system" }
    : { kind: "human", name: session.user.displayName };
}

const yearOf = (iso: string): string => iso.slice(0, 4);
const priorYear = (iso: string): string => String(Number(iso.slice(0, 4)) - 1);
const whole = (v: string): ReturnType<typeof amount> => amount(v, "whole");

function confirmedOf(
  summary: MappingSetSummaryOut,
): { name: string; initials: string; at: string } | null {
  const l1 = summary.sign_offs.find((s) => s.level === 1);
  return l1 === undefined ? null : { name: l1.name, initials: l1.initials, at: l1.at };
}

// ---- The source-file pane ---------------------------------------------------------------------

function SourcePane({
  selected,
  caption,
}: {
  selected: AccountMappingOut | undefined;
  caption: string;
}): JSX.Element {
  const credit = selected !== undefined && selected.balance.startsWith("-");
  const shown = selected === undefined ? null : whole(selected.balance.replace(/^-/u, "")).text;
  return (
    <section
      aria-label={COPY.sourceFile}
      className="pane flex min-h-0 w-[490px] flex-none flex-col"
    >
      <div className="flex h-(--pane-hd-h) flex-none items-center justify-center bg-card hairline-b">
        <h2 className="text-pane font-medium tracking-[-0.012em]">{COPY.sourceFile}</h2>
      </div>
      <div className="flex min-h-0 flex-1 flex-col gap-[8px] overflow-auto bg-shell p-[12px]">
        <table className="w-full overflow-hidden rounded-[6px] bg-card text-cell shadow-e1">
          <thead>
            <tr className="h-[26px] bg-espresso text-th font-medium text-on-dark">
              {COPY.sourceColumns.map((c, i) => (
                <th key={c} className={cn("px-[10px]", i < 2 ? "text-left" : "text-right")}>
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {selected === undefined ? (
              <tr>
                <td colSpan={4} className="px-[10px] py-[28px] text-center text-body text-ink-2">
                  {COPY.selectAccount}
                </td>
              </tr>
            ) : (
              <tr
                data-lit=""
                data-match={selected.citation_match_id}
                className="h-[24px] bg-match-bg ring-1 ring-match-line ring-inset"
              >
                <td className="px-[10px] font-mono text-th">{selected.account_code}</td>
                <td className="px-[10px]">{selected.account_name}</td>
                <td className="px-[10px] text-right tabular-nums">{credit ? "" : shown}</td>
                <td className="px-[10px] text-right tabular-nums">{credit ? shown : ""}</td>
              </tr>
            )}
          </tbody>
        </table>
        <p className="text-pill-sm text-ink-3">{caption}</p>
      </div>
    </section>
  );
}

// ---- The Change picker (O1) -------------------------------------------------------------------

function ChangePicker({
  set,
  row,
  onPick,
}: {
  set: MappingSetSummaryOut;
  row: AccountMappingOut;
  onPick: (line: FsLineOptionOut) => void;
}): JSX.Element {
  const catalogue = useQuery(groupingCatalogueOptions());
  const owner = catalogue.data?.find((g) =>
    g.versions.some((v) => v.id === set.grouping_set_version_id),
  );
  const version = owner?.versions.find((v) => v.id === set.grouping_set_version_id);
  const lines = useQuery({
    ...groupingLinesOptions({
      path: { grouping_set_id: owner?.id ?? "", version_no: version?.version_no ?? 0 },
    }),
    enabled: owner !== undefined && version !== undefined,
  });
  const item = (l: FsLineOptionOut): MenuItem => ({
    label: `${l.grouping_label} › ${l.label}`,
    checked: l.id === row.fs_line_id,
    onSelect: () => {
      onPick(l);
    },
  });
  const data = lines.data;
  const sections: MenuItem[][] =
    data === undefined
      ? []
      : [
          data.recently_used.map((l) => ({ ...item(l), hint: COPY.recentlyUsed })),
          ...data.classes.map((c) =>
            c.groupings
              .flatMap((g) => g.lines)
              .map((l) => ({ ...item(l), hint: COPY.classes[c.class] ?? c.class })),
          ),
        ].filter((s) => s.length > 0);
  return (
    <Menu
      label={COPY.search}
      width={320}
      align="end"
      sections={sections}
      trigger={
        <button
          type="button"
          className="inline-flex items-center gap-[2px] text-body text-ink-3 hover:text-ink"
        >
          {COPY.change}
          <Icon name="chevron-down" size={12} />
        </button>
      }
    />
  );
}

// ---- The screen -------------------------------------------------------------------------------

export function AUD31({
  engagementId,
  onCockpit,
  onOpenTb,
  onSourceDocs,
  height,
}: AUD31Props): JSX.Element {
  const on = useFlag("ledger.tb_mapping") === true;
  const now = useNow();
  const actor = useActor();
  const queryClient = useQueryClient();
  const openOverlay = useOpenOverlay();
  const sets = useQuery({
    ...mappingSetsOptions({ path: { engagement_id: engagementId } }),
    enabled: on,
    retry: false,
  });
  const summary = sets.data?.items[0];
  const setId = summary?.id ?? "";
  const set = useQuery({
    ...mappingSetOptions({ path: { mapping_set_id: setId }, query: { group_by: "fs_line" } }),
    enabled: on && summary !== undefined,
    retry: false,
  });
  const running = (set.data?.summary.run_status ?? summary?.run_status) === "running";
  const run = useQuery({
    ...mappingRunOptions({ path: { mapping_set_id: setId } }),
    enabled: on && running,
    refetchInterval: running ? RUN_POLL_MS : false,
  });
  const [selected, setSelected] = useState<string | null>(null);
  const [open, setOpen] = useState<ReadonlySet<string>>(new Set());
  const [asking, setAsking] = useState(false);
  const [justConfirmed, setJustConfirmed] = useState(false);
  const refresh = (): void => {
    void queryClient.invalidateQueries({
      queryKey: mappingSetQueryKey({ path: { mapping_set_id: setId } }),
    });
    void queryClient.invalidateQueries({
      queryKey: mappingSetsQueryKey({ path: { engagement_id: engagementId } }),
    });
  };
  const edit = useMutation({ ...accountMappingEditMutation(), onSuccess: refresh });
  const confirm = useMutation({ ...mappingConfirmMutation(), onSuccess: refresh });

  let state: ViewState = { kind: "ready" };
  if (!on) state = { kind: "flag-off", flag: "ledger.tb_mapping" };
  else if (set.isError || (sets.isError && !isNotFound(sets.error))) {
    state = { kind: "error", retry: () => void set.refetch() };
  } else if (sets.isError || (sets.isSuccess && summary === undefined)) state = { kind: "empty" };
  else if (set.data === undefined) state = { kind: "loading" };

  const data: MappingSetOut | undefined = set.data;
  const s = data?.summary;
  const rows = data?.rows ?? [];
  const chosen = rows.find((r) => r.account_code === selected);
  const confirmed = s === undefined ? null : confirmedOf(s);
  const isConfirmed = s?.status === "prepared" || s?.status === "reviewed";
  const stale = s?.status === "changed_after_sign_off";
  const allowed = data?.allowed_actions ?? [];
  const canEdit = allowed.includes("account_mapping.edit");

  const change = (row: AccountMappingOut, line: FsLineOptionOut): void => {
    edit.mutate(
      {
        path: { mapping_set_id: setId, account_code: row.account_code },
        body: { fs_line_id: line.id, seen_version: row.seen_version },
      },
      {
        onSuccess: () => toast.show({ kind: "success", text: COPY.toasts.changed }),
        onError: () => toast.show({ kind: "error", text: COPY.toasts.failed }),
      },
    );
  };
  const toRow = (r: AccountMappingOut): MappingTableRow => {
    const b = whole(r.balance);
    const mappedTo =
      r.fs_line_label === null || r.grouping_label === null
        ? null
        : `${r.grouping_label} › ${r.fs_line_label}`;
    return {
      id: r.account_code,
      code: r.account_code,
      name: r.account_name,
      balance: b.text,
      balanceTone: b.tone,
      mapped: mappedTo,
      ...(r.state === "edited" && r.edited_by_initials !== null
        ? {
            marker: (
              <span data-edited="" className="text-meta text-ink-3">
                {COPY.edited(r.edited_by_initials, r.was_fs_line_label)}
              </span>
            ),
          }
        : {}),
      method: r.method === null ? null : (COPY.methods[r.method] ?? r.method),
      confidence: r.confidence === null ? null : (COPY.confidence[r.confidence] ?? r.confidence),
      ...(r.state === "unmapped" && canEdit && s !== undefined
        ? {
            actions: (
              <ChangePicker
                set={s}
                row={r}
                onPick={(l) => {
                  change(r, l);
                }}
              />
            ),
          }
        : r.state === "edited" && canEdit && s !== undefined
          ? {
              actions: (
                <ChangePicker
                  set={s}
                  row={r}
                  onPick={(l) => {
                    change(r, l);
                  }}
                />
              ),
            }
          : {}),
    };
  };
  const review = rows.filter((r) => r.state === "unmapped" || r.state === "suggested");
  const mappedRows = rows.filter((r) => !review.includes(r));
  const groups: MappingTableGroup[] = (data?.subtotals ?? []).map((g: GroupSubtotalOut) => ({
    key: g.grouping_key,
    label: g.grouping_label,
    open: open.has(g.grouping_key),
    rows: mappedRows.filter((r) => r.grouping_label === g.grouping_label).map(toRow),
    subtotal: (
      <span className="flex items-center gap-[8px] tabular-nums">
        {COPY.subtotal(
          whole(g.subtotal).text,
          g.source_total === null ? null : whole(g.source_total).text,
        )}
        {g.off === null ? (
          <Pill variant="green" size="sm" check>
            {COPY.tie}
          </Pill>
        ) : (
          <Pill variant="amber" size="sm">
            {COPY.off(whole(g.off).text)}
          </Pill>
        )}
      </span>
    ),
  }));

  const t = s?.tallies;
  const tally: TallyItem[] =
    t === undefined
      ? []
      : [
          {
            label: COPY.tally.mapped,
            value: running ? COPY.tally.pending : COPY.tally.of(t.mapped, t.accounts),
          },
          t.need_review > 0
            ? { label: COPY.tally.review, pill: { text: String(t.need_review), variant: "amber" } }
            : {
                label: COPY.tally.review,
                value: running ? COPY.tally.pending : String(t.need_review),
              },
          ...(t.prior_year_match === null
            ? []
            : [{ label: COPY.tally.prior, value: String(t.prior_year_match) }]),
          ...(t.number_range === null
            ? []
            : [{ label: COPY.tally.range, value: String(t.number_range) }]),
          {
            label: COPY.tally.balanced,
            value: running ? COPY.tally.pending : COPY.tally.of(t.tb_balanced, t.tb_count),
            ...(t.tb_balanced === t.tb_count && !running
              ? { pill: { text: COPY.tie, variant: "green" as const, check: true } }
              : {}),
          },
        ];

  const pill =
    s === undefined ? null : stale ? (
      <Pill variant="amber" size="sm">
        {COPY.pills.stale}
      </Pill>
    ) : isConfirmed && confirmed !== null ? (
      <Pill variant="green-tint" size="sm">
        {COPY.pills.confirmed(formatDate(confirmed.at, { now }))}
      </Pill>
    ) : s.tallies.need_review > 0 ? (
      <Pill variant="amber" size="sm">
        {COPY.pills.review(s.tallies.need_review)}
      </Pill>
    ) : null;

  const footer =
    s === undefined ? null : isConfirmed ? (
      <>
        <Button variant="primary" onClick={onOpenTb} disabled={onOpenTb === undefined}>
          {COPY.footer.openTb}
        </Button>
        {confirmed !== null && (
          <span className="text-meta text-ink-3">
            {COPY.footer.confirmedNote(
              confirmed.name,
              formatDate(confirmed.at, { now }),
              s.tallies.accounts,
            )}
          </span>
        )}
      </>
    ) : (
      <>
        <HumanAction
          verb="Adopt"
          actor={actor}
          label={COPY.footer.confirm}
          variant="primary"
          aria-haspopup="dialog"
          disabled={
            !allowed.includes("mapping_set.confirm") || s.tallies.need_review > 0 || running
          }
          loading={confirm.isPending}
          onClick={() => {
            setAsking(true);
          }}
        />
        <span className="text-meta text-ink-3">
          {COPY.footer.note(
            s.tallies.accounts,
            actor.kind === "human" ? initials(actor.name) : "",
          )}
        </span>
      </>
    );

  const body = (
    <ViewStateBody
      state={state}
      empty={{ title: COPY.states.empty }}
      noun={COPY.states.noun}
      flagLabel={COPY.states.flag}
    >
      {() =>
        s === undefined || t === undefined ? null : (
          <>
            <div className="flex-none px-[12px] pt-[12px]">
              <TallyStrip label={COPY.title} items={tally} />
            </div>
            <p className="flex h-[30px] flex-none items-center px-[14px] text-meta text-ink-3">
              {s.prior_source === "none"
                ? COPY.runLineNone
                : COPY.runLine(priorYear(s.period_end))}
            </p>
            {justConfirmed && confirmed !== null && (
              <p
                role="status"
                data-aud31="confirmed"
                className="mx-[12px] mb-[8px] flex h-[32px] items-center rounded-nested bg-green-tint px-[12px] text-dense text-green-ink"
              >
                {COPY.banners.confirmed(confirmed.name, time(confirmed.at))}
              </p>
            )}
            {stale && (
              <p
                role="status"
                data-aud31="stale"
                className="mx-[12px] mb-[8px] flex min-h-[32px] items-center gap-[8px] rounded-nested bg-amber-tint px-[12px] text-dense text-amber-ink"
              >
                <Icon name="triangle-alert" size={14} />
                {COPY.banners.stale}
              </p>
            )}
            {running ? (
              <Importing
                done={run.data?.run_done ?? 0}
                total={run.data?.run_total ?? t.accounts}
              />
            ) : (
              <div className="min-h-0 flex-1 overflow-auto">
                <MappingTable
                  label={COPY.title}
                  review={{ label: COPY.review(review.length), rows: review.map(toRow) }}
                  mapped={{
                    label: COPY.mapped(
                      mappedRows.length === rows.length ? t.mapped : mappedRows.length,
                    ),
                    control: (
                      <span className="inline-flex h-[29px] items-center gap-[6px] rounded-pill bg-card px-[11px] text-body shadow-e1">
                        {COPY.groupBy}
                        <Icon name="chevron-down" size={12} className="text-ink-3" />
                      </span>
                    ),
                    groups,
                  }}
                  selected={selected}
                  onSelect={(r) => {
                    setSelected(r.id);
                  }}
                  onToggle={(key) => {
                    setOpen((prev) => {
                      const next = new Set(prev);
                      if (next.has(key)) next.delete(key);
                      else next.add(key);
                      return next;
                    });
                  }}
                />
              </div>
            )}
          </>
        )
      }
    </ViewStateBody>
  );

  return (
    <div
      data-screen="AUD-31"
      className="flex min-h-0 flex-1 flex-col bg-shell"
      {...(height === undefined ? {} : { style: { height } })}
    >
      <div className="relative flex h-[50px] flex-none items-center justify-center px-(--edge-app)">
        <button
          type="button"
          onClick={onCockpit}
          disabled={onCockpit === undefined}
          className="absolute left-(--edge-app) inline-flex items-center gap-[4px] text-tab text-ink enabled:hover:text-ink-2"
        >
          <Icon name="chevron-left" size={14} className="text-ink-3" />
          {COPY.cockpit}
        </button>
        {s !== undefined && (
          <p className="text-tab">{COPY.focus(s.entity_name, yearOf(s.period_end))}</p>
        )}
      </div>
      <div className="flex min-h-0 flex-1 gap-[10px] px-[12px] pb-[12px]">
        <SourcePane
          selected={chosen}
          caption={COPY.sourceCaption(
            confirmed === null || !isConfirmed ? null : formatDate(confirmed.at, { now }),
          )}
        />
        <section aria-label={COPY.title} className="pane flex min-h-0 min-w-0 flex-1 flex-col">
          <div className="flex h-(--pane-hd-h) flex-none items-center gap-[10px] bg-card px-[14px] hairline-b">
            <h2 className="text-pane font-medium tracking-[-0.012em]">{COPY.title}</h2>
            {pill}
            <span className="ml-auto flex items-center gap-[8px]">
              <Button variant="secondary" size="sm" icon="pencil" disabled={!canEdit}>
                {COPY.actions.edit}
              </Button>
              {s !== undefined && (
                <HumanAction
                  verb="Sign off"
                  actor={actor}
                  opensDialog
                  variant="secondary"
                  size="sm"
                  icon="check"
                  aria-haspopup="dialog"
                  disabled={!isConfirmed}
                  onClick={() => {
                    openOverlay(ov.SHL12("mapping_set", s.id));
                  }}
                />
              )}
              <Button
                variant="secondary"
                size="sm"
                icon="file-text"
                onClick={onSourceDocs}
                disabled={onSourceDocs === undefined}
              >
                {COPY.actions.sourceDocs}
              </Button>
            </span>
          </div>
          {body}
          {state.kind === "ready" && footer !== null && (
            <div className="flex h-[56px] flex-none items-center justify-between gap-[12px] px-[14px] hairline-t">
              {footer}
            </div>
          )}
        </section>
      </div>
      {s !== undefined && (
        <ConfirmDialog
          open={asking}
          onOpenChange={setAsking}
          destructive={false}
          title={COPY.dialog.title(s.tallies.accounts, s.tallies.edited ?? 0)}
          confirmLabel={COPY.dialog.confirm}
          onConfirm={() => {
            confirm.mutate(
              { path: { mapping_set_id: s.id }, body: { seen_hash: s.content_hash } },
              {
                onSuccess: () => {
                  setJustConfirmed(true);
                  toast.show({ kind: "success", text: COPY.toasts.confirmed });
                },
                onError: () => toast.show({ kind: "error", text: COPY.toasts.failed }),
              },
            );
          }}
        />
      )}
    </div>
  );
}

function initials(name: string): string {
  return name
    .split(" ")
    .map((p) => p[0] ?? "")
    .join("")
    .toUpperCase();
}

function isNotFound(error: unknown): boolean {
  return (error as { detail?: unknown } | null)?.detail === "not_found";
}

/** b′: the rules running, a ring over the run's progress (no donut in the default state). */
function Importing({ done, total }: { done: number; total: number }): JSX.Element {
  const pct = total === 0 ? 0 : Math.round((done / total) * 100);
  return (
    <div className="flex flex-1 items-start justify-center pt-[48px]">
      <div
        role="status"
        aria-busy="true"
        data-aud31="importing"
        className="flex w-[420px] flex-col items-center gap-[8px] rounded-pane bg-card p-[20px] shadow-e2"
      >
        <svg role="img" aria-label={`${String(pct)}%`} width={22} height={22} viewBox="0 0 22 22">
          <circle cx={11} cy={11} r={9} fill="none" strokeWidth={2.5} className="stroke-nested" />
          <circle
            cx={11}
            cy={11}
            r={9}
            fill="none"
            strokeWidth={2.5}
            strokeDasharray={`${String((pct / 100) * 2 * Math.PI * 9)} ${String(2 * Math.PI * 9)}`}
            transform="rotate(-90 11 11)"
            className="stroke-ink-2"
          />
        </svg>
        <p className="text-body font-medium">{COPY.importing.title}</p>
        <p className="text-center text-dense text-ink-2">{COPY.importing.body}</p>
      </div>
    </div>
  );
}
