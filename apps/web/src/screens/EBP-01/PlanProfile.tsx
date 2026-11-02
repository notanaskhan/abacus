import type {
  AbacusModulesAssuranceEbpContractProviderOut as ProviderOut,
  PlanOut,
  ProvidersOut,
} from "@abacus/api-client";
import {
  ebpPlanEditMutation,
  ebpPlanOptions,
  ebpPlanQueryKey,
  ebpProvidersOptions,
} from "@abacus/api-client/query";
import {
  type CockpitCanvas,
  DASH,
  Icon,
  PaneAction,
  Pill,
  type ViewState,
  cn,
  date as formatDate,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type ReactNode, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useFlag } from "../../app-core/flags";
import { COPY } from "./copy";

// EBP-01 · Plan profile & service providers (A-05-T11; A-05 §2.1, F1; the handoff spec.md): the
// AUD-02 cockpit's Overview › Plan profile canvas over `GET …/ebp/plan` and `…/ebp/providers`
// (A-05-T10). States: a (complete), b (missing PN: the Form 5500 helper), c (provider mismatch:
// the EIN endings and Raise exception…, the TPA's "Correction requested"), d (edit mode with a
// sticky Save). Every figure and status is the server's: the browser computes no due date, no
// filer status and no SOC gap. The sponsor's EIN is never in the payload unmasked (P-12); until
// A-05-T18 captures it the row shows a dash (DEC-1955).

const BLOCK = "overflow-hidden rounded-pane bg-card shadow-e1";
const HEAD = "flex h-[32px] items-center px-[12px] text-section font-medium hairline-b";

function Block({
  title,
  right,
  name,
  children,
  className,
}: {
  title: string;
  right?: ReactNode;
  name: string;
  children: ReactNode;
  className?: string;
}): JSX.Element {
  return (
    <section data-ebp01={name} aria-label={title} className={cn(BLOCK, className)}>
      <h3 className={HEAD}>
        <span className="flex-1">{title}</span>
        {right}
      </h3>
      {children}
    </section>
  );
}

function KV({
  label,
  value,
  field,
  flagged = false,
  help,
  editing,
  onChange,
}: {
  label: string;
  value: string;
  field: string;
  flagged?: boolean;
  help?: string;
  editing?: string | undefined;
  onChange?: ((v: string) => void) | undefined;
}): JSX.Element {
  return (
    <div
      data-field={field}
      className="flex min-h-[33px] flex-col justify-center px-[12px] hairline-b"
    >
      <div className="flex items-center gap-[8px] text-body">
        <span className="flex-1 text-ink-2">{label}</span>
        {onChange !== undefined ? (
          <input
            aria-label={label}
            value={editing ?? value}
            onChange={(e) => {
              onChange(e.target.value);
            }}
            className="h-[24px] w-[220px] rounded-control bg-nested px-[8px] text-right text-ink focus:outline-none focus:ring-2 focus:ring-focus"
          />
        ) : (
          <span className={cn("text-right", value === DASH ? "text-ink-4" : "text-ink")}>
            {flagged && <Icon name="flag" className="mr-[4px] inline text-brick" aria-hidden />}
            {value}
          </span>
        )}
      </div>
      {help !== undefined && (
        <p data-help={field} className="pb-[6px] text-caption text-red-ink">
          {help}
        </p>
      )}
    </div>
  );
}

const day = (v: string, now: Date): string => formatDate(v, { now, withYear: true });

function PlanFacts({
  plan,
  draft,
  onDraft,
}: {
  plan: PlanOut;
  draft: Record<string, string> | null;
  onDraft: (key: string, v: string) => void;
}): JSX.Element {
  const editing = draft !== null;
  const now = useNow();
  const pn = plan.plan_number ?? DASH;
  const k = COPY.keys;
  return (
    <Block title={COPY.facts} name="facts">
      <KV label={k.planName} value={plan.plan_name} field="plan_name" />
      <KV
        label={k.sponsorEin}
        value={plan.sponsor_ein?.last4 != null ? `XX-XXX${plan.sponsor_ein.last4}` : DASH}
        field="sponsor_ein"
      />
      <KV
        label={k.pn}
        value={pn}
        field="plan_number"
        flagged={plan.plan_number === null}
        {...(plan.plan_number === null
          ? { help: COPY.missingPn.replace("{id}", plan.recordkeeper_id ?? DASH) }
          : {})}
        editing={draft?.plan_number}
        onChange={
          editing
            ? (v) => {
                onDraft("plan_number", v);
              }
            : undefined
        }
      />
      <KV
        label={k.recordkeeper}
        value={plan.recordkeeper_id ?? DASH}
        field="recordkeeper_plan_id"
        editing={draft?.recordkeeper_plan_id}
        onChange={
          editing
            ? (v) => {
                onDraft("recordkeeper_plan_id", v);
              }
            : undefined
        }
      />
      <KV
        label={k.planYear}
        value={`${day(plan.plan_year_start, now)} – ${day(plan.plan_year_end, now)}`}
        field="plan_year"
      />
      <KV label={k.planType} value={COPY.planType} field="plan_type" />
      <KV
        label={k.safeHarbor}
        value={COPY.safeHarbor[plan.safe_harbor] ?? plan.safe_harbor}
        field="safe_harbor"
      />
      <KV label={k.auditType} value={COPY.auditType[plan.audit_kind] ?? ""} field="audit_kind" />
    </Block>
  );
}

