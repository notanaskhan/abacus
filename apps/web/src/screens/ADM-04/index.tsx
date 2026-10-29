import type {
  AiPolicyOut,
  AiPolicySections,
  AutoModeDefaults,
  GateRowOut,
} from "@abacus/api-client";
import {
  aiClientDataOptions,
  aiClientDataQueryKey,
  aiPolicyOptions,
  aiPolicyVersionOptions,
  aiPolicyVersionsOptions,
  approveAiPolicyMutation,
  pauseFirmAgentsMutation,
  resumeFirmAgentsMutation,
  setAiClientDataMutation,
  firmMembersOptions,
  publishAiPolicyMutation,
  putAiPolicyDraftMutation,
} from "@abacus/api-client/query";
import {
  Button,
  Checkbox,
  ConfirmDialog,
  Dialog,
  DEFAULT_TZ,
  Drawer,
  ErrorState,
  Fieldset,
  Icon,
  Pill,
  Popover,
  SettingsLayout,
  SheetModal,
  Skeleton,
  Toggle,
  ValueRow,
  date,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useEffect, useState } from "react";
import { currentRoute, signIn } from "../../app-core/auth";
import { useCan } from "../../app-core/can";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useSession } from "../../app-core/session";
import { GROUPS } from "../ADM-01/copy";
import { COPY } from "./copy";

// ADM-04 · AI policy & approval gates (G-02-T25; docs/screens/ADM-04.md; DEC-831). T12 over the
// AI-policy contract (G-02-T15/T24): the provenance chip (the effective version, or "Awaiting
// approval · ‹approver›"), fieldsets A–E from `sections` with every locked cell a Lock and a
// disabled control (`locks`), the gate popover (where the gate appears and how it is logged), the
// dirty draft (PUT on change, If-Match), "Save as v4…" (the change summary, Effective, an approver
// who is never the requester; POST publishes and waits), the approver's "Approve v4", and the
// version-history drawer. Stricter-only is the server's (422 `policy_loosening_refused`).
//
// c and f (the dormant policy principal, DEC-53, ADR P-08) are fixture-only: in fixture builds
// the locked principal toggle opens "Allow policy acceptance?" and f shows the pill and the toast
// without a write; production keeps Off + Lock. No control lets the Accrued Agent approve, sign
// off, release, send, post or export.

export interface Adm04Opens {
  sheet?: boolean; // d
  popover?: number | null; // i: the gate row whose popover is open
  history?: boolean; // j
  confirm?: boolean; // c
  principalOn?: boolean; // f
  scrollTo?: "auto" | null; // h
}

const AUTO_KEYS = COPY.auto.rows.map(([k]) => k);
const TOLERANCES = ["4", "5", "6", "7", "8"].map((v) => ({ value: v, label: `${v}%` }));

// The opt-in answers 403 `forbidden` on a stale second factor (shell/mfa.tsx's test).
function isForbidden(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "detail" in error &&
    error.detail === "forbidden"
  );
}

/** The step-up slot (shell/mfa.tsx's "Confirm it's you"): publish, approve and the opt-in need a
 * fresh second factor (SPEC-349 AC-37, SPEC-036); a fresh sign-in returns here. */
function StepUp({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}): JSX.Element {
  const c = COPY.immediate;
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={c.stepUpTitle}
      description={c.stepUpBody}
    >
      <div className="flex justify-end gap-[8px]">
        <Button
          variant="secondary"
          onClick={() => {
            onOpenChange(false);
          }}
        >
          {c.cancel}
        </Button>
        <Button
          onClick={() => {
            signIn(currentRoute(), { forceLogin: true });
          }}
        >
          {c.signIn}
        </Button>
      </div>
    </Dialog>
  );
}

function locked(policy: AiPolicyOut, path: string): boolean {
  return policy.locks.some((l) => l.path === path || path.startsWith(`${l.path}.`));
}

function same(a: AiPolicySections, b: AiPolicySections): boolean {
  return JSON.stringify(a) === JSON.stringify(b);
}

function attestWord(g: GateRowOut): string {
  return g.attest == null ? COPY.attest.none : COPY.attest[g.attest];
}

