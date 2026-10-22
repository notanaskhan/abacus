import type { ImportOut } from "@abacus/api-client";
import {
  checkMutation,
  connectionOptions,
  connectionQueryKey,
  latestLedgerImportOptions,
  ledgerImportFormatsOptions,
  logOptions,
  providersOptions,
  revokeMutation,
  startMutation,
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
  useFormat,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";
import { ConfirmItsYou, isForbidden } from "../shell/mfa";
import { longDate } from "./importMessages";
import { GlExport } from "./GlExport";
import { importOutcome, LedgerExport } from "./LedgerExport";

const RUN_STATUS: Record<string, string> = {
  running: "Running",
  succeeded: "Retrieved",
  failed_validation: "Failed checks",
  failed: "Failed",
};

function useWhen(): (value: string | null | undefined) => string {
  const f = useFormat();
  return (value) => (value === null || value === undefined ? "Never" : f.dateTime(value));
}

/** SPEC-020 AC-2 to AC-6: the engagement's ledger connection, for the client admin (who may
 * connect) and for the firm's partner and managers (who may check and revoke). SPEC-028 AC-1
 * (TASK-053): connecting is never required; an exported trial balance can be uploaded instead,
 * by the client admin or by the firm for the client (D3). */
export function ConnectionPanel({
  engagementId,
  firmName,
  canConnect,
}: {
  engagementId: string;
  firmName: string;
  canConnect: boolean;
}): JSX.Element {
  const when = useWhen();
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const connection = useQuery({ ...connectionOptions(path), retry: false });
  const [consent, setConsent] = useState<string | null>(null);
  const [confirmRevoke, setConfirmRevoke] = useState(false);
  const [mfa, setMfa] = useState(false);
  const [showLog, setShowLog] = useState(false);
  const [exporting, setExporting] = useState(false);
  // Export is offered when the firm has it on and this person may upload (403/409 hide it).
  const formats = useQuery({ ...ledgerImportFormatsOptions(path), retry: false });
  const canExport = formats.isSuccess && formats.data.length > 0;
  const latest = useQuery({ ...latestLedgerImportOptions(path), retry: false });
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
      {live?.provider === "import" ? (
        <>
          {latest.data != null && <LatestImport latest={latest.data} />}
          {exporting ? (
            <LedgerExport
              engagementId={engagementId}
              onBehalf={!canConnect}
              onDone={() => {
                setExporting(false);
              }}
            />
          ) : (
            <div className="flex flex-wrap gap-2">
              {canExport && (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    setExporting(true);
                  }}
                >
                  Upload a newer export
                </Button>
              )}
              {canConnect && <Providers engagementId={engagementId} onPick={setConsent} />}
              <Button
                size="sm"
                variant="secondary"
                aria-expanded={showLog}
                onClick={() => {
                  setShowLog((s) => !s);
                }}
              >
                {showLog ? "Hide access log" : "Access log"}
              </Button>
            </div>
          )}
          <p className="text-meta text-ink-3">
            An export isn't updated automatically. For a later date, upload a new export.
          </p>
        </>
      ) : live === null ? (
        <>
          {latest.data != null && <LatestImport latest={latest.data} />}
          {exporting ? (
            <LedgerExport
              engagementId={engagementId}
              onBehalf={!canConnect}
              onDone={() => {
                setExporting(false);
              }}
            />
          ) : canConnect ? (
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="flex flex-col gap-2 rounded-md border border-hair p-3">
                <h3 className="font-medium">Connect (fastest)</h3>
                <p className="text-body text-ink-3">
                  Connect your accounting system so your auditor can retrieve records directly.
                </p>
                <Providers engagementId={engagementId} onPick={setConsent} />
              </div>
              {canExport && (
                <div className="flex flex-col gap-2 rounded-md border border-hair p-3">
                  <h3 className="font-medium">Export instead</h3>
                  <p className="text-body text-ink-3">
                    Export your trial balance from your accounting system and upload the file. No
                    connection needed.
                  </p>
                  <div>
                    <Button
                      variant="secondary"
                      onClick={() => {
                        setExporting(true);
                      }}
                    >
                      Export instead
                    </Button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <>
              <p className="text-body text-ink-3">
                Not connected. The client&apos;s administrator can connect their accounting system
                or upload an export.
              </p>
              {canExport && (
                <div>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => {
                      setExporting(true);
                    }}
                  >
                    Upload an export for the client
                  </Button>
                </div>
              )}
            </>
          )}
        </>
      ) : (
        <>
          <dl className="grid grid-cols-[10rem_1fr] gap-x-3 gap-y-1 text-body">
            <dt className="text-ink-3">Status</dt>
            <dd>
              {live.status === "active" ? (
                <StatusPill tone="success">Connected</StatusPill>
              ) : (
                <StatusPill tone="warning">Needs attention</StatusPill>
              )}
            </dd>
            <dt className="text-ink-3">Connected on</dt>
            <dd className="tabular-nums">{when(live.created_at)}</dd>
            <dt className="text-ink-3">Last check</dt>
            <dd className="tabular-nums">
              {when(live.last_checked_at)}
              {live.last_check_ok === false && " · failed"}
            </dd>
            <dt className="text-ink-3">Last retrieval</dt>
            <dd className="tabular-nums">{when(live.last_pull_at)}</dd>
          </dl>
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="secondary"
              disabled={check.isPending}
              onClick={() => {
                check.mutate(path);
              }}
            >
              {check.isPending ? "Checking…" : "Check now"}
            </Button>
            <Button
              size="sm"
              variant="secondary"
              aria-expanded={showLog}
              onClick={() => {
                setShowLog((s) => !s);
              }}
            >
              {showLog ? "Hide access log" : "Access log"}
            </Button>
            <Button
              size="sm"
              variant="destructive"
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
        <p role="alert" className="text-body text-danger">
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
        <ul className="mb-3 flex list-disc flex-col gap-1 pl-5 text-body">
          <li>
            Abacus is built to only read from your system. It has no way to create, change or
            delete anything in it.
          </li>
          <li>
            Every retrieval is recorded in an access log that you can see on this page at any time.
          </li>
          <li>You can disconnect at any time. Retrieval stops straight away.</li>
        </ul>
        <p className="mb-4 text-body text-ink-3">
          On the next screen your accounting system will ask you to approve access. The permission
          it asks for may be broader than reading. Abacus still only reads.
        </p>
        <div className="flex justify-end gap-2">
          <Button
            variant="secondary"
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
            variant="secondary"
            onClick={() => {
              setConfirmRevoke(false);
            }}
          >
            Cancel
          </Button>
          <Button
            variant="destructive"
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
      {/* SPEC-034 (TASK-070): the general ledger detail, when there's no live connector. */}
      {(live === null || live.provider === "import") && <GlExport engagementId={engagementId} />}
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
    return <p className="text-body text-danger">{errorMessage(providers.error)}</p>;
  if (providers.data.length === 0) {
    return <p className="text-body text-ink-3">No accounting system can be connected yet.</p>;
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
  const when = useWhen();
  const [page, setPage] = useState(0);
  const log = useQuery(logOptions({ path: { engagement_id: engagementId }, query: { page } }));
  if (log.isPending) return <Skeleton className="h-24" />;
  if (log.isError) return <p className="text-body text-danger">{errorMessage(log.error)}</p>;
  if (log.data.length === 0 && page === 0) {
    return <p className="text-body text-ink-3">No retrievals yet.</p>;
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

/** SPEC-028 §4.7, AC-6: the latest export, with the same plain-words reason the client saw. */
function LatestImport({ latest }: { latest: ImportOut }): JSX.Element {
  const when = useWhen();
  const outcome = importOutcome({ ...latest, duplicate: false }, latest.system);
  return (
    <dl className="grid grid-cols-[10rem_1fr] gap-x-3 gap-y-1 text-body">
      <dt className="text-ink-3">Latest export</dt>
      <dd>
        {latest.system} · year ending {longDate(latest.period_end)}
        {latest.on_behalf && " · uploaded by the audit team"}
      </dd>
      <dt className="text-ink-3">Uploaded</dt>
      <dd className="tabular-nums">{when(latest.uploaded_at)}</dd>
      <dt className="text-ink-3">Result</dt>
      <dd>
        {latest.status === "received" ? (
          <StatusPill tone="success">Received</StatusPill>
        ) : (
          <span role="alert" className="text-danger">
            {outcome.text}
          </span>
        )}
      </dd>
    </dl>
  );
}
