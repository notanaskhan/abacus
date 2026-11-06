import type {
  AnalysisOut,
  AnalysisRowOut,
  DecisionCardOut,
  InformationReturnOut,
  NoticeOut,
} from "@abacus/api-client";
import {
  analysisOptions,
  noticeActivityOptions,
  noticeOptions,
  noticeStartMutation,
  responseDraftMutation,
} from "@abacus/api-client/query";
import {
  AgentText,
  Amount,
  Button,
  Icon,
  Pill,
  Segmented,
  Skeleton,
  Spinner,
  ViewStateBody,
  type ViewState,
  amount as formatAmount,
  cn,
  useFormat,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useFlag } from "../../app-core/flags";
import { useDecisionCard } from "../../domain/review";
import { ResponseEditor } from "../NOT-03";
import { ViewerPane } from "../SHL-08";
import { COPY } from "./copy";

// NOT-02 · Notice workspace (N-04-T14; N-04 §3; the handoff spec): the T3 Review preset (452 · 452 ·
// 452) over `GET /v1/notices/{id}` and its analysis (N-04-T11). The viewer shows the notice and,
// from the "1099 corrections" source row, its stacked sources ("1 / 2"); the analysis pane is the
// statement grammar over the server's rows (Notice vs return · Information returns · Transcript),
// the information-returns card and Why This Was Surfaced through AgentText (live, off and refused);
// the action pane holds Proposed action with its source row, Draft response (or Start for a new
// notice), the inline `notice_position` card whose radios only the reserved signer can use, and the
// authorization card. Hovering or focusing a payer lights it in all three panes. The browser does
// no arithmetic: every figure is the server's (QN-3).

export type NoticeTab = "analysis" | "response" | "activity";
export type AnalysisSegment = "notice_vs_return" | "information_returns" | "transcript";
const TABS: readonly NoticeTab[] = ["analysis", "response", "activity"];
const SEGMENTS: readonly AnalysisSegment[] = [
  "notice_vs_return",
  "information_returns",
  "transcript",
];

const PANE = "flex min-h-0 flex-col overflow-hidden rounded-pane bg-card shadow-e1";
const HEAD =
  "flex h-[46px] shrink-0 items-center justify-center gap-[6px] text-[14.5px] font-medium hairline-b";
const LIT = "bg-match-bg inset-ring-[1px] inset-ring-match-line";

export interface WorkspaceProps {
  noticeId: string;
  tab?: NoticeTab;
  onTab?: (tab: NoticeTab) => void;
  segment?: AnalysisSegment;
  onSegment?: (segment: AnalysisSegment) => void;
  onBack?: () => void;
  /** NOT-03 once the response is drafted. */
  onResponse?: () => void;
  /** N-04-T20: NOT-03's Approve… opens SHL-12. */
  onApproveResponse?: () => void;
  /** N-04-T20: SIG-02 d on the drafted envelope. */
  onEnvelope?: (envelopeId: string) => void;
  /** SHL-11 for the reserved signer (`?ov=decision:<cardId>`): the sheet records the decision. */
  onDecide?: (cardId: string, optionKey: string, rationale: string) => void;
  /** Hover state for d (the 1099 corrections row lit on open). */
  initialLit?: boolean;
}

function idempotency(): { "Idempotency-Key": string } {
  return { "Idempotency-Key": crypto.randomUUID() };
}

function Header({
  notice,
  onBack,
}: {
  notice: NoticeOut;
  onBack?: (() => void) | undefined;
}): JSX.Element {
  const fmt = useFormat();
  const r = notice.row;
  return (
    <div data-not02="subbar" className="flex h-[42px] shrink-0 items-center gap-[10px] px-[12px]">
      {onBack !== undefined && (
        <button type="button" className="text-[14px] text-ink-2" onClick={onBack}>
          {COPY.back}
        </button>
      )}
      <span className="flex flex-1 items-center justify-center gap-[8px]">
        <span className="text-[15px] font-medium">
          {COPY.title(r.notice_code, r.tax_year, r.client_name)}
        </span>
        <Pill variant="neutral" size="state" data-status={r.status}>
          {COPY.status[r.status] ?? r.status}
        </Pill>
        {r.respond_by !== null && r.respond_by_days !== null && (
          <Pill variant="amber" size="state">
            {COPY.respondBy(fmt.date(r.respond_by), r.respond_by_days)}
          </Pill>
        )}
      </span>
    </div>
  );
}