function GateRow({ g, open }: { g: GateRowOut; open: boolean }): JSX.Element {
  const [action, approver] = COPY.rows[g.row] ?? [g.gate_key, g.approver_rule];
  const cell =
    g.policy_acceptance_available === true ? (
      <span className="flex items-center gap-[8px]">
        <Toggle label={action} checked={g.policy_acceptance_on === true} disabled size="small" />
        <span className="text-meta text-ink-3">
          {COPY.gates.policy(g.acceptance_policy_ref ?? "")}
        </span>
      </span>
    ) : (
      <span className="flex items-center gap-[4px] text-ink-4">
        {COPY.gates.notAllowed}
        <Icon name="lock" size={12} />
      </span>
    );
  const label = (
    <span className="truncate text-left">
      {g.row}. {action}
    </span>
  );
  return (
    <div
      role="row"
      data-gate={g.row}
      className="grid h-[40px] grid-cols-[360px_330px_230px_150px] items-center px-[12px] text-body hairline-b"
    >
      <span role="cell" className="min-w-0">
        {(g.where_shown ?? []).length > 0 ? (
          <Popover
            width={320}
            label={COPY.gates.popoverTitle}
            {...(open ? { forceState: "open" as const } : {})}
            trigger={
              <button type="button" className="max-w-full truncate text-left hover:underline">
                {label}
              </button>
            }
          >
            <div className="flex flex-col gap-[6px] p-[12px] text-body">
              <span className="font-medium">{COPY.gates.popoverTitle}</span>
              <span className="text-ink-2">{(g.where_shown ?? []).join(" · ")}</span>
              <span className="text-meta text-ink-3">{COPY.gates.popoverLog(g.log_action)}</span>
            </div>
          </Popover>
        ) : (
          label
        )}
      </span>
      <span role="cell" className="truncate text-ink-2">
        {approver}
      </span>
      <span role="cell">{cell}</span>
      <span role="cell" className="flex items-center gap-[4px] text-ink-3">
        {attestWord(g)}
        {g.policy_acceptance_available === true && <Icon name="lock" size={12} />}
      </span>
    </div>
  );
}

export interface ADM04Props {
  opens?: Adm04Opens;
  onNavigate?: (section: string) => void;
}

