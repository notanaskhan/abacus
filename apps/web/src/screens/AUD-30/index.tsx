// AUD-30 · Post-issuance & subsequent discovery (Q-05-T24; TASK-8934; docs/screens/AUD-30.md;
// handoff AUD-30 a–f; SPEC-711 AC-15 to AC-18; DEC-5936): the T2 cockpit on the archived audit
// (rail, canvas, a Decision dock) for the engagement partner. Every figure is the server's: the
// case list and each case's comparison and evaluation (code's, ADR-050), the kept analysis (the
// agent's, through AgentBlocks), the archive additions. The browser formats only.
//   a PI-01 under evaluation · b decided "No action" (the addition logged) · c revise and reissue,
//   "Reopen for reissue" to AUD-23 g · d PI-02 (an omitted procedure, no figures) · e the Archive
//   additions tab · f New case…
// The decision is the engagement partner's (`post_issuance.decide`, the server's options); the
// agent shows its analysis and a recommendation tag only. Nothing here edits the archive: a case
// reaches it only as a logged addition. A difference below clearly trivial is never red (AVOID).
import type {
  ArchiveAdditionOut,
  AuditSectionRowOut,
  PostIssuanceCaseOut,
} from "@abacus/api-client";
import {
  auditArchiveAdditionsOptions,
  postIssuanceAnalysisReadOptions,
  postIssuanceCaseCreateMutation,
  postIssuanceCasesOptions,
  postIssuanceDecisionMutation,
  postIssuanceReissueMutation,
} from "@abacus/api-client/query";
import {
  type AgentBlocksPayload,
  AgentBlocks,
  Button,
  DASH,
  DecisionCard,
  Icon,
  Pill,
  Picker,
  RecordCockpit,
  Segmented,
  SheetModal,
  StatusDisc,
  Timeline,
  type TimelineEvent,
  type ViewState,
  amount,
  cn,
  date,
  status,
  time,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type ReactNode, useState } from "react";
import { useNow } from "../../app-core/clock";
import { DockViewer, SectionRail, auditBarProps, useAuditCockpit } from "../../domain/audits";
import { COPY as C } from "./copy";

export type Aud30View = "cases" | "additions";

export interface AUD30Props {
  /** The assurance work item (`$auditId`). */
  auditId: string;
  /** `?view=`: the cases (default) or the archive additions (e). */
  view?: Aud30View;
  onView?: (view: Aud30View) => void;
  /** `?case=`: the selected case's ref (PI-01 by default; d: PI-02). */
  caseRef?: string;
  onCase?: (ref: string) => void;
  /** f: the New case sheet open on arrival. */
  newCase?: boolean;
  /** A rail row other than Post-issuance: the cockpit's section. */
  onSection?: (row: AuditSectionRowOut) => void;
  /** "Reopen for reissue" succeeded: AUD-23 g (the cockpit's Auditor's report section). */
  onReissued?: () => void;
  /** "All Audits". */
  onBack?: () => void;
}

const FACTS = "subsequently_discovered_facts";

/** The case's title and its longer description: the description's first line, then the rest. */
export function caseText(description: string): { title: string; body: string | null } {
  const [first = "", ...rest] = description.split("\n");
  const body = rest.join("\n").trim();
  return { title: first.trim(), body: body === "" ? null : body };
}

function KV({ k, children }: { k: string; children: ReactNode }): JSX.Element {
  return (
    <div className="flex min-h-[30px] items-center gap-[12px] px-[14px] py-[5px] hairline-b text-[12.5px]">
      <dt className="w-[130px] flex-none text-ink-2">{k}</dt>
      <dd className="min-w-0 flex-1">{children}</dd>
    </div>
  );
}

function Band({ children }: { children: ReactNode }): JSX.Element {
  return (
    <h4 className="bg-nested px-[14px] py-[6px] text-[12.5px] font-normal text-ink-2">
      {children}
    </h4>
  );
}

