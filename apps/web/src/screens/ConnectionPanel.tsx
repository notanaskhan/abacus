import {
  checkMutation,
  connectionOptions,
  connectionQueryKey,
  logOptions,
  providersOptions,
  revokeMutation,
  startMutation,
} from "@abacus/api-client/query";
import { Alert, Button, Dialog, Panel, Skeleton, StatusPill, Table, Td, Th } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";
import { ConfirmItsYou, isForbidden } from "../shell/mfa";

const RUN_STATUS: Record<string, string> = {
  running: "Running",
  succeeded: "Retrieved",
  failed_validation: "Failed checks",
  failed: "Failed",
};

function when(value: string | null | undefined): string {
  return value === null || value === undefined ? "Never" : new Date(value).toLocaleString();
}

/** SPEC-020 AC-2 to AC-6: the engagement's ledger connection, for the client admin (who may
 * connect) and for the firm's partner and managers (who may check and revoke). */
export function ConnectionPanel({
  engagementId,
  firmName,
  canConnect,
}: {
  engagementId: string;
  firmName: string;
  canConnect: boolean;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const connection = useQuery({ ...connectionOptions(path), retry: false });
  const [consent, setConsent] = useState<string | null>(null);
  const [confirmRevoke, setConfirmRevoke] = useState(false);
  const [mfa, setMfa] = useState(false);
  const [showLog, setShowLog] = useState(false);
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: connectionQueryKey(path) });
  };
  const start = useMutation({
    ...startMutation(),
    onSuccess: (data) => {
      window.location.assign(data.authorise_url);
    },
    onError: (error) => {
      setConsent(null);
      if (isForbidden(error)) setMfa(true);
    },
  });
  const check = useMutation({ ...checkMutation(), onSuccess: refresh });
  const revoke = useMutation({
    ...revokeMutation(),
    onSuccess: () => {
      setConfirmRevoke(false);
      refresh();
    },
    onError: () => {
      setConfirmRevoke(false);
    },
  });

  if (connection.isPending) return <Skeleton className="h-24" />;
  if (connection.isError) {
    return isForbidden(connection.error) ? (
      <></>
    ) : (
      <Alert title="Couldn't load the connection">{errorMessage(connection.error)}</Alert>
    );
  }
  const live = connection.data;
  const failure = [check, revoke, start].find((m) => m.isError && !isForbidden(m.error));

  return (
    <Panel title="Accounting system">
      {live === null ? (
        <>
          <p className="text-sm text-muted">
            Not connected.{" "}
            {canConnect
              ? "Connect your accounting system so your auditor can retrieve records directly."
              : "The client's administrator can connect their accounting system."}
          </p>
          {canConnect && <Providers engagementId={engagementId} onPick={setConsent} />}
        </>
      ) : (
        <>
          <dl className="grid grid-cols-[10rem_1fr] gap-x-3 gap-y-1 text-sm">
            <dt className="text-muted">Status</dt>
            <dd>
              {live.status === "active" ? (
                <StatusPill tone="success">Connected</StatusPill>
              ) : (
                <StatusPill tone="warning">Needs attention</StatusPill>
              )}
            </dd>
            <dt className="text-muted">Connected on</dt>
            <dd className="tabular-nums">{when(live.created_at)}</dd>
            <dt className="text-muted">Last check</dt>
            <dd className="tabular-nums">
              {when(live.last_checked_at)}
              {live.last_check_ok === false && " · failed"}
            </dd>
            <dt className="text-muted">Last retrieval</dt>
            <dd className="tabular-nums">{when(live.last_pull_at)}</dd>
          </dl>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={check.isPending}
              onClick={() => {
                check.mutate(path);
              }}
            >
              {check.isPending ? "Checking…" : "Check now"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              aria-expanded={showLog}
              onClick={() => {
                setShowLog((s) => !s);
              }}
            >
              {showLog ? "Hide access log" : "Access log"}
            </Button>
            <Button
              size="sm"
              variant="danger"
              onClick={() => {
                setConfirmRevoke(true);
              }}
            >
              Disconnect
            </Button>
          </div>
        </>
      )}
      {failure !== undefined && (
        <p role="alert" className="text-sm text-danger">
          {errorMessage(failure.error)}
        </p>
      )}
      {showLog && live !== null && <AccessLog engagementId={engagementId} />}
      <Dialog
        open={consent !== null}
        onOpenChange={(open) => {
          if (!open) setConsent(null);
        }}
        title="Connect your accounting system"
        description={`Your auditor at ${firmName} will be able to retrieve the records they request for this audit, such as your trial balance, directly from your accounting system.`}
      >
        <ul className="mb-3 flex list-disc flex-col gap-1 pl-5 text-sm">
          <li>
            Abacus is built to only read from your system. It has no way to create, change or
            delete anything in it.
          </li>
          <li>
            Every retrieval is recorded in an access log that you can see on this page at any time.
          </li>
          <li>You can disconnect at any time. Retrieval stops straight away.</li>
        </ul>
        <p className="mb-4 text-sm text-muted">
          On the next screen your accounting system will ask you to approve access. The permission
          it asks for may be broader than reading. Abacus still only reads.
        </p>
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            onClick={() => {
              setConsent(null);
            }}
          >
            Cancel
          </Button>
          <Button
            disabled={start.isPending}
            onClick={() => {
              if (consent !== null) start.mutate({ ...path, body: { provider: consent } });
            }}
          >
            Connect
          </Button>
        </div>
      </Dialog>
      <Dialog
        open={confirmRevoke}
        onOpenChange={setConfirmRevoke}
        title="Disconnect the accounting system?"
        description="Retrieval stops straight away and the stored access is deleted. It can be connected again later."
      >
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            onClick={() => {
              setConfirmRevoke(false);
            }}
          >
            Cancel
          </Button>
          <Button
            variant="danger"
            disabled={revoke.isPending}
            onClick={() => {
              revoke.mutate(path);
            }}
          >
            Disconnect
          </Button>
        </div>
      </Dialog>
      <ConfirmItsYou open={mfa} onOpenChange={setMfa} />
    </Panel>
  );
}