export function ADM04({ opens = {}, onNavigate }: ADM04Props): JSX.Element {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const me = useSession().user?.id ?? null;
  const queries = useQueryClient();
  const policy = useQuery(aiPolicyOptions());
  const members = useQuery(firmMembersOptions());
  const [sections, setSections] = useState<AiPolicySections | null>(null);
  const [version, setVersion] = useState(1);
  const [sheet, setSheet] = useState(opens.sheet === true);
  const [history, setHistory] = useState(opens.history === true);
  const [confirm, setConfirm] = useState(opens.confirm === true);
  const [attested, setAttested] = useState(false);
  const [principalOn, setPrincipalOn] = useState(opens.principalOn === true);
  const [approver, setApprover] = useState<string | null>(null);
  const saveDraft = useMutation(putAiPolicyDraftMutation());
  const [stepUp, setStepUp] = useState(false);
  const onError = (error: unknown): void => {
    if (isForbidden(error)) setStepUp(true);
  };
  const publish = useMutation({ ...publishAiPolicyMutation(), onError });
  const approve = useMutation({ ...approveAiPolicyMutation(), onError });

  const data = policy.data;
  useEffect(() => {
    if (data !== undefined && sections === null) {
      setSections(data.draft?.sections ?? data.sections);
      setVersion(data.draft?.version ?? 1);
    }
  }, [data, sections]);
  useEffect(() => {
    if (opens.principalOn === true) toast.show({ kind: "success", text: COPY.principal.toast });
  }, [opens.principalOn]);
  useEffect(() => {
    if (opens.scrollTo === "auto") {
      const el = document.getElementById("adm04-auto");
      // jsdom has no scrollIntoView.
      if (el !== null && "scrollIntoView" in el) el.scrollIntoView({ block: "start" });
    }
  }, [opens.scrollTo, sections]);

  if (policy.isPending || data === undefined || sections === null) {
    return policy.isError ? (
      <ErrorState title={COPY.title} onRetry={() => void policy.refetch()} />
    ) : (
      <div aria-busy="true" className="flex flex-col gap-[12px] p-[12px]">
        <Skeleton className="h-[46px] w-full" />
        <Skeleton className="h-[320px] w-full" />
      </div>
    );
  }

  const actions = data.actions ?? [];
  const canEdit = actions.includes("ai_policy.draft");
  const readOnly = !canEdit;
  const next = data.effective.version_no + 1;
  const dirty = !same(sections, data.sections);
  const pending = data.pending ?? null;
  const tolerance = sections.governance.override_tolerance_pct ?? 8;
  const effectiveTolerance = data.sections.governance.override_tolerance_pct ?? 8;

  const change = (patch: (s: AiPolicySections) => AiPolicySections): void => {
    const updated = patch(sections);
    setSections(updated);
    saveDraft.mutate(
      { body: { sections: updated }, headers: { "If-Match": version } },
      {
        onSuccess: (draft) => {
          setVersion(draft.version);
        },
      },
    );
  };
  const setAuto = (key: keyof AutoModeDefaults, on: boolean): void => {
    change((s) => ({ ...s, auto_mode_defaults: { ...s.auto_mode_defaults, [key]: on } }));
  };

  const others = (members.data ?? []).filter((m) => m.user_id !== me);
  const chosen =
    approver ?? others.find((m) => m.display_name === "Daniel Reyes")?.user_id ?? null;
  const effectiveOn = new Date(now.getTime() + 86_400_000).toISOString().slice(0, 10);
  const published = data.effective;
  const chip =
    pending !== null
      ? COPY.awaiting(pending.approver?.display_name ?? "")
      : COPY.chip(
          published.version_no,
          date(published.decided_at ?? published.effective_from, { now, tz, withYear: true }),
          published.requested_by?.display_name ?? "",
        );
  const principalLocked = locked(data, "policy_principal.on");
  const principalClickable = !readOnly && (!principalLocked || PLANNED_VISIBLE);

  return (
    <div data-screen="ADM-04" className="flex min-h-0 flex-1 flex-col">
      <SettingsLayout
        bare
        wide
        toolbar={{ nav: [], active: "", firm: "" }}
        title={COPY.title}
        navTitle="Settings"
        groups={GROUPS.map((g) => ({
          ...g,
          sections: g.sections.filter(
            (s) =>
              ["general", "people", "offices", "security", "audit-log", COPY.section].includes(
                s.id,
              ) || PLANNED_VISIBLE,
          ),
        })).filter((g) => g.sections.length > 0)}
        active={COPY.section}
        onSelect={(id) => {
          if (id !== COPY.section) onNavigate?.(id);
        }}
        dirty={dirty && pending === null}
        readOnly={readOnly}
        readOnlyText={COPY.readOnly}
        labels={{ save: COPY.saveAs(next), discard: COPY.discard, unsaved: COPY.unsaved }}
        onSave={() => {
          setSheet(true);
        }}
        onDiscard={() => {
          setSections(data.sections);
        }}
      >
        <div className="flex flex-col gap-[12px]">
          <div className="flex items-center gap-[8px]">
            <span className="rounded-pill bg-nested px-[10px] py-[3px] text-dense text-ink-2">
              {chip}
            </span>
            <span className="flex-1" />
            {pending !== null && actions.includes("ai_policy.approve") && (
              <Button
                size="sm"
                onClick={() => {
                  approve.mutate(
                    { path: { version_no: pending.version_no } },
                    { onSuccess: () => void queries.invalidateQueries() },
                  );
                }}
              >
                {COPY.approve(pending.version_no)}
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setHistory(true);
              }}
            >
              {COPY.history}
            </Button>
          </div>

          {(data.immediate.client_data_opt_in.on || actions.includes("firm_agents.pause")) && (
            <ImmediateBand policy={data} canPause={actions.includes("firm_agents.pause")} />
          )}

          <Fieldset
            title={COPY.gates.title}
            action={<span className="text-meta text-ink-3">{COPY.gates.band}</span>}
            flush
          >
            <div role="table" aria-label={COPY.gates.title}>
              <div
                role="row"
                className="grid h-[30px] grid-cols-[360px_330px_230px_150px] items-center bg-card px-[12px] text-meta font-medium text-ink-2 hairline-b"
              >
                {COPY.gates.columns.map((c) => (
                  <span key={c} role="columnheader">
                    {c}
                  </span>
                ))}
              </div>
              {data.gates.map((g) => (
                <GateRow key={g.row} g={g} open={opens.popover === g.row} />
              ))}
            </div>
            <p className="px-[12px] py-[8px] text-meta text-ink-3">{COPY.gates.footer}</p>
          </Fieldset>

          <Fieldset
            title={COPY.principal.title}
            action={
              principalOn ? (
                <Pill variant="green-tint">{COPY.principal.on}</Pill>
              ) : (
                <Pill variant="amber">{COPY.principal.off}</Pill>
              )
            }
          >
            <ValueRow
              kind="toggle"
              label={COPY.principal.allow}
              checked={principalOn}
              disabled={!principalClickable}
              lock={principalLocked && !PLANNED_VISIBLE}
              onChange={(on) => {
                if (on) setConfirm(true);
                else setPrincipalOn(false);
              }}
            />
            <ValueRow kind="info" label={COPY.principal.aje} indented>
              {null}
            </ValueRow>
            <ValueRow kind="info" label={COPY.principal.doc} indented>
              {null}
            </ValueRow>
            <p className="px-[12px] py-[8px] text-para text-ink-2">{COPY.principal.help}</p>
            <ValueRow kind="value" label={COPY.principal.requires}>
              {COPY.principal.requiresValue}
            </ValueRow>
          </Fieldset>

          <div id="adm04-auto">
            <Fieldset title={COPY.auto.title}>
              <p className="px-[12px] pt-[8px] text-meta text-ink-3">{COPY.auto.help}</p>
              {COPY.auto.rows.map(([key, label]) => (
                <ValueRow
                  key={key}
                  kind="toggle"
                  label={label}
                  checked={sections.auto_mode_defaults[key] === true}
                  disabled={
                    readOnly ||
                    locked(data, `auto_mode_defaults.${key}`) ||
                    // Stricter only: Auto mode turns on only where the effective policy has it.
                    (sections.auto_mode_defaults[key] !== true &&
                      data.sections.auto_mode_defaults[key] !== true)
                  }
                  lock={locked(data, `auto_mode_defaults.${key}`)}
                  {...(data.real_firm ? { help: COPY.auto.realFirm } : {})}
                  onChange={(on) => {
                    setAuto(key, on);
                  }}
                />
              ))}
            </Fieldset>
          </div>

          <Fieldset title={COPY.data.title}>
            <ValueRow
              kind="toggle"
              label={COPY.data.consent}
              checked={sections.client_data.require_7216_consent !== false}
              disabled
              lock={locked(data, "client_data.require_7216_consent")}
              help={
                <span>
                  {COPY.data.consentHelp} <span className="text-ink-2">{COPY.data.registry}</span>
                </span>
              }
            />
            <ValueRow kind="value" label={COPY.data.template}>
              {COPY.data.templateValue}
            </ValueRow>
            <ValueRow
              kind="toggle"
              label={COPY.data.disclosure}
              checked={sections.client_data.disclosure_in_letters !== false}
              disabled={readOnly || sections.client_data.disclosure_in_letters !== false}
              onChange={(on) => {
                change((s) => ({
                  ...s,
                  client_data: { ...s.client_data, disclosure_in_letters: on },
                }));
              }}
            />
            <ValueRow kind="value" label={COPY.data.region} trailing="lock">
              {COPY.data.regionValue}
            </ValueRow>
            <ValueRow kind="value" label={COPY.data.training} trailing="lock">
              {COPY.data.trainingValue}
            </ValueRow>
            <p className="px-[12px] pt-[10px] text-meta font-medium text-ink-2">
              {COPY.data.subProcessors}
            </p>
            {data.sub_processors.map((p) => (
              <ValueRow key={p.name} kind="value" label={`${p.name} · ${p.region}`}>
                {COPY.data.dpa}
              </ValueRow>
            ))}
          </Fieldset>

          <Fieldset title={COPY.governance.title}>
            <ValueRow kind="value" label={COPY.governance.install}>
              {COPY.governance.installValue[sections.governance.install_role ?? "manager_plus"]}
            </ValueRow>
            <ValueRow kind="value" label={COPY.governance.publish}>
              {COPY.governance.publishValue}
            </ValueRow>
            <ValueRow
              kind="select"
              label={COPY.governance.tolerance}
              value={String(tolerance)}
              options={TOLERANCES.filter((o) => Number(o.value) <= effectiveTolerance)}
              readOnly={readOnly}
              help={COPY.governance.toleranceHelp}
              onChange={(v) => {
                change((s) => ({
                  ...s,
                  governance: { ...s.governance, override_tolerance_pct: Number(v) },
                }));
              }}
            />
            <ValueRow kind="value" label={COPY.governance.sample}>
              {COPY.governance.sampleValue(sections.governance.accuracy_sample_n ?? 25)}
            </ValueRow>
            <ValueRow kind="value" label={COPY.governance.retention} trailing="lock">
              {COPY.governance.retentionValue(sections.governance.trace_retention_years ?? 7)}
            </ValueRow>
          </Fieldset>
        </div>
      </SettingsLayout>

      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title={COPY.principal.confirmTitle}
        confirmLabel={COPY.principal.confirmAllow}
        cancelLabel={COPY.principal.cancel}
        destructive={false}
        onConfirm={() => {
          if (!attested) return;
          setPrincipalOn(true);
          toast.show({ kind: "success", text: COPY.principal.toast });
        }}
      >
        <p className="text-para text-ink-2">{COPY.principal.confirmBody}</p>
        <Checkbox label={COPY.principal.confirmCheck} checked={attested} onChange={setAttested} />
      </ConfirmDialog>

      <SheetModal
        open={sheet}
        onOpenChange={setSheet}
        title={COPY.sheet.title(next)}
        footer={
          <Button
            disabled={chosen === null || !dirty}
            loading={publish.isPending}
            onClick={() => {
              if (chosen === null) return;
              publish.mutate(
                { body: { effective_from: effectiveOn, approver_user_id: chosen } },
                {
                  onSuccess: () => {
                    setSheet(false);
                    void queries.invalidateQueries();
                  },
                },
              );
            }}
          >
            {COPY.sheet.publish(next)}
          </Button>
        }
      >
        <Fieldset title={COPY.sheet.changes}>
          {tolerance !== effectiveTolerance && (
            <ValueRow kind="info" label={COPY.sheet.tolerance(effectiveTolerance, tolerance)}>
              {null}
            </ValueRow>
          )}
          {AUTO_KEYS.filter(
            (k) => sections.auto_mode_defaults[k] !== data.sections.auto_mode_defaults[k],
          ).map((k) => (
            <ValueRow key={k} kind="info" label={COPY.auto.rows.find(([x]) => x === k)?.[1] ?? k}>
              {null}
            </ValueRow>
          ))}
        </Fieldset>
        <Fieldset>
          <ValueRow kind="value" label={COPY.sheet.effective}>
            {date(`${effectiveOn}T12:00:00Z`, { now, tz, withYear: true })}
          </ValueRow>
          <ValueRow
            kind="select"
            label={COPY.sheet.approver}
            value={chosen ?? ""}
            options={others.map((m) => ({ value: m.user_id, label: m.display_name }))}
            onChange={setApprover}
          />
        </Fieldset>
      </SheetModal>

      <HistoryDrawer open={history} onOpenChange={setHistory} />
      <StepUp open={stepUp} onOpenChange={setStepUp} />
    </div>
  );
}

