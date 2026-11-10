import type {
  FiguresOut,
  Form5500Out,
  Form5500RowOut,
  Schedule4iOut,
  PartIvLineOut,
} from "@abacus/api-client";
import {
  ebpForm5500NoteMutation,
  ebpForm5500Options,
  ebpSchedule4iOptions,
  ebpSchedule4aOptions,
} from "@abacus/api-client/query";
import {
  type CockpitCanvas,
  type ViewState,
  Button,
  Icon,
  MATCH_ROW,
  PaneAction,
  Pill,
  Segmented,
  amount,
  cn,
  useMatch,
} from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import type { JSX } from "react";
import { useFlag } from "../../app-core/flags";
import { COPY } from "./copy";

// EBP-07 · Form 5500 tie-out & supplemental schedules (A-05-T58; A-05 §3 F7; SPEC-640; the handoff
// spec): the Testing › Form 5500 Tie-Out canvas in the cockpit, the draft's PDF in the viewer dock.
// Every figure, difference and classification is the server's (A-05-T36's tie-out); the screen adds
// nothing up. A row and the draft's field share the citation's own match id (C4 §3.1; INV-2), so
// one match lights both. Form values the TPA typed render in the form-typed ink; FS figures do not.
// No "$" in the statement table.

export const FORM_5500 = "ebp_07";
const FLAG = "ebp.modules";
export type Form5500Tab = keyof typeof COPY.tabs;
const TABS: readonly Form5500Tab[] = ["schedule_h", "part_iv", "schedules"];
const ASSETS = /^1/u;
const TOTALS = new Set(["1f", "1l", "2d", "2j", "2k"]);

const whole = (v: string | null | undefined): string => amount(v ?? null, "whole").text;

export interface Form5500Options {
  active?: boolean;
  tab?: Form5500Tab;
  onTab?: (tab: Form5500Tab) => void;
  onSignOff?: () => void;
  onSourceDocs?: () => void;
  /** The draft's PDF: the cockpit opens it in the viewer dock. */
  onOpenDraft?: (evidenceVersionId: string) => void;
  /** A Part IV evidence link: EBP-04, EBP-05, EBP-01 or EBP-06. */
  onEvidence?: (screen: string) => void;
  /** "Raise exception…": SHL-15, then AUD-15. */
  onRaise?: (line: PartIvLineOut) => void;
  /** "Remind Summit": POR-14's follow-up. */
  onRemind?: () => void;
}

function Line({ row }: { row: Form5500RowOut }): JSX.Element {
  const match = useMatch((row.match_id ?? `ebp07:${row.id}`) as never, "row");
  const total = TOTALS.has(row.line_code);
  const ties = row.classification === "tie";
  return (
    <tr
      data-line={row.line_code}
      data-classification={row.classification ?? undefined}
      {...(row.match_id == null ? {} : match.bind)}
      className={cn(
        "h-[28px] text-[11.5px] hairline-t",
        MATCH_ROW,
        total && "font-medium",
        row.line_code === "1l" && "border-b-[3px] border-double border-ink",
      )}
    >
      <td className="w-[54px] px-[10px] text-ink-2 tabular-nums">{row.line_code}</td>
      <td className="w-[170px] pr-[8px]">{row.caption}</td>
      <td data-col="fs" className="w-[96px] pr-[8px] text-right tabular-nums">
        {whole(row.fs_amount)}
      </td>
      <td data-col="form" className="w-[96px] pr-[8px] text-right tabular-nums">
        {whole(row.f5500_amount)}
      </td>
      <td
        data-col="difference"
        className={cn(
          "w-[80px] pr-[10px] text-right tabular-nums",
          row.classification === "reconciling_item" && "text-amber-ink",
          row.classification === "inconsistent" && "text-red-ink",
        )}
      >
        {ties ? (
          <span className="text-green">{COPY.tick}</span>
        ) : (
          <>
            {whole(row.difference)}
            {row.note_ref != null && !total && (
              <Pill size="chip" variant="amber" className="ml-[6px]">
                {row.note_ref}
              </Pill>
            )}
          </>
        )}
      </td>
    </tr>
  );
}

