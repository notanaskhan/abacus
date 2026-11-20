// FIL-02 · Retention & legal hold (Q-05-T21, TASK-8827; docs/screens/FIL-02.md; handoff FIL-02): T1
// at /files/retention. Policies with the legal minimum beside the firm's longer policy; holds;
// the destruction batch with two approvals and the typed confirmation (enabled only on the exact
// phrase); held documents excluded; read-only for non-admins; the policy drawer with its versions;
// Place hold (until released, notify); the destroyed state with its certificate. Every figure is
// the server's (retention, legal holds, destruction batches); the agent destroys nothing.
import type { RetentionPolicyOut } from "@abacus/api-client";
import {
  destructionApprovalMutation,
  destructionBatchesOptions,
  listLegalHoldsOptions,
  listRetentionPoliciesOptions,
  retentionPolicyVersionsOptions,
  retentionSummaryOptions,
} from "@abacus/api-client/query";
import {
  Button,
  Dialog,
  Drawer,
  Pill,
  Segmented,
  Skeleton,
  Toggle,
  count,
  date,
} from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { COPY as C } from "./copy";
import { useSession } from "../../app-core/session";

export type Fil02Tab = "policies" | "holds" | "destruction";

export interface FIL02Props {
  tab?: Fil02Tab;
  readOnly?: boolean;
  /** d, g, h: an overlay open on arrival. */
  initial?: "approve" | "drawer" | "hold" | undefined;
  /** g: the version id of the policy whose drawer opens. */
  drawerPolicyId?: string | undefined;
}

function Tile({
  n,
  label,
  tone,
}: {
  n: string;
  label: string;
  tone: "neutral" | "amber" | "muted";
}): JSX.Element {
  return (
    <div
      className="flex h-[72px] w-[120px] flex-col items-center justify-center gap-[4px] rounded-[12px] bg-card shadow-e1"
      data-fil02="tile"
    >
      <span className="text-[18px] tabular-nums">{n}</span>
      <Pill variant={tone}>{label}</Pill>
    </div>
  );
}

