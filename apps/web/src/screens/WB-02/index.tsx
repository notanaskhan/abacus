// WB-02 New session & context picker (W-02-T08 skeleton, W-02-T16; docs/screens/WB-02.md; SPEC-653
// AC-C1–C5, AC-A1–A5). a: the blank, firm-wide session ("Firm-wide · read-only") with four
// suggested prompts that fill the composer and never send (f, AC-C2). b: the O1 picker with three
// tabs, search, check discs, "n selected" and "Only records you can open are listed." (the server
// lists only what the viewer can open; INV-3). c: Add to session cascades skeleton cards; d: they
// resolve to code's summary lines with chips that remove (AC-C4, AC-C5). e: the typed question's
// grounded answer: agent text only through AgentBlocks, every source a citation that opens SHL-08
// with its region lit, the Internal Control link to AUD-09, and the code's "Nothing was written."
import type {
  ContextItemOut,
  ContextItemsOut,
  ContextOptionOut,
  ContextOptionsOut,
  SessionSnapshotOut,
} from "@abacus/api-client";
import {
  type AgentBlocksPayload,
  AgentBlocks,
  type BlockFact,
  Button,
  type CitationView,
  EmptySession,
  Icon,
  Popover,
  SearchField,
  Segmented,
  SkeletonRows,
  WorkbenchLayout,
} from "@abacus/ui";
import { type JSX, type ReactNode, useState } from "react";
import { useOpenOverlay } from "../../app-core/open";
import { VIEWER_OVERLAY, sourceViewerArgs } from "../../app-core/overlays";
import {
  useAttachContext,
  useContextOptions,
  useCreateSession,
  usePostMessage,
  useRemoveContext,
  useWorkbenchSession,
} from "../../domain/workbench";
import { COPY, SUGGESTED_PROMPTS } from "./copy";

export type ContextTab = ContextOptionsOut["tab"];
const TABS: readonly ContextTab[] = ["client_record", "documents", "workpapers"];

export interface AnswerSource {
  id: string;
  n: number;
  title: string;
  loc: string;
  evidenceVersionId: string | null;
  matchId: string | null;
}

export interface GroundedAnswer {
  blocks: AgentBlocksPayload;
  facts: Readonly<Record<string, BlockFact>>;
  cites: Readonly<Record<string, CitationView>>;
  sources: readonly AnswerSource[];
  /** The turn wrote nothing: the code's line follows the answer (AC-A3). */
  nothingWritten: boolean;
  /** The answer points to a control conclusion reserved to a role (AC-A2). */
  controlLink: boolean;
  /** The audit the answer's `entity_ref` names (record type `audit`): AUD-09's `auditId`. */
  controlAuditId: string | null;
  /** The question the person typed. */
  question: string;
}

export interface WB02ViewProps {
  list: ReactNode;
  context?: ContextItemsOut | undefined;
  /** c: refs being added; each draws a skeleton card until it resolves. */
  adding?: readonly string[];
  pickerOpen?: boolean;
  tab?: ContextTab;
  options?: ContextOptionsOut | undefined;
  picked?: ReadonlySet<string>;
  pickerQuery?: string;
  draft?: string;
  answer?: GroundedAnswer | undefined;
  onDraft?: (text: string) => void;
  onPickerOpen?: (open: boolean) => void;
  onTab?: (tab: ContextTab) => void;
  onPickerQuery?: (q: string) => void;
  onToggle?: (option: ContextOptionOut) => void;
  onAdd?: () => void;
  onRemove?: (item: ContextItemOut) => void;
  onSend?: (text: string) => void;
  onOpenSource?: (source: AnswerSource) => void;
  onOpenControl?: (auditId: string | null) => void;
}

