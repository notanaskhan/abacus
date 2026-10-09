import type { SetupOut } from "@abacus/api-client";
import {
  acceptanceMutation,
  independenceMutation,
  letterMutation,
  meOptions,
  setupOptions,
  setupQueryKey,
} from "@abacus/api-client/query";
import { Alert, Button, Input, Label, Panel, Skeleton, StatusPill } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type SyntheticEvent, useState } from "react";
import { errorMessage } from "../api";
import { ConfirmItsYou, isForbidden } from "../shell/mfa";

const LETTER_LABEL: Record<string, string> = {
  not_started: "Not started",
  sent: "Sent to the client",
  signed: "Signed",
  not_required_this_year: "Not required this year",
};
const SELECT = "h-9 rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm";

function when(value: string | null | undefined): string {
  return value == null ? "" : new Date(value).toLocaleDateString();
}

/** SPEC-025 AC-4 to AC-6: acceptance, the letter and independence for one engagement. Recorded
 * here; the procedures themselves live in the firm's methodology and tools. */
export function EngagementRecords({
  engagementId,
  role,
}: {
  engagementId: string;
  role: string | null;
}): JSX.Element {
  const setup = useQuery({
    ...setupOptions({ path: { engagement_id: engagementId } }),
    retry: false,
  });
  if (setup.isPending) return <Skeleton className="h-40" />;
  if (setup.isError) {
    return (
      <Alert title="Couldn't load acceptance and independence">{errorMessage(setup.error)}</Alert>
    );
  }
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <AcceptancePanel
        engagementId={engagementId}
        data={setup.data}
        isPartner={role === "engagement_partner"}
      />
      <div className="flex flex-col gap-4">
        <IndependencePanel engagementId={engagementId} data={setup.data} />
        <LetterPanel
          engagementId={engagementId}
          data={setup.data}
          canRecord={role === "engagement_partner" || role === "manager"}
        />
      </div>
    </div>
  );
}

function useRefresh(engagementId: string): () => void {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({
      queryKey: setupQueryKey({ path: { engagement_id: engagementId } }),
    });
  };
}

