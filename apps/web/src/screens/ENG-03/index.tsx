import type {
  EngagementDraftOut,
  EngagementGateOut,
  EngagementTypeEntryOut,
} from "@abacus/api-client";
import { createEngagementDraftMutation } from "@abacus/api-client/query";
import {
  Button,
  type CatalogueGroup,
  DEFAULT_TZ,
  Dialog,
  Fieldset,
  GateCard,
  Icon,
  Pill,
  Segmented,
  TypeCatalogue,
  ValueRow,
  Wizard,
  type WizardStep,
  date,
  time,
  toast,
} from "@abacus/ui";
import { useMutation } from "@tanstack/react-query";
import { type JSX, useEffect, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useEntitlement } from "../../app-core/flags";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useSession } from "../../app-core/session";
import { useClientRecord } from "../../domain/clients";
import { useStaffNames } from "../../domain/requests";
import {
  type ConsentPreview,
  conflictOf,
  useDraft,
  useDraftWrites,
  useEngagementTypes,
} from "../../domain/engagements";
import { COPY, type StepCode } from "./copy";

// ENG-03 · New engagement wizard, core (P-07-T21; docs/screens/ENG-03.md). O6 `Wizard` with the
// TPL-18 type catalogue and gate cards (F-05-T38) over `GET /v1/engagement-types` and one draft
// (`/v1/engagement-drafts/{id}`): the six steps, the gate block (G1–G3 from the draft's gates),
// autosave with `seen_version` ("Draft · saved 9:39 AM"), "Discard this draft?", "Start
// acceptance" while G1 is unmet, and Create (a person's click, with an Idempotency-Key). Each
// artboard is its data (fixtures/scenarios/ENG-03.ts):
//
//   a  step 1, Fairhaven Foods 401(k) Plan, EBP audit selected, G1 met Aug 28
//   b  step 2: standards and the §103(a)(3)(C) scope
//   c  step 4: five team rows, Fiona Nash's independence requested (G2 blocks her only)
//   d  Granite Peak, FS audit, no acceptance decision: G1 unmet, Next disabled, Start acceptance
//   f  a with the Single audit tile's tooltip: "Not in this release. …"
//
// P-07-T34 (DEC-345): the steps re-shape by the selected type's catalogue schema (tax "Return
// setup", attest standards and EQR, the planned CAS close plan, the advisory proposal), and:
//
//   e  Ferris, Form 1040, step 5: the §7216 consents card (fixture-only until C19, passed in as
//      `consents`); Create answers 409 `possible_duplicate`: "Open it · Create anyway"
//   g  Harlow & Pike, FS audit: the Group audit (SAS 149) toggle with entitlement `group_audit`
//   h  Tessellate, SOC 2 (entitlement `attest`) on step 2
//
// "Set up with AI" (ENG-14, K-04) and the proposal (ENG-09, T-09) are planned: fixture builds draw
// them disabled with their hints; production draws neither. Single audit is a static tile, never a
// catalogue type (D10).

const STEPS: readonly StepCode[] = [
  "client_type",
  "standards_methodology",
  "period_deadlines",
  "team_independence",
  "binder_portal",
  "letter_review",
];

const GROUP_LOOK: Readonly<
  Record<EngagementTypeEntryOut["family"], Pick<CatalogueGroup, "tone" | "icon">>
> = {
  tax: { tone: "clay", icon: "file-text" },
  audit_assurance: { tone: "espresso", icon: "file-search" },
  cas_advisory: { tone: "green", icon: "landmark" },
};

/** The catalogue as the kit's groups, with the static Single audit tile after the audit types. */
export function catalogueGroups(items: readonly EngagementTypeEntryOut[]): CatalogueGroup[] {
  const families: EngagementTypeEntryOut["family"][] = ["tax", "audit_assurance", "cas_advisory"];
  return families.map((family) => ({
    id: family,
    label: COPY.groups[family].toUpperCase(),
    ...GROUP_LOOK[family],
    types: [
      ...items
        .filter((i) => i.family === family)
        .map((i) => ({
          id: i.code,
          label: i.label,
          sub: i.standard_line,
          ...(i.entitlement == null ? {} : { entitlement: i.entitlement }),
        })),
      ...(family === "audit_assurance"
        ? [
            {
              id: "coming-soon-tile",
              label: COPY.comingSoon.label,
              sub: COPY.comingSoon.sub,
              comingSoon: true,
            },
          ]
        : []),
    ],
  }));
}