function ContextStack({
  context,
  adding,
  onRemove,
}: {
  context: ContextItemsOut | undefined;
  adding: readonly string[];
  onRemove?: ((item: ContextItemOut) => void) | undefined;
}): JSX.Element | null {
  const items = context?.items ?? [];
  if (items.length === 0 && adding.length === 0) return null;
  return (
    <div data-wb02="context" className="flex flex-col gap-[8px] px-[16px] pt-[12px]">
      {items.map((item) => (
        <section
          key={item.id}
          aria-label={item.card_title}
          className="rounded-[10px] bg-card p-[10px] shadow-e1"
        >
          <p className="text-[11px] font-medium uppercase tracking-[0.04em] text-ink-3">
            {item.card_title}
          </p>
          {item.summary_lines.map((line) => (
            <p key={line} className="text-body text-ink">
              {line}
            </p>
          ))}
        </section>
      ))}
      {adding.map((ref) => (
        <section
          key={ref}
          aria-busy="true"
          aria-label={COPY.loadingCard}
          className="rounded-[10px] bg-card p-[10px] shadow-e1"
        >
          <SkeletonRows type="card" immediate label={COPY.loadingCard} />
        </section>
      ))}
      {items.length > 0 ? (
        <div className="flex flex-wrap gap-[6px]">
          {items.map((item) => (
            <span
              key={item.id}
              className="inline-flex h-[24px] items-center gap-[4px] rounded-pill bg-nested px-[8px] text-[12px] text-ink"
            >
              {item.chip_label}
              {onRemove === undefined ? null : (
                <button
                  type="button"
                  aria-label={COPY.remove(item.chip_label)}
                  onClick={() => {
                    onRemove(item);
                  }}
                >
                  <Icon name="x" size={12} />
                </button>
              )}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function Picker({
  open,
  tab,
  options,
  picked,
  query,
  onOpen,
  onTab,
  onQuery,
  onToggle,
  onAdd,
}: {
  open: boolean;
  tab: ContextTab;
  options: ContextOptionsOut | undefined;
  picked: ReadonlySet<string>;
  query: string;
  onOpen?: ((open: boolean) => void) | undefined;
  onTab?: ((tab: ContextTab) => void) | undefined;
  onQuery?: ((q: string) => void) | undefined;
  onToggle?: ((o: ContextOptionOut) => void) | undefined;
  onAdd?: (() => void) | undefined;
}): JSX.Element {
  const rows = options?.items ?? [];
  return (
    <Popover
      open={open}
      onOpenChange={(o) => onOpen?.(o)}
      label={COPY.picker}
      width={380}
      trigger={
        <Button variant="ghost" size="sm">
          {COPY.addContext}
        </Button>
      }
    >
      <div className="flex flex-col gap-[8px]">
        <Segmented
          size="small"
          label={COPY.picker}
          options={TABS.map((t) => COPY.tabs[t])}
          active={COPY.tabs[tab]}
          onChange={(label) => {
            const next = TABS.find((t) => COPY.tabs[t] === label);
            if (next !== undefined) onTab?.(next);
          }}
        />
        <SearchField label={COPY.pickerSearch} value={query} onChange={(v) => onQuery?.(v)} />
        <ul aria-label={COPY.tabs[tab]} className="flex max-h-[260px] flex-col overflow-y-auto">
          {rows.map((o) => {
            const on = picked.has(o.ref_id) || o.attached === true;
            return (
              <li key={o.ref_id}>
                <button
                  type="button"
                  role="checkbox"
                  aria-checked={on}
                  onClick={() => onToggle?.(o)}
                  className="flex w-full items-center gap-[8px] rounded-[6px] px-[8px] py-[6px] text-left hover:bg-nested"
                >
                  <span
                    aria-hidden
                    className={`flex size-[16px] items-center justify-center rounded-pill border ${on ? "border-green bg-green text-card" : "border-hair"}`}
                  >
                    {on ? <Icon name="check" size={12} /> : null}
                  </span>
                  <span className="flex min-w-0 flex-col">
                    <span className="truncate text-body text-ink">{o.title}</span>
                    {o.detail ? (
                      <span className="truncate text-[11.5px] text-ink-3">{o.detail}</span>
                    ) : null}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
        <div className="flex items-center gap-[8px] border-t border-hair pt-[8px]">
          <span className="flex-1 text-[11.5px] text-ink-3">{COPY.pickerFooter}</span>
          <span className="text-[12px] text-ink-2">{COPY.selected(picked.size)}</span>
          <Button variant="primary" size="sm" disabled={picked.size === 0} onClick={onAdd}>
            {COPY.add}
          </Button>
        </div>
      </div>
    </Popover>
  );
}

function Answer({
  answer,
  onOpenSource,
  onOpenControl,
}: {
  answer: GroundedAnswer;
  onOpenSource?: ((s: AnswerSource) => void) | undefined;
  onOpenControl?: ((auditId: string | null) => void) | undefined;
}): JSX.Element {
  return (
    <div data-wb02="answer" className="flex flex-col gap-[10px] px-[16px] py-[12px]">
      <p className="self-end rounded-[12px] bg-nested px-[12px] py-[8px] text-body text-ink">
        {answer.question}
      </p>
      <div className="rounded-[12px] bg-card p-[12px] shadow-e1">
        <AgentBlocks blocks={answer.blocks} facts={answer.facts} cites={answer.cites} />
        {answer.sources.length > 0 ? (
          <div className="mt-[8px] flex flex-wrap items-center gap-[6px]">
            <span className="text-[11.5px] text-ink-3">{COPY.sources}</span>
            {answer.sources.map((s) => (
              <button
                key={s.id}
                type="button"
                data-cite={s.n}
                onClick={() => onOpenSource?.(s)}
                className="inline-flex h-[24px] items-center gap-[4px] rounded-pill bg-nested px-[8px] text-[12px] text-ink hover:bg-match-bg hover:text-match-ink"
              >
                [{s.n}] {s.title} · {s.loc}
              </button>
            ))}
          </div>
        ) : null}
        {answer.controlLink ? (
          <button
            type="button"
            onClick={() => onOpenControl?.(answer.controlAuditId)}
            className="mt-[6px] text-body text-ink underline-offset-2 hover:underline"
          >
            {COPY.controlLink}
          </button>
        ) : null}
      </div>
      {answer.nothingWritten ? (
        <p className="text-[11.5px] text-ink-3">{COPY.readOnlyLine}</p>
      ) : null}
    </div>
  );
}

export function WB02View({
  list,
  context,
  adding = [],
  pickerOpen = false,
  tab = "client_record",
  options,
  picked = new Set<string>(),
  pickerQuery = "",
  draft = "",
  answer,
  onDraft,
  onPickerOpen,
  onTab,
  onPickerQuery,
  onToggle,
  onAdd,
  onRemove,
  onSend,
  onOpenSource,
  onOpenControl,
}: WB02ViewProps): JSX.Element {
  const firmWide = context === undefined || context.firm_wide || context.items.length === 0;
  const empty = answer === undefined && (context?.items.length ?? 0) === 0 && adding.length === 0;
  return (
    <WorkbenchLayout
      tab="sessions"
      list={list}
      chat={
        <div data-screen="WB-02" className="flex min-h-0 flex-1 flex-col">
          <div className="flex h-[46px] flex-none items-center gap-[8px] px-[16px]">
            <span className="flex-1 text-[14.5px] font-medium text-ink">{COPY.newSession}</span>
            {firmWide ? (
              <span
                data-chip="firm-wide"
                className="inline-flex h-[24px] items-center rounded-pill bg-nested px-[8px] text-[12px] text-ink-2"
              >
                {COPY.firmWide}
              </span>
            ) : null}
            <Picker
              open={pickerOpen}
              tab={tab}
              options={options}
              picked={picked}
              query={pickerQuery}
              onOpen={onPickerOpen}
              onTab={onTab}
              onQuery={onPickerQuery}
              onToggle={onToggle}
              onAdd={onAdd}
            />
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            {empty ? (
              <EmptySession
                title={COPY.title}
                body={COPY.body}
                prompts={SUGGESTED_PROMPTS}
                onPick={(text) => onDraft?.(text)}
              />
            ) : null}
            <ContextStack context={context} adding={adding} onRemove={onRemove} />
            {answer !== undefined ? (
              <Answer answer={answer} onOpenSource={onOpenSource} onOpenControl={onOpenControl} />
            ) : null}
          </div>
          <form
            className="flex h-[50px] flex-none items-center gap-[8px] border-t border-hair px-[12px]"
            onSubmit={(e) => {
              e.preventDefault();
              if (draft.trim() !== "") onSend?.(draft.trim());
            }}
          >
            <input
              aria-label={COPY.composer}
              value={draft}
              onChange={(e) => onDraft?.(e.target.value)}
              className="h-[34px] flex-1 rounded-[8px] bg-card px-[10px] text-body shadow-e1"
            />
            <Button type="submit" variant="primary" size="sm" disabled={draft.trim() === ""}>
              {COPY.send}
            </Button>
          </form>
        </div>
      }
    />
  );
}

// --- the route's screen: state and the generated client -----------------------------------------

type Item = SessionSnapshotOut["items"][number];

function text(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : typeof v === "number" ? String(v) : fallback;
}

function record(v: unknown): Record<string, unknown> {
  return typeof v === "object" && v !== null ? (v as Record<string, unknown>) : {};
}

/** The first audit an answer's blocks name (`entity_ref` with record type `audit`). */
function auditOf(parts: unknown): string | null {
  if (!Array.isArray(parts)) return null;
  for (const part of parts as unknown[]) {
    const r = record(part);
    if (r["kind"] === "entity_ref" && r["record_type"] === "audit") {
      return typeof r["record_id"] === "string" ? r["record_id"] : null;
    }
  }
  return null;
}

/** e: the newest question and its answer from the session's items (C6 v2), as stored: the blocks
 * the verifier kept, their sources, and whether the turn's code line follows. */
export function answerOf(items: readonly Item[] | undefined): GroundedAnswer | undefined {
  const list = items ?? [];
  const at = list.map((i) => i.kind).lastIndexOf("agent_blocks");
  if (at < 0) return undefined;
  const item = list[at];
  const asked = list
    .slice(0, at)
    .reverse()
    .find((i) => i.kind === "user_message");
  const payload = record(item?.payload);
  const blocks = record(payload["blocks"]);
  if (!Array.isArray(blocks["parts"])) return undefined;
  const raw = Array.isArray(payload["citations"]) ? (payload["citations"] as unknown[]) : [];
  const sources: AnswerSource[] = raw.map((c, i) => {
    const r = record(c);
    return {
      id: text(r["id"], String(i)),
      n: Number(r["n"] ?? i + 1),
      title: text(r["title"]),
      loc: text(r["loc"]),
      evidenceVersionId:
        typeof r["evidence_version_id"] === "string" ? r["evidence_version_id"] : null,
      matchId: typeof r["match_id"] === "string" ? r["match_id"] : null,
    };
  });
  const after = list.slice(at + 1);
  return {
    blocks: blocks as unknown as AgentBlocksPayload,
    facts: record(payload["facts"]) as Readonly<Record<string, BlockFact>>,
    cites: Object.fromEntries(
      sources.map((s) => [s.id, { n: s.n, title: s.title, quote: "", loc: s.loc, match: null }]),
    ) as unknown as Readonly<Record<string, CitationView>>,
    sources,
    nothingWritten: after.some(
      (i) => i.kind === "notice" && record(i.payload)["code"] === "nothing_written",
    ),
    controlLink:
      auditOf(blocks["parts"]) !== null ||
      (Array.isArray(payload["links"]) && (payload["links"] as unknown[]).length > 0),
    controlAuditId: auditOf(blocks["parts"]),
    question: text(record(asked?.payload)["body"]),
  };
}

export interface WB02Props {
  /** The session list beside the thread (WB-01's, with the new row on top). */
  list: ReactNode;
  /** A suggested prompt's text goes to the composer; nothing is sent. */
  onDraft: (text: string) => void;
  /** AUD-09: the Internal Control link in an answer. */
  onOpenControl?: (auditId: string | null) => void;
}

export function WB02({ list, onDraft, onOpenControl }: WB02Props): JSX.Element {
  const [draft, setDraft] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [tab, setTab] = useState<ContextTab>("client_record");
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState<ReadonlyMap<string, ContextOptionOut>>(new Map());
  const [adding, setAdding] = useState<readonly string[]>([]);
  const [context, setContext] = useState<ContextItemsOut | undefined>(undefined);
  const create = useCreateSession();
  const attach = useAttachContext();
  const detach = useRemoveContext();
  const post = usePostMessage();
  const options = useContextOptions(tab, query, sessionId);
  const snapshot = useWorkbenchSession(sessionId);
  const openOverlay = useOpenOverlay();
  const ensure = async (): Promise<string> => {
    if (sessionId !== null) return sessionId;
    const made = await create.create();
    setSessionId(made.id);
    return made.id;
  };
  return (
    <WB02View
      list={list}
      context={context}
      adding={adding}
      pickerOpen={pickerOpen}
      tab={tab}
      options={options.data}
      picked={new Set(picked.keys())}
      pickerQuery={query}
      draft={draft}
      answer={answerOf(snapshot.data?.items)}
      onDraft={(text) => {
        setDraft(text);
        onDraft(text);
      }}
      onPickerOpen={setPickerOpen}
      onTab={setTab}
      onPickerQuery={setQuery}
      onToggle={(o) => {
        const next = new Map(picked);
        if (next.has(o.ref_id)) next.delete(o.ref_id);
        else next.set(o.ref_id, o);
        setPicked(next);
      }}
      onAdd={() => {
        const refs = [...picked.values()];
        setPickerOpen(false);
        setAdding(refs.map((r) => r.ref_id));
        void (async () => {
          const id = await ensure();
          const done = await attach.attach(
            id,
            refs.map((r) => ({ kind: r.kind, ref_id: r.ref_id })),
          );
          setContext(done);
          setAdding([]);
          setPicked(new Map());
        })();
      }}
      onRemove={(item) => {
        if (sessionId !== null) void detach.detach(sessionId, item.id).then(setContext);
      }}
      onSend={(text) => {
        setDraft("");
        void ensure().then((id) => post.post(id, text));
      }}
      onOpenSource={(s) => {
        if (s.evidenceVersionId !== null) {
          openOverlay({
            key: VIEWER_OVERLAY,
            args: sourceViewerArgs({ evidenceVersionId: s.evidenceVersionId, matchId: s.matchId }),
          });
        }
      }}
      {...(onOpenControl === undefined ? {} : { onOpenControl })}
    />
  );
}