function Providers({
  engagementId,
  onPick,
}: {
  engagementId: string;
  onPick: (provider: string) => void;
}): JSX.Element {
  const providers = useQuery(providersOptions({ path: { engagement_id: engagementId } }));
  if (providers.isPending) return <Skeleton className="h-9" />;
  if (providers.isError)
    return <p className="text-sm text-danger">{errorMessage(providers.error)}</p>;
  if (providers.data.length === 0) {
    return <p className="text-sm text-muted">No accounting system can be connected yet.</p>;
  }
  return (
    <div className="flex flex-wrap gap-2">
      {providers.data.map((p) => (
        <Button
          key={p.provider}
          onClick={() => {
            onPick(p.provider);
          }}
        >
          Connect {p.name}
        </Button>
      ))}
    </div>
  );
}

function AccessLog({ engagementId }: { engagementId: string }): JSX.Element {
  const [page, setPage] = useState(0);
  const log = useQuery(logOptions({ path: { engagement_id: engagementId }, query: { page } }));
  if (log.isPending) return <Skeleton className="h-24" />;
  if (log.isError) return <p className="text-sm text-danger">{errorMessage(log.error)}</p>;
  if (log.data.length === 0 && page === 0) {
    return <p className="text-sm text-muted">No retrievals yet.</p>;
  }
  return (
    <div className="flex flex-col gap-2">
      <div className="overflow-x-auto">
        <Table className="min-w-[560px]" aria-label="Access log">
          <thead>
            <tr>
              <Th>When</Th>
              <Th>What</Th>
              <Th>Period</Th>
              <Th>Result</Th>
            </tr>
          </thead>
          <tbody>
            {log.data.map((entry) => (
              <tr key={entry.id}>
                <Td className="tabular-nums">{when(entry.started_at)}</Td>
                <Td>{entry.dataset === "trial_balance" ? "Trial balance" : entry.dataset}</Td>
                <Td className="tabular-nums">
                  {entry.period_start} to {entry.period_end}
                </Td>
                <Td>{RUN_STATUS[entry.status] ?? entry.status}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </div>
      <div className="flex gap-2">
        <Button
          size="sm"
          variant="ghost"
          disabled={page === 0}
          onClick={() => {
            setPage((p) => p - 1);
          }}
        >
          Newer
        </Button>
        <Button
          size="sm"
          variant="ghost"
          disabled={log.data.length < 50}
          onClick={() => {
            setPage((p) => p + 1);
          }}
        >
          Older
        </Button>
      </div>
    </div>
  );
}