function AcceptancePanel({
  engagementId,
  data,
  isPartner,
}: {
  engagementId: string;
  data: SetupOut;
  isPartner: boolean;
}): JSX.Element {
  const refresh = useRefresh(engagementId);
  const a = data.acceptance;
  const [editing, setEditing] = useState(false);
  const [decision, setDecision] = useState<"accepted" | "declined">("accepted");
  const [documented, setDocumented] = useState(a?.documented_at ?? "");
  const [predecessor, setPredecessor] = useState(a?.predecessor_auditor ?? "");
  const [communicated, setCommunicated] = useState(a?.predecessor_communicated_on ?? "");
  const [concluded, setConcluded] = useState(a?.independence_concluded_at != null);
  const [concludedAt, setConcludedAt] = useState(a?.independence_documented_at ?? "");
  const [confirm, setConfirm] = useState(false);
  const save = useMutation({
    ...acceptanceMutation(),
    onSuccess: () => {
      setEditing(false);
      refresh();
    },
    onError: (error) => {
      if (isForbidden(error)) setConfirm(true);
    },
  });
  const isNew = a?.kind === "new_client" || a === null;
  const submit = (event: SyntheticEvent): void => {
    event.preventDefault();
    save.mutate({
      path: { engagement_id: engagementId },
      body: {
        decision,
        documented_at: documented,
        ...(predecessor.trim() !== "" ? { predecessor_auditor: predecessor } : {}),
        ...(communicated !== "" ? { predecessor_communicated_on: communicated } : {}),
        independence_concluded: concluded,
        ...(concluded && concludedAt.trim() !== ""
          ? { independence_documented_at: concludedAt }
          : {}),
      },
    });
  };
  return (
    <Panel
      title="Acceptance and independence conclusion"
      action={
        isPartner && !editing ? (
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setEditing(true);
            }}
          >
            {a === null ? "Record" : "Update"}
          </Button>
        ) : undefined
      }
    >
      {a === null ? (
        <p className="text-sm text-muted">
          Not recorded yet. The engagement partner records the acceptance or continuance decision
          and their independence conclusion.
        </p>
      ) : (
        <dl className="grid grid-cols-[11rem_1fr] gap-x-3 gap-y-1 text-sm">
          <dt className="text-muted">Decision</dt>
          <dd>
            <StatusPill tone={a.decision === "accepted" ? "success" : "danger"}>
              {a.decision === "accepted" ? "Accepted" : "Declined"}
            </StatusPill>{" "}
            {a.kind === "continuance" ? "Continuance" : "New client"}
            {a.before_act_1 && <span className="text-muted"> · recorded before Act 1</span>}
          </dd>
          <dt className="text-muted">Documented in</dt>
          <dd>{a.documented_at}</dd>
          {a.predecessor_auditor !== null && (
            <>
              <dt className="text-muted">Predecessor auditor</dt>
              <dd>
                {a.predecessor_auditor}
                {a.predecessor_communicated_on !== null &&
                  ` · communicated ${when(a.predecessor_communicated_on)}`}
              </dd>
            </>
          )}
          <dt className="text-muted">Independence</dt>
          <dd>
            {a.independence_concluded_at !== null
              ? `Concluded ${when(a.independence_concluded_at)}${a.independence_documented_at ? ` · ${a.independence_documented_at}` : ""}`
              : "Not concluded yet"}
          </dd>
          {a.file_name !== null && (
            <>
              <dt className="text-muted">File</dt>
              <dd className="break-all">{a.file_name}</dd>
            </>
          )}
        </dl>
      )}
      {editing && (
        <form className="flex flex-col gap-3" onSubmit={submit}>
          <div className="flex flex-col gap-1">
            <Label htmlFor="acc-decision">Decision</Label>
            <select
              id="acc-decision"
              className={SELECT}
              value={decision}
              onChange={(e) => {
                setDecision(e.target.value === "declined" ? "declined" : "accepted");
              }}
            >
              <option value="accepted">Accept</option>
              <option value="declined">Decline</option>
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="acc-documented">Where it&apos;s documented</Label>
            <Input
              id="acc-documented"
              required
              maxLength={300}
              placeholder="e.g. PPC 1-200 in the binder"
              value={documented}
              onChange={(e) => {
                setDocumented(e.target.value);
              }}
            />
          </div>
          {isNew && (
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="flex flex-col gap-1">
                <Label htmlFor="acc-predecessor">Predecessor auditor (optional)</Label>
                <Input
                  id="acc-predecessor"
                  maxLength={200}
                  value={predecessor}
                  onChange={(e) => {
                    setPredecessor(e.target.value);
                  }}
                />
              </div>
              <div className="flex flex-col gap-1">
                <Label htmlFor="acc-communicated">Date communicated (optional)</Label>
                <Input
                  id="acc-communicated"
                  type="date"
                  value={communicated}
                  onChange={(e) => {
                    setCommunicated(e.target.value);
                  }}
                />
              </div>
            </div>
          )}
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={concluded}
              onChange={(e) => {
                setConcluded(e.target.checked);
              }}
            />
            I have concluded on compliance with independence requirements for this engagement
          </label>
          {concluded && (
            <div className="flex flex-col gap-1">
              <Label htmlFor="acc-ind-doc">Where the conclusion is documented (optional)</Label>
              <Input
                id="acc-ind-doc"
                maxLength={300}
                value={concludedAt}
                onChange={(e) => {
                  setConcludedAt(e.target.value);
                }}
              />
            </div>
          )}
          {save.isError && !isForbidden(save.error) && (
            <p role="alert" className="text-sm text-danger">
              {errorMessage(save.error)}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => {
                setEditing(false);
              }}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={save.isPending || documented.trim() === ""}>
              Save
            </Button>
          </div>
        </form>
      )}
      <ConfirmItsYou open={confirm} onOpenChange={setConfirm} />
    </Panel>
  );
}

function IndependencePanel({
  engagementId,
  data,
}: {
  engagementId: string;
  data: SetupOut;
}): JSX.Element {
  const refresh = useRefresh(engagementId);
  const me = useQuery(meOptions());
  const mine = data.confirmations.find((c) => c.user_id === me.data?.user_id);
  const answer = useMutation({ ...independenceMutation(), onSuccess: refresh });
  const confirmed = data.confirmations.filter((c) => c.status === "confirmed").length;
  return (
    <Panel
      title="Independence"
      action={
        <StatusPill
          tone={confirmed === data.confirmations.length ? "success" : "warning"}
        >{`${String(confirmed)} of ${String(data.confirmations.length)} confirmed`}</StatusPill>
      }
    >
      <ul aria-label="Independence confirmations" className="flex flex-col gap-1 text-sm">
        {data.confirmations.map((c) => (
          <li key={c.user_id} className="flex flex-wrap items-center justify-between gap-2">
            <span>{c.display_name || "Team member"}</span>
            <span className="flex items-center gap-2">
              {c.status === "confirmed" ? (
                <StatusPill tone="success">
                  {c.before_act_1 ? "Confirmed (before Act 1)" : "Confirmed"}
                </StatusPill>
              ) : c.status === "declined" ? (
                <StatusPill tone="danger">Declined</StatusPill>
              ) : (
                <StatusPill tone="neutral">Waiting</StatusPill>
              )}
            </span>
            {c.note !== null && <span className="w-full text-xs text-muted">Note: {c.note}</span>}
          </li>
        ))}
      </ul>
      {mine !== undefined && mine.status !== "confirmed" && (
        <Button
          size="sm"
          disabled={answer.isPending}
          onClick={() => {
            answer.mutate({ path: { engagement_id: engagementId }, body: { confirm: true } });
          }}
        >
          Confirm my independence
        </Button>
      )}
    </Panel>
  );
}