function gate(draft: EngagementDraftOut, id: EngagementGateOut["gate"]) {
  return draft.gates?.find((g) => g.gate === id);
}

export interface ENG03Props {
  draftId: string;
  onClose?: () => void;
  onCreated?: (engagementId: string) => void;
  /** e's "Open it": the engagement a duplicate answer names. */
  onOpen?: (engagementId: string) => void;
  /** The §7216 consents card, fixture-only until C19 (DEC-345); the route never passes it. */
  consents?: ConsentPreview | undefined;
}

function duplicateOf(error: unknown): string | null {
  if (conflictOf(error) !== "possible_duplicate") return null;
  const facts = (error as { facts?: { engagement_id?: unknown } } | null)?.facts;
  return typeof facts?.engagement_id === "string" ? facts.engagement_id : "";
}

export function ENG03({
  draftId,
  onClose,
  onCreated,
  onOpen,
  consents,
}: ENG03Props): JSX.Element | null {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const draftQ = useDraft(draftId);
  const types = useEngagementTypes().data?.items ?? [];
  const writes = useDraftWrites(draftId);
  const staff = useStaffNames();
  const attest = useEntitlement("attest");
  const groupAudit = useEntitlement("group_audit");
  const [discarding, setDiscarding] = useState(false);
  const [duplicate, setDuplicate] = useState<string | null>(null);
  const draft = draftQ.data;
  const client = useClientRecord(draft?.client_id ?? "");
  if (draft === undefined) return null;

  const step = draft.step;
  const index = STEPS.indexOf(step);
  // The selected type's catalogue entry shapes the steps (P-07-T34; `steps_of` on the server).
  const entry = types.find((t) => t.code === draft.type_code);
  const kind = entry?.work_item_kind;
  const fieldsOf = (s: StepCode): readonly string[] =>
    entry?.steps.find((x) => x.step === s)?.field_codes ?? [];
  const stepLabel = (s: StepCode): string => {
    if (kind === undefined || (kind === "close" && !PLANNED_VISIBLE)) return COPY.steps[s];
    return COPY.stepByKind[kind]?.[s] ?? COPY.steps[s];
  };
  const steps: WizardStep[] = STEPS.map((s, i) => ({
    id: s,
    label: stepLabel(s),
    state: i < index ? "done" : i === index ? "current" : "todo",
  }));
  const g1 = gate(draft, "G1");
  const g2 = gate(draft, "G2");
  const g1Met = g1?.met === true;
  const pendingIds = new Set(
    (g2?.blockers ?? []).filter((b) => b.type === "user").map((b) => b.id),
  );
  const nameOf = (id: string | null | undefined): string =>
    id == null ? COPY.none : (staff.get(id) ?? COPY.none);

  const save = async (change: Parameters<typeof writes.save>[1]): Promise<void> => {
    try {
      await writes.save(draft, change);
    } catch {
      toast.show({ kind: "error", text: COPY.toast.failed });
    }
  };
  const go = (next: StepCode): void => {
    void save({ step: next });
  };

  const aside = (
    <div className="flex flex-col gap-[8px]">
      {g1?.met === true ? (
        <GateCard tone="met">
          {COPY.gates.g1(
            nameOf(g1.met_by_user_id),
            g1.met_at == null ? COPY.none : date(g1.met_at, { now, tz, withYear: true }),
          )}
        </GateCard>
      ) : (
        <GateCard
          tone="needs"
          action={
            <Button
              variant="secondary"
              size="sm"
              disabled={!(draft.allowed_actions ?? []).includes("client.intake")}
              onClick={() => {
                void writes.startAcceptance().then(() => {
                  toast.show({ kind: "success", text: COPY.gates.startAcceptance });
                });
              }}
            >
              {COPY.gates.startAcceptance}
            </Button>
          }
        >
          <span id="eng03-g1-reason">{COPY.gates.g1Unmet}</span>
        </GateCard>
      )}
      {g2 === undefined ? (
        <GateCard tone="met">{COPY.gates.g2NotRequired}</GateCard>
      ) : (
        <GateCard tone={g2.met ? "met" : "needs"}>
          {g2.met ? COPY.gates.g2Met : COPY.gates.g2}
        </GateCard>
      )}
      <GateCard tone="needs">{COPY.gates.g3}</GateCard>
    </div>
  );

  const groups = catalogueGroups(types);
  const entityName =
    client.data?.entities.find((e) => e.id === draft.client_entity_id)?.name ?? null;
  const displayLine =
    [draft.payload.name, entityName].filter((v) => v != null && v !== "").join(" · ") || COPY.none;
  const create = async (confirmDuplicate: boolean): Promise<void> => {
    try {
      const out = await writes.create(confirmDuplicate);
      setDuplicate(null);
      toast.show({ kind: "success", text: COPY.toast.created(draft.payload.name ?? "") });
      onCreated?.(out.engagement_id);
    } catch (error) {
      const other = duplicateOf(error);
      if (other !== null) setDuplicate(other);
      else toast.show({ kind: "error", text: COPY.toast.createFailed });
    }
  };
  const typeLine = [draft.payload.period_label, entry?.label]
    .filter((v) => v != null && v !== "")
    .join(" ");
  const notice =
    duplicate === null ? null : (
      <div
        role="status"
        data-duplicate=""
        className="flex min-h-[32px] items-center gap-[6px] rounded-pane bg-nested px-[12px] text-dense text-ink-2"
      >
        <span>{COPY.duplicate.notice(typeLine, client.data?.name ?? COPY.none)}</span>
        <span aria-hidden="true">·</span>
        <Button
          variant="link"
          size="sm"
          disabled={duplicate === "" || onOpen === undefined}
          onClick={() => {
            onOpen?.(duplicate);
          }}
        >
          {COPY.duplicate.open}
        </Button>
        <span aria-hidden="true">·</span>
        <Button
          variant="link"
          size="sm"
          disabled={writes.creating}
          onClick={() => void create(true)}
        >
          {COPY.duplicate.anyway}
        </Button>
      </div>
    );
  const team = draft.payload.team ?? [];
  const pendingName = team.find((m) => pendingIds.has(m.user_id));

  const body = (() => {
    switch (step) {
      case "client_type":
        return (
          <div className="flex flex-col gap-[10px]">
            {PLANNED_VISIBLE && (
              <section
                aria-label={COPY.ai.title}
                data-planned="ENG-14"
                className="flex items-center gap-[12px] rounded-pane bg-card px-[14px] py-[12px] shadow-e1"
              >
                <span
                  aria-hidden="true"
                  className="inline-flex size-[28px] shrink-0 items-center justify-center rounded-tile bg-espresso text-on-dark"
                >
                  <Icon name="sparkles" size={14} />
                </span>
                <span className="flex min-w-0 flex-1 flex-col gap-[2px]">
                  <span className="text-section">{COPY.ai.title}</span>
                  <span className="text-dense text-ink-2">{COPY.ai.body}</span>
                </span>
                <Button variant="secondary" size="sm" opensDialog disabled title={COPY.ai.hint}>
                  {COPY.ai.action}
                </Button>
              </section>
            )}
            <Fieldset title={COPY.card.client} flush>
              <ValueRow kind="info" label={COPY.keys.client}>
                {client.data?.name ?? COPY.none}
              </ValueRow>
              <ValueRow kind="info" label={COPY.keys.entity}>
                {client.data?.entities.find((e) => e.id === draft.client_entity_id)?.name ??
                  COPY.none}
              </ValueRow>
              <ValueRow kind="info" label={COPY.keys.acceptance}>
                {g1?.met === true && g1.met_at != null ? (
                  <span className="text-green-ink">
                    {COPY.acceptance(date(g1.met_at, { now, tz, withYear: true }))}
                  </span>
                ) : (
                  COPY.none
                )}
              </ValueRow>
              {PLANNED_VISIBLE && kind === "advisory_project" && (
                <ValueRow kind="info" label={COPY.keys.proposal}>
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled
                    title={COPY.advisory.proposalHint}
                    data-planned="ENG-09"
                  >
                    {COPY.advisory.proposal}
                  </Button>
                </ValueRow>
              )}
            </Fieldset>
            <TypeCatalogue
              groups={groups}
              entitlements={[
                ...(attest ? ["attest"] : []),
                ...(groupAudit ? ["group_audit"] : []),
              ]}
              selected={draft.type_code ?? null}
              soonLabel={COPY.comingSoon.badge}
              soonHint={COPY.comingSoon.tooltip}
              onSelect={(code) => {
                void save({ type_code: code });
              }}
            />
            <Fieldset title={COPY.card.name} flush>
              <ValueRow kind="info" label={COPY.keys.name}>
                {draft.payload.name ?? COPY.none}
              </ValueRow>
              <ValueRow kind="info" label={COPY.keys.display}>
                <span className="text-ink-3">{displayLine}</span>
              </ValueRow>
              {entry?.group_audit_allowed === true && groupAudit && (
                <ValueRow
                  kind="toggle"
                  label={COPY.groupAudit.label}
                  help={COPY.groupAudit.helper}
                  checked={draft.payload.group_audit === true}
                  onChange={(on) => {
                    void save({ payload: { ...draft.payload, group_audit: on } });
                  }}
                />
              )}
            </Fieldset>
          </div>
        );
      case "standards_methodology":
        return (
          <Fieldset title={stepLabel("standards_methodology")} flush>
            <ValueRow kind="info" label={COPY.keys.methodology}>
              {COPY.none}
            </ValueRow>
            {(entry === undefined || fieldsOf(step).includes("standards_code")) && (
              <ValueRow kind="info" label={COPY.keys.standardsSet}>
                {draft.payload.standards_code ?? COPY.none}
              </ValueRow>
            )}
            {(draft.type_code === "soc1" || draft.type_code === "soc2") && (
              <ValueRow kind="info" label={COPY.keys.period}>
                {draft.payload.period_label ?? COPY.none}
              </ValueRow>
            )}
            {PLANNED_VISIBLE && kind === "close" && (
              <ValueRow
                kind="info"
                label={COPY.closePlan.key}
                help={COPY.closePlan.hint}
                data-planned="C-01"
              >
                {COPY.none}
              </ValueRow>
            )}
            {(entry === undefined || draft.type_code === "ebp_audit") && (
              <ValueRow kind="info" label={COPY.keys.auditScope}>
                <Segmented
                  size="small"
                  label={COPY.keys.auditScope}
                  options={COPY.scope}
                  active={
                    draft.payload.scope_code === "full_scope" ? COPY.scope[1] : COPY.scope[0]
                  }
                  onChange={(label) => {
                    void save({
                      payload: {
                        ...draft.payload,
                        scope_code: label === COPY.scope[1] ? "full_scope" : "limited_scope",
                      },
                    });
                  }}
                />
              </ValueRow>
            )}
          </Fieldset>
        );
      case "period_deadlines":
        return (
          <Fieldset title={COPY.card.period} flush>
            <ValueRow kind="info" label={COPY.keys.periodStart}>
              {draft.payload.fiscal_period_start ?? COPY.none}
            </ValueRow>
            <ValueRow kind="info" label={COPY.keys.periodEnd}>
              {draft.payload.fiscal_period_end ?? COPY.none}
            </ValueRow>
          </Fieldset>
        );
      case "team_independence":
        return (
          <Fieldset title={COPY.card.team} flush>
            {[
              ...team.map((m) => ({ ...m, eqr: false })),
              ...(draft.payload.eqr_user_id == null
                ? []
                : [{ user_id: draft.payload.eqr_user_id, role: "eqr_reviewer", eqr: true }]),
            ].map((m) => (
              <ValueRow key={m.user_id} kind="info" label={nameOf(m.user_id)}>
                <span className="flex flex-col items-end gap-[2px]">
                  <span className="flex items-center gap-[8px]">
                    <span className="text-ink-2">{COPY.roles[m.role] ?? COPY.none}</span>
                    <Pill variant={pendingIds.has(m.user_id) ? "muted" : "green"} size="state">
                      {pendingIds.has(m.user_id) ? COPY.team.requested : COPY.team.confirmed}
                    </Pill>
                  </span>
                  {m.eqr && (
                    <span className="text-meta text-green-ink">{COPY.team.eqrEligible}</span>
                  )}
                </span>
              </ValueRow>
            ))}
            {pendingName !== undefined && (
              <p className="px-[12px] py-[8px] text-meta text-ink-3">
                {COPY.team.g2Footer(nameOf(pendingName.user_id))}
              </p>
            )}
          </Fieldset>
        );
      case "binder_portal":
        return (
          <div className="flex flex-col gap-[10px]">
            <Fieldset title={COPY.card.portal} flush>
              <ValueRow kind="info" label={COPY.keys.portalContacts}>
                {String((draft.payload.portal_contact_ids ?? []).length)}
              </ValueRow>
              {kind === "close" && (
                <ValueRow kind="info" label={COPY.keys.approverOfRecord}>
                  {COPY.none}
                </ValueRow>
              )}
            </Fieldset>
            {PLANNED_VISIBLE && consents !== undefined && kind === "tax_return" && (
              <Fieldset title={COPY.consents.card} flush>
                <ValueRow
                  kind="info"
                  label={COPY.consents.key}
                  help={COPY.consents.helper(consents.family)}
                  helpTone="amber"
                >
                  {consents.summary}
                </ValueRow>
              </Fieldset>
            )}
          </div>
        );
      case "letter_review":
        return (
          <Fieldset title={COPY.card.review} flush>
            <ValueRow kind="info" label={COPY.keys.name}>
              {draft.payload.name ?? COPY.none}
            </ValueRow>
          </Fieldset>
        );
    }
  })();

  const last = index === STEPS.length - 1;
  return (
    <>
      <Wizard
        open
        onOpenChange={(open) => {
          if (!open) setDiscarding(true);
        }}
        title={COPY.title}
        subtitle={COPY.saved(time(draft.saved_at, { tz }))}
        subtitleAt="title"
        steps={steps}
        onStepChange={(id) => {
          const s = STEPS.find((x) => x === id);
          if (s !== undefined) go(s);
        }}
        aside={aside}
        {...(index > 0
          ? {
              onBack: () => {
                const prev = STEPS[index - 1];
                if (prev !== undefined) go(prev);
              },
            }
          : {})}
        {...(last
          ? {}
          : {
              onNext: () => {
                const next = STEPS[index + 1];
                if (next !== undefined) go(next);
              },
            })}
        nextDisabled={!g1Met || draft.type_code == null}
        onSaveDraft={() => {
          void save({});
        }}
        {...(last
          ? {
              createLabel: COPY.create,
              createDisabled: !g1Met || writes.creating,
              onCreate: () => {
                void create(false);
              },
            }
          : {})}
      >
        {notice === null ? (
          body
        ) : (
          <div className="flex flex-col gap-[10px]">
            {notice}
            {body}
          </div>
        )}
      </Wizard>
      <Dialog
        open={discarding}
        onOpenChange={setDiscarding}
        size="sm"
        title={COPY.discard.title}
        action={
          <Button
            variant="primary"
            onClick={() => {
              void writes.discard().then(() => {
                setDiscarding(false);
                onClose?.();
              });
            }}
          >
            {COPY.discard.discard}
          </Button>
        }
      >
        <Button
          variant="secondary"
          onClick={() => {
            setDiscarding(false);
          }}
        >
          {COPY.discard.keep}
        </Button>
      </Dialog>
    </>
  );
}

/** The route's page: resume `?draft=`, or start one (prefilled with `?client=`). */
export function NewEngagementPage({
  draftId,
  clientId,
  onClose,
  onCreated,
  onOpen,
}: {
  draftId?: string | undefined;
  clientId?: string | undefined;
  onClose?: () => void;
  onCreated?: (engagementId: string) => void;
  onOpen?: (engagementId: string) => void;
}): JSX.Element | null {
  const start = useMutation({ ...createEngagementDraftMutation() });
  const [id, setId] = useState<string | undefined>(draftId);
  useEffect(() => {
    if (id !== undefined || start.isPending) return;
    void start
      .mutateAsync({
        body: { step: "client_type", ...(clientId === undefined ? {} : { client_id: clientId }) },
      })
      .then((d) => {
        setId(d.id);
      });
  }, [id, clientId, start]);
  if (id === undefined) return null;
  return (
    <ENG03
      draftId={id}
      {...(onClose === undefined ? {} : { onClose })}
      {...(onCreated === undefined ? {} : { onCreated })}
      {...(onOpen === undefined ? {} : { onOpen })}
    />
  );
}
