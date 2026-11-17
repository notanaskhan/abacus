// CLS-06 · Close › Review (C-01-T39; handoff CLS-06 a, a2, b, c, d, e, f, g; SPEC-655 F7): the
// severity-band queue with its detail beside the register, T9 close-review inside the close
// shell's Review tab. The queue is code's (`GET /v1/closes/{id}/issues`): open exceptions are
// Medium + Low (2 + 5 = 7 = the Review badge) and notes never count. Resolving is a person's
// (`issue.resolve`, the agent denied): an issue assigned to the Accrued Agent still offers Resolve
// only to a person who holds the grant, and Resolve stays disabled until the note is written.
import type { CloseIssueOut } from "@abacus/api-client";
import {
  closeIssuesOptions,
  closeReconciliationOptions,
  closeRegisterOptions,
} from "@abacus/api-client/query";
import {
  AgentText,
  Amount,
  Button,
  DASH,
  Dialog,
  Pill,
  Picker,
  Segmented,
  Skeleton,
  TallyPill,
  cn,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useId, useState } from "react";
import {
  ASSIGNEES,
  CLIENT_ANSWER,
  ISSUE_DETAIL,
  REVIEW_NOTES,
  RESOLVED_SHOPIFY,
} from "../kit-close-data";
import { COPY as C } from "./copy";

/** The person's grants as the server's allowed actions answer them (Raj holds issue.resolve). */
export const PERSON_GRANTS = ["issue.resolve"] as const;

export interface CLS06Props {
  closeId: string;
  initial?: {
    selected?: "soundElectric" | "check2281";
    tab?: "exceptions" | "notes";
    register?: "detail" | "reconciliation";
    resolving?: boolean;
    answered?: boolean;
    showResolved?: boolean;
  };
  grants?: readonly string[];
  onResolve?: (issueId: string, note: string) => void;
  onAskClient?: (issueId: string) => void;
  onOpen?: (target: "CLS-07" | "CLS-10") => void;
}

const ROW = "h-[30px] px-[8px] text-[12.5px]";

function money(v: string | null | undefined): JSX.Element {
  if (v == null) return <span className="text-ink-3">{DASH}</span>;
  return <Amount value={v} style="money" zero="explicit" />;
}

function QueueRow({
  issue,
  selected,
  onSelect,
}: {
  issue: CloseIssueOut;
  selected: boolean;
  onSelect: () => void;
}) {
  const detail = ISSUE_DETAIL[issue.issue_id];
  return (
    <li>
      <button
        type="button"
        data-issue={issue.issue_id}
        data-status={issue.status}
        aria-pressed={selected}
        onClick={onSelect}
        className={cn(
          "flex w-full gap-[9px] px-[12px] pt-[8px] pb-[9px] text-left hairline-t",
          selected && "bg-selected font-medium",
        )}
      >
        <span
          aria-hidden="true"
          className={issue.severity === "high" ? "text-red-ink" : "text-amber-ink"}
        >
          ⚑
        </span>
        <span className="flex flex-col">
          <span className="line-clamp-2 text-[12.5px]">{issue.title}</span>
          <span className="text-[11px] text-ink-3">
            {issue.status === "resolved" ? RESOLVED_SHOPIFY.meta : (detail?.sub ?? "")}
          </span>
        </span>
      </button>
    </li>
  );
}

function ResolveDialog({
  open,
  onOpenChange,
  held,
  initialNote,
  onResolve,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  held: boolean;
  initialNote: string;
  onResolve: (note: string) => void;
}): JSX.Element {
  const id = useId();
  const [note, setNote] = useState(initialNote);
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={C.dialog.title}
      {...(held ? { forceState: "open" as const } : {})}
      action={
        <Button
          variant="primary"
          disabled={note.trim() === ""}
          onClick={() => {
            onResolve(note.trim());
          }}
        >
          {C.dialog.confirm}
        </Button>
      }
    >
      <div data-cls06="resolve" className="flex flex-col gap-[8px] p-[16px]">
        <label htmlFor={id} className="text-[12.5px] text-ink-2">
          {C.dialog.note}
        </label>
        <textarea
          id={id}
          required
          value={note}
          maxLength={2000}
          onChange={(e) => {
            setNote(e.target.value);
          }}
          className="min-h-[88px] rounded-input bg-card p-[8px] text-cell inset-ring-[0.5px] inset-ring-stroke"
        />
        <p className="text-[11.5px] text-ink-3">{C.dialog.noteHelp}</p>
        <Button variant="secondary" size="sm">
          {C.dialog.evidence}
        </Button>
        <Button variant="secondary" size="sm">
          {C.dialog.propose}
        </Button>
      </div>
    </Dialog>
  );
}