function Viewer({
  notice,
  docs,
  at,
}: {
  notice: NoticeOut;
  docs: readonly string[];
  at: number;
}): JSX.Element {
  const fmt = useFormat();
  const r = notice.row;
  const version = docs[at];
  return (
    <section data-not02="viewer" className={PANE}>
      <header className={HEAD}>
        <Icon name="file-text" size={14} />
        {COPY.viewer.title(
          r.agency_name,
          r.notice_code,
          notice.notice_date === null ? "" : fmt.date(notice.notice_date, { withYear: true }),
        )}
      </header>
      {docs.length > 1 && (
        <p
          data-not02="stack"
          className="flex h-[30px] items-center justify-center text-dense tabular-nums"
        >
          {`${String(at + 1)} `}
          <span className="pl-[3px] text-ink-2">{`/ ${String(docs.length)}`}</span>
        </p>
      )}
      <div className="min-h-0 flex-1 overflow-hidden bg-shell">
        {version !== undefined && (
          <ViewerPane target={{ versionId: version, matchId: null, anchor: null }} />
        )}
      </div>
    </section>
  );
}

function StatementRow({
  row,
  lit,
  running,
}: {
  row: AnalysisRowOut;
  lit: boolean;
  running: boolean;
}): JSX.Element {
  const total = row.key === "total_due";
  return (
    <div
      role="row"
      data-row={row.key}
      data-lit={lit ? "true" : undefined}
      className={cn(
        "grid h-[32px] grid-cols-[170px_90px_90px_80px] items-center text-[12.5px] tabular-nums hairline-b",
        total && "font-medium border-t-[0.5px] border-stroke",
        lit && LIT,
      )}
    >
      <span className="truncate px-[10px]">{row.label}</span>
      <Amount value={row.as_filed ?? ""} style="cents" className="pr-[8px] text-right" />
      {running ? (
        <span className="flex justify-end pr-[8px]">
          <Spinner label={COPY.analysis.running} />
        </span>
      ) : (
        <Amount value={row.irs ?? ""} style="cents" className="pr-[8px] text-right" />
      )}
      <span className="pr-[8px] text-right">
        {row.difference === null || row.difference === undefined || running
          ? ""
          : change(row.difference)}
      </span>
    </div>
  );
}

/** The Change column: the server's signed difference, "+" for an increase (display only). */
function change(v: string): string {
  const f = formatAmount(v, "cents");
  return f.tone === "pos" ? `+${f.text}` : f.text;
}

function InfoReturns({
  items,
  lit,
  onLight,
}: {
  items: readonly InformationReturnOut[];
  lit: string | null;
  onLight: (payer: string | null) => void;
}): JSX.Element {
  const missing = items.filter((i) => !i.on_return);
  const agree = items.filter((i) => i.on_return);
  return (
    <div
      data-not02="info-returns"
      className="flex flex-col rounded-[10px] bg-shell inset-shadow-hair"
    >
      <p className="px-[10px] pt-[8px] text-dense font-medium">{COPY.analysis.infoReturns}</p>
      {missing.map((i) => (
        <div
          key={`${i.form}:${i.payer_name}`}
          role="row"
          tabIndex={0}
          data-payer={i.payer_name}
          data-lit={lit === i.payer_name ? "true" : undefined}
          className={cn(
            "flex h-[36px] items-center gap-[6px] px-[10px] text-[12.5px]",
            lit === i.payer_name && LIT,
          )}
          onMouseEnter={() => {
            onLight(i.payer_name);
          }}
          onMouseLeave={() => {
            onLight(null);
          }}
          onFocus={() => {
            onLight(i.payer_name);
          }}
          onBlur={() => {
            onLight(null);
          }}
        >
          <span className="min-w-0 flex-1 truncate">
            {`${i.form} · ${i.payer_name} · `}
            <Amount value={i.amount} style="cents" />
            {i.issued_after_filing ? ` · ${COPY.analysis.issuedAfter}` : ""}
          </span>
          <Pill variant="red-tint" size="sm">
            {COPY.analysis.notOnReturn}
          </Pill>
        </div>
      ))}
      {agree.length > 0 && (
        <div className="flex h-[36px] items-center gap-[6px] px-[10px] text-[12.5px]">
          <span className="min-w-0 flex-1 truncate">
            {COPY.analysis.others(agree.length, agree.map((i) => i.form).join(", "))}
          </span>
          <Pill variant="green-tint" size="sm">
            {COPY.analysis.agree}
          </Pill>
        </div>
      )}
    </div>
  );
}

