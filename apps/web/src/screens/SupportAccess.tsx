import type { SupportSessionOut } from "@abacus/api-client";
import {
  acknowledgeSupportSessionMutation,
  approveSupportSessionMutation,
  listSupportSessionsOptions,
  listSupportSessionsQueryKey,
  revokeSupportSessionMutation,
} from "@abacus/api-client/query";
import {
  Alert,
  Button,
  Dialog,
  Panel,
  Skeleton,
  StatusPill,
  Table,
  Td,
  Th,
  type Tone,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";
import { ConfirmItsYou, isForbidden } from "../shell/mfa";

type Action = "approve" | "revoke" | "acknowledge";

const ACTIONS: Record<Action, { label: string; question: string }> = {
  approve: {
    label: "Approve",
    question:
      "Approve this support session? Platform support can then open your firm's data for the window shown.",
  },
  revoke: { label: "Revoke", question: "Revoke this support session? Access ends immediately." },
  acknowledge: {
    label: "Acknowledge",
    question: "Acknowledge this emergency session? Confirm you've reviewed why it was opened.",
  },
};

const STATUS: Record<SupportSessionOut["status"], { text: string; tone: Tone }> = {
  requested: { text: "Requested", tone: "warning" },
  active: { text: "Active", tone: "info" },
  ended: { text: "Ended", tone: "neutral" },
  revoked: { text: "Revoked", tone: "neutral" },
  expired: { text: "Expired", tone: "neutral" },
};

function when(value: string | null): string {
  return value === null ? "—" : new Date(value).toLocaleString();
}

/** SPEC-019 AC-5: break-glass sessions, with approve (fresh MFA), revoke and acknowledge. */
export function SupportAccess(): JSX.Element {
  const queryClient = useQueryClient();
  const sessions = useQuery(listSupportSessionsOptions());
  const [pending, setPending] = useState<{ action: Action; session: SupportSessionOut } | null>(
    null,
  );
  const [confirm, setConfirm] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: listSupportSessionsQueryKey() });
  };
  const handlers = {
    onSuccess: () => {
      setPending(null);
      setNotice(null);
      refresh();
    },
    onError: (error: unknown) => {
      setPending(null);
      if (isForbidden(error)) {
        setConfirm(true);
      } else if (errorMessage(error) === "support_session_conflict") {
        setNotice("Already handled. The list has been refreshed.");
        refresh();
      } else {
        setNotice(errorMessage(error));
      }
    },
  };
  const approve = useMutation({ ...approveSupportSessionMutation(), ...handlers });
  const revoke = useMutation({ ...revokeSupportSessionMutation(), ...handlers });
  const acknowledge = useMutation({ ...acknowledgeSupportSessionMutation(), ...handlers });
  const busy = approve.isPending || revoke.isPending || acknowledge.isPending;
  const run = (): void => {
    if (pending === null) return;
    const options = { path: { session_id: pending.session.id } };
    if (pending.action === "approve") approve.mutate(options);
    else if (pending.action === "revoke") revoke.mutate(options);
    else acknowledge.mutate(options);
  };

  const list = sessions.data ?? [];
  const current = list.filter((s) => s.status === "requested" || s.status === "active");
  const past = list.filter((s) => s.status !== "requested" && s.status !== "active");

  const table = (rows: SupportSessionOut[]): JSX.Element => (
    <div className="overflow-x-auto">
      <Table className="min-w-[860px]">
        <thead>
          <tr>
            <Th>Support staff</Th>
            <Th>Reason</Th>
            <Th>Scope</Th>
            <Th>Window</Th>
            <Th>Approval</Th>
            <Th>Requests</Th>
            <Th>Status</Th>
            <Th>
              <span className="sr-only">Actions</span>
            </Th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => (
            <tr key={s.id}>
              <Td>{s.staff_subject}</Td>
              <Td className="max-w-xs whitespace-pre-wrap">{s.reason}</Td>
              <Td>{s.scope === "content" ? "Content" : "Metadata only"}</Td>
              <Td className="text-xs tabular-nums">
                {s.starts_at === null
                  ? `${String(s.duration_minutes)} min, from approval`
                  : `${when(s.starts_at)} – ${when(s.ended_at ?? s.expires_at)}`}
              </Td>
              <Td>{s.approved_by_kind ?? "—"}</Td>
              <Td className="tabular-nums">{s.requests}</Td>
              <Td>
                <span className="inline-flex flex-wrap items-center gap-1.5">
                  <StatusPill tone={STATUS[s.status].tone}>{STATUS[s.status].text}</StatusPill>
                  {s.emergency && (
                    <StatusPill tone="danger">
                      {s.acknowledged ? "Emergency · acknowledged" : "Emergency"}
                    </StatusPill>
                  )}
                </span>
              </Td>
              <Td>
                <span className="flex gap-1.5">
                  {s.status === "requested" && (
                    <Button
                      size="sm"
                      onClick={() => {
                        setPending({ action: "approve", session: s });
                      }}
                    >
                      Approve
                    </Button>
                  )}
                  {(s.status === "requested" || s.status === "active") && (
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={() => {
                        setPending({ action: "revoke", session: s });
                      }}
                    >
                      Revoke
                    </Button>
                  )}
                  {s.emergency && !s.acknowledged && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        setPending({ action: "acknowledge", session: s });
                      }}
                    >
                      Acknowledge
                    </Button>
                  )}
                </span>
              </Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  );

  return (
    <div className="flex flex-col gap-4">
      {notice !== null && (
        <p role="alert" className="text-sm text-danger">
          {notice}
        </p>
      )}
      {sessions.isPending ? (
        <Skeleton className="h-32" />
      ) : sessions.isError ? (
        isForbidden(sessions.error) ? (
          <Alert title="Not available">Only firm admins can see support access.</Alert>
        ) : (
          <Alert title="Couldn't load support sessions">{errorMessage(sessions.error)}</Alert>
        )
      ) : (
        <>
          <Panel title="Requested and active">
            {current.length === 0 ? (
              <p className="text-sm text-muted">No support session is requested or active.</p>
            ) : (
              table(current)
            )}
          </Panel>
          <Panel title="Past sessions">
            {past.length === 0 ? (
              <p className="text-sm text-muted">No past support sessions.</p>
            ) : (
              table(past)
            )}
          </Panel>
        </>
      )}
      <Dialog
        open={pending !== null}
        onOpenChange={(next) => {
          if (!next) setPending(null);
        }}
        title={pending === null ? "Confirm" : `${ACTIONS[pending.action].label} support session`}
        description={pending === null ? "" : ACTIONS[pending.action].question}
      >
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            onClick={() => {
              setPending(null);
            }}
          >
            Cancel
          </Button>
          <Button
            variant={pending?.action === "revoke" ? "danger" : "default"}
            disabled={busy}
            onClick={run}
          >
            {pending === null ? "Confirm" : ACTIONS[pending.action].label}
          </Button>
        </div>
      </Dialog>
      <ConfirmItsYou open={confirm} onOpenChange={setConfirm} />
    </div>
  );
}
