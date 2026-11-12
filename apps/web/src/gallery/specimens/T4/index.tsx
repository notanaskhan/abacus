import {
  AgentDetail,
  AppShell,
  ChatHeader,
  ChatThread,
  ContextChips,
  type ContextItem,
  type ContextKind,
  ContextPicker,
  EmptySession,
  type QuestionAnswer,
  QuestionCard,
  type QuestionPayload,
  SessionList,
  type SessionRow,
  Spinner,
  type ThreadItem,
  WorkbenchLayout,
  type WorkbenchTab,
} from "@abacus/ui";
import { T5Board } from "@abacus/ui/specimens";
import { type JSX, useEffect, useMemo, useState } from "react";
import { useSession } from "../../../app-core/session";
import { RunStore, ScriptedRunSource, useRunStore } from "../../../domain/agents";
import {
  QUESTION,
  RUN_ID,
  SESSION_ID,
  SUGGESTED_PROMPTS,
  type Tpl04Frame,
  sessionRows,
  threadItems,
  tpl04Script,
} from "../../../fixtures/seed/tpl04-sessions";
import type { FixtureParams } from "../../fixture-mode";
import { specimenToolbar } from "../firm-toolbar";
import { COPY, T4A_PROMPTS, T4F_AGENTS, T4F_DETAIL } from "./copy";

// T4 Workbench chat template (T4a–f) and the TPL-04 specimen (a–e) in the gallery (F-07-T08;
// SPEC-652 AC-1 to AC-5; handoff T4, TPL-04). Hannah Leclerc at E0, Mon Sep 14, 2026, 9:24 AM CT.
// Both render the scripted session from the Brightwater Hale seed (F-07-T04): the TPL-04 frames
// are its own; the T4 states map onto it (a empty → TPL-04b, b running → c, c awaiting answer →
// a, d complete → d, e failed → e), since T4's parity is Tier D (geometry) and the seed wins over
// kit sample content. T4f is WB-06 with the handoff's agent detail. The running frame plays a
// `ScriptedRunSource`; `?static=1` freezes it on the running page so a capture is stable.
// Every intent (Bug → run-trace, Create Agent… → edit-agent:new, Save to Files, answers, sends,
// context, retry, run) lands in the gallery's action log under the artboard; nothing fetches.
// The Agents and Connect tabs mount F-05's T5 specimens. Registered for
// /components/screens/T4?st=a…f and /components/screens/TPL-04?st=a…e.

export const T4_STATES = ["a", "b", "c", "d", "e", "f"] as const;
export type T4State = (typeof T4_STATES)[number];
export const TPL04_STATES: readonly Tpl04Frame[] = ["a", "b", "c", "d", "e"];

const T4_FRAME: Readonly<Record<Exclude<T4State, "f">, Tpl04Frame>> = {
  a: "b",
  b: "c",
  c: "a",
  d: "d",
  e: "e",
};

/** The gallery's action log: each intent the artboard emits, in order. */
function useIntentLog(): [readonly string[], (intent: string) => void] {
  const [log, setLog] = useState<string[]>([]);
  return [log, (intent) => setLog((l) => [...l, intent])];
}

function IntentLog({ log }: { log: readonly string[] }): JSX.Element {
  return (
    <ol
      data-intent-log
      aria-label={COPY.intentLog}
      aria-live="polite"
      className="mt-[8px] flex flex-col gap-[2px] font-mono text-[11.5px] text-ink-3"
    >
      {log.map((intent, i) => (
        <li key={`${String(i)}-${intent}`}>{intent}</li>
      ))}
    </ol>
  );
}

function rowsOf(frame: Tpl04Frame): SessionRow[] {
  return sessionRows(frame).map((r) => ({ ...r }));
}

function questionOf(items: readonly ThreadItem[]): QuestionPayload | null {
  const asked = [...items].reverse().find((i) => i.kind === "question");
  const answered = items.some((i) => i.kind === "answer");
  return asked && !answered ? (QUESTION as unknown as QuestionPayload) : null;
}

