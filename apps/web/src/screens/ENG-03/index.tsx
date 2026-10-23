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
import { useSession } from "../../app-core/session";
import { useClientRecord } from "../../domain/clients";
import { useStaffNames } from "../../domain/requests";
import { useDraft, useDraftWrites, useEngagementTypes } from "../../domain/engagements";
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
// e, g and h are P-07-T34's. Single audit is a static tile, never a catalogue type (D10).

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
}

export function ENG03({ draftId, onClose, onCreated }: ENG03Props): JSX.Element | null {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const draftQ = useDraft(draftId);
  const types = useEngagementTypes().data?.items ?? [];
  const writes = useDraftWrites(draftId);
  const staff = useStaffNames();
  const attest = useEntitlement("attest");
  const [discarding, setDiscarding] = useState(false);
  const draft = draftQ.data;
  const client = useClientRecord(draft?.client_id ?? "");
  if (draft === undefined) return null;

  const step = draft.step;
  const index = STEPS.indexOf(step);
  const steps: WizardStep[] = STEPS.map((s, i) => ({
    id: s,
    label: COPY.steps[s],
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
      <GateCard tone={g2?.met === true ? "met" : "needs"}>{COPY.gates.g2}</GateCard>
      <GateCard tone="needs">{COPY.gates.g3}</GateCard>
    </div>
  );

  const groups = catalogueGroups(types);
  const team = draft.payload.team ?? [];
  const pendingName = team.find((m) => pendingIds.has(m.user_id));

  const body = (() => {
    switch (step) {
      case "client_type":
        return (
          <div className="flex flex-col gap-[10px]">
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
            </Fieldset>
            <TypeCatalogue
              groups={groups}
              entitlements={attest ? ["attest"] : []}
              selected={draft.type_code ?? null}
              soonLabel={COPY.comingSoon.badge}
              soonHint={COPY.comingSoon.tooltip}
              onSelect={(code) => {
                void save({ type_code: code });
              }}
            />
          </div>
        );
      case "standards_methodology":
        return (
          <Fieldset title={COPY.card.standards} flush>
            <ValueRow kind="info" label={COPY.keys.standardsSet}>
              {draft.payload.standards_code ?? COPY.none}
            </ValueRow>
            <ValueRow kind="info" label={COPY.keys.auditScope}>
              <Segmented
                size="small"
                label={COPY.keys.auditScope}
                options={COPY.scope}
                active={draft.payload.scope_code === "full_scope" ? COPY.scope[1] : COPY.scope[0]}
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
          <Fieldset title={COPY.card.portal} flush>
            <ValueRow kind="info" label={COPY.keys.portalContacts}>
              {String((draft.payload.portal_contact_ids ?? []).length)}
            </ValueRow>
          </Fieldset>
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
                void writes.create().then((out) => {
                  toast.show({
                    kind: "success",
                    text: COPY.toast.created(draft.payload.name ?? ""),
                  });
                  onCreated?.(out.engagement_id);
                });
              },
            }
          : {})}
      >
        {body}
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
}: {
  draftId?: string | undefined;
  clientId?: string | undefined;
  onClose?: () => void;
  onCreated?: (engagementId: string) => void;
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
    />
  );
}