function ImmediateBand({
  policy,
  canPause,
}: {
  policy: AiPolicyOut;
  canPause: boolean;
}): JSX.Element {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const queries = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  const done = { onSuccess: () => void queries.invalidateQueries() };
  const pause = useMutation({ ...pauseFirmAgentsMutation(), ...done });
  const resume = useMutation({ ...resumeFirmAgentsMutation(), ...done });
  const { client_data_opt_in: optIn, agent_stages: stages, firm_pause: firm } = policy.immediate;
  const c = COPY.immediate;
  // SPEC-036's opt-in: turning it on needs the disclosure read and a fresh sign-in (403 opens
  // the step-up); turning it off is stricter and needs neither dialog.
  const canOptIn = useCan("firm.ai_client_data");
  const optInState = useQuery({ ...aiClientDataOptions(), enabled: canOptIn, retry: false });
  const [disclosing, setDisclosing] = useState(false);
  const [read, setRead] = useState(false);
  const [stepUp, setStepUp] = useState(false);
  const setOptIn = useMutation({
    ...setAiClientDataMutation(),
    onSuccess: (next) => {
      queries.setQueryData(aiClientDataQueryKey(), next);
      setRead(false);
      void queries.invalidateQueries();
    },
    onError: (error) => {
      if (isForbidden(error)) setStepUp(true);
    },
  });
  const disclosure = optInState.data?.disclosure ?? null;
  const optInLabel = optIn.on
    ? c.on(date(optIn.changed_at ?? "", { now, tz }), optIn.changed_by?.display_name ?? "")
    : c.off;
  return (
    <Fieldset title={c.title} data-band="immediate">
      {canOptIn ? (
        <ValueRow
          kind="toggle"
          label={c.clientData}
          checked={optIn.on}
          disabled={setOptIn.isPending || optInState.data?.available !== true}
          help={optInState.data?.available === false ? c.unavailable : optInLabel}
          onChange={(on) => {
            if (on) setDisclosing(true);
            else setOptIn.mutate({ body: { on: false } });
          }}
        />
      ) : (
        <ValueRow kind="value" label={c.clientData}>
          {optInLabel}
        </ValueRow>
      )}
      {stages.map((s) => (
        <ValueRow key={s.agent_key} kind="value" label={c.agentNames[s.agent_key] ?? s.agent_key}>
          {c.stage[s.stage]}
        </ValueRow>
      ))}
      <ValueRow kind="value" label={c.agents} help={c.pauseHelp}>
        <span className="flex items-center gap-[8px]">
          {firm.paused ? c.paused : c.running}
          {canPause && (
            <Button
              size="sm"
              variant={firm.paused ? "primary" : "secondary"}
              disabled={pause.isPending || resume.isPending}
              onClick={() => {
                if (firm.paused) resume.mutate({});
                else setConfirm(true);
              }}
            >
              {firm.paused ? c.resume : c.pause}
            </Button>
          )}
        </span>
      </ValueRow>
      <ConfirmDialog
        open={disclosing}
        onOpenChange={setDisclosing}
        title={c.turnOnTitle}
        confirmLabel={c.turnOn}
        cancelLabel={c.cancel}
        destructive={false}
        onConfirm={() => {
          if (read) setOptIn.mutate({ body: { on: true } });
        }}
      >
        {disclosure !== null && (
          <dl className="flex flex-col gap-[4px] text-body">
            <dt className="font-medium">{c.whoRuns}</dt>
            <dd className="text-ink-3">
              {c.whoRunsValue(disclosure.provider, disclosure.region)}
            </dd>
            <dt className="font-medium">{c.yourData}</dt>
            <dd className="text-ink-3">{c.yourDataValue}</dd>
            {disclosure.subprocessors.length > 0 && (
              <>
                <dt className="font-medium">{c.subprocessors}</dt>
                <dd className="text-ink-3">{disclosure.subprocessors.join(", ")}</dd>
              </>
            )}
            <dt className="font-medium">{c.letter}</dt>
            <dd className="text-ink-3">{disclosure.letter_wording}</dd>
            <dt className="font-medium">{c.reviewedBy}</dt>
            <dd className="text-ink-3 tabular-nums">{disclosure.review_by}</dd>
          </dl>
        )}
        <Checkbox label={c.read} checked={read} onChange={setRead} />
      </ConfirmDialog>
      <StepUp open={stepUp} onOpenChange={setStepUp} />
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title={c.confirmPause}
        confirmLabel={c.pause}
        cancelLabel={c.cancel}
        destructive
        onConfirm={() => {
          pause.mutate({});
        }}
      >
        <p className="text-para text-ink-2">{c.pauseHelp}</p>
      </ConfirmDialog>
    </Fieldset>
  );
}