/** The running frame's run: played, or frozen on its running page under `?static=1`. */
function useScriptedRun(frame: Tpl04Frame, still: boolean): Tpl04Frame {
  const store = useMemo(() => new RunStore(), []);
  useEffect(() => {
    if (frame !== "c") return undefined;
    const script = still ? tpl04Script().slice(0, 1) : tpl04Script();
    return store.connect(new ScriptedRunSource(script, { freeze: still }));
  }, [frame, still, store]);
  const feed = useRunStore(store);
  return frame === "c" && feed.run?.state === "succeeded" ? "d" : frame;
}

function SessionsFrame({
  initial,
  still,
  source,
  log,
}: {
  initial: Tpl04Frame;
  still: boolean;
  /** Whose words the empty session shows: T4a's handoff prompts or TPL-04b's seed prompts. */
  source: "t4" | "tpl04";
  log: (intent: string) => void;
}): JSX.Element {
  const [tab, setTab] = useState<WorkbenchTab>("sessions");
  const [frame, setFrame] = useState<Tpl04Frame>(initial);
  const shown = useScriptedRun(frame, still);
  const [draft, setDraft] = useState<{ text: string; nonce: number } | null>(null);
  const [attached, setAttached] = useState<ContextItem[]>([]);
  const [pickerKind, setPickerKind] = useState<ContextKind | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const items = threadItems(shown) as unknown as ThreadItem[];
  const question = questionOf(items);
  const empty = shown === "b";
  const rows = rowsOf(shown);
  const prompts = source === "tpl04" ? SUGGESTED_PROMPTS : null;

  if (tab !== "sessions") {
    return <T5Board id={tab === "agents" ? "tpl-05a" : "t5e"} />;
  }

  const answer = (a: QuestionAnswer) => {
    log("skipped" in a ? `answer:${a.question_id}:skipped` : `answer:${a.question_id}:${a.key}`);
    if (!("skipped" in a) && a.step < (QUESTION.m ?? 1)) return;
    setFrame("c");
  };

  return (
    <WorkbenchLayout
      tab={tab}
      onTab={(t) => {
        log(`tab:${t}`);
        setTab(t);
      }}
      list={
        <SessionList
          rows={rows}
          selectedId={SESSION_ID}
          still={still}
          onSelect={(id) => log(`select:${id}`)}
          onNew={() => {
            log("new-session");
            setFrame("b");
          }}
          onFilter={() => log("filter")}
        />
      }
      chat={
        <div className="flex min-h-0 flex-1 flex-col">
          <ChatHeader
            title={empty ? "New session" : "TY2025 season progress by office"}
            owner={{ kind: "human", name: "Hannah Leclerc" }}
            live={!empty}
            still={still}
            contextCount={attached.length}
            onContext={() => {
              log("context");
              setPickerKind(null);
              setPickerOpen(true);
            }}
            onOpenTrace={() => log(`run-trace:${RUN_ID}`)}
            onRename={() => log("rename")}
            onDelete={() => log("delete")}
            onCreateAgent={() => log("edit-agent:new")}
          />
          <ChatThread
            items={items}
            still={still}
            draft={draft}
            empty={
              <EmptySession
                prompts={
                  prompts
                    ? prompts.map((title, i) => ({ id: `tpl04b-${String(i)}`, title }))
                    : T4A_PROMPTS
                }
                onPick={(text) => {
                  log("prompt");
                  setDraft((d) => ({ text, nonce: (d?.nonce ?? 0) + 1 }));
                }}
              />
            }
            above={
              question ? (
                <QuestionCard
                  question={question}
                  onAnswer={answer}
                  onSomethingElse={() => log("answer:other")}
                />
              ) : empty ? (
                <ContextPicker
                  trigger={<span />}
                  open={pickerOpen}
                  onOpenChange={setPickerOpen}
                  kind={pickerKind}
                  items={{}}
                  attached={new Set(attached.map((a) => a.id))}
                  onAttach={(item) => {
                    log(`attach:${item.id}`);
                    setAttached((a) => [...a, item]);
                  }}
                  onDetach={(item) => {
                    log(`detach:${item.id}`);
                    setAttached((a) => a.filter((x) => x.id !== item.id));
                  }}
                />
              ) : null
            }
            onRetryStep={(step) => log(`retry:${step}`)}
            onOpenRun={(run) => log(`open-run:${run}`)}
            onArtifact={(id, intent) =>
              log(intent === "save" ? `save-to-files:${id}` : `artifact:${intent}:${id}`)
            }
            onSend={(body) => log(`send:${String(body.length)}`)}
          />
          {empty ? (
            <div className="mx-[16px] mb-[8px]">
              <ContextChips
                attached={attached}
                onAdd={(kind) => {
                  log(`context:${kind}`);
                  setPickerKind(kind);
                  setPickerOpen(true);
                }}
                onRemove={(item) => setAttached((a) => a.filter((x) => x.id !== item.id))}
              />
            </div>
          ) : null}
        </div>
      }
    />
  );
}

