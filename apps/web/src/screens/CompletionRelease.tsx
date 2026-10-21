import type { CompletionOut } from "@abacus/api-client";
import {
  approveReportMutation,
  completionStateOptions,
  completionStateQueryKey,
  concurEqrMutation,
  goingConcernMutation,
  listEvidenceVersionsOptions,
  lockArchiveMutation,
  meOptions,
  recordReportMutation,
  releaseReportMutation,
  repLetterMutation,
  teamOptions,
} from "@abacus/api-client/query";
import { Alert, Button, Skeleton, StatusPill, toast } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type ReactNode, useState } from "react";
import { errorMessage } from "../api";
import { blockerWord } from "./ReviewMatrix";

// SPEC-314 (TASK-332): completion, release and archive (A-07, record mode). The server builds
// the EQR digest and every gate fact by code; each step here is a named person's act: the EQR
// concurs (G6), the partner decides going concern, approves the report and releases (G8), the
// signed representation letter carries the report date (G7), and a manager or the partner locks
// and seals the archive (G9), after which the engagement is read-only.

const ITEM: Record<CompletionOut["checklist"][number]["key"], string> = {
  accepted: "Engagement accepted",
  independence: "Independence confirmed",
  engagement_letter: "Engagement letter",
  review_complete: "Review complete",
  eqr_concurred: "EQR concurred",
  going_concern: "Going concern decided",
  report_approved: "Report approved by the partner",
  rep_letter: "Representation letter dated the report date",
  released: "Report released",
  archived: "Archive locked",
};
const GOING_CONCERN: Record<string, string> = {
  no_substantial_doubt: "No substantial doubt",
  doubt_alleviated: "Substantial doubt alleviated by management's plans",
  doubt_exists: "Substantial doubt exists",
};
const OPINION: Record<string, string> = {
  unmodified: "Unmodified",
  qualified: "Qualified",
  adverse: "Adverse",
  disclaimer: "Disclaimer of opinion",
};
const RECORDERS = new Set(["engagement_partner", "manager", "senior"]);
const LOCKERS = new Set(["engagement_partner", "manager"]);

/** Fixed words for a server blocker code (never free text). */
export function completionBlocker(code: string): string {
  if (code.startsWith("G5:")) return blockerWord(code.slice(3));
  const words: Record<string, string> = {
    "G6:eqr_not_concurred": "The EQR hasn't concurred",
    "G6:eqr_digest_changed": "A judgment changed after the EQR concurred",
    "G7:no_report": "No report recorded",
    "G7:no_rep_letter": "No signed representation letter",
    "G7:rep_letter_date_mismatch": "The representation letter isn't dated the report date",
    going_concern_not_decided: "Going concern not decided",
    report_not_approved: "Report not approved by the partner",
    already_released: "Already released",
    not_released: "The report isn't released yet",
    already_locked: "Already locked",
  };
  return words[code] ?? code;
}

function Card({
  title,
  aside,
  children,
}: {
  title: string;
  aside?: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="flex flex-col rounded-pane bg-card shadow-e2">
      <div className="flex min-h-[46px] items-center gap-2 border-b-[0.5px] border-hair px-4">
        <h3 className="text-[14px] font-medium tracking-[-0.01em]">{title}</h3>
        <span className="flex-1" />
        {aside}
      </div>
      <div className="flex flex-col gap-2 p-4 text-[12.5px]">{children}</div>
    </section>
  );
}