function Why({ analysis }: { analysis: AnalysisOut }): JSX.Element {
  const a = analysis.agent;
  return (
    <div
      data-not02="why"
      data-stage={a.stage}
      className="flex flex-col gap-[6px] rounded-[10px] bg-card p-[12px] shadow-e1"
    >
      <p className="flex items-center gap-[6px] text-[13.5px] font-medium">
        <span
          aria-hidden
          className="flex size-[15px] items-center justify-center rounded-full bg-green text-on-dark"
        >
          <Icon name="check" size={12} />
        </span>
        {COPY.analysis.why}
      </p>
      {a.stage === "off" || a.stage === "shadow" ? (
        <p className="text-[12.5px] text-ink-3">{COPY.analysis.off}</p>
      ) : a.stage === "refused" ? (
        <p role="note" className="text-[12.5px] text-ink-3">
          {a.refusal ?? ""}
        </p>
      ) : (
        <AgentText
          text={a.explanation ?? ""}
          className="text-[12.5px] leading-[1.55] text-ink-2"
        />
      )}
    </div>
  );
}

function AnalysisPane({
  analysis,
  segment,
  onSegment,
  lit,
  onLight,
}: {
  analysis: AnalysisOut;
  segment: AnalysisSegment;
  onSegment: (s: AnalysisSegment) => void;
  lit: string | null;
  onLight: (payer: string | null) => void;
}): JSX.Element {
  const running = analysis.status === "running";
  const C = COPY.analysis.columns;
  const litRow = lit === null ? null : "taxable_interest";
  return (
    <section data-not02="analysis" className={PANE}>
      <header className={HEAD}>
        {running && <span aria-hidden data-live className="size-[8px] rounded-full bg-green" />}
        {COPY.analysis.title}
      </header>
      <div className="flex flex-col gap-[10px] overflow-y-auto p-[10px]">
        <Segmented
          size="small"
          label={COPY.analysis.segmentsLabel}
          options={[...COPY.analysis.segments]}
          active={COPY.analysis.segments[SEGMENTS.indexOf(segment)] ?? COPY.analysis.segments[0]}
          onChange={(label) => {
            const i = COPY.analysis.segments.findIndex((s) => s === label);
            const next = SEGMENTS[i];
            if (next !== undefined) onSegment(next);
          }}
        />
        {segment === "information_returns" ? (
          <InfoReturns items={analysis.information_returns} lit={lit} onLight={onLight} />
        ) : (
          <div role="table" data-not02="statement" className="flex flex-col">
            <div
              role="row"
              className="grid h-[30px] grid-cols-[170px_90px_90px_80px] items-center bg-nested text-[11.5px] font-medium text-ink-3"
            >
              <span className="px-[10px]">{C.line}</span>
              <span className="pr-[8px] text-right">{C.asFiled}</span>
              <span className="pr-[8px] text-right">{C.irs}</span>
              <span className="pr-[8px] text-right">{C.change}</span>
            </div>
            {(segment === "transcript" ? analysis.transcript_rows : analysis.rows).map((r) => (
              <StatementRow key={r.key} row={r} lit={litRow === r.key} running={running} />
            ))}
            {segment === "transcript" && analysis.transcript_rows.length === 0 && (
              <p className="p-[10px] text-[12.5px] text-ink-3">{COPY.analysis.noTranscript}</p>
            )}
            {running && (
              <p data-not02="progress" className="p-[10px] text-[12.5px] text-ink-3">
                {analysis.progress_label ?? COPY.analysis.running}
              </p>
            )}
          </div>
        )}
        {segment === "notice_vs_return" && !running && (
          <InfoReturns items={analysis.information_returns} lit={lit} onLight={onLight} />
        )}
        {!running && <Why analysis={analysis} />}
      </div>
    </section>
  );
}

