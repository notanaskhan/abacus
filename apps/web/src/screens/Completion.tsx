import type { AdjustmentIn, AdjustmentOut, FindingOut, LineBody } from "@abacus/api-client";
import {
  addRepresentationMutation,
  adjustmentsOptions,
  adjustmentsQueryKey,
  approveAdjustmentMutation,
  clientAnswerMutation,
  communicatedMutation,
  concludeSeverityMutation,
  findingsQueryKey,
  proposeAdjustmentMutation,
  proposeSeverityMutation,
  removeRepresentationMutation,
  representationsOptions,
  representationsQueryKey,
} from "@abacus/api-client/query";
import {
  Alert,
  Badge,
  Button,
  type Column,
  DataTable,
  EmptyState,
  Fieldset,
  Sheet,
  Skeleton,
  StatusPill,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";

// SPEC-301 (TASK-302): deficiency severity (the partner concludes), proposed entries (debits
// equal credits, checked by the server) and the representation list. The firm never posts.

type Severity = "deficiency" | "significant_deficiency" | "material_weakness";

export const SEVERITY: Record<Severity, string> = {
  deficiency: "Deficiency",
  significant_deficiency: "Significant deficiency",
  material_weakness: "Material weakness",
};

const ENTRY_STATUS: Record<
  AdjustmentOut["status"],
  { label: string; tone: "neutral" | "info" | "success" | "warning" }
> = {
  proposed: { label: "Proposed", tone: "neutral" },
  approved: { label: "Approved · with the client", tone: "info" },
  client_accepted: { label: "Accepted by the client", tone: "success" },
  client_declined: { label: "Passed", tone: "warning" },
};

const PROPOSERS = new Set(["engagement_partner", "manager", "senior"]);
const APPROVERS = new Set(["engagement_partner", "manager"]);

function amount(value: string | number): string {
  return Number(value).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

const field =
  "h-[30px] rounded-tile border-0 bg-nested px-2.5 text-[13px] inset-shadow-hair focus:bg-card";

export function SeverityBadge({ finding }: { finding: FindingOut }): JSX.Element | null {
  const d = finding.deficiency;
  if (d == null) return null;
  if (d.concluded != null)
    return (
      <Badge tone={d.concluded === "deficiency" ? "warning" : "danger"}>
        {SEVERITY[d.concluded]}
      </Badge>
    );
  return <Badge tone="neutral">{`${SEVERITY[d.proposed ?? "deficiency"]} · proposed`}</Badge>;
}

/** The finding drawer's severity section (AC-1 to AC-3). */
export function DeficiencyFieldset({
  engagementId,
  finding,
  role,
}: {
  engagementId: string;
  finding: FindingOut;
  role: string;
}): JSX.Element {
  const queryClient = useQueryClient();
  const d = finding.deficiency;
  const path = { path: { engagement_id: engagementId, finding_id: finding.id } };
  const [severity, setSeverity] = useState<Severity>(d?.concluded ?? d?.proposed ?? "deficiency");
  const [why, setWhy] = useState("");
  const [on, setOn] = useState(new Date().toISOString().slice(0, 10));
  const [to, setTo] = useState("");
  const done = (message: string) => (data: FindingOut[]) => {
    queryClient.setQueryData(findingsQueryKey({ path: { engagement_id: engagementId } }), data);
    setWhy("");
    toast.show(message);
  };
  const propose = useMutation({
    ...proposeSeverityMutation(),
    onSuccess: done("Severity proposed"),
  });
  const conclude = useMutation({
    ...concludeSeverityMutation(),
    onSuccess: done("Severity concluded"),
  });
  const told = useMutation({
    ...communicatedMutation(),
    onSuccess: done("Communication recorded"),
  });
  const isPartner = role === "engagement_partner";
  const error = propose.error ?? conclude.error ?? told.error;
  return (
    <Fieldset title="Deficiency (AU-C 265)">
      {d != null && (
        <dl className="mb-3 flex flex-col gap-1 text-[12.5px]">
          {d.proposed != null && (
            <div className="flex gap-2">
              <dt className="w-[92px] text-ink-3">Proposed</dt>
              <dd>{`${SEVERITY[d.proposed]} · ${d.proposed_by_name ?? ""}`}</dd>
            </div>
          )}
          {d.concluded != null && (
            <div className="flex gap-2">
              <dt className="w-[92px] text-ink-3">Concluded</dt>
              <dd>
                {`${SEVERITY[d.concluded]} · ${d.concluded_by_name ?? ""}`}
                {d.conclusion_rationale != null && (
                  <span className="block text-ink-2">{d.conclusion_rationale}</span>
                )}
              </dd>
            </div>
          )}
          {d.communicated_on != null && (
            <div className="flex gap-2">
              <dt className="w-[92px] text-ink-3">Communicated</dt>
              <dd>{`${d.communicated_on} · ${d.communicated_to ?? ""}`}</dd>
            </div>
          )}
        </dl>
      )}
      {PROPOSERS.has(role) ? (
        <div className="flex flex-col gap-2 text-[13px]">
          <label className="flex items-center justify-between gap-3">
            Severity
            <select
              value={severity}
              onChange={(e) => {
                setSeverity(e.target.value as Severity);
              }}
              className={field}
            >
              {Object.entries(SEVERITY).map(([k, v]) => (
                <option key={k} value={k}>
                  {v}
                </option>
              ))}
            </select>
          </label>
          <textarea
            aria-label="Severity rationale"
            value={why}
            maxLength={2000}
            placeholder={
              isPartner
                ? "Why (required to conclude): magnitude, likelihood, compensating controls"
                : "Why (optional)"
            }
            onChange={(e) => {
              setWhy(e.target.value);
            }}
            className="min-h-[64px] w-full rounded-tile border-0 bg-nested p-2.5 text-[13px] inset-shadow-hair focus:bg-card"
          />
          <div className="flex justify-end gap-2">
            <Button
              size="sm"
              variant={isPartner ? "outline" : "default"}
              disabled={propose.isPending}
              onClick={() => {
                propose.mutate({
                  ...path,
                  body: why.trim() === "" ? { severity } : { severity, rationale: why },
                });
              }}
            >
              Propose severity
            </Button>
            {isPartner && (
              <Button
                size="sm"
                disabled={why.trim() === "" || conclude.isPending}
                onClick={() => {
                  conclude.mutate({ ...path, body: { severity, rationale: why } });
                }}
              >
                Conclude severity
              </Button>
            )}
          </div>
          {!isPartner && (
            <p className="text-[11.5px] text-ink-3">Only the engagement partner concludes.</p>
          )}
        </div>
      ) : d == null ? (
        <p className="text-[12.5px] text-ink-2">No severity proposed.</p>
      ) : null}
      {d?.concluded != null && APPROVERS.has(role) && d.status !== "communicated" && (
        <div className="mt-3 flex flex-wrap items-center gap-2 border-t-[0.5px] border-hair pt-3 text-[13px]">
          <input
            type="date"
            aria-label="Communicated on"
            value={on}
            onChange={(e) => {
              setOn(e.target.value);
            }}
            className={field}
          />
          <input
            aria-label="Communicated to"
            value={to}
            maxLength={300}
            placeholder="To whom, for example the audit committee"
            onChange={(e) => {
              setTo(e.target.value);
            }}
            className={`${field} flex-1`}
          />
          <Button
            size="sm"
            variant="outline"
            disabled={to.trim() === "" || on === "" || told.isPending}
            onClick={() => {
              told.mutate({ ...path, body: { communicated_on: on, recipients: to } });
            }}
          >
            Record communication
          </Button>
        </div>
      )}
      {error != null && <p className="mt-2 text-meta text-danger">{errorMessage(error)}</p>}
    </Fieldset>
  );
}

export function Adjustments({
  engagementId,
  role,
  findings,
}: {
  engagementId: string;
  role: string;
  findings: FindingOut[];
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const entries = useQuery({ ...adjustmentsOptions(path), retry: false });
  const [creating, setCreating] = useState(false);
  const store = (data: AdjustmentOut[]): void => {
    queryClient.setQueryData(adjustmentsQueryKey(path), data);
    void queryClient.invalidateQueries({ queryKey: representationsQueryKey(path) });
  };
  const approve = useMutation({
    ...approveAdjustmentMutation(),
    onSuccess: (data) => {
      store(data);
      toast.show("Entry approved");
    },
  });
  const answer = useMutation({
    ...clientAnswerMutation(),
    onSuccess: (data) => {
      store(data);
      toast.show("Client's answer recorded");
    },
  });
  if (entries.isPending) return <Skeleton className="h-40" />;
  if (entries.isError)
    return <Alert title="Entries aren't available">{errorMessage(entries.error)}</Alert>;
  const rows = entries.data;
  const titles = new Map(findings.map((f) => [f.id, f.title]));
  const at = (a: AdjustmentOut) => ({
    path: { engagement_id: engagementId, adjustment_id: a.id },
  });
  const columns: Column<AdjustmentOut>[] = [
    {
      key: "ref",
      header: "",
      cell: (a) => <span className="font-mono text-[12px] text-ink-3">{a.ref}</span>,
      sortValue: (a) => a.ref,
    },
    {
      key: "description",
      header: "Entry",
      cell: (a) => (
        <span className="flex flex-col">
          <span className="font-medium">{a.description}</span>
          <span className="text-[11.5px] text-ink-3 tabular-nums">
            {a.lines
              .map((l) =>
                Number(l.debit) > 0
                  ? `Dr ${l.account_code} ${amount(l.debit)}`
                  : `Cr ${l.account_code} ${amount(l.credit)}`,
              )
              .join(" · ")}
            {a.finding_id != null && titles.has(a.finding_id)
              ? ` · ${titles.get(a.finding_id) ?? ""}`
              : ""}
          </span>
        </span>
      ),
    },
    {
      key: "total",
      header: "Amount",
      align: "right",
      cell: (a) => <span className="tabular-nums">{amount(a.total)}</span>,
      sortValue: (a) => Number(a.total),
    },
    {
      key: "status",
      header: "Status",
      cell: (a) => (
        <StatusPill tone={ENTRY_STATUS[a.status].tone}>{ENTRY_STATUS[a.status].label}</StatusPill>
      ),
    },
    {
      key: "act",
      header: "",
      align: "right",
      cell: (a) =>
        !APPROVERS.has(role) ? null : a.status === "proposed" ? (
          <Button
            size="sm"
            variant="outline"
            disabled={approve.isPending}
            onClick={() => {
              approve.mutate(at(a));
            }}
          >
            Approve
          </Button>
        ) : a.status === "approved" ? (
          <span className="flex justify-end gap-1.5">
            <Button
              size="sm"
              variant="outline"
              disabled={answer.isPending}
              onClick={() => {
                answer.mutate({ ...at(a), body: { accepted: true } });
              }}
            >
              Client accepted
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={answer.isPending}
              onClick={() => {
                answer.mutate({ ...at(a), body: { accepted: false } });
              }}
            >
              Declined · pass
            </Button>
          </span>
        ) : null,
    },
  ];
  const passed = rows.filter((a) => a.status === "client_declined");
  return (
    <section
      aria-labelledby="aje-heading"
      className="flex flex-col overflow-hidden rounded-pane bg-card shadow-e2"
    >
      <div className="flex min-h-[50px] items-center gap-2 border-b-[0.5px] border-hair px-4">
        <h2 id="aje-heading" className="text-[15px] font-medium tracking-[-0.012em]">
          Proposed entries
        </h2>
        <span className="text-[12.5px] text-ink-3 tabular-nums">
          {[
            `${String(rows.length)} entries`,
            ...(passed.length > 0 ? [`${String(passed.length)} passed`] : []),
          ].join(" · ")}
        </span>
        <span className="flex-1" />
        {PROPOSERS.has(role) && (
          <Button
            size="sm"
            onClick={() => {
              setCreating(true);
            }}
          >
            Propose entry
          </Button>
        )}
      </div>
      {(approve.isError || answer.isError) && (
        <p className="px-4 pt-2 text-meta text-danger">
          {errorMessage(approve.error ?? answer.error)}
        </p>
      )}
      {rows.length === 0 ? (
        <EmptyState title="No proposed entries">
          Propose an adjusting (AJE) or reclassifying (RJE) entry. The client books it; the firm
          never posts.
        </EmptyState>
      ) : (
        <DataTable label="Proposed entries" rows={rows} columns={columns} rowKey={(a) => a.id} />
      )}
      {creating && (
        <NewEntry
          engagementId={engagementId}
          findings={findings}
          onDone={store}
          onClose={() => {
            setCreating(false);
          }}
        />
      )}
    </section>
  );
}

function NewEntry({
  engagementId,
  findings,
  onDone,
  onClose,
}: {
  engagementId: string;
  findings: FindingOut[];
  onDone: (data: AdjustmentOut[]) => void;
  onClose: () => void;
}): JSX.Element {
  const [kind, setKind] = useState<AdjustmentIn["kind"]>("aje");
  const [description, setDescription] = useState("");
  const [findingId, setFindingId] = useState("");
  const [lines, setLines] = useState<LineBody[]>([
    { account_code: "", debit: "", credit: "" },
    { account_code: "", debit: "", credit: "" },
  ]);
  const propose = useMutation({
    ...proposeAdjustmentMutation(),
    onSuccess: (data) => {
      onDone(data);
      toast.show("Entry proposed");
      onClose();
    },
  });
  const cents = (v: string | number | undefined): number => Math.round(Number(v ?? 0) * 100);
  const debits = lines.reduce((t, l) => t + cents(l.debit), 0);
  const credits = lines.reduce((t, l) => t + cents(l.credit), 0);
  const oneSided = lines.every(
    (l) => l.account_code.trim() !== "" && cents(l.debit) > 0 !== cents(l.credit) > 0,
  );
  const balanced = debits > 0 && debits === credits;
  const valid = description.trim() !== "" && oneSided && balanced;
  const set = (i: number, patch: Partial<LineBody>): void => {
    setLines(lines.map((l, j) => (j === i ? { ...l, ...patch } : l)));
  };
  return (
    <Sheet
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title="Propose entry"
      footer={
        <Button
          disabled={!valid || propose.isPending}
          onClick={() => {
            propose.mutate({
              path: { engagement_id: engagementId },
              body: {
                kind,
                description,
                ...(findingId === "" ? {} : { finding_id: findingId }),
                lines: lines.map((l) => ({
                  account_code: l.account_code.trim(),
                  debit: String(Number(l.debit || 0)),
                  credit: String(Number(l.credit || 0)),
                })),
              },
            });
          }}
        >
          Propose entry
        </Button>
      }
    >
      <Fieldset title="Entry">
        <div className="flex flex-col gap-2 text-[13px]">
          <label className="flex items-center justify-between gap-3">
            Kind
            <select
              value={kind}
              onChange={(e) => {
                setKind(e.target.value as AdjustmentIn["kind"]);
              }}
              className={field}
            >
              <option value="aje">Adjusting (AJE)</option>
              <option value="rje">Reclassifying (RJE)</option>
            </select>
          </label>
          <input
            aria-label="Entry description"
            value={description}
            maxLength={500}
            placeholder="What the entry corrects"
            onChange={(e) => {
              setDescription(e.target.value);
            }}
            className={`${field} w-full`}
          />
          {findings.length > 0 && (
            <label className="flex items-center justify-between gap-3">
              Finding
              <select
                value={findingId}
                onChange={(e) => {
                  setFindingId(e.target.value);
                }}
                className={`${field} max-w-[240px]`}
              >
                <option value="">None</option>
                {findings.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.title}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
      </Fieldset>
      <Fieldset title="Lines">
        <div className="flex flex-col gap-1.5 text-[13px]">
          <div className="grid grid-cols-[1fr_110px_110px_24px] gap-1.5 text-[11.5px] text-ink-3">
            <span>Account</span>
            <span className="text-right">Debit</span>
            <span className="text-right">Credit</span>
            <span />
          </div>
          {lines.map((l, i) => (
            <div key={i} className="grid grid-cols-[1fr_110px_110px_24px] gap-1.5">
              <input
                aria-label={`Line ${String(i + 1)} account`}
                value={l.account_code}
                maxLength={64}
                onChange={(e) => {
                  set(i, { account_code: e.target.value });
                }}
                className={field}
              />
              <input
                aria-label={`Line ${String(i + 1)} debit`}
                inputMode="decimal"
                value={l.debit ?? ""}
                onChange={(e) => {
                  set(i, { debit: e.target.value });
                }}
                className={`${field} text-right tabular-nums`}
              />
              <input
                aria-label={`Line ${String(i + 1)} credit`}
                inputMode="decimal"
                value={l.credit ?? ""}
                onChange={(e) => {
                  set(i, { credit: e.target.value });
                }}
                className={`${field} text-right tabular-nums`}
              />
              <button
                type="button"
                aria-label={`Remove line ${String(i + 1)}`}
                disabled={lines.length <= 2}
                onClick={() => {
                  setLines(lines.filter((_, j) => j !== i));
                }}
                className="text-ink-3 disabled:opacity-30"
              >
                ×
              </button>
            </div>
          ))}
          <div className="mt-1 flex items-center justify-between">
            <Button
              size="sm"
              variant="ghost"
              disabled={lines.length >= 50}
              onClick={() => {
                setLines([...lines, { account_code: "", debit: "", credit: "" }]);
              }}
            >
              Add line
            </Button>
            <span
              className={`text-[12px] tabular-nums ${balanced ? "text-ink-3" : "text-danger"}`}
            >
              {balanced
                ? `Balanced · ${amount(debits / 100)}`
                : `Debits ${amount(debits / 100)} · credits ${amount(credits / 100)}`}
            </span>
          </div>
        </div>
      </Fieldset>
      {propose.isError && <p className="text-meta text-danger">{errorMessage(propose.error)}</p>}
    </Sheet>
  );
}

export function Representations({
  engagementId,
  role,
}: {
  engagementId: string;
  role: string;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const list = useQuery({ ...representationsOptions(path), retry: false });
  const [draft, setDraft] = useState("");
  const [about, setAbout] = useState<{ kind: "finding" | "adjustment"; id: string } | null>(null);
  const add = useMutation({
    ...addRepresentationMutation(),
    onSuccess: (data) => {
      queryClient.setQueryData(representationsQueryKey(path), data);
      setDraft("");
      setAbout(null);
      toast.show("Representation added");
    },
  });
  const remove = useMutation({
    ...removeRepresentationMutation(),
    onSuccess: (data) => {
      queryClient.setQueryData(representationsQueryKey(path), data);
      toast.show("Taken off the list");
    },
  });
  if (list.isPending) return <Skeleton className="h-40" />;
  if (list.isError)
    return <Alert title="The list isn't available">{errorMessage(list.error)}</Alert>;
  const { items, passed, gaps } = list.data;
  const canEdit = PROPOSERS.has(role);
  return (
    <section
      aria-labelledby="rep-heading"
      className="flex flex-col overflow-hidden rounded-pane bg-card shadow-e2"
    >
      <div className="flex min-h-[50px] items-center gap-2 border-b-[0.5px] border-hair px-4">
        <h2 id="rep-heading" className="text-[15px] font-medium tracking-[-0.012em]">
          Specific representations
        </h2>
        <span className="text-[12.5px] text-ink-3 tabular-nums">{items.length}</span>
      </div>
      <div className="flex flex-col gap-3 p-4">
        {gaps.length > 0 && (
          <div className="flex flex-col gap-1.5 rounded-nested bg-shell px-3 py-2.5">
            <p className="text-[12px] text-ink-3">Not yet covered by a representation</p>
            <div className="flex flex-wrap gap-1.5">
              {gaps.map((g) => (
                <button
                  key={g.id}
                  type="button"
                  disabled={!canEdit}
                  onClick={() => {
                    setAbout({ kind: g.kind, id: g.id });
                  }}
                  className={`rounded-[var(--radius-badge)] px-2 py-0.5 text-[12px] inset-shadow-hair ${about?.id === g.id ? "bg-sel-bg" : "bg-card"}`}
                >
                  {g.kind === "finding" ? `Deficiency: ${g.label}` : `Passed entry ${g.label}`}
                </button>
              ))}
            </div>
          </div>
        )}
        {items.length === 0 ? (
          <p className="text-[12.5px] text-ink-2">No specific representations yet.</p>
        ) : (
          <ol className="flex list-decimal flex-col gap-2 pl-5 text-[13px] leading-[1.5]">
            {items.map((r) => (
              <li key={r.id}>
                <span className="flex items-start gap-2">
                  <span className="flex-1 whitespace-pre-line">{r.body}</span>
                  {canEdit && (
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={remove.isPending}
                      onClick={() => {
                        remove.mutate({
                          path: { engagement_id: engagementId, representation_id: r.id },
                        });
                      }}
                    >
                      Remove
                    </Button>
                  )}
                </span>
                <span className="text-[11.5px] text-ink-3">{r.raised_by_name}</span>
              </li>
            ))}
          </ol>
        )}
        {passed.length > 0 && (
          <p className="text-[12.5px] text-ink-2">
            {`Attached: the summary of uncorrected misstatements, including passed entries ${passed.join(", ")}.`}
          </p>
        )}
        {canEdit && (
          <div className="flex flex-col gap-2 border-t-[0.5px] border-hair pt-3">
            <textarea
              aria-label="New representation"
              value={draft}
              maxLength={2000}
              placeholder={
                about === null
                  ? "A specific representation management will make"
                  : "The representation covering the selected item"
              }
              onChange={(e) => {
                setDraft(e.target.value);
              }}
              className="min-h-[72px] w-full rounded-tile border-0 bg-nested p-2.5 text-[13px] inset-shadow-hair focus:bg-card"
            />
            <div className="flex justify-end gap-2">
              {about !== null && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setAbout(null);
                  }}
                >
                  Clear link
                </Button>
              )}
              <Button
                size="sm"
                disabled={draft.trim() === "" || add.isPending}
                onClick={() => {
                  add.mutate({
                    ...path,
                    body: {
                      body: draft,
                      ...(about?.kind === "finding" ? { finding_id: about.id } : {}),
                      ...(about?.kind === "adjustment" ? { adjustment_id: about.id } : {}),
                    },
                  });
                }}
              >
                Add representation
              </Button>
            </div>
          </div>
        )}
        {(add.isError || remove.isError) && (
          <p className="text-meta text-danger">{errorMessage(add.error ?? remove.error)}</p>
        )}
      </div>
    </section>
  );
}