function AgentListPane({ log }: { log: (intent: string) => void }): JSX.Element {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div style={{ height: 46 }} className="flex items-center justify-center">
        <span className="text-[14.5px] font-medium">{COPY.agentsTitle}</span>
      </div>
      <ul className="flex flex-col">
        {T4F_AGENTS.map((agent, i) => (
          <li key={agent.id}>
            <button
              type="button"
              data-agent={agent.id}
              aria-current={i === 0 ? "true" : undefined}
              onClick={() => log(`select-agent:${agent.id}`)}
              className={`flex h-[48px] w-full items-center gap-[10px] px-[12px] text-left ${
                i === 0 ? "bg-sel-bg" : ""
              }`}
            >
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-[13px]">{agent.name}</span>
                <span className="truncate text-[11.5px] text-ink-3">{agent.meta}</span>
              </span>
              {agent.dot === "amber" ? (
                <span aria-hidden="true" className="size-[8px] rounded-pill bg-amber" />
              ) : agent.dot === "spin" ? (
                <Spinner size={12} label="Running" showLabel={false} still />
              ) : null}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function AgentFrame({ log }: { log: (intent: string) => void }): JSX.Element {
  return (
    <WorkbenchLayout
      tab="agents"
      variant="agent_detail"
      onTab={(t) => log(`tab:${t}`)}
      list={<AgentListPane log={log} />}
      chat={
        <AgentDetail
          name={T4F_DETAIL.name}
          provenance={T4F_DETAIL.provenance}
          icon="panels-top-left"
          purpose={T4F_DETAIL.purpose}
          meta={T4F_DETAIL.meta}
          facts={T4F_DETAIL.facts}
          runs={T4F_DETAIL.runs}
          onEdit={() => log("edit-agent:soc1")}
          onArchive={() => log("archive-agent:soc1")}
          onRun={() => log("run-agent:soc1")}
          onOpenRun={(id) => log(`run-trace:${id}`)}
        />
      }
    />
  );
}

function Window({ children, firm }: { children: JSX.Element; firm: string }): JSX.Element {
  return (
    <AppShell frame height={860} toolbar={specimenToolbar(firm, "Workbench")}>
      {children}
    </AppShell>
  );
}

export function T4Artboard({ params }: { params: FixtureParams }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const state = (T4_STATES as readonly string[]).includes(params.st ?? "")
    ? (params.st as T4State)
    : "a";
  const [log, push] = useIntentLog();
  const still = params.static === true;
  return (
    <div data-specimen="T4" data-state={state} data-artboard={state}>
      <Window firm={firm}>
        {state === "f" ? (
          <AgentFrame log={push} />
        ) : (
          <SessionsFrame
            key={state}
            initial={T4_FRAME[state]}
            still={still}
            source="t4"
            log={push}
          />
        )}
      </Window>
      <IntentLog log={log} />
    </div>
  );
}

export function Tpl04Artboard({ params }: { params: FixtureParams }): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const frame = (TPL04_STATES as readonly string[]).includes(params.st ?? "")
    ? (params.st as Tpl04Frame)
    : "a";
  const [log, push] = useIntentLog();
  return (
    <div data-specimen="TPL-04" data-state={frame} data-artboard={frame}>
      <Window firm={firm}>
        <SessionsFrame
          key={frame}
          initial={frame}
          still={params.static === true}
          source="tpl04"
          log={push}
        />
      </Window>
      <IntentLog log={log} />
    </div>
  );
}
