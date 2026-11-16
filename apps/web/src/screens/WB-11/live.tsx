import type { ConnectIntegrationDetailOut } from "@abacus/api-client";
import {
  connectDetailOptions,
  connectFirmMutation,
  connectPersonalMutation,
  disconnectFirmMutation,
} from "@abacus/api-client/query";
import {
  Button,
  Drawer,
  DrawerCard,
  ErrorState,
  Skeleton,
  status as statusWord,
  toast,
  useFormat,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import type { OverlayRenderProps } from "../../app-core/overlays";

// WB-11 live (S47, TASK-8338): the O2 480 drawer over its host (`?ov=integration:<key>`), every
// word and figure the API's `GET /v1/integrations/{key}`. Connection card, what Accrued may read,
// recent events, agents using it, the footer actions the viewer holds (Reconnect…, Disconnect…
// with the typed name). A section the catalogue has no content for yet is not drawn. No control
// here connects a client's ledger.

const COPY = {
  connection: "Connection",
  authMode: "Auth mode",
  connectedBy: "Connected by",
  tokenRenews: "Token renews",
  lastSync: "Last sync",
  mayDo: "What Accrued may do",
  read: "Read",
  never: "Never",
  health: "Health",
  recent: "Recent events",
  agents: (n: number): string => `Agents using it · ${String(n)}`,
  reconnect: "Reconnect…",
  disconnect: "Disconnect…",
  manages: (name: string): string => `${name} manages this firm connection.`,
  confirmTitle: (name: string): string => `Disconnect ${name}?`,
  confirmType: (name: string): string => `Type ${name}`,
  confirm: "Disconnect",
  kept: "Data already in Accrued is kept.",
  failed: "That didn't work. Try again.",
  cancel: "Cancel",
  continueTo: (name: string): string => `Continue to ${name}`,
} as const;

export function IntegrationLayer({ ref, close }: OverlayRenderProps): JSX.Element | null {
  const [key] = ref.args;
  if (key === undefined) return null;
  return <LiveDrawer integrationKey={key} close={close} />;
}

function LiveDrawer({
  integrationKey,
  close,
}: {
  integrationKey: string;
  close: () => void;
}): JSX.Element {
  const detail = useQuery(connectDetailOptions({ path: { key: integrationKey } }));
  const onOpenChange = (open: boolean): void => {
    if (!open) close();
  };
  const data = detail.data;
  if (data === undefined) {
    return (
      <Drawer open onOpenChange={onOpenChange} title="" width={480}>
        <div data-screen="WB-11" data-live>
          {detail.isError ? (
            <ErrorState
              onRetry={() => {
                void detail.refetch();
              }}
            />
          ) : (
            <Skeleton className="h-[198px]" />
          )}
        </div>
      </Drawer>
    );
  }
  return <Loaded data={data} onOpenChange={onOpenChange} />;
}

function Loaded({
  data,
  onOpenChange,
}: {
  data: ConnectIntegrationDetailOut;
  onOpenChange: (open: boolean) => void;
}): JSX.Element {
  const fmt = useFormat();
  const client = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const refresh = (): void => {
    void client.invalidateQueries({ queryKey: [{ _id: "connectDetail" }] });
    void client.invalidateQueries({ queryKey: [{ _id: "connectCatalog" }] });
  };
  const failed = (): void => {
    toast.show({ kind: "error", text: COPY.failed });
  };
  const reconnect = useMutation({
    ...connectFirmMutation(),
    onSuccess: (r) => {
      if (r.authorise_url) window.location.assign(r.authorise_url);
      refresh();
    },
    onError: failed,
  });
  // W-01-T17 (WB-11 b): a personal app's consent, then the provider.
  const personal = useMutation({
    ...connectPersonalMutation(),
    onSuccess: (r) => {
      if (r.authorise_url) window.location.assign(r.authorise_url);
      refresh();
    },
    onError: failed,
  });
  const disconnect = useMutation({
    ...disconnectFirmMutation(),
    onSuccess: () => {
      setConfirming(false);
      refresh();
    },
    onError: failed,
  });
  const card = data.connection;
  const at = (v: string | null | undefined): string | null =>
    v === null || v === undefined ? null : fmt.dateTime(v);
  const by =
    card.connected_by === null
      ? null
      : [card.connected_by, at(card.connected_at)].filter((x) => x !== null).join(" · ");
  const rows: [string, string][] = [[COPY.authMode, card.auth_mode_label]];
  if (by !== null) rows.push([COPY.connectedBy, by]);
  const renews = at(card.token_renews_at);
  if (renews !== null) rows.push([COPY.tokenRenews, renews]);
  const synced = at(card.last_sync_at);
  if (synced !== null) rows.push([COPY.lastSync, synced]);
  const actions = new Set(data.allowed_actions);
  const canReconnect =
    actions.has("integration.connect_firm") &&
    (data.status === "needs_reauth" || data.status === "needs_attention");
  const canDisconnect = actions.has("integration.disconnect_firm") && data.status !== "available";
  const firmManaged = !actions.has("integration.connect_firm") && data.managed_by;
  const footer = firmManaged ? (
    <p className="text-[11.5px] text-ink-3">{COPY.manages(data.managed_by ?? "")}</p>
  ) : canReconnect || canDisconnect ? (
    <div className="flex w-full items-center justify-between">
      {canReconnect ? (
        <Button
          disabled={reconnect.isPending}
          onClick={() => {
            reconnect.mutate({
              path: { key: data.key },
              headers: { "Idempotency-Key": crypto.randomUUID() },
            });
          }}
        >
          {COPY.reconnect}
        </Button>
      ) : (
        <span />
      )}
      {canDisconnect && (
        <Button
          variant="destructive"
          onClick={() => {
            setConfirming(true);
          }}
        >
          {COPY.disconnect}
        </Button>
      )}
    </div>
  ) : undefined;
  return (
    <Drawer
      open
      onOpenChange={onOpenChange}
      title={data.name}
      width={480}
      meta={<span data-pill>{statusWord("integration", data.status).label}</span>}
      {...(footer === undefined ? {} : { footer })}
    >
      <div data-screen="WB-11" data-live data-status={data.status}>
        {confirming ? (
          <Confirm
            name={data.name}
            agents={data.dependents.count}
            pending={disconnect.isPending}
            onConfirm={() => {
              disconnect.mutate({
                path: { key: data.key },
                body: { confirm_name: data.name, seen_version: data.version },
                headers: { "Idempotency-Key": crypto.randomUUID() },
              });
            }}
          />
        ) : null}
        {data.consent &&
        data.status === "available" &&
        actions.has("integration.connect_personal") ? (
          <DrawerCard aria-label={data.consent.heading}>
            <p>{data.consent.heading}</p>
            <ul>
              {data.consent.reads.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
            <p>{data.consent.never}</p>
            <Button
              variant="secondary"
              onClick={() => {
                onOpenChange(false);
              }}
            >
              {COPY.cancel}
            </Button>
            <Button
              disabled={personal.isPending}
              onClick={() => {
                personal.mutate({
                  path: { key: data.key },
                  headers: { "Idempotency-Key": crypto.randomUUID() },
                });
              }}
            >
              {data.consent.continue_label ?? COPY.continueTo(data.name)}
            </Button>
          </DrawerCard>
        ) : null}
        {data.status_line ? <p className="text-[11.5px] text-ink-3">{data.status_line}</p> : null}
        <DrawerCard aria-label={COPY.connection}>
          <dl>
            {rows.map(([k, v]) => (
              <div key={k} className="flex h-[33px] items-center justify-between">
                <dt className="text-ink-2">{k}</dt>
                <dd className="font-medium">{v}</dd>
              </div>
            ))}
          </dl>
        </DrawerCard>
        {data.may_do.read.length + data.may_do.never.length > 0 && (
          <DrawerCard aria-label={COPY.mayDo}>
            {data.may_do.read.length > 0 && (
              <>
                <h3>{COPY.read}</h3>
                <ul>
                  {data.may_do.read.map((r) => (
                    <li key={r.label} data-state={r.state}>
                      {r.label}
                    </li>
                  ))}
                </ul>
              </>
            )}
            {data.may_do.never.length > 0 && (
              <>
                <h3>{COPY.never}</h3>
                <ul>
                  {data.may_do.never.map((r) => (
                    <li key={r.label} data-state="never">
                      {r.label}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </DrawerCard>
        )}
        {data.health.events.length > 0 && (
          <DrawerCard aria-label={COPY.health}>
            <h3>{COPY.recent}</h3>
            <ol>
              {data.health.events.map((e) => (
                <li key={e.id} data-ok={e.ok}>
                  <time dateTime={e.at}>{fmt.dateTime(e.at)}</time> {e.label}
                </li>
              ))}
            </ol>
          </DrawerCard>
        )}
        {data.dependents.count > 0 && (
          <DrawerCard aria-label={COPY.agents(data.dependents.count)}>
            <ul>
              {data.dependents.items.map((a) => (
                <li key={a.key}>{a.name}</li>
              ))}
            </ul>
          </DrawerCard>
        )}
      </div>
    </Drawer>
  );
}

function Confirm({
  name,
  agents,
  pending,
  onConfirm,
}: {
  name: string;
  agents: number;
  pending: boolean;
  onConfirm: () => void;
}): JSX.Element {
  const [typed, setTyped] = useState("");
  return (
    <section role="dialog" aria-label={COPY.confirmTitle(name)}>
      <h2>{COPY.confirmTitle(name)}</h2>
      <p>
        {agents > 0 ? `${String(agents)} agents stop working. ` : ""}
        {COPY.kept}
      </p>
      <label>
        {COPY.confirmType(name)}
        <input
          value={typed}
          onChange={(e) => {
            setTyped(e.target.value);
          }}
        />
      </label>
      <Button variant="destructive" disabled={typed !== name || pending} onClick={onConfirm}>
        {COPY.confirm}
      </Button>
    </section>
  );
}