function Tallies({ view }: { view: Form5500Out }): JSX.Element {
  const rows = view.rows ?? [];
  const net = rows.find((r) => r.line_code === "1l");
  const income = rows.find((r) => r.line_code === "2d");
  const reconciled = rows.every((r) => r.classification !== "inconsistent");
  const off = (r: Form5500RowOut | undefined): string =>
    r?.difference == null ? COPY.tallies.tie : `${COPY.tallies.off} ${whole(r.difference)}`;
  return (
    <div data-ebp07="tallies" className="grid grid-cols-3 gap-[8px] px-[12px] py-[8px]">
      {[
        [COPY.tallies.assets, off(net), net?.difference == null],
        [COPY.tallies.income, off(income), income?.difference == null],
        [COPY.tallies.reconciled, reconciled ? COPY.tallies.tie : COPY.tallies.off, reconciled],
      ].map(([label, value, ok]) => (
        <div key={String(label)} className="rounded-[10px] bg-card px-[10px] py-[6px] shadow-e1">
          <div className="text-[11px] text-ink-3">{label}</div>
          <Pill size="chip" variant={ok === true ? "green-tint" : "amber"}>
            {value}
          </Pill>
        </div>
      ))}
    </div>
  );
}

function NoteCard({ view, workItemId }: { view: Form5500Out; workItemId: string }): JSX.Element {
  const rows = view.rows ?? [];
  const net = rows.find((r) => r.line_code === "1l");
  const income = rows.find((r) => r.line_code === "2k");
  const send = useMutation(ebpForm5500NoteMutation());
  return (
    <section data-ebp07="note" className="m-[12px] rounded-[12px] bg-card p-[12px] shadow-e1">
      <h4 className="text-[13px] font-medium">{COPY.note.title}</h4>
      <p className="mt-[6px] text-[12px] leading-[1.55] tabular-nums">
        {COPY.note.body(
          whole(net?.fs_amount),
          whole(net?.difference),
          whole(net?.f5500_amount),
          whole(income?.fs_amount),
          whole(income?.f5500_amount),
        )}
      </p>
      <div className="mt-[8px] flex items-center justify-between">
        <Pill size="chip" variant="green-tint">
          {COPY.note.status}
        </Pill>
        <Button
          size="xs"
          variant="secondary"
          disabled={send.isPending || !view.allowed_actions.includes("ebp_form5500.send_note")}
          onClick={() => {
            send.mutate({
              path: { work_item_id: workItemId },
              headers: { "Idempotency-Key": crypto.randomUUID() },
            });
          }}
        >
          {COPY.note.send}
        </Button>
      </div>
    </section>
  );
}

function ScheduleH({ view, workItemId }: { view: Form5500Out; workItemId: string }): JSX.Element {
  const rows = view.rows ?? [];
  const group = (title: string, lines: Form5500RowOut[]): JSX.Element[] => [
    <tr key={title} className="h-[28px] text-[11.5px] font-medium hairline-t">
      <td colSpan={5} className="px-[10px]">
        {title}
      </td>
    </tr>,
    ...lines.map((row) => <Line key={row.id} row={row} />),
  ];
  return (
    <>
      <Tallies view={view} />
      <div className="bg-card">
        <table data-ebp07="schedule-h" className="w-full">
          <thead>
            <tr className="h-[30px] bg-band-hd text-[11.5px] font-medium text-ink-3">
              <th className="px-[10px] text-left font-medium">{COPY.columns.line}</th>
              <th className="pr-[8px] text-left font-medium">{COPY.columns.caption}</th>
              <th className="pr-[8px] text-right font-medium">{COPY.columns.fs}</th>
              <th className="pr-[8px] text-right font-medium">{COPY.columns.form}</th>
              <th className="pr-[10px] text-right font-medium">{COPY.columns.difference}</th>
            </tr>
          </thead>
          <tbody>
            {group(
              COPY.groups.assets,
              rows.filter((r) => ASSETS.test(r.line_code)),
            )}
            {group(
              COPY.groups.income,
              rows.filter((r) => !ASSETS.test(r.line_code)),
            )}
          </tbody>
        </table>
      </div>
      <NoteCard view={view} workItemId={workItemId} />
    </>
  );
}

const EVIDENCE = /EBP-0\d/gu;

