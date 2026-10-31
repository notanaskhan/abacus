import type {
  AbacusModulesMethodologyContractStepOut as StepOut,
  GuidanceBlockOut,
  ProgramOut,
} from "@abacus/api-client";
import { exportVersion } from "@abacus/api-client";
import {
  addStepMutation,
  agentRunOptions,
  editStepMutation,
  getVersionOptions,
  listCitationsOptions,
  listTemplatesOptions,
  programOptions,
  programQueryKey,
  programStepsOptions,
  programStepsQueryKey,
  removeStepMutation,
  submitVersionMutation,
  versionProgramsOptions,
} from "@abacus/api-client/query";
import {
  AgentText,
  Button,
  CitationPopover,
  DASH,
  EmptyState,
  GroupBand,
  Icon,
  OverviewCard,
  Pill,
  Popover,
  RailRow,
  RecordCockpit,
  RecordHeader,
  Segmented,
  StatusDisc,
  Tooltip,
  type ToolbarProps,
  type ViewState,
  date as formatDate,
  time,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type ReactNode, useState } from "react";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { COPY } from "./copy";

// KNW-03 · Program editor (K-01-T13; K-01 §3.4; KNW-03 handoff + R2) on T2 RecordCockpit: the record
// bar (‹ Knowledge, the template, its version and Published pill), the rail (overview card, Change
// log, the version's programs), the steps table (# · Step · Assertions · Standard · PBC link ·
// Level · Rules · Skill · Lock) under the Steps / Guidance / PBC links / Rules / Change log
// segments, and the Guidance dock with where the lit step is cited (C4). Scenarios a (arrived from
// a citation: `?step=4&from=citation` lights the row), b (the SHL-07 popover on that step) and e
// (the Change log: v2 → v3 computed here by comparing the two versions' steps). "Open in Excel"
// downloads K-01-T12's export. Editing (c), tailoring (d) and Fix in Knowledge (f) are later rows:
// Edit and + Step are drawn disabled only where planned screens are.
//
// K-01-T15 adds c, d and f. c: a draft (status draft) opens in edit mode for its drafter: the
// optional steps' text edits in place (If-Match row_version), + Step adds a row, removal is per
// optional step, mandatory steps stay locked with the QM-owner tooltip, and the banner offers
// Submit for approval…. d: A-04's tailoring (fixture-only until its read lands) adds the
// engagement chip and each tailored step's tag; trash stays disabled. f: `from=run` lights the
// step and quotes the run's error through AgentText; Retry waits for P-09.

export type Knw03Segment = "steps" | "guidance" | "pbc" | "rules" | "changes";
const SEGMENTS: readonly Knw03Segment[] = ["steps", "guidance", "pbc", "rules", "changes"];

/** d: A-04's tailoring of a program on one engagement (its program-tailoring read; fixture-only
 * until A-04's contract is live): the engagement's name and each tailored step's words. */
export interface Tailoring {
  engagement: string;
  steps: Readonly<Record<string, { kind: "tailored" | "decided"; text: string } | undefined>>;
}

export interface StepChange {
  kind: "added" | "changed" | "removed";
  number: number;
  text: string;
  /** The prior version's text, struck above a changed row (KNW-02 c grammar). */
  was?: string;
}

const fingerprint = (s: StepOut): string =>
  JSON.stringify([s.text, s.mandatory, s.level, s.standard_refs, s.assertions, s.lock_note]);

/** The program's changes against the prior version, by stable step key (AC4.3: computed by code). */
export function changesOf(now: readonly StepOut[], prior: readonly StepOut[]): StepChange[] {
  const before = new Map(prior.map((s) => [s.step_key, s]));
  const after = new Set(now.map((s) => s.step_key));
  const out: StepChange[] = [];
  for (const s of now) {
    const was = before.get(s.step_key);
    if (was === undefined) out.push({ kind: "added", number: s.number, text: s.text });
    else if (fingerprint(was) !== fingerprint(s)) {
      out.push({
        kind: "changed",
        number: s.number,
        text: s.text,
        ...(was.text === s.text ? {} : { was: was.text }),
      });
    }
  }
  for (const s of prior) {
    if (!after.has(s.step_key)) out.push({ kind: "removed", number: s.number, text: s.text });
  }
  return out.sort((a, b) => a.number - b.number);
}