export function FIL02({
  tab = "policies",
  readOnly = false,
  initial,
  drawerPolicyId,
}: FIL02Props): JSX.Element {
  const firmName = useSession().tenant?.firm_name ?? "";
  const sum = useQuery(retentionSummaryOptions());
  const pol = useQuery(listRetentionPoliciesOptions());
  const hld = useQuery(listLegalHoldsOptions());
  const bat = useQuery(destructionBatchesOptions());
  const [active, setActive] = useState<Fil02Tab>(tab);
  const [overlay, setOverlay] = useState(initial);
  const [typed, setTyped] = useState("");
  const [until, setUntil] = useState(true);
  const approve = useMutation(destructionApprovalMutation());
  const versions = useQuery({
    ...retentionPolicyVersionsOptions({ path: { policy_id: drawerPolicyId ?? "" } }),
    enabled: overlay === "drawer" && drawerPolicyId !== undefined,
  });
  if (
    sum.data === undefined ||
    pol.data === undefined ||
    hld.data === undefined ||
    bat.data === undefined
  ) {
    return <Skeleton aria-label={C.title} className="h-[700px] w-full" />;
  }
  const s = sum.data;
  const batch = bat.data.items[0];
  const tabs = {
    policies: `${C.tabs.policies} ${String(s.policies)}`,
    holds: `${C.tabs.holds} ${String(s.active_holds)}`,
    destruction: `${C.tabs.destruction} ${String(s.pending_batches)}`,
  };
  const left = batch ? batch.eligible_count - batch.held_excluded_count : 0;
  return (
    <div data-screen="FIL-02" className="flex flex-col gap-[8px] px-[12px]">
      <div className="flex h-[42px] items-center justify-between">
        <span className="text-[14px] text-ink-2">{C.back}</span>
        <h1 className="text-[15px] font-medium">
          {C.title} <span className="font-normal text-ink-2">{firmName}</span>
        </h1>
        <span />
      </div>
      <div className="flex justify-center">
        <Segmented
          size="small"
          label={C.title}
          active={tabs[active]}
          options={[tabs.policies, tabs.holds, tabs.destruction]}
          onChange={(v) => {
            setActive((Object.keys(tabs) as Fil02Tab[]).find((k) => tabs[k] === v) ?? "policies");
          }}
        />
      </div>
      <div className="flex items-center gap-[8px]">
        <Tile n={String(s.policies)} label={C.tiles.policies} tone="neutral" />
        <Tile n={String(s.active_holds)} label={C.tiles.holds} tone="amber" />
        <Tile n={String(s.pending_batches)} label={C.tiles.awaiting} tone="amber" />
        <Tile n={count(s.pending_documents)} label={C.tiles.eligible} tone="muted" />
        <span className="ml-auto text-[12.5px] text-ink-3">
          {C.lastDestruction(
            s.last_certificate_at ? date(s.last_certificate_at, { now: 0, withYear: true }) : "",
            s.last_certificate_ref ?? "",
          )}
        </span>
      </div>
      {readOnly ? (
        <p className="text-[12.5px] text-ink-3" data-fil02="read-only">
          {C.readOnly}
        </p>
      ) : null}
      {active === "policies" ? (
        <section aria-label={C.tabs.policies} className="rounded-card bg-card shadow-e1">
          <div className="flex h-[46px] items-center justify-between px-[12px]">
            <span />
            <h2 className="text-[13.5px] font-medium">{C.tabs.policies}</h2>
            {readOnly ? (
              <span />
            ) : (
              <Button variant="primary" size="sm">
                {C.newPolicy}
              </Button>
            )}
          </div>
          <table className="w-full text-[13px]">
            <thead>
              <tr className="h-[30px] bg-nested text-[11.5px]">
                {C.columns.map((c) => (
                  <th key={c} className="px-[10px] text-left font-medium">
                    {c}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pol.data.items.map((p: RetentionPolicyOut) => {
                const [label, legal] = C.records[p.record_type] ?? [p.record_type, ""];
                return (
                  <tr
                    key={p.record_type}
                    className="h-[44px] border-t border-hair"
                    data-fil02="policy"
                  >
                    <td className="px-[10px]">{label}</td>
                    <td className="px-[10px] text-[12px] text-ink-2">{legal}</td>
                    <td className="px-[10px]">{C.years(p.firm_years)}</td>
                    <td className="px-[10px]">
                      {C.anchors[p.clock_start_event] ?? p.clock_start_event}
                    </td>
                    <td className="px-[10px]">
                      {p.lock ? <Pill variant="soon">{C.locked}</Pill> : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <p className="px-[12px] py-[8px] text-[12px] text-ink-3">{C.footer}</p>
        </section>
      ) : null}
      {active === "holds" ? (
        <section aria-label={C.tabs.holds} className="rounded-card bg-card shadow-e1">
          <div className="flex h-[46px] items-center justify-between px-[12px]">
            <span />
            <h2 className="text-[13.5px] font-medium">{C.tabs.holds}</h2>
            {readOnly ? (
              <span />
            ) : (
              <Button
                variant="primary"
                size="sm"
                onClick={() => {
                  setOverlay("hold");
                }}
              >
                {C.placeHold}
              </Button>
            )}
          </div>
          {hld.data.items.map((h) => (
            <div
              key={h.id}
              className="flex h-[44px] items-center gap-[10px] border-t border-hair px-[12px] text-[13px]"
              data-fil02="hold"
            >
              <span className="flex-1">{`TY${String(h.tax_year ?? "")}`}</span>
              <span>{C.reasons[h.reason_code] ?? h.reason_code}</span>
              <span>{h.placed_by}</span>
              <Pill variant="amber">{C.active}</Pill>
            </div>
          ))}
        </section>
      ) : null}
      {active === "destruction" && batch ? (
        <section
          aria-label={C.tabs.destruction}
          className="rounded-card bg-card p-[12px] shadow-e1"
          data-fil02="batch"
        >
          <h2 className="text-[13.5px] font-medium">{C.batch(batch.ref)}</h2>
          <p className="text-[13px] tabular-nums">{count(left)}</p>
          {batch.held_excluded_count > 0 && batch.status !== "destroyed" ? (
            <p className="text-[12.5px] text-amber-ink">
              {C.excluded(batch.held_excluded_count, left)}
            </p>
          ) : null}
          <h3 className="mt-[8px] text-[12px] font-medium">{C.approvals}</h3>
          {batch.approvals.map((a) => (
            <p
              key={a.approver_role}
              className="text-[12.5px]"
            >{`${a.approver.name} · ${a.approver_role}`}</p>
          ))}
          {batch.status === "destroyed" ? (
            <p className="mt-[8px] flex items-center gap-[8px] text-[13px]">
              <Pill variant="muted">{C.destroyed}</Pill>
              {C.certificate(batch.certificate_ref ?? "")}
            </p>
          ) : (
            <>
              <p className="text-[12.5px] text-ink-3">{C.secondApproval}</p>
              {readOnly ? null : (
                <Button
                  variant="primary"
                  onClick={() => {
                    setOverlay("approve");
                  }}
                >
                  {C.approveBatch}
                </Button>
              )}
            </>
          )}
        </section>
      ) : null}
      <Dialog
        open={overlay === "approve"}
        onOpenChange={(o) => {
          setOverlay(o ? "approve" : undefined);
        }}
        title={C.dialog.title(left)}
        description={C.dialog.type(batch?.confirmation_phrase ?? "")}
      >
        <input
          aria-label={C.dialog.type(batch?.confirmation_phrase ?? "")}
          className="mx-[12px] rounded-[8px] px-[8px] shadow-e1"
          value={typed}
          onChange={(e) => {
            setTyped(e.target.value);
          }}
        />
        <div className="flex justify-end p-[12px]">
          <Button
            variant="destructive"
            disabled={typed !== batch?.confirmation_phrase}
            onClick={() => {
              if (!batch) return;
              approve.mutate({
                path: { batch_id: batch.batch_id },
                body: { items_seen: left, confirmation: typed },
                headers: { "Idempotency-Key": `fil02-${crypto.randomUUID()}` },
              });
              setOverlay(undefined);
            }}
          >
            {C.dialog.confirm}
          </Button>
        </div>
      </Dialog>
      <Dialog
        open={overlay === "hold"}
        onOpenChange={(o) => {
          setOverlay(o ? "hold" : undefined);
        }}
        title={C.holdSheet.title}
      >
        <div className="px-[12px]">
          <Toggle label={C.holdSheet.until} checked={until} onChange={setUntil} />
        </div>
        <div className="flex justify-end p-[12px]">
          <Button variant="primary">{C.holdSheet.place}</Button>
        </div>
      </Dialog>
      <Drawer
        open={overlay === "drawer"}
        onOpenChange={(o) => {
          setOverlay(o ? "drawer" : undefined);
        }}
        title={C.drawer.title}
      >
        <h3 className="px-[12px] text-[12px] font-medium">{C.drawer.versions}</h3>
        {(versions.data?.items ?? []).map((v) => (
          <p
            key={v.version_id}
            className="px-[12px] text-[12.5px]"
            data-fil02="version"
          >{`v${String(v.version_no)} · ${String(v.retention_years)} years · ${v.created_by.name}${v.policy_text ? ` · ${v.policy_text}` : ""}`}</p>
        ))}
      </Drawer>
    </div>
  );
}