function DecisionInline({
  card,
  onDecide,
}: {
  card: DecisionCardOut;
  onDecide?: ((cardId: string, optionKey: string, rationale: string) => void) | undefined;
}): JSX.Element {
  const fmt = useFormat();
  const reserved = card.card.allowed_actions.includes("decision.decide") && card.decision === null;
  const [option, setOption] = useState<string | null>(card.recommendation?.option_key ?? null);
  const [rationale, setRationale] = useState("");
  const decided = card.decision;
  return (
    <section
      data-not02="decision"
      data-reserved={reserved ? "true" : "false"}
      className="flex flex-col gap-[8px] rounded-pane bg-card p-[12px] shadow-ask"
    >
      <p className="flex items-center gap-[6px] text-[14px] font-medium">
        <span
          aria-hidden
          className="flex size-[18px] items-center justify-center rounded-full bg-nested text-meta"
        >
          ?
        </span>
        {card.question}
      </p>
      {decided !== null ? (
        <p data-not02="decided" className="text-dense text-ink-2">
          {COPY.decision.decided(
            card.options.find((o) => o.key === decided.option_key)?.label ?? decided.option_key,
            decided.decided_by_name,
            fmt.time(decided.decided_at),
          )}
        </p>
      ) : (
        <>
          <div role="radiogroup" aria-label={card.question} className="flex flex-col gap-[6px]">
            {card.options.map((o) => (
              <label
                key={o.key}
                className={cn("flex items-start gap-[8px] text-dense", !reserved && "text-ink-3")}
              >
                <input
                  type="radio"
                  name={`position-${card.card.id}`}
                  value={o.key}
                  checked={option === o.key}
                  disabled={!reserved}
                  onChange={() => {
                    setOption(o.key);
                  }}
                  className="mt-[2px] size-[17px]"
                />
                <span className="flex flex-col">
                  <span>{o.label}</span>
                  {o.recommended && (
                    <span className="text-meta text-ink-2">
                      {COPY.decision.recommended}
                      {o.detail === null ? "" : ` · ${o.detail}`}
                    </span>
                  )}
                </span>
              </label>
            ))}
          </div>
          <textarea
            aria-label={COPY.decision.reasonField}
            placeholder={COPY.decision.reasonField}
            disabled={!reserved}
            value={rationale}
            onChange={(e) => {
              setRationale(e.target.value);
            }}
            className="h-[56px] rounded-nested bg-nested p-[8px] text-dense"
          />
          <Button
            variant="primary"
            size="md"
            disabled={!reserved || option === null || rationale.trim() === ""}
            onClick={() => {
              if (option !== null) onDecide?.(card.card.id, option, rationale);
            }}
          >
            {COPY.decision.decide}
          </Button>
          {!reserved && card.card.reserved_user_name !== null && (
            <p data-not02="reserved" className="text-[11.5px] text-ink-3">
              {COPY.decision.reserved(card.card.reserved_user_name)}
            </p>
          )}
        </>
      )}
    </section>
  );
}