function Blocks({ blocks }: { blocks: readonly GuidanceBlockOut[] }): JSX.Element {
  return (
    <div className="flex flex-col gap-[8px] px-[14px] py-[12px] text-dense leading-[1.45] text-ink">
      {blocks.map((b, i) =>
        b.kind === "ordered_list" ? (
          <ol key={i} className="flex list-decimal flex-col gap-[6px] pl-[18px]">
            {b.items.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ol>
        ) : (
          <p key={i}>{b.text}</p>
        ),
      )}
    </div>
  );
}

function StepsTable({
  steps,
  pbc,
  lit,
  newKeys,
  label,
  expanded,
  onExpand,
  popover,
  editing = false,
  tailoring,
  onEditText,
  onRemove,
}: {
  steps: readonly StepOut[];
  pbc: readonly string[];
  lit: number | null;
  newKeys: ReadonlySet<string>;
  label: string;
  expanded: number | null;
  onExpand: (n: number | null) => void;
  popover: (step: StepOut) => ReactNode;
  /** c: a draft's optional steps are editable and removable; mandatory ones stay locked. */
  editing?: boolean;
  /** d: A-04's tailoring of this program on an engagement, by step key. */
  tailoring?: Tailoring | undefined;
  onEditText?: (step: StepOut, text: string) => void;
  onRemove?: (step: StepOut) => void;
}): JSX.Element {
  const th = "h-[30px] bg-band-hd px-[10px] text-left text-th font-normal text-ink-2 hairline-b";
  const trash = editing || tailoring !== undefined;
  return (
    <table className="w-full table-fixed text-cell">
      <thead>
        <tr>
          <th className={`${th} w-[44px]`}>{COPY.columns.n}</th>
          <th className={th}>{COPY.columns.step}</th>
          <th className={`${th} w-[84px]`}>{COPY.columns.assertions}</th>
          <th className={`${th} w-[92px]`}>{COPY.columns.standard}</th>
          <th className={`${th} w-[110px]`}>{COPY.columns.pbc}</th>
          <th className={`${th} w-[84px]`}>{COPY.columns.level}</th>
          <th className={`${th} w-[52px]`}>{COPY.columns.rules}</th>
          <th className={`${th} w-[104px]`}>{COPY.columns.skill}</th>
          <th className={`${th} w-[64px]`}>{COPY.columns.lock}</th>
          {trash && <th className={`${th} w-[40px]`} aria-label={COPY.columns.remove} />}
        </tr>
      </thead>
      <tbody>
        {steps.map((s) => {
          const isLit = lit === s.number;
          const open = expanded === s.number;
          const links = s.pbc_positions.map((p) => pbc[p - 1]).filter((x) => x !== undefined);
          return [
            <tr
              key={s.id}
              data-step={s.number}
              {...(isLit ? { "data-lit": "" } : {})}
              aria-expanded={open}
              onClick={() => {
                onExpand(open ? null : s.number);
              }}
              className={`h-[40px] cursor-pointer align-top hairline-b hover:bg-band-hd ${open ? "bg-band-hd" : ""}`}
            >
              <td
                className={`px-[10px] py-[11px] tabular-nums ${isLit ? "border-l-2 border-match-line bg-match-bg" : ""}`}
              >
                <span className="inline-flex items-center gap-[4px]">
                  {s.number}
                  {isLit && popover(s)}
                </span>
              </td>
              <td className="px-[10px] py-[11px]">
                {editing && s.allowed_actions.includes("methodology.edit_step") ? (
                  <input
                    aria-label={COPY.draft.stepLabel(s.number)}
                    defaultValue={s.text}
                    onClick={(e) => {
                      e.stopPropagation();
                    }}
                    onBlur={(e) => {
                      const text = e.currentTarget.value.trim();
                      if (text !== "" && text !== s.text) onEditText?.(s, text);
                    }}
                    className="w-full rounded-[6px] bg-transparent px-[4px] text-dense outline-none focus:bg-nested"
                  />
                ) : (
                  <span className="line-clamp-2 text-dense">{s.text}</span>
                )}
                {tailoring?.steps[s.step_key] !== undefined && (
                  <span className="mt-[4px] inline-flex" data-tailoring={s.step_key}>
                    <Pill
                      variant={
                        tailoring.steps[s.step_key]?.kind === "tailored" ? "amber" : "neutral"
                      }
                      size="sm"
                    >
                      {tailoring.steps[s.step_key]?.text}
                    </Pill>
                  </span>
                )}
                {newKeys.has(s.step_key) && (
                  <span className="mt-[4px] inline-flex">
                    <Pill variant="green-tint" size="sm">
                      {COPY.newIn(label)}
                    </Pill>
                  </span>
                )}
              </td>
              <td className="px-[10px] py-[11px]">
                {s.assertions.length === 0 ? (
                  <span className="text-ink-4">{DASH}</span>
                ) : (
                  s.assertions.join(", ")
                )}
              </td>
              <td className="px-[10px] py-[11px]">{s.standard_refs.join("; ")}</td>
              <td className="px-[10px] py-[11px]">
                {links.length === 0 ? (
                  <span className="text-ink-4">{DASH}</span>
                ) : (
                  <span className="line-clamp-2">{links.join("; ")}</span>
                )}
              </td>
              <td className="px-[10px] py-[11px]">{COPY.levels[s.level]}</td>
              <td className="px-[10px] py-[11px] tabular-nums">
                {s.rules_count === 0 ? <span className="text-ink-4">{DASH}</span> : s.rules_count}
              </td>
              <td className="px-[10px] py-[11px]">
                {/* K-05 links skills to steps; until then every step reads a dash (R2). */}
                <span className="text-ink-4">{DASH}</span>
              </td>
              <td className="px-[10px] py-[11px]">
                {s.mandatory ? (
                  <span className="flex flex-col gap-[2px]">
                    {trash ? (
                      <Tooltip content={COPY.draft.lockTip}>
                        <span tabIndex={0} className="inline-flex" aria-label={COPY.draft.lockTip}>
                          <Icon name="lock" size={13} aria-hidden className="text-ink-2" />
                        </span>
                      </Tooltip>
                    ) : (
                      <Icon
                        name="lock"
                        size={13}
                        aria-label={COPY.mandatory}
                        className="text-ink-2"
                      />
                    )}
                    {s.lock_note != null && (
                      <span className="text-[11px] leading-[1.2] text-ink-3">{s.lock_note}</span>
                    )}
                  </span>
                ) : (
                  <span className="text-ink-4">{DASH}</span>
                )}
              </td>
              {trash && (
                <td className="px-[6px] py-[9px]">
                  <Button
                    variant="ghost"
                    size="xs"
                    icon="trash-2"
                    aria-label={COPY.draft.remove(s.number)}
                    disabled={!editing || !s.allowed_actions.includes("methodology.remove_step")}
                    onClick={(e) => {
                      e.stopPropagation();
                      onRemove?.(s);
                    }}
                  />
                </td>
              )}
            </tr>,
            open ? (
              <tr
                key={`${s.id}-open`}
                data-step-detail={s.number}
                className="bg-band-hd hairline-b"
              >
                <td />
                <td colSpan={trash ? 9 : 8} className="px-[10px] pt-[4px] pb-[12px]">
                  <p className="text-dense leading-[1.45]">{s.text}</p>
                  {s.guidance.length > 0 && <Blocks blocks={s.guidance} />}
                  <p className="mt-[6px] text-meta text-ink-3">
                    {COPY.skillLine} · {DASH}
                  </p>
                  <p className="text-meta text-ink-3">
                    {COPY.rulesLine} · {s.rules_count === 0 ? DASH : s.rules_count}
                  </p>
                </td>
              </tr>
            ) : null,
          ];
        })}
      </tbody>
    </table>
  );
}

function ChangeLog({ changes }: { changes: readonly StepChange[] }): JSX.Element {
  return (
    <ul aria-label={COPY.changeLog} className="flex flex-col">
      {changes.map((c) => (
        <li
          key={`${c.kind}-${String(c.number)}`}
          data-change={c.kind}
          className="flex items-start gap-[10px] px-[14px] py-[10px] hairline-b"
        >
          <span className="w-[28px] flex-none text-dense tabular-nums text-ink-2">{c.number}</span>
          <span className="flex min-w-0 flex-1 flex-col gap-[3px]">
            {c.was !== undefined && (
              <span className="text-dense text-ink-3 line-through">{c.was}</span>
            )}
            <span
              className={
                c.kind === "removed"
                  ? "text-dense text-ink-3 line-through"
                  : c.kind === "changed"
                    ? "border-l-2 border-green pl-[8px] text-dense text-green-ink"
                    : "text-dense"
              }
            >
              {c.text}
            </span>
          </span>
          <Pill
            variant={
              c.kind === "added" ? "green-tint" : c.kind === "removed" ? "neutral" : "amber"
            }
            size="sm"
          >
            {COPY.change[c.kind]}
          </Pill>
        </li>
      ))}
    </ul>
  );
}

async function download(versionId: string): Promise<void> {
  const { data, response } = await exportVersion({
    path: { version_id: versionId },
    parseAs: "blob",
    throwOnError: true,
  });
  const header = response.headers.get("Content-Disposition") ?? "";
  const name = /filename="([^"]+)"/u.exec(header)?.[1] ?? "program.xlsx";
  const url = URL.createObjectURL(data);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

