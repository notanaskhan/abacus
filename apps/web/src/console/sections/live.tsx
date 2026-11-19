// The console's sections on the live API (G-04-T17; DEC-5701): Support sessions, Status and
// Publications as tabs, the Support queue pill opening its drawer, and the Plan requests tile with
// each request's card. Data only through the generated client; every write is a staff member's own
// (the server's two-person rule decides who may publish).
import { consoleTenant } from "@abacus/api-client";
import {
  consoleIncidentsOptions,
  consoleIncidentsQueryKey,
  consoleMarkAppliedMutation,
  consolePlanRequestsOptions,
  consolePlanRequestsQueryKey,
  consolePostIncidentMutation,
  consolePublicationsOptions,
  consolePublicationsQueryKey,
  consolePublishMutation,
  consoleQueueConversationOptions,
  consoleQueueOptions,
  consoleQueueReplyMutation,
  consoleResolveIncidentMutation,
  consoleSupportSessionsOptions,
  consoleUpdateIncidentMutation,
  consoleWithdrawMutation,
} from "@abacus/api-client/query";
import { Pill, Segmented, Skeleton } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { SECTIONS_COPY as C } from "./copy";
import { PlanRequestsCard, PlanRequestsTile } from "./PlanRequestsCard";
import { Publications } from "./Publications";
import { Status } from "./Status";
import { SupportQueue } from "./SupportQueue";
import { SupportSessions } from "./SupportSessions";

type Tab = "sessions" | "status" | "publications";
const TABS: readonly Tab[] = ["sessions", "status", "publications"];
const LOADING = <Skeleton className="h-[320px] w-full" />;

function idempotencyKey(): string {
  return crypto.randomUUID();
}

function SessionsTab(): JSX.Element {
  const q = useQuery({ ...consoleSupportSessionsOptions(), retry: false });
  return q.data === undefined ? LOADING : <SupportSessions data={q.data} />;
}

function StatusTab(): JSX.Element {
  const client = useQueryClient();
  const q = useQuery({ ...consoleIncidentsOptions(), retry: false });
  const settle = {
    onSuccess: () => client.invalidateQueries({ queryKey: consoleIncidentsQueryKey() }),
  };
  const post = useMutation({ ...consolePostIncidentMutation(), ...settle });
  const update = useMutation({ ...consoleUpdateIncidentMutation(), ...settle });
  const resolve = useMutation({ ...consoleResolveIncidentMutation(), ...settle });
  if (q.data === undefined) return LOADING;
  const components = [...new Set(q.data.items.map((i) => i.component_key))];
  return (
    <Status
      data={q.data}
      components={components}
      onPost={(body) => {
        post.mutate({ body, headers: { "Idempotency-Key": idempotencyKey() } });
      }}
      onUpdate={(i, note) => {
        update.mutate({ path: { incident_id: i.id }, body: { note } });
      }}
      onResolve={(i, note) => {
        resolve.mutate({ path: { incident_id: i.id }, body: { note } });
      }}
    />
  );
}

function PublicationsTab(): JSX.Element {
  const client = useQueryClient();
  const q = useQuery({ ...consolePublicationsOptions(), retry: false });
  const settle = {
    onSuccess: () => client.invalidateQueries({ queryKey: consolePublicationsQueryKey() }),
  };
  const publish = useMutation({ ...consolePublishMutation(), ...settle });
  const withdraw = useMutation({ ...consoleWithdrawMutation(), ...settle });
  if (q.data === undefined) return LOADING;
  return (
    <Publications
      data={q.data}
      onPublish={(p) => {
        publish.mutate({
          path: { kind: p.kind, publication_id: p.id },
          body: { reason: C.publications.publish },
        });
      }}
      onWithdraw={(p) => {
        withdraw.mutate({
          path: { kind: p.kind, publication_id: p.id },
          body: { reason: C.publications.withdraw },
        });
      }}
    />
  );
}

function Queue({ open, onOpenChange }: { open: boolean; onOpenChange: (o: boolean) => void }) {
  const [selected, setSelected] = useState<string | null>(null);
  const list = useQuery({ ...consoleQueueOptions(), retry: false, enabled: open });
  const detail = useQuery({
    ...consoleQueueConversationOptions({ path: { conversation_id: selected ?? "" } }),
    retry: false,
    enabled: open && selected !== null,
  });
  const reply = useMutation({ ...consoleQueueReplyMutation(), onSuccess: () => detail.refetch() });
  if (!open) return null;
  return (
    <SupportQueue
      data={list.data ?? { counts: {}, items: [] }}
      detail={selected === null ? null : (detail.data ?? null)}
      open={open}
      onOpenChange={(o) => {
        if (!o) setSelected(null);
        onOpenChange(o);
      }}
      onSelect={setSelected}
      onReply={(conversationId, body) => {
        reply.mutate({
          path: { conversation_id: conversationId },
          headers: { "Idempotency-Key": idempotencyKey() },
          body: { body },
        });
      }}
    />
  );
}

function PlanRequests(): JSX.Element | null {
  const client = useQueryClient();
  const [shown, setShown] = useState(false);
  const q = useQuery({ ...consolePlanRequestsOptions(), retry: false });
  const mark = useMutation({
    ...consoleMarkAppliedMutation(),
    onSuccess: () => client.invalidateQueries({ queryKey: consolePlanRequestsQueryKey() }),
  });
  if (q.data === undefined) return null;
  const tenants = [...new Set(q.data.items.map((r) => r.tenant_code))];
  return (
    <div className="flex flex-col gap-[8px]">
      <PlanRequestsTile
        data={q.data}
        selected={shown}
        onSelect={() => {
          setShown((s) => !s);
        }}
      />
      {shown
        ? tenants.map((code) => (
            <PlanRequestsCard
              key={code}
              tenantCode={code}
              data={q.data}
              onMarkApplied={(r) => {
                void consoleTenant({ path: { tenant_code: r.tenant_code } }).then((t) => {
                  if (t.data === undefined) return;
                  mark.mutate({
                    path: { request_id: r.id },
                    body: { entitlement_version: t.data.entitlement_version },
                  });
                });
              }}
            />
          ))
        : null}
    </div>
  );
}

export function LiveSections(): JSX.Element {
  const [tab, setTab] = useState<Tab>("sessions");
  const [queue, setQueue] = useState(false);
  return (
    <div className="flex flex-col gap-[12px]" data-console="sections">
      <div className="flex items-center gap-[12px]">
        <Segmented
          label={C.nav.sessions}
          options={TABS.map((t) => C.nav[t])}
          active={C.nav[tab]}
          onChange={(label) => {
            const found = TABS.find((t) => C.nav[t] === label);
            if (found !== undefined) setTab(found);
          }}
        />
        <button
          type="button"
          onClick={() => {
            setQueue(true);
          }}
        >
          <Pill variant="outline" size="sm">
            {C.nav.queue}
          </Pill>
        </button>
      </div>
      <PlanRequests />
      {tab === "sessions" ? <SessionsTab /> : null}
      {tab === "status" ? <StatusTab /> : null}
      {tab === "publications" ? <PublicationsTab /> : null}
      <Queue open={queue} onOpenChange={setQueue} />
    </div>
  );
}