function LetterPanel({
  engagementId,
  data,
  canRecord,
}: {
  engagementId: string;
  data: SetupOut;
  canRecord: boolean;
}): JSX.Element {
  const refresh = useRefresh(engagementId);
  const l = data.letter;
  const [editing, setEditing] = useState(false);
  const [status, setStatus] = useState(l?.status ?? "signed");
  const [date, setDate] = useState(l?.letter_date ?? "");
  const [reason, setReason] = useState(l?.reason ?? "");
  const [link, setLink] = useState(l?.link ?? "");
  const save = useMutation({
    ...letterMutation(),
    onSuccess: () => {
      setEditing(false);
      refresh();
    },
  });
  const submit = (event: SyntheticEvent): void => {
    event.preventDefault();
    save.mutate({
      path: { engagement_id: engagementId },
      body: {
        status: status as "not_started" | "sent" | "signed" | "not_required_this_year",
        ...(date !== "" ? { letter_date: date } : {}),
        ...(reason.trim() !== "" ? { reason } : {}),
        ...(link.trim() !== "" ? { link } : {}),
      },
    });
  };
  return (
    <Panel
      title="Engagement letter"
      action={
        canRecord && !editing ? (
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setEditing(true);
            }}
          >
            {l === null ? "Record" : "Update"}
          </Button>
        ) : undefined
      }
    >
      {l === null ? (
        <p className="text-sm text-muted">
          Not recorded.{" "}
          {data.letter_required
            ? "Your firm requires it before client data."
            : "Recommended before the work begins."}
        </p>
      ) : (
        <p className="text-sm">
          <StatusPill
            tone={
              l.status === "signed" || l.status === "not_required_this_year"
                ? "success"
                : "warning"
            }
          >
            {LETTER_LABEL[l.status] ?? l.status}
          </StatusPill>
          {l.letter_date !== null && ` · ${when(l.letter_date)}`}
          {l.reason !== null && <span className="block text-xs text-muted">{l.reason}</span>}
          {l.link !== null && (
            <a
              href={l.link}
              target="_blank"
              rel="noreferrer noopener"
              className="block text-xs text-accent hover:underline"
            >
              Where the signed copy lives
            </a>
          )}
          {l.file_name !== null && (
            <span className="block text-xs text-muted">Signed copy: {l.file_name}</span>
          )}
        </p>
      )}
      {editing && (
        <form className="flex flex-col gap-3" onSubmit={submit}>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1">
              <Label htmlFor="letter-status">Status</Label>
              <select
                id="letter-status"
                className={SELECT}
                value={status}
                onChange={(e) => {
                  setStatus(e.target.value);
                }}
              >
                {Object.entries(LETTER_LABEL).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1">
              <Label htmlFor="letter-date">Date</Label>
              <Input
                id="letter-date"
                type="date"
                value={date}
                onChange={(e) => {
                  setDate(e.target.value);
                }}
              />
            </div>
          </div>
          {status === "not_required_this_year" && (
            <div className="flex flex-col gap-1">
              <Label htmlFor="letter-reason">Why not this year</Label>
              <Input
                id="letter-reason"
                required
                maxLength={500}
                value={reason}
                onChange={(e) => {
                  setReason(e.target.value);
                }}
              />
            </div>
          )}
          <div className="flex flex-col gap-1">
            <Label htmlFor="letter-link">
              Link to the signed copy (Ignition, Karbon, your files)
            </Label>
            <Input
              id="letter-link"
              type="url"
              placeholder="https://"
              value={link}
              onChange={(e) => {
                setLink(e.target.value);
              }}
            />
          </div>
          {save.isError && (
            <p role="alert" className="text-sm text-danger">
              {errorMessage(save.error)}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button
              variant="outline"
              onClick={() => {
                setEditing(false);
              }}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={save.isPending}>
              Save
            </Button>
          </div>
        </form>
      )}
    </Panel>
  );
}