export function CompletionRelease({ engagementId }: { engagementId: string }): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const state = useQuery({ ...completionStateOptions(path), retry: false });
  const team = useQuery({ ...teamOptions(path), retry: false });
  const me = useQuery(meOptions());
  const evidence = useQuery({ ...listEvidenceVersionsOptions(path), retry: false });
  const role = team.data?.find((m) => m.user_id === me.data?.user_id)?.role ?? "";
  const opts = {
    onSuccess: (data: CompletionOut) => {
      queryClient.setQueryData(completionStateQueryKey(path), data);
    },
    onError: (e: unknown) => {
      const code = errorMessage(e);
      toast.show(
        code === "not_the_eqr"
          ? "Only the assigned EQR can concur."
          : code === "already_released"
            ? "The report is already released; completion records can't change."
            : code === "forbidden"
              ? "Your role can't do that."
              : code.startsWith("completion_blocked")
                ? "Something still blocks this step."
                : code,
      );
    },
  };
  const concur = useMutation({ ...concurEqrMutation(), ...opts });
  const decide = useMutation({ ...goingConcernMutation(), ...opts });
  const report = useMutation({ ...recordReportMutation(), ...opts });
  const approve = useMutation({ ...approveReportMutation(), ...opts });
  const letter = useMutation({ ...repLetterMutation(), ...opts });
  const release = useMutation({ ...releaseReportMutation(), ...opts });
  const lock = useMutation({ ...lockArchiveMutation(), ...opts });
  const [notInvolved, setNotInvolved] = useState(false);
  const [gc, setGc] = useState("no_substantial_doubt");
  const [gcWhy, setGcWhy] = useState("");
  const [opinion, setOpinion] = useState("unmodified");
  const [emphasis, setEmphasis] = useState(false);
  const [reportDate, setReportDate] = useState("");
  const [reportDoc, setReportDoc] = useState("");
  const [letterDate, setLetterDate] = useState("");
  const [letterDoc, setLetterDoc] = useState("");
  const [attestRelease, setAttestRelease] = useState(false);
  const [attestLock, setAttestLock] = useState(false);
  if (state.isPending) return <Skeleton className="h-96" />;
  if (state.isError) {
    return <Alert title="Completion isn't available">{errorMessage(state.error)}</Alert>;
  }
  const s = state.data;
  const released = s.release != null;
  const partnerBasis = s.going_concern?.rationale; // the partner's words, not the agent's
  const isPartner = role === "engagement_partner";
  const docs = evidence.data ?? [];
  const docLabel = (id: string | null | undefined): string => {
    const v = docs.find((d) => d.id === id);
    return v === undefined ? "a document" : `${v.source}, version ${String(v.version_no)}`;
  };
  const input = "h-[28px] rounded-tile border-0 bg-nested px-2 inset-shadow-hair";
  const docPicker = (value: string, set: (v: string) => void, label: string) => (
    <select
      aria-label={label}
      value={value}
      onChange={(e) => {
        set(e.target.value);
      }}
      className={input}
    >
      <option value="">Choose the document…</option>
      {docs.map((d) => (
        <option key={d.id} value={d.id}>{`${d.source}, version ${String(d.version_no)}`}</option>
      ))}
    </select>
  );
  const done = s.checklist.filter((c) => c.applicable && c.done).length;
  const applicable = s.checklist.filter((c) => c.applicable).length;
  return (
    <div className="grid items-start gap-3 xl:grid-cols-[340px_1fr]">
      <Card
        title="Completion"
        aside={
          <span className="tabular-nums text-ink-3">{`${String(done)} of ${String(applicable)}`}</span>
        }
      >
        <ul aria-label="Completion checklist" className="flex flex-col gap-1.5">
          {s.checklist.map((c) => (
            <li key={c.key} className="flex items-start gap-2">
              <span
                aria-hidden="true"
                className={
                  "mt-[2px] inline-block size-[10px] shrink-0 rounded-full " +
                  (!c.applicable ? "bg-nested" : c.done ? "bg-green" : "bg-amber")
                }
              />
              <span className="flex flex-col">
                <span className={c.applicable ? "" : "text-ink-4"}>
                  {ITEM[c.key]}
                  {c.gate != null && (
                    <span className="ml-1.5 text-[11px] text-ink-3">{c.gate}</span>
                  )}
                  {!c.applicable && (
                    <span className="ml-1.5 text-[11px] text-ink-3">not required</span>
                  )}
                </span>
                {c.applicable &&
                  !c.done &&
                  c.key === "review_complete" &&
                  c.blockers.length > 0 && (
                    <span className="text-[11.5px] text-ink-3">
                      {blockerWord(c.blockers[0] ?? "")}
                    </span>
                  )}
              </span>
            </li>
          ))}
        </ul>
      </Card>
      <div className="flex flex-col gap-3">
        <Card
          title="Engagement quality review"
          aside={
            !s.eqr.required ? (
              <StatusPill tone="neutral">Not required</StatusPill>
            ) : s.eqr.concurrence?.current === true ? (
              <StatusPill tone="success">Concurred · G6</StatusPill>
            ) : s.eqr.concurrence != null ? (
              <StatusPill tone="warning">Changed since concurrence</StatusPill>
            ) : (
              <StatusPill tone="warning">Awaiting EQR</StatusPill>
            )
          }
        >
          {s.eqr.required && <p className="text-ink-3">{`EQR: ${s.eqr.eqr_names.join(", ")}`}</p>}
          <div className="grid gap-2 md:grid-cols-3">
            {s.eqr.digest.map((card) => (
              <div key={card.kind} className="rounded-nested bg-card p-2.5 shadow-e1">
                <p className="mb-1 font-medium">{card.title}</p>
                <dl className="flex flex-col gap-0.5">
                  {card.facts.map(([label, value]) => (
                    <div key={label} className="flex justify-between gap-2">
                      <dt className="text-ink-3">{label}</dt>
                      <dd className="tabular-nums">{value}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            ))}
          </div>
          <p className="text-[11.5px] text-ink-3">
            Built by code from the engagement's decided judgments.
          </p>
          {s.eqr.concurrence != null && (
            <p>{`Concurred by ${s.eqr.concurrence.by_name} · ${s.eqr.concurrence.at.slice(0, 10)}`}</p>
          )}
          {s.eqr.is_me && !released && s.eqr.concurrence?.current !== true && (
            <div className="flex flex-wrap items-center gap-2">
              <label className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={notInvolved}
                  onChange={(e) => {
                    setNotInvolved(e.target.checked);
                  }}
                />
                I was not involved in performing this engagement
              </label>
              <Button
                size="sm"
                disabled={!notInvolved || s.eqr.open_notes > 0 || concur.isPending}
                onClick={() => {
                  concur.mutate({ ...path, body: { not_involved: true } });
                }}
              >
                Concur
              </Button>
              {s.eqr.open_notes > 0 && (
                <span className="text-ink-3">{`Blocked: ${String(s.eqr.open_notes)} review notes not cleared`}</span>
              )}
            </div>
          )}
        </Card>
        <Card
          title="Going concern"
          aside={
            s.going_concern != null ? (
              <StatusPill tone="success">Decided</StatusPill>
            ) : (
              <StatusPill tone="warning">Open</StatusPill>
            )
          }
        >
          {s.going_concern != null && (
            <p>
              {`${GOING_CONCERN[s.going_concern.choice ?? ""] ?? ""} · ${s.going_concern.by_name}`}
              {partnerBasis != null && <span className="block text-ink-3">{partnerBasis}</span>}
            </p>
          )}
          {isPartner && !released ? (
            <div className="flex flex-col gap-1.5">
              {Object.entries(GOING_CONCERN).map(([code, word]) => (
                <label key={code} className="flex items-center gap-1.5">
                  <input
                    type="radio"
                    name="gc"
                    checked={gc === code}
                    onChange={() => {
                      setGc(code);
                    }}
                  />
                  {word}
                </label>
              ))}
              {gc !== "no_substantial_doubt" && (
                <textarea
                  aria-label="Going concern basis"
                  value={gcWhy}
                  maxLength={1000}
                  placeholder="The basis for the conclusion"
                  onChange={(e) => {
                    setGcWhy(e.target.value);
                  }}
                  className="h-[56px] rounded-tile border-0 bg-nested p-2 inset-shadow-hair"
                />
              )}
              <div>
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={
                    (gc !== "no_substantial_doubt" && gcWhy.trim() === "") || decide.isPending
                  }
                  onClick={() => {
                    decide.mutate({
                      ...path,
                      body: {
                        choice: gc as "no_substantial_doubt",
                        ...(gcWhy.trim() === "" ? {} : { rationale: gcWhy.trim() }),
                      },
                    });
                  }}
                >
                  {s.going_concern != null ? "Decide again" : "Decide"}
                </Button>
              </div>
            </div>
          ) : (
            s.going_concern == null && (
              <p className="text-ink-3">Reserved to the engagement partner.</p>
            )
          )}
        </Card>
        <Card
          title="Report"
          aside={
            s.report?.approved_by_name != null ? (
              <StatusPill tone="success">Approved</StatusPill>
            ) : s.report != null ? (
              <StatusPill tone="warning">Awaiting partner</StatusPill>
            ) : (
              <StatusPill tone="neutral">Not recorded</StatusPill>
            )
          }
        >
          {s.report != null && (
            <p>
              {`${OPINION[s.report.record.choice ?? ""] ?? ""} opinion${s.report.record.emphasis === true ? " with a going-concern paragraph" : ""} · dated ${s.report.record.document_date ?? ""} · ${docLabel(s.report.record.evidence_version_id)}`}
              {s.report.approved_by_name != null && (
                <span className="block text-ink-3">{`Approved by ${s.report.approved_by_name}`}</span>
              )}
            </p>
          )}
          {RECORDERS.has(role) && !released && (
            <div className="flex flex-wrap items-center gap-2">
              <select
                aria-label="Opinion"
                value={opinion}
                onChange={(e) => {
                  setOpinion(e.target.value);
                }}
                className={input}
              >
                {Object.entries(OPINION).map(([code, word]) => (
                  <option key={code} value={code}>
                    {word}
                  </option>
                ))}
              </select>
              <label className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={emphasis}
                  onChange={(e) => {
                    setEmphasis(e.target.checked);
                  }}
                />
                Going-concern paragraph
              </label>
              <input
                aria-label="Report date"
                type="date"
                value={reportDate}
                onChange={(e) => {
                  setReportDate(e.target.value);
                }}
                className={input}
              />
              {docPicker(reportDoc, setReportDoc, "Report document")}
              <Button
                size="sm"
                variant="secondary"
                disabled={reportDate === "" || reportDoc === "" || report.isPending}
                onClick={() => {
                  report.mutate({
                    ...path,
                    body: {
                      opinion: opinion as "unmodified",
                      emphasis,
                      report_date: reportDate,
                      evidence_version_id: reportDoc,
                    },
                  });
                }}
              >
                Record report
              </Button>
            </div>
          )}
          {isPartner && s.report != null && s.report.approved_by_name == null && !released && (
            <div>
              <Button
                size="sm"
                disabled={approve.isPending}
                onClick={() => {
                  approve.mutate({ ...path });
                }}
              >
                Approve report
              </Button>
            </div>
          )}
        </Card>
        <Card
          title="Representation letter"
          aside={
            s.checklist.find((c) => c.key === "rep_letter")?.done === true ? (
              <StatusPill tone="success">Dated the report date · G7</StatusPill>
            ) : s.rep_letter != null ? (
              <StatusPill tone="warning">Date doesn't match the report</StatusPill>
            ) : (
              <StatusPill tone="neutral">Not recorded</StatusPill>
            )
          }
        >
          {s.rep_letter != null && (
            <p>{`Signed letter dated ${s.rep_letter.document_date ?? ""} · ${docLabel(s.rep_letter.evidence_version_id)} · recorded by ${s.rep_letter.by_name}`}</p>
          )}
          {RECORDERS.has(role) && !released && (
            <div className="flex flex-wrap items-center gap-2">
              <input
                aria-label="Letter date"
                type="date"
                value={letterDate}
                onChange={(e) => {
                  setLetterDate(e.target.value);
                }}
                className={input}
              />
              {docPicker(letterDoc, setLetterDoc, "Signed letter")}
              <Button
                size="sm"
                variant="secondary"
                disabled={letterDate === "" || letterDoc === "" || letter.isPending}
                onClick={() => {
                  letter.mutate({
                    ...path,
                    body: { letter_date: letterDate, evidence_version_id: letterDoc },
                  });
                }}
              >
                Record signed letter
              </Button>
            </div>
          )}
        </Card>
        <Card
          title="Issuance & release"
          aside={
            released ? (
              <StatusPill tone="success">Released · G8</StatusPill>
            ) : (
              <StatusPill tone="neutral">Not released</StatusPill>
            )
          }
        >
          {s.release != null ? (
            <p>
              {`Released by ${s.release.released_by_name} · report dated ${s.release.report_date}`}
              <span className="block text-ink-3">{`Documentation completion due ${s.release.documentation_due} (60 days)`}</span>
            </p>
          ) : (
            <>
              {s.release_blockers.length > 0 && (
                <ul aria-label="What blocks release" className="flex flex-col gap-0.5 text-ink-2">
                  {s.release_blockers.map((b) => (
                    <li key={b}>{completionBlocker(b)}</li>
                  ))}
                </ul>
              )}
              {isPartner ? (
                <div className="flex flex-wrap items-center gap-2">
                  <label className="flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      checked={attestRelease}
                      onChange={(e) => {
                        setAttestRelease(e.target.checked);
                      }}
                    />
                    I am the engagement partner and I authorize release of this report
                  </label>
                  <Button
                    size="sm"
                    disabled={!s.can_release || !attestRelease || release.isPending}
                    onClick={() => {
                      release.mutate({ ...path, body: { attest: true } });
                    }}
                  >
                    Release report
                  </Button>
                </div>
              ) : (
                <p className="text-ink-3">Only the engagement partner can release this report.</p>
              )}
            </>
          )}
        </Card>
        <Card
          title="Assembly & archive"
          aside={
            s.archive != null ? (
              <StatusPill tone="success">Locked · G9</StatusPill>
            ) : (
              <StatusPill tone="neutral">Open</StatusPill>
            )
          }
        >
          {s.archive != null ? (
            <p>
              {`Locked by ${s.archive.locked_by_name} · seal ${s.archive.seal.slice(0, 4)}…${s.archive.seal.slice(-4)} · ${String(s.archive.leaf_count)} items sealed`}
              <span className="block text-ink-3">The engagement is archived and read-only.</span>
            </p>
          ) : (
            <>
              {s.lock_blockers.length > 0 && (
                <ul aria-label="What blocks the lock" className="flex flex-col gap-0.5 text-ink-2">
                  {s.lock_blockers.map((b) => (
                    <li key={b}>{completionBlocker(b)}</li>
                  ))}
                </ul>
              )}
              {LOCKERS.has(role) && (
                <div className="flex flex-wrap items-center gap-2">
                  <label className="flex items-center gap-1.5">
                    <input
                      type="checkbox"
                      checked={attestLock}
                      onChange={(e) => {
                        setAttestLock(e.target.checked);
                      }}
                    />
                    Assembly is complete
                  </label>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={!s.can_lock || !attestLock || lock.isPending}
                    onClick={() => {
                      lock.mutate({ ...path, body: { attest: true } });
                    }}
                  >
                    Lock archive
                  </Button>
                </div>
              )}
            </>
          )}
        </Card>
      </div>
    </div>
  );
}