function PartIv({
  view,
  onEvidence,
  onRaise,
}: {
  view: Form5500Out;
  onEvidence?: (screen: string) => void;
  onRaise?: (line: PartIvLineOut) => void;
}): JSX.Element {
  const c = COPY.partIv.columns;
  return (
    <table data-ebp07="part-iv" className="w-full bg-card">
      <thead>
        <tr className="h-[30px] bg-band-hd text-[11.5px] font-medium text-ink-3">
          {[c.line, c.question, c.answer, c.amount, c.evidence, c.result].map((h) => (
            <th key={h} className="px-[8px] text-left font-medium">
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {view.part_iv.map((row) => {
          const bad = row.consistency === "inconsistent";
          const links = row.basis.match(EVIDENCE) ?? [];
          return (
            <tr
              key={row.line}
              data-part-iv={row.line}
              data-consistency={row.consistency}
              className="h-[34px] text-[11.5px] hairline-t"
            >
              <td className="px-[8px] tabular-nums text-ink-2">{row.line}</td>
              <td className="px-[8px]">{COPY.partIv.questions[row.line] ?? row.line}</td>
              <td className="px-[8px]">
                {row.draft_answer === "yes"
                  ? COPY.partIv.yes
                  : row.draft_answer === "no"
                    ? COPY.partIv.no
                    : ""}
              </td>
              <td className="px-[8px] text-right tabular-nums">{whole(row.draft_amount)}</td>
              <td className="px-[8px] text-ink-2">
                {links.length === 0 ? (
                  row.basis
                ) : (
                  <button
                    type="button"
                    data-evidence={links[0]}
                    className="text-left underline-offset-2 hover:underline"
                    onClick={() => {
                      onEvidence?.(links[0] ?? "");
                    }}
                  >
                    {row.basis}
                  </button>
                )}
              </td>
              <td className="px-[8px]">
                {bad ? (
                  <span data-ebp07="inconsistent" className="flex items-center gap-[6px]">
                    <Icon name="flag" size={12} className="text-red" />
                    <span className="text-red-ink">{COPY.partIv.inconsistent}</span>
                    <Button
                      size="xs"
                      variant="secondary"
                      onClick={() => {
                        onRaise?.(row);
                      }}
                    >
                      {COPY.partIv.raise}
                    </Button>
                  </span>
                ) : row.consistency === "consistent" ? (
                  <span className="text-green">{COPY.tick}</span>
                ) : (
                  <span data-ebp07="not-checked" className="text-ink-3">
                    —
                  </span>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function Schedules({
  schedule,
  late,
}: {
  schedule: Schedule4iOut | undefined;
  late: FiguresOut | undefined;
}): JSX.Element {
  const c = COPY.schedules.columns;
  return (
    <>
      <section data-ebp07="schedule-4i" className="m-[12px] rounded-[12px] bg-card shadow-e1">
        <h4 className="flex h-[32px] items-center px-[12px] text-[13px] font-medium hairline-b">
          {COPY.schedules.title4i}
        </h4>
        <table className="w-full">
          <thead>
            <tr className="h-[28px] text-[11.5px] text-ink-3">
              <th className="w-[28px] pl-[12px] text-left font-normal">{c.mark}</th>
              <th className="px-[8px] text-left font-normal">{c.identity}</th>
              <th className="px-[8px] text-left font-normal">{c.description}</th>
              <th className="px-[8px] text-right font-normal">{c.cost}</th>
              <th className="pr-[12px] text-right font-normal">{c.current}</th>
            </tr>
          </thead>
          <tbody>
            {(schedule?.rows ?? []).map((r) => (
              <tr
                key={r.identity}
                data-held={r.identity}
                data-mark={r.mark}
                className="h-[28px] text-[11.5px] hairline-t"
              >
                <td className="pl-[12px]">{r.mark}</td>
                <td className="px-[8px]">{r.identity}</td>
                <td className="px-[8px] text-ink-2">{r.description}</td>
                <td className="px-[8px] text-right tabular-nums">
                  {r.cost_omitted ? COPY.schedules.omitted : whole(r.cost)}
                </td>
                <td className="pr-[12px] text-right tabular-nums">{whole(r.current_value)}</td>
              </tr>
            ))}
            <tr
              data-held="total"
              data-ties={schedule?.ties === true ? "" : undefined}
              className="h-[28px] text-[11.5px] font-medium hairline-t"
            >
              <td />
              <td className="px-[8px]" colSpan={3}>
                {COPY.schedules.total}
              </td>
              <td className="pr-[12px] text-right tabular-nums">{whole(schedule?.total)}</td>
            </tr>
          </tbody>
        </table>
        <ul className="px-[12px] py-[6px] text-[11px] text-ink-3">
          {COPY.schedules.footnotes.map((f) => (
            <li key={f}>{f}</li>
          ))}
        </ul>
      </section>
      <section data-ebp07="schedule-4a" className="m-[12px] rounded-[12px] bg-card shadow-e1">
        <h4 className="flex h-[32px] items-center px-[12px] text-[13px] font-medium hairline-b">
          {late?.title ?? COPY.schedules.title4a}
        </h4>
        <table className="w-full">
          <tbody>
            {(late?.rows ?? []).map((r) => (
              <tr key={r.key} className="h-[28px] text-[11.5px] hairline-t">
                <td className="px-[12px]">{r.label}</td>
                <td className="pr-[12px] text-right tabular-nums">{whole(r.amount)}</td>
              </tr>
            ))}
            <tr className="h-[28px] text-[11.5px] font-medium hairline-t">
              <td className="px-[12px]">{COPY.schedules.total}</td>
              <td className="pr-[12px] text-right tabular-nums">{whole(late?.total)}</td>
            </tr>
          </tbody>
        </table>
      </section>
    </>
  );
}

export function useForm5500Canvas(
  workItemId: string,
  options: Form5500Options = {},
): CockpitCanvas {
  const on = useFlag(FLAG) === true;
  const tab = options.tab ?? "schedule_h";
  const enabled = options.active !== false && on;
  const path = { path: { work_item_id: workItemId } };
  const found = useQuery({ ...ebpForm5500Options(path), enabled, retry: false });
  const schedules = enabled && tab === "schedules";
  const schedule4i = useQuery({
    ...ebpSchedule4iOptions(path),
    enabled: schedules,
    retry: false,
  });
  const late = useQuery({ ...ebpSchedule4aOptions(path), enabled: schedules, retry: false });
  const view = found.data;
  let state: ViewState = { kind: "ready" };
  if (!on) state = { kind: "flag-off", flag: FLAG };
  else if (found.isError) {
    const code = (found.error as { status?: number } | null)?.status;
    state =
      code === 404
        ? { kind: "restricted", reason: "walled" }
        : { kind: "error", retry: () => void found.refetch() };
  } else if (view === undefined) state = { kind: "loading" };
  else if (!view.draft_received) {
    state = {
      kind: "empty",
      ...(options.onRemind === undefined
        ? {}
        : { action: { label: COPY.empty.remind, onSelect: options.onRemind } }),
    };
  }
  const signOff = options.onSignOff === undefined ? {} : { onClick: options.onSignOff };
  const source =
    options.onSourceDocs !== undefined
      ? { onClick: options.onSourceDocs }
      : view?.evidence_version_id != null && options.onOpenDraft !== undefined
        ? {
            onClick: () => {
              options.onOpenDraft?.(view.evidence_version_id ?? "");
            },
          }
        : {};
  const cited = (view?.rows ?? []).filter((r) => r.match_id != null).length;
  return {
    title: COPY.title,
    well: true,
    state,
    empty: { icon: "file-text", title: COPY.empty.title, body: COPY.empty.body },
    actions: (
      <>
        <Pill size="chip" variant="muted">
          {COPY.agentDraft}
        </Pill>
        <PaneAction label={COPY.edit} />
        <PaneAction label={COPY.signOff} {...signOff} />
        <PaneAction label={COPY.sourceDocs} {...source} />
      </>
    ),
    controls: (
      <div className="flex w-full items-center justify-between">
        <Segmented
          label={COPY.title}
          size="small"
          active={COPY.tabs[tab]}
          options={TABS.map((t) => COPY.tabs[t])}
          onChange={(label) => {
            const next = TABS.find((t) => COPY.tabs[t] === label);
            if (next !== undefined) options.onTab?.(next);
          }}
        />
        {view?.draft_received === true && (
          <span className="text-[11.5px] text-ink-3">{COPY.uploaded}</span>
        )}
      </div>
    ),
    footer:
      view?.draft_received === true ? (
        <span className="flex gap-[6px] text-[11.5px] text-ink-2">
          <Pill size="chip" variant="outline">
            {COPY.footer.citations(cited)}
          </Pill>
          <Pill size="chip" variant="outline">
            {COPY.footer.procedures}
          </Pill>
        </span>
      ) : undefined,
    children:
      view === undefined || !view.draft_received ? null : (
        <div data-screen="EBP-07" data-tab={tab} className="min-h-0 flex-1 overflow-y-auto">
          {tab === "schedule_h" && <ScheduleH view={view} workItemId={workItemId} />}
          {tab === "part_iv" && (
            <PartIv
              view={view}
              {...(options.onEvidence === undefined ? {} : { onEvidence: options.onEvidence })}
              {...(options.onRaise === undefined ? {} : { onRaise: options.onRaise })}
            />
          )}
          {tab === "schedules" && <Schedules schedule={schedule4i.data} late={late.data} />}
        </div>
      ),
  };
}