function CaseRow({
  c,
  selected,
  onSelect,
  now,
}: {
  c: PostIssuanceCaseOut;
  selected: boolean;
  onSelect: () => void;
  now: Date;
}): JSX.Element {
  const s = status("post_issuance_case", c.status);
  const { title } = caseText(c.description);
  const word =
    c.type === "omitted_procedure" && c.status === "concluded_no_action" && c.decided_at
      ? C.concludedOn(date(c.decided_at, { now }))
      : s.label;
  const sub = [
    C.typeLine[c.type] ?? c.type,
    c.standard == null ? null : (C.standard[c.standard] ?? null),
    c.source_kind === "inspection_finding"
      ? C.foundInInspection(date(c.received_at, { now, withYear: true }))
      : C.received(date(c.received_at, { now, withYear: true })),
  ]
    .filter((x): x is string => x !== null)
    .join(" · ");
  return (
    <li>
      <button
        type="button"
        data-case={c.ref}
        aria-current={selected ? "true" : undefined}
        onClick={onSelect}
        className={cn(
          "flex min-h-[52px] w-full items-center gap-[10px] px-[14px] py-[6px] text-left",
          selected && "bg-nested",
        )}
      >
        <StatusDisc
          state={
            c.status === "under_evaluation"
              ? "warn"
              : c.status === "reissue_in_progress"
                ? "half"
                : "done"
          }
          size={15}
        />
        <span className="min-w-0 flex-1">
          <span className="block text-[13px]">
            <span className="text-ink-3">{c.ref}</span>{" "}
            <span className="font-medium text-ink">{title}</span>
          </span>
          <span className="block text-[11.5px] text-ink-3">{sub}</span>
        </span>
        <Pill variant={s.variant ?? "neutral"} size="sm">
          {word}
        </Pill>
      </button>
    </li>
  );
}