function StatusCard({ plan }: { plan: PlanOut }): JSX.Element {
  const k = COPY.keys;
  const now = useNow();
  return (
    <Block title={COPY.status} name="status">
      <KV
        label={k.filer}
        value={`${COPY.filer[plan.filer_status] ?? ""} ${COPY.participantsAtBoy(plan.participants_boy)}`}
        field="filer_status"
      />
      <KV label={k.eoy} value={String(plan.participants_eoy)} field="participants_eoy" />
      <KV label={k.due} value={day(plan.form5500_due_on, now)} field="form5500_due_on" />
    </Block>
  );
}

function ProviderRow({ p }: { p: ProviderOut }): JSX.Element {
  const flagged = p.check_note !== null;
  const variant =
    p.status === "received" ? "green" : p.status === "correction_requested" ? "amber" : "neutral";
  return (
    <tr data-provider={p.name} className="h-[44px] hairline-b align-top text-body">
      <td className="px-[12px] py-[6px] text-ink">{p.name}</td>
      <td className="px-[12px] py-[6px] text-ink-2">{COPY.roles[p.role] ?? p.role}</td>
      <td className="px-[12px] py-[6px] text-ink-2">
        {p.soc_report ?? COPY.noSoc}
        {flagged && (
          <p data-check-note className="mt-[2px] flex items-start gap-[4px] text-caption text-ink">
            <Icon name="triangle-alert" className="mt-[2px] text-amber" aria-hidden />
            <span>{p.check_note}</span>
          </p>
        )}
      </td>
      <td className="px-[12px] py-[6px]">
        <Pill variant={variant} size="sm">
          {COPY.statuses[p.status] ?? p.status}
        </Pill>
        {flagged && (
          <button type="button" data-raise className="mt-[4px] block text-caption text-ink-2">
            {COPY.raise}
          </button>
        )}
      </td>
    </tr>
  );
}

function Providers({ data }: { data: ProvidersOut | undefined }): JSX.Element {
  const c = COPY.columns;
  return (
    <Block
      title={COPY.providers}
      name="providers"
      right={
        data?.allowed_actions.includes("ebp_provider.manage") === true ? (
          <PaneAction label={COPY.add} />
        ) : undefined
      }
    >
      <table className="w-full table-fixed">
        <thead>
          <tr className="h-[30px] bg-nested text-caption text-ink-2">
            <th className="w-[220px] px-[12px] text-left font-normal">{c.provider}</th>
            <th className="w-[220px] px-[12px] text-left font-normal">{c.role}</th>
            <th className="px-[12px] text-left font-normal">{c.soc}</th>
            <th className="w-[160px] px-[12px] text-left font-normal">{c.status}</th>
          </tr>
        </thead>
        <tbody>
          {(data?.items ?? []).map((p) => (
            <ProviderRow key={p.id} p={p} />
          ))}
        </tbody>
      </table>
    </Block>
  );
}

export interface PlanProfileOptions {
  active?: boolean;
  /** The artboards' edit mode (EBP-01 d). */
  initialEditing?: boolean;
}

export function usePlanProfileCanvas(
  workItemId: string,
  options: PlanProfileOptions = {},
): CockpitCanvas {
  const on = useFlag("ebp.modules") === true;
  const active = (options.active ?? true) && on;
  const path = { path: { work_item_id: workItemId } };
  const plan = useQuery({ ...ebpPlanOptions(path), enabled: active, retry: false });
  const providers = useQuery({ ...ebpProvidersOptions(path), enabled: active, retry: false });
  const [draft, setDraft] = useState<Record<string, string> | null>(
    options.initialEditing === true ? {} : null,
  );
  const queryClient = useQueryClient();
  const save = useMutation({
    ...ebpPlanEditMutation(),
    onSuccess: (next) => {
      queryClient.setQueryData(ebpPlanQueryKey(path), next);
      setDraft(null);
    },
  });

  let state: ViewState = { kind: "ready" };
  if (!on) state = { kind: "flag-off", flag: "ebp.modules" };
  else if (plan.isError) {
    const status = (plan.error as { status?: number } | null)?.status;
    state =
      status === 404
        ? { kind: "restricted", reason: "walled" }
        : { kind: "error", retry: () => void plan.refetch() };
  } else if (plan.data === undefined) state = { kind: "loading" };

  const data = plan.data;
  const canEdit = data?.allowed_actions.includes("ebp_plan.edit") === true;
  const editing = draft !== null;
  const changed = draft !== null && Object.keys(draft).length > 0;
  return {
    title: COPY.title,
    well: true,
    state,
    actions: (
      <>
        {canEdit && !editing && (
          <PaneAction
            icon="pencil"
            label={COPY.edit}
            onClick={() => {
              setDraft({});
            }}
          />
        )}
        {editing && (
          <PaneAction
            kind="round"
            icon="check"
            label={COPY.save}
            disabled={!changed || save.isPending}
            onClick={() => {
              if (data === undefined) return;
              save.mutate({
                ...path,
                headers: { "Idempotency-Key": crypto.randomUUID() },
                body: {
                  fields: draft,
                  citation_note: COPY.noteRequired,
                  seen_version: data.version,
                },
              });
            }}
          />
        )}
        <PaneAction icon="file" label={COPY.sourceDocs} />
        {data !== undefined && <PaneAction label={COPY.invite} />}
      </>
    ),
    children:
      data === undefined ? null : (
        <div
          data-screen="EBP-01"
          data-editing={editing ? "true" : "false"}
          className="flex flex-col gap-[12px] p-[12px]"
        >
          <div className="grid grid-cols-2 gap-[12px]">
            <PlanFacts
              plan={data}
              draft={draft}
              onDraft={(key, v) => {
                setDraft((d) => ({ ...(d ?? {}), [key]: v }));
              }}
            />
            <StatusCard plan={data} />
          </div>
          <Providers data={providers.data} />
        </div>
      ),
  };
}