export interface KNW03Props {
  programId: string;
  segment?: Knw03Segment;
  onSegment?: (segment: Knw03Segment) => void;
  /** `?step=`: the step to light, with `from=citation` (a) or `from=run` (f, Fix in Knowledge). */
  step?: number;
  from?: "citation" | "run";
  /** f: the failed run the arrival quotes (C6 v1). */
  run?: string;
  /** d: A-04's tailoring of this program on an engagement. */
  tailoring?: Tailoring;
  /** b: the SHL-07 popover held open on the lit step (the gallery's artboard). */
  popoverOpen?: boolean;
  onProgram?: (programId: string) => void;
  onBack?: () => void;
  toolbar?: ToolbarProps;
  frame?: boolean;
}

export function KNW03({
  programId,
  segment = "steps",
  onSegment,
  step,
  from,
  run,
  tailoring,
  popoverOpen = false,
  onProgram,
  onBack,
  toolbar,
  frame = false,
}: KNW03Props): JSX.Element {
  const now = useNow();
  const [expanded, setExpanded] = useState<number | null>(null);
  const [pop, setPop] = useState(popoverOpen);
  const program = useQuery(programOptions({ path: { program_id: programId } }));
  const versionId = program.data?.version.version_id ?? "";
  const ready = versionId !== "";
  const version = useQuery({
    ...getVersionOptions({ path: { version_id: versionId } }),
    enabled: ready,
  });
  const programs = useQuery({
    ...versionProgramsOptions({ path: { version_id: versionId } }),
    enabled: ready,
  });
  const steps = useQuery(programStepsOptions({ path: { program_id: programId } }));
  const templates = useQuery(listTemplatesOptions());
  const current = version.data?.summary;
  const priorVersion = (templates.data ?? []).find(
    (t) =>
      current !== undefined &&
      t.template_id === current.template_id &&
      t.version === current.version - 1,
  );
  const priorPrograms = useQuery({
    ...versionProgramsOptions({ path: { version_id: priorVersion?.version_id ?? "" } }),
    enabled: priorVersion !== undefined,
  });
  const priorProgram = (priorPrograms.data ?? []).find((p) => p.code === program.data?.code);
  const priorSteps = useQuery({
    ...programStepsOptions({ path: { program_id: priorProgram?.id ?? "" } }),
    enabled: priorProgram !== undefined,
  });
  const lit = (from === "citation" || from === "run") && step !== undefined ? step : null;
  const queryClient = useQueryClient();
  const versionState = program.data?.version;
  const isDraft = versionState?.status === "draft";
  const [editing, setEditing] = useState(true);
  const draftEditing =
    isDraft && editing && versionState.allowed_actions.includes("methodology.edit");
  const failedRun = useQuery({
    ...agentRunOptions({ path: { run_id: run ?? "" } }),
    enabled: from === "run" && run !== undefined,
  });
  const refreshSteps = (): void => {
    void queryClient.invalidateQueries({
      queryKey: programStepsQueryKey({ path: { program_id: programId } }),
    });
    void queryClient.invalidateQueries({
      queryKey: programQueryKey({ path: { program_id: programId } }),
    });
  };
  const addStep = useMutation({ ...addStepMutation(), onSuccess: refreshSteps });
  const editStep = useMutation({ ...editStepMutation(), onSuccess: refreshSteps });
  const removeStep = useMutation({ ...removeStepMutation(), onSuccess: refreshSteps });
  const submit = useMutation({
    ...submitVersionMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: programQueryKey({ path: { program_id: programId } }),
      });
    },
  });
  const failed = (text: string) => (): void => {
    toast.show({ kind: "error", text });
  };
  const litStep = (steps.data ?? []).find((s) => s.number === lit);
  const citations = useQuery({
    ...listCitationsOptions({
      query: { kind: "methodology_step", anchor_ref: litStep?.anchor ?? "" },
    }),
    enabled: litStep !== undefined,
  });

  const label = program.data?.version.label ?? "";
  const priorLabel = priorVersion === undefined ? "" : `v${String(priorVersion.version)}`;
  const changes =
    steps.data === undefined || priorSteps.data === undefined
      ? []
      : changesOf(steps.data, priorSteps.data);
  const newKeys = new Set(
    changes
      .filter((c) => c.kind === "added")
      .map((c) => (steps.data ?? []).find((s) => s.number === c.number)?.step_key ?? ""),
  );
  const pbc = (version.data?.items ?? []).map((i) => i.description);
  const all = programs.data ?? [];
  const totalSteps = all.reduce((n, p) => n + p.step_count, 0);
  const totalMandatory = all.reduce((n, p) => n + p.mandatory_count, 0);

  const state: ViewState =
    program.isError || steps.isError
      ? {
          kind: "error",
          retry: () => {
            void program.refetch();
            void steps.refetch();
          },
        }
      : program.data === undefined || steps.data === undefined
        ? { kind: "loading" }
        : { kind: "ready" };

  const header = (
    <RecordHeader
      variant="settings"
      title={current?.template_name ?? ""}
      context={label}
      state={
        isDraft
          ? COPY.draft.pill
          : program.data?.version.status === "published" &&
              program.data.version.effective_from != null
            ? COPY.publishedFrom(
                formatDate(program.data.version.effective_from, { now, withYear: true }),
              )
            : ""
      }
      stateTone={isDraft ? "amber" : "green-tint"}
      backLabel={COPY.back}
      {...(onBack === undefined ? {} : { onBack })}
    />
  );

  const rail = (
    <section aria-label={COPY.rail} className="pane flex min-h-0 flex-1 flex-col overflow-hidden">
      <div className="flex h-(--pane-hd-h) flex-none items-center justify-center bg-card hairline-b">
        <h2 className="text-pane font-medium tracking-[-0.012em]">{COPY.rail}</h2>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        {label !== "" && (
          <OverviewCard
            icon="notebook-text"
            title={COPY.card(label)}
            sub={COPY.cardSub(totalSteps, totalMandatory)}
            state={COPY.published}
          />
        )}
        {priorLabel !== "" && (
          <RailRow
            link={{
              id: "changes",
              icon: "history",
              title: COPY.changeLog,
              sub: COPY.changesFrom(changes.length, priorLabel),
            }}
            onOpen={() => onSegment?.("changes")}
          />
        )}
        <GroupBand title={COPY.programs} />
        {all.map((p: ProgramOut) => (
          <button
            key={p.id}
            type="button"
            aria-current={p.id === programId ? "true" : undefined}
            onClick={() => onProgram?.(p.id)}
            className={`flex min-h-[38px] w-full items-center gap-[10px] px-[12px] py-[6px] text-left hairline-b hover:bg-nested ${p.id === programId ? "bg-sel-bg" : ""}`}
          >
            <StatusDisc state="done" />
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="truncate text-dense">{`${p.code} ${p.name}`}</span>
              <span className="text-meta text-ink-3">
                {p.id === programId
                  ? COPY.cardSub(p.step_count, p.mandatory_count)
                  : COPY.programSub(p.step_count, p.mandatory_count)}
              </span>
            </span>
          </button>
        ))}
      </div>
    </section>
  );

  const popover = (s: StepOut): ReactNode => {
    const list = (citations.data?.items ?? []).map((c) => ({
      n: c.n,
      title: c.title,
      quote: c.quote ?? s.text,
      loc: c.loc,
      match: null,
    }));
    if (list.length === 0) return null;
    return (
      <span
        onClick={(e) => {
          e.stopPropagation();
        }}
      >
        <Popover
          label={COPY.openStep}
          width={372}
          align="start"
          open={pop}
          onOpenChange={setPop}
          trigger={
            <button type="button" aria-label={COPY.openStep} className="text-ink-3 hover:text-ink">
              <Icon name="external-link" size={12} />
            </button>
          }
        >
          <CitationPopover payload={{ list, index: 0 }} />
          <p className="px-[15px] pb-[10px] text-meta text-ink-3">{COPY.citations(list.length)}</p>
        </Popover>
      </span>
    );
  };

  const stepsList = steps.data ?? [];
  const table = (shown: readonly StepOut[]): JSX.Element => (
    <StepsTable
      steps={shown}
      pbc={pbc}
      lit={lit}
      newKeys={newKeys}
      label={label}
      expanded={expanded}
      onExpand={setExpanded}
      popover={popover}
      editing={draftEditing}
      tailoring={tailoring}
      onEditText={(st, text) => {
        editStep
          .mutateAsync({
            path: { version_id: versionId, step_id: st.id },
            headers: { "If-Match": st.row_version },
            body: { text },
          })
          .catch(failed(COPY.draft.saveFailed));
      }}
      onRemove={(st) => {
        removeStep
          .mutateAsync({
            path: { version_id: versionId, step_id: st.id },
            headers: { "If-Match": st.row_version },
          })
          .catch(failed(COPY.draft.saveFailed));
      }}
    />
  );
  const draftNumber = current?.version ?? 0;
  const runOut = failedRun.data?.run;
  const banner: ReactNode = isDraft ? (
    <div
      data-knw03="draft-banner"
      className="mx-[12px] mt-[10px] flex min-h-[40px] items-center gap-[8px] rounded-nested bg-nested px-[12px] text-dense text-ink-2"
    >
      <Icon name="pencil" size={14} className="flex-none" />
      <span className="flex-1">{COPY.draft.banner(draftNumber)}</span>
      {versionState.allowed_actions.includes("methodology.submit") && (
        <Button
          variant="secondary"
          size="sm"
          disabled={submit.isPending}
          onClick={() => {
            submit
              .mutateAsync({
                path: { version_id: versionId },
                body: { row_version: versionState.row_version },
              })
              .then(() => {
                toast.show({ kind: "success", text: COPY.draft.submitted(draftNumber) });
              })
              .catch(failed(COPY.draft.submitFailed));
          }}
        >
          {COPY.draft.submit}
        </Button>
      )}
    </div>
  ) : runOut?.state === "failed" && runOut.state_reason != null ? (
    <div
      role="status"
      data-knw03="run-error"
      className="mx-[12px] mt-[10px] flex min-h-[36px] items-start gap-[8px] rounded-nested bg-amber-tint px-[12px] py-[8px] text-dense text-amber-ink"
    >
      <Icon name="triangle-alert" size={14} className="mt-[2px] flex-none" />
      {/* The run's error is the agent's words: plain text through AgentText, never markup. */}
      <AgentText inline text={runOut.state_reason} className="text-dense text-amber-ink" />
    </div>
  ) : null;
  const body =
    segment === "changes" ? (
      <ChangeLog changes={changes} />
    ) : segment === "rules" ? (
      stepsList.some((s) => s.rules_count > 0) ? (
        table(stepsList.filter((s) => s.rules_count > 0))
      ) : (
        <EmptyState icon="list-filter" title={COPY.noRules} />
      )
    ) : segment === "guidance" ? (
      stepsList.some((s) => s.guidance.length > 0) ? (
        table(stepsList.filter((s) => s.guidance.length > 0))
      ) : (
        <EmptyState icon="book-open" title={COPY.noGuidance} />
      )
    ) : segment === "pbc" ? (
      stepsList.some((s) => s.pbc_positions.length > 0) ? (
        table(stepsList.filter((s) => s.pbc_positions.length > 0))
      ) : (
        <EmptyState icon="list-checks" title={COPY.noPbc} />
      )
    ) : (
      table(stepsList)
    );

  const guided = litStep?.guidance.length ? litStep : stepsList.find((s) => s.guidance.length > 0);
  const guidanceTitle = guided?.prepopulates
    .map((k) => COPY.guidanceTitles[k])
    .find((t) => t !== undefined);
  const dock = (
    <div className="flex flex-col gap-[12px] p-[10px]">
      {runOut?.state === "failed" && (
        <section
          aria-label={COPY.run.label}
          data-knw03="run-card"
          className="flex flex-col gap-[6px] rounded-pane bg-card p-[14px] shadow-e1"
        >
          <span className="flex items-center gap-[8px] text-body font-medium">
            <StatusDisc state="fail" />
            {COPY.run.failed(runOut.agent_label, time(runOut.started_at))}
          </span>
          <span className="pl-[23px] text-meta text-ink-3">
            {runOut.subject === null
              ? COPY.run.noEvidence
              : `${runOut.subject} · ${COPY.run.noEvidence}`}
          </span>
          {/* Retry belongs to P-09's dock; until then the card offers only the draft. */}
          {PLANNED_VISIBLE && (
            <span className="pl-[23px]">
              <Button variant="secondary" size="sm" disabled title={COPY.run.linkHint}>
                {COPY.run.linkTemplate}
              </Button>
            </span>
          )}
        </section>
      )}
      {guided !== undefined && (
        <section
          aria-label={guidanceTitle ?? COPY.dock}
          className="rounded-pane bg-card shadow-e1"
        >
          {guidanceTitle !== undefined && (
            <h3 className="flex h-[38px] items-center px-[14px] text-record font-medium hairline-b">
              {guidanceTitle}
            </h3>
          )}
          <Blocks blocks={guided.guidance} />
        </section>
      )}
      {litStep !== undefined && citations.data !== undefined && (
        <section aria-label={COPY.whereCited(litStep.number)} className="flex flex-col">
          <h3 className="px-[4px] pb-[6px] text-dense font-medium">
            {COPY.whereCited(litStep.number)}
          </h3>
          <p className="px-[4px] text-meta text-ink-3">{COPY.citations(citations.data.total)}</p>
        </section>
      )}
    </div>
  );

  const actions = (
    <span className="flex items-center gap-[8px]">
      {tailoring !== undefined && (
        <Pill variant="neutral" size="sm">
          {COPY.tailored.chip(tailoring.engagement)}
        </Pill>
      )}
      {isDraft && versionState.allowed_actions.includes("methodology.edit") ? (
        <>
          <Button
            variant={editing ? "tonal" : "secondary"}
            size="sm"
            icon={editing ? "check" : "pencil"}
            onClick={() => {
              setEditing(!editing);
            }}
          >
            {editing ? COPY.draft.done : COPY.actions.edit}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            disabled={!draftEditing || addStep.isPending}
            onClick={() => {
              addStep
                .mutateAsync({
                  path: { version_id: versionId, program_id: programId },
                  body: { text: COPY.draft.newStep, level: "planning" },
                })
                .catch(failed(COPY.draft.saveFailed));
            }}
          >
            {COPY.actions.addStep}
          </Button>
        </>
      ) : (
        PLANNED_VISIBLE && (
          <>
            <Button variant="secondary" size="sm" icon="pencil" disabled>
              {COPY.actions.edit}
            </Button>
            <Button variant="secondary" size="sm" disabled>
              {COPY.actions.addStep}
            </Button>
          </>
        )
      )}
      <Button
        variant="secondary"
        size="sm"
        icon="file-spreadsheet"
        disabled={!ready}
        onClick={() => {
          download(versionId).catch(() => {
            toast.show({ kind: "error", text: COPY.exportFailed });
          });
        }}
      >
        {COPY.actions.excel}
      </Button>
    </span>
  );

  return (
    <div data-screen="KNW-03" className="flex min-h-0 flex-1 flex-col">
      <RecordCockpit
        {...(toolbar === undefined ? {} : { toolbar })}
        frame={frame}
        {...(frame ? { height: 860 } : {})}
        header={header}
        rail={rail}
        canvas={{
          title: program.data === undefined ? "" : `${program.data.code} ${program.data.name}`,
          actions,
          controls: (
            <Segmented
              size="small"
              label={COPY.segments.label}
              options={SEGMENTS.map((k) => ({
                label: COPY.segments[k],
                ...(k === "changes" && changes.length > 0 ? { count: changes.length } : {}),
              }))}
              active={COPY.segments[segment]}
              onChange={(l) => {
                const next = SEGMENTS.find((k) => COPY.segments[k] === l);
                if (next !== undefined) onSegment?.(next);
              }}
            />
          ),
          state,
          footer:
            program.data === undefined ? undefined : (
              <span className="text-meta text-ink-3">
                {COPY.footer(program.data.step_count, program.data.mandatory_count)}
              </span>
            ),
          children: (
            <>
              {banner}
              {body}
            </>
          ),
        }}
        dock={{ view: "Notes", views: ["Notes"], title: COPY.dock, children: dock }}
        defaultDockOpen
      />
    </div>
  );
}

/** The screen with its own segment: the gallery's artboard and the tests' host. */
export function ProgramEditorPage(
  props: Omit<KNW03Props, "segment" | "onSegment"> & { initialSegment?: Knw03Segment },
): JSX.Element {
  const { initialSegment = "steps", ...rest } = props;
  const [segment, setSegment] = useState<Knw03Segment>(initialSegment);
  return <KNW03 {...rest} segment={segment} onSegment={setSegment} />;
}