function Comparison({ c }: { c: PostIssuanceCaseOut }): JSX.Element {
  const ev = c.evaluation;
  if (c.comparison === undefined || c.comparison.length === 0 || ev == null) {
    return (
      <p className="px-[14px] py-[10px] text-[12.5px] text-ink-3">{C.comparisonUnavailable}</p>
    );
  }
  const below = ev.below_clearly_trivial;
  const ct = amount(ev.clearly_trivial, "whole").text;
  return (
    <>
      <table className="w-full border-collapse text-[12.5px]" data-aud30="comparison">
        <thead>
          <tr className="hairline-b text-ink-2">
            <th scope="col" className="h-[30px] px-[14px] text-left font-normal">
              {C.columns.line}
            </th>
            <th scope="col" className="px-[14px] text-right font-normal">
              {C.columns.certified}
            </th>
            <th scope="col" className="px-[14px] text-right font-normal">
              {C.columns.corrected}
            </th>
            <th scope="col" className="px-[14px] text-right font-normal">
              {C.columns.difference}
            </th>
          </tr>
        </thead>
        <tbody>
          {c.comparison.map((ln) => {
            const diff = amount(ln.difference, "whole");
            return (
              <tr key={ln.line_key} className="h-[30px] hairline-b">
                <td className="px-[14px]">{ln.label}</td>
                <td className="px-[14px] text-right tabular-nums">
                  {amount(ln.as_certified, "whole").text}
                </td>
                <td className="px-[14px] text-right tabular-nums">
                  {amount(ln.as_corrected, "whole").text}
                </td>
                {/* AVOID: no alarm styling for a below-CT difference; above CT it reads red. */}
                <td
                  data-difference={diff.tone}
                  className={cn(
                    "px-[14px] text-right tabular-nums",
                    !below && diff.tone === "neg" && "text-red",
                  )}
                >
                  {diff.text}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <Band>{C.evaluation}</Band>
      <dl>
        <KV k={C.clearlyTrivial}>{below ? C.belowCt(ct) : C.aboveCt(ct)}</KV>
        <KV k={C.share}>
          {C.shareValue(ev.share_pct, amount(ev.overall_materiality, "whole").text)}
        </KV>
        <KV k={C.disclosures}>{c.disclosure_affected === true ? C.some : C.none}</KV>
      </dl>
    </>
  );
}

function Analysis({
  auditId,
  c,
  run,
}: {
  auditId: string;
  c: PostIssuanceCaseOut;
  run: number | null;
}): JSX.Element | null {
  const kept = useQuery({
    ...postIssuanceAnalysisReadOptions({
      path: { work_item_id: auditId, case_id: c.case_id },
    }),
    enabled: c.analysis_run_id != null,
    retry: false,
  });
  if (kept.data === undefined) return null;
  return (
    <section
      aria-label={C.agent(run ?? 0)}
      data-aud30="analysis"
      className="m-[10px] rounded-nested bg-nested p-[12px]"
    >
      <header className="mb-[6px] flex items-center gap-[8px] text-[12.5px] font-medium">
        <Icon name="atom" size={14} />
        <span className="flex-1">{C.agent(run ?? 0)}</span>
        <span className="text-ink-2">{C.run} ›</span>
      </header>
      <div className="text-[12.5px] leading-[1.55] text-ink-2">
        <AgentBlocks blocks={kept.data.blocks as unknown as AgentBlocksPayload} facts={{}} />
      </div>
    </section>
  );
}

function CaseDetail({
  auditId,
  c,
  run,
  now,
  onSource,
}: {
  auditId: string;
  c: PostIssuanceCaseOut;
  run: number | null;
  now: Date;
  onSource: () => void;
}): JSX.Element {
  const { body } = caseText(c.description);
  const omitted = c.type === "omitted_procedure";
  // The engagement partner's own words (sealed, the decider's), never model text.
  const resolution = c.rationale ?? null;
  return (
    <section data-aud30="detail" className="m-[10px] rounded-[12px] bg-card shadow-e1">
      <dl>
        <KV k={C.kv.source}>
          {c.source_kind === "inspection_finding" ? (
            <span>{C.inspectionSource(date(c.received_at, { now, withYear: true }))}</span>
          ) : c.source_name != null ? (
            <span className="flex items-center gap-[8px]">
              <button
                type="button"
                data-aud30="source"
                onClick={onSource}
                className="inline-flex h-[26px] items-center gap-[6px] rounded-pill bg-nested px-[10px] text-[12px]"
              >
                <Icon name="file" size={13} />
                {c.source_name}
              </button>
              <span className="text-[11.5px] text-ink-3">
                {C.viaInbox(date(c.received_at, { now, withYear: true }))}
              </span>
            </span>
          ) : (
            C.otherSource
          )}
        </KV>
        <KV k={C.kv.raisedBy}>{c.raised_by_name ?? DASH}</KV>
        <KV k={C.kv.released}>
          {c.report_released_at == null
            ? DASH
            : date(c.report_released_at, { now, withYear: true })}
        </KV>
        {omitted && c.decided_at != null ? (
          <KV k={C.kv.concluded}>
            {`${date(c.decided_at, { now, withYear: true })} · ${c.decided_by_name ?? DASH}`}
          </KV>
        ) : null}
      </dl>
      {omitted ? (
        <>
          {body !== null ? (
            <>
              <Band>{C.omittedTitle}</Band>
              <p className="px-[14px] py-[10px] text-[12.5px] text-ink-2">{body}</p>
            </>
          ) : null}
          {resolution !== null ? (
            <>
              <Band>{C.alternativeTitle}</Band>
              <p className="px-[14px] py-[10px] text-[12.5px] text-ink-2" data-aud30="resolution">
                {resolution}
              </p>
            </>
          ) : null}
        </>
      ) : (
        <>
          <Comparison c={c} />
          <Analysis auditId={auditId} c={c} run={run} />
        </>
      )}
    </section>
  );
}

function AdditionsTable({
  rows,
  cases,
  now,
}: {
  rows: readonly ArchiveAdditionOut[];
  cases: readonly PostIssuanceCaseOut[];
  now: Date;
}): JSX.Element {
  const refOf = (id: string | null | undefined): string | null =>
    cases.find((c) => c.case_id === id)?.ref ?? null;
  return (
    <section data-aud30="additions" className="m-[10px] rounded-[12px] bg-card shadow-e1">
      {rows.length === 0 ? (
        <p className="px-[14px] py-[10px] text-[12.5px] text-ink-3">{C.additions.empty}</p>
      ) : (
        <table className="w-full border-collapse text-[12.5px]">
          <thead>
            <tr className="hairline-b text-ink-2">
              {[
                C.additions.date,
                C.additions.addition,
                C.additions.addedBy,
                C.additions.approvedBy,
                C.additions.reason,
              ].map((h) => (
                <th key={h} scope="col" className="h-[30px] px-[14px] text-left font-normal">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => {
              const ref = refOf(a.post_issuance_case_id);
              const reason = C.additions.reasons[a.reason_code] ?? a.reason_code;
              return (
                <tr key={a.id} className="hairline-b align-top" data-addition={a.id}>
                  <td className="px-[14px] py-[8px]">
                    {date(a.added_at, { now, withYear: true })}
                  </td>
                  <td className="w-[200px] px-[14px] py-[8px]">
                    <span className="block font-medium">{a.description}</span>
                    <span className="block text-[11px] text-ink-3">
                      {C.additions.hash(a.content_sha256)}
                    </span>
                  </td>
                  <td className="px-[14px] py-[8px]">{a.added_by_name}</td>
                  <td className="px-[14px] py-[8px]">
                    {a.decision === "approved" ? (
                      (a.decided_by_name ?? DASH)
                    ) : (
                      <Pill
                        variant={status("archive_addition", a.decision).variant ?? "amber"}
                        size="sm"
                      >
                        {status("archive_addition", a.decision).label}
                      </Pill>
                    )}
                  </td>
                  <td className="px-[14px] py-[8px] text-ink-2">
                    {ref === null ? reason : `${reason} (${ref})`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
      <p className="flex items-center gap-[8px] px-[14px] py-[8px] text-[11.5px] text-ink-3">
        <Icon name="lock" size={12} />
        <span className="flex-1">{C.additions.footer}</span>
      </p>
    </section>
  );
}

function events(
  c: PostIssuanceCaseOut,
  additions: readonly ArchiveAdditionOut[],
  run: number | null,
  now: Date,
): TimelineEvent[] {
  const out: (TimelineEvent & { at: string })[] = [
    {
      id: "received",
      at: c.received_at,
      date: date(c.received_at, { now }),
      state: "done",
      title:
        c.source_kind === "inbox_evidence"
          ? C.events.receivedInbox
          : c.source_kind === "inspection_finding"
            ? C.events.foundInspection
            : C.events.received,
    },
  ];
  if (c.opened_at != null && c.raised_by_name != null) {
    out.push({
      id: "opened",
      at: c.opened_at,
      date: date(c.opened_at, { now }),
      state: "done",
      title: C.events.opened(c.raised_by_name),
    });
  }
  if (c.analysis_run_id != null && run !== null && c.opened_at != null) {
    out.push({
      id: "analysis",
      at: c.opened_at,
      date: date(c.opened_at, { now }),
      state: "done",
      title: C.events.analysis(run),
    });
  }
  for (const a of additions.filter((x) => x.post_issuance_case_id === c.case_id)) {
    out.push({
      id: `addition:${a.id}`,
      at: a.added_at,
      date: date(a.added_at, { now }),
      state: "done",
      title: C.events.added(a.description),
    });
  }
  if (c.decided_at != null && c.decision != null) {
    out.push({
      id: "decided",
      at: c.decided_at,
      date: date(c.decided_at, { now }),
      state: "done",
      title: C.events.decided(
        c.decided_by_name ?? DASH,
        C.decisionWords[c.decision] ?? c.decision,
      ),
    });
  }
  return out.sort((x, y) => Date.parse(x.at) - Date.parse(y.at));
}

function DecisionDock({
  auditId,
  c,
  additions,
  run,
  now,
  onReissued,
}: {
  auditId: string;
  c: PostIssuanceCaseOut;
  additions: readonly ArchiveAdditionOut[];
  run: number | null;
  now: Date;
  onReissued?: () => void;
}): JSX.Element {
  const queries = useQueryClient();
  const kind = c.type === "omitted_procedure" ? "omitted" : "facts";
  const words = C.options[kind];
  const offered = c.options ?? [];
  const [choice, setChoice] = useState<string | undefined>(undefined);
  const [rationale, setRationale] = useState("");
  const decide = useMutation({
    ...postIssuanceDecisionMutation(),
    onSuccess: async () => {
      setRationale("");
      await queries.invalidateQueries();
    },
  });
  const reissue = useMutation({
    ...postIssuanceReissueMutation(),
    onSuccess: () => {
      onReissued?.();
    },
  });
  const canDecide = (c.allowed_actions ?? []).includes("post_issuance.decide");
  // The decider's own words (a person's, sealed on the case), never model text.
  const reason = c.rationale ?? null;
  const decided =
    c.decision != null && c.decided_at != null
      ? {
          option: words[c.decision].label,
          by: c.decided_by_name ?? DASH,
          at: `${date(c.decided_at, { now, withYear: true })} · ${time(c.decided_at)}`,
        }
      : null;
  const question = kind === "omitted" ? C.question.omitted : C.question.facts;
  return (
    <div className="flex flex-col gap-[10px] p-[10px]" data-aud30="dock">
      <DecisionCard
        title={question}
        reservedNote={C.reserved}
        options={offered.map((o) => ({
          key: o,
          label: words[o].label,
          ...(words[o].detail === "" ? {} : { detail: words[o].detail }),
          ...(c.recommended_option === o ? { recommended: true } : {}),
        }))}
        recommendationLabel={C.recommendation}
        {...(choice === undefined ? {} : { value: choice })}
        onChange={setChoice}
        actor={{ kind: "human", name: c.decided_by_name ?? "" }}
        decided={decided}
        busy={decide.isPending}
        {...(canDecide && decided === null && choice !== undefined && rationale.trim() !== ""
          ? {
              onDecide: () => {
                decide.mutate({
                  path: { work_item_id: auditId, case_id: c.case_id },
                  body: {
                    decision: choice as "no_action" | "revise_and_reissue" | "notify_users",
                    rationale: rationale.trim(),
                    ...(kind === "facts" && c.source_evidence_version_id != null
                      ? { addition_description: C.additionFor(c.ref) }
                      : {}),
                  },
                  headers: { "Idempotency-Key": `aud30-${c.case_id}-${choice}` },
                });
              },
            }
          : {})}
      />
      {decided === null ? (
        <label className="flex flex-col gap-[4px] px-[4px] text-[12px] text-ink-2">
          {C.rationaleLabel}
          <textarea
            aria-label={C.rationaleLabel}
            placeholder={C.rationalePlaceholder}
            value={rationale}
            disabled={!canDecide}
            onChange={(e) => {
              setRationale(e.target.value);
            }}
            className="h-[70px] rounded-nested bg-nested p-[8px] text-[12.5px] text-ink"
          />
        </label>
      ) : reason !== null ? (
        <p className="px-[4px] text-[12px] text-ink-2" data-aud30="rationale">
          <span className="font-medium text-ink">{C.rationaleLabel}</span> · {reason}
        </p>
      ) : null}
      {c.status === "reissue_in_progress" &&
      (c.allowed_actions ?? []).includes("post_issuance.reissue") ? (
        <Button
          variant="primary"
          disabled={reissue.isPending}
          onClick={() => {
            reissue.mutate({
              path: { work_item_id: auditId, case_id: c.case_id },
              headers: { "Idempotency-Key": `aud30-reissue-${c.case_id}` },
            });
          }}
        >
          {C.reopen}
        </Button>
      ) : null}
      <section aria-label={C.timeline} className="rounded-[12px] bg-card shadow-e1">
        <h3 className="px-[12px] pt-[10px] text-[13px] font-medium">{C.timeline}</h3>
        <Timeline label={C.timeline} events={events(c, additions, run, now)} />
      </section>
    </div>
  );
}

function NewCaseSheet({
  auditId,
  open,
  onClose,
}: {
  auditId: string;
  open: boolean;
  onClose: () => void;
}): JSX.Element {
  const queries = useQueryClient();
  const [type, setType] = useState<string>(FACTS);
  const [source, setSource] = useState<string>("inbox_evidence");
  const [text, setText] = useState("");
  const create = useMutation({
    ...postIssuanceCaseCreateMutation(),
    onSuccess: async () => {
      setText("");
      onClose();
      await queries.invalidateQueries();
    },
  });
  return (
    <SheetModal
      open={open}
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={C.sheet.title}
    >
      <form
        data-aud30="new-case"
        className="flex flex-col gap-[10px] p-[14px] text-[12.5px]"
        onSubmit={(e) => {
          e.preventDefault();
          if (text.trim() === "") return;
          create.mutate({
            path: { work_item_id: auditId },
            body: {
              type: type as PostIssuanceCaseOut["type"],
              source_kind: source as PostIssuanceCaseOut["source_kind"],
              description: text.trim(),
            },
            headers: { "Idempotency-Key": `aud30-new-${text.trim().length.toString()}` },
          });
        }}
      >
        <div className="flex flex-col gap-[4px]">
          <span className="text-ink-2">{C.sheet.type}</span>
          <Picker
            label={C.sheet.type}
            options={Object.entries(C.typeLine).map(([value, label]) => ({ value, label }))}
            value={type}
            onChange={setType}
          />
        </div>
        <div className="flex flex-col gap-[4px]">
          <span className="text-ink-2">{C.sheet.source}</span>
          <Picker
            label={C.sheet.source}
            options={Object.entries(C.sheet.sources).map(([value, label]) => ({ value, label }))}
            value={source}
            onChange={setSource}
          />
        </div>
        <label className="flex flex-col gap-[4px]">
          <span className="text-ink-2">{C.sheet.description}</span>
          <textarea
            aria-label={C.sheet.description}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
            }}
            className="h-[90px] rounded-nested bg-nested p-[8px]"
          />
        </label>
        <p className="text-[11.5px] text-ink-3">{C.sheet.note}</p>
        <div className="flex justify-end gap-[8px]">
          <Button variant="secondary" type="button" onClick={onClose}>
            {C.sheet.cancel}
          </Button>
          <Button
            variant="primary"
            type="submit"
            disabled={text.trim() === "" || create.isPending}
          >
            {C.sheet.open}
          </Button>
        </div>
      </form>
    </SheetModal>
  );
}

export function AUD30({
  auditId,
  view = "cases",
  onView,
  caseRef,
  onCase,
  newCase = false,
  onSection,
  onReissued,
  onBack,
}: AUD30Props): JSX.Element {
  const now = useNow();
  const cockpit = useAuditCockpit(auditId);
  const list = useQuery(postIssuanceCasesOptions({ path: { work_item_id: auditId } }));
  const added = useQuery(auditArchiveAdditionsOptions({ path: { work_item_id: auditId } }));
  const [tab, setTab] = useState<Aud30View>(view);
  const [selected, setSelected] = useState<string | undefined>(caseRef);
  const [sheet, setSheet] = useState(newCase);
  const [dockView, setDockView] = useState<"decision" | "viewer">("decision");
  const cases = list.data?.items ?? [];
  const additions = added.data?.items ?? [];
  const current =
    cases.find((c) => c.ref === selected) ??
    cases.find((c) => c.status === "under_evaluation") ??
    cases[0];
  const kept = useQuery({
    ...postIssuanceAnalysisReadOptions({
      path: { work_item_id: auditId, case_id: current?.case_id ?? "" },
    }),
    enabled: current?.analysis_run_id != null,
    retry: false,
  });
  const run = kept.data?.run_number ?? null;
  const state: ViewState = list.isError
    ? {
        kind: "error",
        retry: () => {
          void list.refetch();
        },
      }
    : list.data === undefined
      ? { kind: "loading" }
      : cases.length === 0 && tab === "cases"
        ? { kind: "empty" }
        : { kind: "ready" };
  const locked = list.data?.archive_locked_at;
  const reissuing = cases.some((c) => c.status === "reissue_in_progress");
  const bar =
    cockpit.data === undefined ? undefined : auditBarProps(cockpit.data, onBack ? { onBack } : {});
  const archivedWord = status("audit_engagement", "archived");
  const pick = (v: Aud30View): void => {
    setTab(v);
    onView?.(v);
  };
  return (
    <div data-screen="AUD-30" className="flex min-h-0 flex-1 flex-col">
      <RecordCockpit
        embedded
        {...(bar === undefined
          ? {}
          : {
              record: {
                ...bar,
                state: archivedWord.label,
                stateTone: archivedWord.variant ?? "neutral",
                right: (
                  <div data-aud30="bar-right" className="ml-auto flex items-center gap-[8px]">
                    {reissuing ? (
                      <Pill
                        variant={
                          status("post_issuance_case", "reissue_in_progress").variant ?? "red-tint"
                        }
                        size="sm"
                      >
                        {status("post_issuance_case", "reissue_in_progress").label}
                      </Pill>
                    ) : null}
                    {locked != null ? (
                      <span className="flex items-center gap-[4px] text-body text-ink-3">
                        <Icon name="lock" size={12} />
                        {C.lockedBar(date(locked, { now, withYear: true }))}
                      </span>
                    ) : null}
                  </div>
                ),
              },
            })}
        rail={
          cockpit.data === undefined ? null : (
            <SectionRail
              cockpit={cockpit.data}
              selected="post_issuance"
              onOpen={(row) => {
                if (row.key !== "post_issuance") onSection?.(row);
              }}
            />
          )
        }
        canvas={{
          title: C.title,
          actions: (
            <Button
              variant="secondary"
              size="sm"
              icon="plus"
              onClick={() => {
                setSheet(true);
              }}
            >
              {C.newCase}
            </Button>
          ),
          controls: (
            <Segmented
              size="small"
              label={C.tabsLabel}
              options={[
                { label: C.tabs.cases, count: cases.length },
                { label: C.tabs.additions, count: additions.length },
              ]}
              active={tab === "cases" ? C.tabs.cases : C.tabs.additions}
              onChange={(label) => {
                pick(label === C.tabs.cases ? "cases" : "additions");
              }}
            />
          ),
          well: true,
          state,
          empty: { title: C.empty },
          children:
            tab === "additions" ? (
              <AdditionsTable rows={additions} cases={cases} now={now} />
            ) : (
              <>
                <ul
                  data-aud30="cases"
                  className="m-[10px] overflow-hidden rounded-[12px] bg-card shadow-e1"
                >
                  {cases.map((c) => (
                    <CaseRow
                      key={c.case_id}
                      c={c}
                      now={now}
                      selected={current?.case_id === c.case_id}
                      onSelect={() => {
                        setSelected(c.ref);
                        setDockView("decision");
                        onCase?.(c.ref);
                      }}
                    />
                  ))}
                </ul>
                {current === undefined ? null : (
                  <CaseDetail
                    auditId={auditId}
                    c={current}
                    run={run}
                    now={now}
                    onSource={() => {
                      setDockView("viewer");
                    }}
                  />
                )}
              </>
            ),
        }}
        {...(current === undefined
          ? {}
          : {
              dock: {
                view: "Agent" as const,
                views: ["Agent"] as const,
                title: dockView === "viewer" ? C.kv.source : C.dock,
                children:
                  dockView === "viewer" ? (
                    <div className="flex min-h-0 flex-1 flex-col">
                      <Button
                        variant="tonal"
                        size="sm"
                        className="m-[10px] self-start"
                        onClick={() => {
                          setDockView("decision");
                        }}
                      >
                        {C.dock}
                      </Button>
                      <DockViewer versionId={current.source_evidence_version_id ?? null} />
                    </div>
                  ) : (
                    <DecisionDock
                      auditId={auditId}
                      c={current}
                      additions={additions}
                      run={run}
                      now={now}
                      {...(onReissued === undefined ? {} : { onReissued })}
                    />
                  ),
              },
            })}
      />
      <NewCaseSheet
        auditId={auditId}
        open={sheet}
        onClose={() => {
          setSheet(false);
        }}
      />
    </div>
  );
}