function HistoryDrawer({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}): JSX.Element {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const versions = useQuery({ ...aiPolicyVersionsOptions(), enabled: open });
  const [picked, setPicked] = useState<number | null>(null);
  const detail = useQuery({
    ...aiPolicyVersionOptions({ path: { version_no: picked ?? 0 } }),
    enabled: open && picked !== null,
  });
  return (
    <Drawer open={open} onOpenChange={onOpenChange} title={COPY.drawer.title}>
      <ul className="flex flex-col">
        {(versions.data?.items ?? []).map((v) => (
          <li key={v.version_no} className="hairline-b">
            <button
              type="button"
              className="flex w-full items-center justify-between px-[12px] py-[9px] text-left text-body"
              onClick={() => {
                setPicked(v.version_no);
              }}
            >
              <span className="font-medium">{COPY.drawer.version(v.version_no)}</span>
              <span className="text-ink-3">
                {date(v.decided_at ?? v.effective_from, { now, tz, withYear: true })}
              </span>
            </button>
            {picked === v.version_no &&
              (detail.data?.diff ?? []).map((d) => (
                <p key={d.path} className="px-[12px] pb-[6px] text-meta text-ink-3">
                  {d.path}: {JSON.stringify(d.before)} → {JSON.stringify(d.after)}
                </p>
              ))}
          </li>
        ))}
      </ul>
    </Drawer>
  );
}