function ActionPane({
  notice,
  analysis,
  card,
  lit,
  onLight,
  onResponse,
  onDecide,
}: {
  notice: NoticeOut;
  analysis: AnalysisOut;
  card: DecisionCardOut | undefined;
  lit: string | null;
  onLight: (payer: string | null) => void;
  onResponse?: (() => void) | undefined;
  onDecide?: ((cardId: string, optionKey: string, rationale: string) => void) | undefined;
}): JSX.Element {
  const qc = useQueryClient();
  const refresh = (): void => {
    void qc.invalidateQueries({
      queryKey: noticeOptions({ path: { notice_id: notice.row.id } }).queryKey,
    });
  };
  const draft = useMutation({
    ...responseDraftMutation(),
    onSuccess: () => {
      refresh();
      onResponse?.();
    },
  });
  const start = useMutation({ ...noticeStartMutation(), onSuccess: refresh });
  const running = analysis.status === "running";
  const source = analysis.sources[0];
  const isNew = notice.row.status === "received" || notice.row.status === "classified";
  const position = analysis.agent.recommended_position;
  const auth = notice.row.authorization;
  const payers = analysis.information_returns.filter((i) => !i.on_return).map((i) => i.payer_name);
  return (
    <section
      data-not02="action"
      className="flex min-h-0 flex-col gap-[10px] overflow-y-auto rounded-pane bg-shell p-[10px]"
    >
      {running ? (
        <Skeleton data-not02="proposed-skeleton" className="h-[160px] rounded-[12px]" />
      ) : (
        <div data-not02="proposed" className="flex flex-col rounded-[12px] bg-card shadow-e1">
          <p className="flex h-[46px] items-center px-[14px] text-[14.5px] font-medium">
            {COPY.action.proposed}
          </p>
          {position !== null && analysis.agent.stage === "live" && (
            <p className="px-[13px] pt-[19px] pb-[20px] text-center text-[14px] leading-[1.45]">
              {COPY.action.recommends(COPY.position[position] ?? position)}
            </p>
          )}
          {source !== undefined && (
            <div
              role="row"
              tabIndex={0}
              data-not02="source-row"
              data-lit={lit !== null ? "true" : undefined}
              className={cn(
                "flex h-[52px] items-center gap-[10px] px-[14px] hairline-t",
                lit !== null && LIT,
              )}
              onMouseEnter={() => {
                onLight(payers[0] ?? null);
              }}
              onMouseLeave={() => {
                onLight(null);
              }}
              onFocus={() => {
                onLight(payers[0] ?? null);
              }}
              onBlur={() => {
                onLight(null);
              }}
            >
              <Icon name="file-text" size={18} className="text-ink-3" />
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-[14px] font-medium">{source.label}</span>
                <span className="text-[12px] text-ink-3">
                  {COPY.action.documents(source.document_ids.length, source.citation_ids.length)}
                </span>
              </span>
              <button
                type="button"
                aria-label={COPY.action.jump(source.label)}
                className="flex size-[23px] items-center justify-center rounded-full bg-card shadow-[0_0_0_0.5px_var(--color-stroke)]"
                onClick={() => {
                  onLight(payers[0] ?? null);
                }}
              >
                <Icon name="arrow-right" size={12} />
              </button>
            </div>
          )}
        </div>
      )}
      {isNew && notice.allowed_actions.includes("notice.start") ? (
        <Button
          variant="primary"
          size="xl"
          className="w-full rounded-[22px]"
          disabled={start.isPending}
          onClick={() => {
            start.mutate({ path: { notice_id: notice.row.id }, headers: idempotency() });
          }}
        >
          {COPY.action.start}
        </Button>
      ) : (
        notice.allowed_actions.includes("notice_response.draft") && (
          <Button
            variant="primary"
            size="xl"
            className="w-full rounded-[22px]"
            disabled={draft.isPending || running}
            onClick={() => {
              draft.mutate({ path: { notice_id: notice.row.id }, headers: idempotency() });
            }}
          >
            {COPY.action.draft}
          </Button>
        )
      )}
      {card !== undefined && <DecisionInline card={card} onDecide={onDecide} />}
      <section
        data-not02="authorization"
        className={cn(
          "flex flex-col gap-[6px] rounded-[12px] p-[12px] shadow-e1",
          auth.on_file ? "bg-card" : "bg-red-tint",
        )}
      >
        <p className="text-dense font-medium">{COPY.authorization.title}</p>
        <p className="text-dense">{auth.on_file ? auth.label : COPY.authorization.none}</p>
        {auth.on_file && !auth.can_represent && (
          <div className="flex items-center gap-[8px] rounded-nested bg-amber-tint p-[8px] text-[12.5px] text-amber-ink">
            <span className="flex-1">{COPY.authorization.note}</span>
            <Button variant="ghost" size="xs">
              {COPY.authorization.draft2848}
            </Button>
          </div>
        )}
      </section>
    </section>
  );
}

function Activity({ noticeId }: { noticeId: string }): JSX.Element {
  const fmt = useFormat();
  const activity = useQuery(noticeActivityOptions({ path: { notice_id: noticeId } }));
  const items = activity.data?.items ?? [];
  return (
    <ol data-not02="activity" className="mx-auto flex w-[640px] flex-col gap-[2px] p-[16px]">
      {items.length === 0 && <li className="text-dense text-ink-3">{COPY.activity.empty}</li>}
      {items.map((i) => (
        <li
          key={`${i.event}:${i.at}`}
          data-event={i.event}
          className="flex h-[36px] items-center gap-[10px] text-dense hairline-b"
        >
          <span className="w-[120px] text-ink-3 tabular-nums">{fmt.date(i.at)}</span>
          <span className="flex-1">{i.label}</span>
          {i.actor_label !== null && <span className="text-ink-2">{i.actor_label}</span>}
        </li>
      ))}
    </ol>
  );
}