export function CLS06({
  closeId,
  initial = {},
  grants = PERSON_GRANTS,
  onResolve,
  onAskClient,
  onOpen,
}: CLS06Props): JSX.Element {
  const issues = useQuery(
    closeIssuesOptions({
      path: { close_id: closeId },
      query: { include_resolved: initial.showResolved === true },
    }),
  );
  const [tab, setTab] = useState(initial.tab ?? "exceptions");
  const [registerView, setRegisterView] = useState(initial.register ?? "detail");
  const [resolving, setResolving] = useState(initial.resolving === true);
  const [assignee, setAssignee] = useState<string | null>(null);
  const data = issues.data;
  const open = (data?.items ?? []).filter(
    (i) => i.status === "open" || i.status === "reopened" || i.status === "in_progress",
  );
  const resolvedItems = (data?.items ?? []).filter((i) => i.status === "resolved");
  const defaultSelected =
    initial.selected === "check2281"
      ? open.find((i) => i.title.includes("#2281"))?.issue_id
      : (data?.items ?? []).find((i) => i.title.startsWith("Sound Electric"))?.issue_id;
  const [picked, setPicked] = useState<string | null>(null);
  const selectedId = picked ?? defaultSelected ?? null;
  const selected = (data?.items ?? []).find((i) => i.issue_id === selectedId);
  const detail = selected ? ISSUE_DETAIL[selected.issue_id] : undefined;
  const register = useQuery({
    ...closeRegisterOptions({ path: { close_id: closeId, account_ref: "35" } }),
    enabled: registerView === "detail",
  });
  const rec = useQuery({
    ...closeReconciliationOptions({ path: { close_id: closeId, account_ref: "35" } }),
    enabled: registerView === "reconciliation",
  });
  const canResolve = grants.includes("issue.resolve");
  const isResolved = selected?.status === "resolved";
  const who = assignee ?? detail?.assignee ?? "RM";
  return (
    <div data-screen="CLS-06" className="flex gap-[10px] bg-shell p-[12px]">
      <section
        aria-label={C.issues}
        className="flex w-[790px] flex-col rounded-pane bg-card shadow-e1"
      >
        <header className="flex h-[46px] items-center justify-between px-[12px]">
          <Picker
            label={C.picker}
            options={C.pickerOptions}
            value="issues"
            onChange={(v) => {
              if (v === "adjustments") onOpen?.("CLS-07");
              if (v === "flux") onOpen?.("CLS-10");
            }}
          />
          <h2 className="text-[14.5px] font-medium">{C.issues}</h2>
          <button type="button" className="text-[13.5px] text-ink-3">
            {C.showResolved}
          </button>
        </header>
        {data === undefined ? (
          <Skeleton className="m-[12px] h-[400px]" />
        ) : (
          <div className="flex min-h-0 flex-1">
            <div className="flex w-[310px] flex-col hairline-r">
              <div className="flex h-[40px] items-center justify-center">
                <Segmented
                  size="small"
                  label={C.tabLabel}
                  options={[C.tabs.exceptions(data.open), C.tabs.notes(data.notes)]}
                  active={
                    tab === "notes" ? C.tabs.notes(data.notes) : C.tabs.exceptions(data.open)
                  }
                  onChange={(l) => {
                    setTab(l.startsWith("Notes") ? "notes" : "exceptions");
                  }}
                />
              </div>
              {tab === "notes" ? (
                <ul data-cls06="notes">
                  {REVIEW_NOTES.map((n) => (
                    <li
                      key={n}
                      data-note=""
                      className="flex gap-[9px] px-[12px] pt-[8px] pb-[9px] hairline-t"
                    >
                      <span
                        aria-hidden="true"
                        className="mt-[2px] size-[13px] rounded-full inset-ring-[1px] inset-ring-ink-3"
                      />
                      <span className="flex flex-col">
                        <span className="text-[12.5px]">{n}</span>
                        <span className="text-[11px] text-ink-3">{C.evidenceOnly}</span>
                      </span>
                    </li>
                  ))}
                </ul>
              ) : open.length === 0 && resolvedItems.length === 0 ? (
                <div data-cls06="empty" className="p-[24px] text-center">
                  <p className="text-[13px] font-medium">{C.empty.title}</p>
                  <p className="text-[12px] text-ink-3">{C.empty.body}</p>
                </div>
              ) : (
                <div data-cls06="queue">
                  {(["high", "medium", "low"] as const).map((sev) => {
                    const band = open.filter((i) => i.severity === sev);
                    if (band.length === 0) return null;
                    return (
                      <section key={sev} aria-label={C.severity[sev]} data-band={sev}>
                        <h3 className="flex items-baseline gap-[6px] bg-nested px-[12px] pt-[8px] pb-[9px] text-[14px] font-normal">
                          {C.severity[sev]}{" "}
                          <span className="text-[12px] text-ink-3">{band.length}</span>
                        </h3>
                        <ul>
                          {band.map((i) => (
                            <QueueRow
                              key={i.issue_id}
                              issue={i}
                              selected={i.issue_id === selectedId}
                              onSelect={() => {
                                setPicked(i.issue_id);
                              }}
                            />
                          ))}
                        </ul>
                      </section>
                    );
                  })}
                  {initial.showResolved === true && resolvedItems.length > 0 && (
                    <section
                      aria-label={C.resolvedBand(resolvedItems.length)}
                      data-band="resolved"
                    >
                      <h3 className="bg-nested px-[12px] pt-[8px] pb-[9px] text-[14px] font-normal">
                        {C.resolvedBand(resolvedItems.length)}
                      </h3>
                      <ul>
                        {resolvedItems.map((i) => (
                          <QueueRow
                            key={i.issue_id}
                            issue={i}
                            selected={i.issue_id === selectedId}
                            onSelect={() => {
                              setPicked(i.issue_id);
                            }}
                          />
                        ))}
                      </ul>
                    </section>
                  )}
                </div>
              )}
            </div>
            <div className="flex w-[480px] flex-col" data-cls06="detail">
              {selected && detail ? (
                <>
                  <h3
                    className={cn(
                      "bg-shell px-[13px] pt-[11px] pb-[12px] text-[14.5px] font-medium",
                      isResolved && "text-ink-2",
                    )}
                  >
                    {selected.title} {isResolved && <Pill variant="green-tint">{C.resolved}</Pill>}
                  </h3>
                  {isResolved && selected.resolved_by && (
                    <p className="px-[13px] text-[12px] text-ink-3">
                      {C.resolvedBy(selected.resolved_by.name, "1:20 PM")}
                    </p>
                  )}
                  <dl className="text-[13px]">
                    <div className="flex h-[35px] items-center justify-between px-[13px]">
                      <dt className="text-ink-2">{C.fields.assigned}</dt>
                      <dd>
                        <Picker
                          label={C.fields.assigned}
                          options={ASSIGNEES}
                          value={who}
                          onChange={(v) => {
                            setAssignee(v);
                          }}
                        />
                      </dd>
                    </div>
                    <div className="flex h-[35px] items-center justify-between px-[13px]">
                      <dt className="text-ink-2">{C.fields.severity}</dt>
                      <dd className="font-medium">{C.severity[selected.severity]}</dd>
                    </div>
                    <div className="flex h-[35px] items-center justify-between px-[13px]">
                      <dt className="text-ink-2">{C.fields.status}</dt>
                      <dd className="font-medium">
                        {isResolved ? C.resolved : C.open}
                        {selected.waiting_on_client === true && (
                          <span className="ml-[6px] font-normal text-amber-ink">{C.waiting}</span>
                        )}
                      </dd>
                    </div>
                    <div className="flex h-[35px] items-center justify-between px-[13px]">
                      <dt className="text-ink-2">{C.fields.account}</dt>
                      <dd className="font-medium">{detail.account}</dd>
                    </div>
                  </dl>
                  {selected.why_surfaced && (
                    <>
                      <h4 className="flex h-[38px] items-center gap-[6px] bg-shell px-[13px] text-[13.5px] font-medium">
                        <span aria-hidden="true" className="text-green">
                          ✓
                        </span>
                        {C.why}
                      </h4>
                      <p className="px-[13px] py-[8px] text-[12.5px] text-ink-2">
                        <AgentText text={selected.why_surfaced} />
                      </p>
                    </>
                  )}
                  {detail.question && (
                    <div data-cls06="question" className="px-[13px] py-[8px]">
                      <h4 className="text-[13.5px] font-medium">{C.question}</h4>
                      <p className="text-[12.5px]">{detail.question.text}</p>
                      <p className="text-[11.5px] text-ink-3">{detail.question.meta}</p>
                      {initial.answered === true && (
                        <div
                          data-cls06="answer"
                          className="mt-[6px] rounded-nested bg-nested p-[8px] text-[12.5px]"
                        >
                          <p>{CLIENT_ANSWER.reply}</p>
                          <span className="text-[11.5px]">{CLIENT_ANSWER.attachment}</span>
                          <p className="mt-[4px] text-ink-2">
                            <AgentText text={CLIENT_ANSWER.agentNote} />
                          </p>
                        </div>
                      )}
                      <button type="button" className="text-[13px] font-medium">
                        {C.openThread} ›
                      </button>
                    </div>
                  )}
                  {detail.linked.length > 0 && (
                    <div className="px-[13px] py-[8px]">
                      <h4 className="text-[13.5px] font-medium">{C.linked}</h4>
                      <ul>
                        {detail.linked.map((l) => (
                          <li key={l.title} className="flex h-[46px] flex-col justify-center">
                            <span className="text-[13px]">{l.title}</span>
                            <span className="text-[11.5px] text-ink-3">{l.sub}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <footer className="mt-auto flex flex-col gap-[8px] p-[10px] hairline-t">
                    {isResolved ? (
                      <Button variant="secondary">{C.reopen}</Button>
                    ) : (
                      <>
                        {canResolve && (
                          <Button
                            variant="primary"
                            onClick={() => {
                              setResolving(true);
                            }}
                          >
                            {C.resolve}
                          </Button>
                        )}
                        {canResolve && <Button variant="secondary">{C.notApplicable}</Button>}
                        {registerView === "reconciliation" && (
                          <Button
                            variant="secondary"
                            onClick={() => onAskClient?.(selected.issue_id)}
                          >
                            {C.askClient}
                          </Button>
                        )}
                      </>
                    )}
                  </footer>
                </>
              ) : null}
            </div>
          </div>
        )}
      </section>
      <section
        aria-label={C.register}
        className="flex w-[576px] flex-col rounded-pane bg-card shadow-e1"
      >
        <header className="flex h-[46px] items-center justify-center text-[14.5px] font-medium">
          {C.register}
        </header>
        <div className="flex h-[54px] items-center justify-center">
          <Segmented
            size="small"
            label={C.registerLabel}
            options={[C.registerViews.detail, C.registerViews.reconciliation]}
            active={
              registerView === "detail" ? C.registerViews.detail : C.registerViews.reconciliation
            }
            onChange={(l) => {
              setRegisterView(l === C.registerViews.detail ? "detail" : "reconciliation");
            }}
          />
        </div>
        {registerView === "detail" ? (
          <table className="w-full" data-cls06="register">
            <thead>
              <tr>
                {C.registerColumns.map((h, i) => (
                  <th
                    key={h}
                    scope="col"
                    className={cn(
                      ROW,
                      "bg-nested font-normal text-ink-2",
                      i === 5 ? "text-right" : "text-left",
                    )}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(register.data?.items ?? []).map((r) => (
                <tr
                  key={r.line_ref}
                  data-register-line={r.line_ref}
                  data-selected={selected?.register_line_ref === r.line_ref ? "" : undefined}
                  className={cn(
                    "hairline-b",
                    selected?.register_line_ref === r.line_ref && "bg-selected font-medium",
                  )}
                >
                  <td className={ROW}>{r.txn_date}</td>
                  <td className={ROW}>{r.txn_type ?? DASH}</td>
                  <td className={ROW}>
                    {selected?.register_line_ref === r.line_ref ? "⚑ " : ""}
                    {r.category ?? DASH}
                  </td>
                  <td className={ROW}>{r.payee ?? DASH}</td>
                  <td className={ROW}>{r.memo ?? DASH}</td>
                  <td className={cn(ROW, "text-right")}>{money(r.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <div data-cls06="inline-rec" className="px-[12px] text-[12.5px]">
            {rec.data && (
              <p className="flex items-center gap-[8px]">
                {C.differenceRow} {money(rec.data.difference)}
                {rec.data.tally === "tie" && <TallyPill code="tie" />}
              </p>
            )}
          </div>
        )}
      </section>
      {selected && (
        <ResolveDialog
          key={`${selected.issue_id}:${String(initial.answered === true)}`}
          open={resolving && canResolve}
          onOpenChange={setResolving}
          held={initial.resolving === true}
          initialNote={initial.answered === true ? CLIENT_ANSWER.agentNote : ""}
          onResolve={(note) => {
            onResolve?.(selected.issue_id, note);
            setResolving(false);
          }}
        />
      )}
    </div>
  );
}