export function NoticeWorkspace({
  noticeId,
  tab: tabProp,
  onTab,
  segment: segmentProp,
  onSegment,
  onBack,
  onResponse,
  onApproveResponse,
  onEnvelope,
  onDecide,
  initialLit = false,
}: WorkspaceProps): JSX.Element {
  const on = useFlag("notices.workspace") === true;
  const notice = useQuery({ ...noticeOptions({ path: { notice_id: noticeId } }), enabled: on });
  const analysis = useQuery({
    ...analysisOptions({ path: { notice_id: noticeId } }),
    enabled: on,
    // The run is background work (DEC-2359): the spinner stops when a version lands.
    refetchInterval: (q) => (q.state.data?.status === "running" ? 3000 : false),
  });
  const cardId = analysis.data?.decision_card_id ?? "";
  const card = useDecisionCard(cardId);
  const [ownTab, setOwnTab] = useState<NoticeTab>(tabProp ?? "analysis");
  const [ownSegment, setOwnSegment] = useState<AnalysisSegment>(segmentProp ?? "notice_vs_return");
  const tab = tabProp ?? ownTab;
  const segment = segmentProp ?? ownSegment;
  const payers = (analysis.data?.information_returns ?? [])
    .filter((i) => !i.on_return)
    .map((i) => i.payer_name);
  const [lit, setLit] = useState<string | null>(initialLit ? (payers[0] ?? "lit") : null);
  const docs = lit === null ? [] : (analysis.data?.sources[0]?.document_ids ?? []);
  const at = 0;

  let state: ViewState = { kind: "ready" };
  if (!on) state = { kind: "flag-off", flag: "notices.workspace" };
  else if (notice.isError) {
    const status = (notice.error as { status?: number } | null)?.status;
    state =
      status === 404
        ? { kind: "restricted", reason: "walled" }
        : { kind: "error", retry: () => void notice.refetch() };
  } else if (notice.data === undefined || analysis.data === undefined) state = { kind: "loading" };

  return (
    <div data-screen="NOT-02" data-tab={tab} className="flex min-h-0 flex-1 flex-col">
      <ViewStateBody state={state} empty={{ title: COPY.states.empty }} noun="notice">
        {() =>
          notice.data === undefined || analysis.data === undefined ? null : (
            <>
              <Header notice={notice.data} onBack={onBack} />
              <div className="flex h-[44px] shrink-0 items-center justify-center">
                <Segmented
                  label={COPY.tabsLabel}
                  options={[...COPY.tabs]}
                  active={COPY.tabs[TABS.indexOf(tab)] ?? COPY.tabs[0]}
                  onChange={(label) => {
                    const next = TABS[COPY.tabs.findIndex((t) => t === label)];
                    if (next === undefined) return;
                    setOwnTab(next);
                    onTab?.(next);
                  }}
                />
              </div>
              {tab === "response" ? (
                <ResponseEditor
                  noticeId={noticeId}
                  notice={notice.data}
                  {...(onApproveResponse === undefined ? {} : { onApprove: onApproveResponse })}
                  {...(onEnvelope === undefined ? {} : { onEnvelope })}
                />
              ) : tab === "activity" ? (
                <Activity noticeId={noticeId} />
              ) : (
                <div className="grid min-h-0 flex-1 grid-cols-[452px_452px_452px] gap-[10px] px-[12px] pt-[10px] pb-[12px]">
                  <Viewer
                    notice={notice.data}
                    docs={
                      docs.length > 0
                        ? docs
                        : (analysis.data.sources[0]?.document_ids.slice(0, 1) ?? [])
                    }
                    at={at}
                  />
                  <AnalysisPane
                    analysis={analysis.data}
                    segment={segment}
                    onSegment={(s) => {
                      setOwnSegment(s);
                      onSegment?.(s);
                    }}
                    lit={lit}
                    onLight={setLit}
                  />
                  <ActionPane
                    notice={notice.data}
                    analysis={analysis.data}
                    card={card.data}
                    lit={lit}
                    onLight={setLit}
                    onResponse={onResponse}
                    onDecide={onDecide}
                  />
                </div>
              )}
            </>
          )
        }
      </ViewStateBody>
    </div>
  );
}
