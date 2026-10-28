import type { RollForwardDraftOut, RollForwardDraftPatchIn } from "@abacus/api-client";
import {
  rollForwardCreateMutation,
  rollForwardDraftDiscardMutation,
  rollForwardDraftOptions,
  rollForwardDraftQueryKey,
  rollForwardDraftUpdateMutation,
} from "@abacus/api-client/query";
import {
  Button,
  DEFAULT_TZ,
  Dialog,
  Fieldset,
  GateCard,
  Pill,
  Segmented,
  Toggle,
  ValueRow,
  Wizard,
  type WizardStep,
  date,
  time,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useSession } from "../../app-core/session";
import type { CarryPreview } from "../../fixtures/scenarios/ENG-13";
import { COPY, type CarryCode, type StepCode } from "./copy";

// ENG-13 · Roll forward (P-07-T60; docs/screens/ENG-13.md). O6 `Wizard` over the roll-forward v2
// draft (P-07-T55; docs/contracts/engagements-v2.md §8a): five steps (Source · What to carry ·
// Template version · Team · Review), Carry · Skip per v1 category with autosave on
// `seen_version`, the live "Carrying" card, the gate block, "Discard this draft?" and Create (a
// person's click, with an Idempotency-Key). Production draws only the v1 categories the API
// serves: team, template version, request list (as Draft) and prior-year notes. The handoff's
// attest and structure rows, the bridge-letter toggle, learned context (a, b, d) and the template
// conflicts (c) are a fixture-only `preview` (X-01, K-03 to K-05; DEC-805): the route passes
// none, and a production build draws none even if passed. Evidence, results and sign-offs never
// move; the screen says so and the card counts "0 evidence copied".

const STEPS: readonly StepCode[] = ["source", "carry", "template", "team", "review"];
const CARRY: readonly CarryCode[] = ["team", "template", "request_list", "prior_year_notes"];

function useRollForward(sourceId: string, draftId: string) {
  const queryClient = useQueryClient();
  const path = { engagement_id: sourceId, draft_id: draftId };
  const key = rollForwardDraftQueryKey({ path });
  const draft = useQuery({ ...rollForwardDraftOptions({ path }), retry: false });
  const patch = useMutation({
    ...rollForwardDraftUpdateMutation(),
    onSuccess: (d) => {
      queryClient.setQueryData(key, d);
    },
  });
  const discard = useMutation({ ...rollForwardDraftDiscardMutation() });
  const create = useMutation({ ...rollForwardCreateMutation() });
  return {
    draft,
    save: (d: RollForwardDraftOut, change: Omit<RollForwardDraftPatchIn, "seen_version">) =>
      patch.mutateAsync({ path, body: { ...change, seen_version: d.version } }),
    discard: () => discard.mutateAsync({ path }),
    create: () =>
      create.mutateAsync({ path, headers: { "Idempotency-Key": globalThis.crypto.randomUUID() } }),
    creating: create.isPending,
  };
}

function CarrySwitch({
  label,
  carry,
  disabled,
  onChange,
}: {
  label: string;
  carry: boolean;
  disabled?: boolean;
  onChange?: (carry: boolean) => void;
}): JSX.Element {
  return (
    <Segmented
      size="small"
      label={COPY.toggleLabel(label)}
      options={[COPY.toggle.carry, COPY.toggle.skip]}
      active={carry ? COPY.toggle.carry : COPY.toggle.skip}
      {...(disabled === true || onChange === undefined
        ? {}
        : {
            onChange: (picked: string) => {
              onChange(picked === COPY.toggle.carry);
            },
          })}
    />
  );
}

function CarryRow({
  label,
  detail,
  children,
}: {
  label: string;
  detail: string;
  children?: JSX.Element | null;
}): JSX.Element {
  return (
    <div className="flex min-h-[46px] items-center gap-[12px] px-[14px] py-[6px]">
      <span className="flex min-w-0 flex-1 flex-col gap-[2px]">
        <span className="text-row font-medium">{label}</span>
        <span className="text-dense text-ink-3">{detail}</span>
      </span>
      {children}
    </div>
  );
}

export interface ENG13Props {
  sourceId: string;
  draftId: string;
  /** The step the wizard opens on (an artboard's; a fresh draft opens on What to carry). */
  initialStep?: StepCode;
  onClose?: () => void;
  onCreated?: (engagementId: string) => void;
  /** The handoff's fixture-only rows (a–d); the route never passes one (DEC-805). */
  preview?: CarryPreview | undefined;
}

export function ENG13({
  sourceId,
  draftId,
  initialStep = "carry",
  onClose,
  onCreated,
  preview,
}: ENG13Props): JSX.Element | null {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const rf = useRollForward(sourceId, draftId);
  const [step, setStep] = useState<StepCode>(initialStep);
  const [discarding, setDiscarding] = useState(false);
  const [chosen, setChosen] = useState<Record<number, string>>({});
  const draft = rf.draft.data;
  if (draft === undefined) return null;
  const extra = PLANNED_VISIBLE ? preview : undefined;

  const index = STEPS.indexOf(step);
  const steps: WizardStep[] = STEPS.map((s, i) => ({
    id: s,
    label: COPY.steps[s],
    state: i < index ? "done" : i === index ? "current" : "todo",
  }));
  const may = draft.allowed_actions.includes("roll_forward.create");
  const catalogue = draft.catalogue;
  const template = catalogue.template ?? null;
  const picks = draft.selections;
  const carried = new Set(draft.team.map((m) => m.user_id));
  const period = (start: string, end: string): string =>
    `${date(start, { now, tz, withYear: true })} – ${date(end, { now, tz, withYear: true })}`;
  const sourcePeriod = period(draft.source.fiscal_period_start, draft.source.fiscal_period_end);
  const targetPeriod = period(draft.target_period_start, draft.target_period_end);
  const statusWord = draft.source.status === "archived" ? "Archived" : "Delivered";

  const save = async (change: Omit<RollForwardDraftPatchIn, "seen_version">): Promise<void> => {
    try {
      await rf.save(draft, change);
    } catch {
      toast.show({ kind: "error", text: COPY.toast.failed });
    }
  };
  const setCarry = (code: CarryCode, carry: boolean): void => {
    void save({ selections: { [code]: carry } });
  };
  const setPerson = (userId: string, carry: boolean): void => {
    const ids = draft.team.map((m) => m.user_id).filter((id) => id !== userId);
    void save({ team_user_ids: carry ? [...ids, userId] : ids });
  };
  const create = async (): Promise<void> => {
    try {
      const out = await rf.create();
      toast.show({ kind: "success", text: COPY.toast.created(draft.name, targetPeriod) });
      onCreated?.(out.engagement_id);
    } catch {
      toast.show({ kind: "error", text: COPY.toast.createFailed });
    }
  };

  const detailOf = (code: CarryCode): string => {
    switch (code) {
      case "team":
        return COPY.carry.detail.team(draft.team.length);
      case "template":
        return template === null
          ? COPY.carry.detail.noTemplate
          : COPY.carry.detail.template(template.template_name, template.current_version);
      case "request_list":
        return COPY.carry.detail.requests(catalogue.request_count);
      case "prior_year_notes":
        return COPY.carry.detail.notes;
    }
  };

  const carrying = [
    ...(picks.team ? [COPY.carrying.people(draft.team.length)] : []),
    ...(picks.template && template !== null
      ? [COPY.carrying.template(template.template_name, template.current_version)]
      : [COPY.carrying.noTemplate]),
    ...(picks.request_list
      ? [COPY.carrying.requests(catalogue.request_count + (extra?.extraRequests ?? 0))]
      : []),
    ...(picks.prior_year_notes ? [COPY.carrying.notes] : []),
    ...(extra?.carrying ?? []),
    COPY.carrying.evidence(catalogue.evidence_copied ?? 0),
  ];
  const aside = (
    <div className="flex flex-col gap-[8px]">
      <GateCard tone="met">{COPY.gates.released(statusWord)}</GateCard>
      <GateCard tone="needs">{COPY.gates.g1}</GateCard>
      <GateCard tone="needs">{COPY.gates.g2}</GateCard>
      <GateCard tone="needs">{COPY.gates.g3}</GateCard>
      <section
        aria-label={COPY.carrying.title}
        data-carrying=""
        className="flex flex-col gap-[4px] rounded-pane bg-card px-[12px] py-[10px] shadow-e1"
      >
        <span className="text-caption font-medium text-ink-3">{COPY.carrying.title}</span>
        {carrying.map((line) => (
          <span key={line} className="text-dense">
            {line}
          </span>
        ))}
      </section>
    </div>
  );

  const conflicts = extra?.conflicts;
  const unresolved =
    step === "template" &&
    conflicts !== undefined &&
    conflicts.rows.some((_, i) => !(i in chosen));

  const body = (() => {
    switch (step) {
      case "source":
        return (
          <div className="flex flex-col gap-[10px]">
            <Fieldset title={COPY.source.card} flush>
              <ValueRow kind="info" label={COPY.source.engagement}>
                {draft.source.name}
              </ValueRow>
              <ValueRow kind="info" label={COPY.source.status}>
                <Pill variant={draft.source.status === "archived" ? "soon" : "green"}>
                  {statusWord}
                </Pill>
              </ValueRow>
              <ValueRow kind="info" label={COPY.source.period}>
                {sourcePeriod}
              </ValueRow>
            </Fieldset>
            <Fieldset title={COPY.source.target} flush>
              <ValueRow kind="info" label={COPY.source.name}>
                {draft.name}
              </ValueRow>
              <ValueRow kind="info" label={COPY.source.newPeriod}>
                {targetPeriod}
              </ValueRow>
            </Fieldset>
          </div>
        );
      case "carry":
        return (
          <div className="flex flex-col gap-[10px]">
            <header className="flex flex-col gap-[2px]">
              <h2 className="text-section">{COPY.carry.title(draft.name, targetPeriod)}</h2>
              <p className="text-dense text-ink-3">
                {COPY.carry.from(draft.source.name, sourcePeriod, statusWord)}
              </p>
            </header>
            <Fieldset title={COPY.carry.card} flush>
              {CARRY.map((code) => (
                <CarryRow key={code} label={COPY.carry.rows[code]} detail={detailOf(code)}>
                  <CarrySwitch
                    label={COPY.carry.rows[code]}
                    carry={picks[code]}
                    disabled={!may || (code === "template" && template === null)}
                    onChange={(carry) => {
                      setCarry(code, carry);
                    }}
                  />
                </CarryRow>
              ))}
            </Fieldset>
            {extra?.cards.map((card) => (
              <Fieldset
                key={card.title}
                title={card.title}
                flush
                data-preview=""
                {...(card.tag === undefined
                  ? {}
                  : { action: <Pill variant="muted">{card.tag}</Pill> })}
              >
                {card.rows.map((row) => (
                  <CarryRow key={row.label} label={row.label} detail={row.detail}>
                    {row.control === "carry" ? (
                      <span className="flex items-center gap-[8px]">
                        {row.pill === undefined ? null : (
                          <Pill variant="green-tint">{row.pill}</Pill>
                        )}
                        <CarrySwitch label={row.label} carry disabled />
                      </span>
                    ) : row.control === "toggle" ? (
                      <Toggle checked disabled label={row.label} />
                    ) : null}
                  </CarryRow>
                ))}
              </Fieldset>
            ))}
            <p className="text-dense text-ink-3">
              {draft.source.status === "archived" ? COPY.carry.archived : COPY.carry.note}
            </p>
          </div>
        );
      case "template":
        return (
          <div className="flex flex-col gap-[10px]">
            <Fieldset title={COPY.template.card} flush>
              {template === null ? (
                <CarryRow label={COPY.template.card} detail={COPY.template.none} />
              ) : (
                <CarryRow
                  label={template.template_name}
                  detail={
                    template.current
                      ? COPY.template.pinned
                      : COPY.template.newer(template.source_version, template.current_version)
                  }
                >
                  {template.current ? (
                    <Pill variant="green-tint">{COPY.template.current}</Pill>
                  ) : null}
                </CarryRow>
              )}
            </Fieldset>
            {conflicts === undefined ? (
              <Fieldset title={COPY.template.changes} flush>
                <CarryRow label={COPY.template.nothing} detail={COPY.template.signedNever} />
              </Fieldset>
            ) : (
              <Fieldset title={COPY.template.changes} flush data-preview="">
                <div role="note" className="bg-amber-tint px-[14px] py-[10px] text-dense">
                  {conflicts.banner}
                </div>
                {conflicts.changes.map((line) => (
                  <CarryRow key={line} label={line} detail="" />
                ))}
                {conflicts.rows.map((row, i) => (
                  <CarryRow key={row.label} label={row.label} detail="">
                    <div role="group" aria-label={row.label} className="flex gap-[6px]">
                      {row.options.map((option) => (
                        <Button
                          key={option}
                          size="sm"
                          variant={chosen[i] === option ? "primary" : "secondary"}
                          aria-pressed={chosen[i] === option}
                          onClick={() => {
                            setChosen((c) => ({ ...c, [i]: option }));
                          }}
                        >
                          {option}
                        </Button>
                      ))}
                    </div>
                  </CarryRow>
                ))}
                <p className="px-[14px] py-[8px] text-dense text-ink-3">
                  {COPY.template.signedNever}
                </p>
              </Fieldset>
            )}
          </div>
        );
      case "team":
        return (
          <Fieldset title={COPY.team.card} flush>
            {catalogue.team.map((m) => (
              <CarryRow
                key={m.user_id}
                label={m.display_name}
                detail={COPY.team.roles[m.role] ?? m.role}
              >
                {m.available ? (
                  <span className="flex items-center gap-[8px]">
                    {carried.has(m.user_id) ? (
                      <Pill variant="muted">{COPY.team.requested}</Pill>
                    ) : null}
                    <CarrySwitch
                      label={m.display_name}
                      carry={carried.has(m.user_id)}
                      disabled={!may || !picks.team}
                      onChange={(carry) => {
                        setPerson(m.user_id, carry);
                      }}
                    />
                  </span>
                ) : (
                  <Pill variant="muted">{COPY.team.unavailable}</Pill>
                )}
              </CarryRow>
            ))}
          </Fieldset>
        );
      case "review":
        return (
          <div className="flex flex-col gap-[10px]">
            <Fieldset title={COPY.review.source} flush>
              <ValueRow kind="info" label={COPY.source.engagement}>
                {`${draft.source.name} · ${sourcePeriod}`}
              </ValueRow>
              <ValueRow kind="info" label={COPY.source.target}>
                {`${draft.name} · ${targetPeriod}`}
              </ValueRow>
            </Fieldset>
            <Fieldset title={COPY.review.carry} flush>
              {CARRY.map((code) => (
                <ValueRow key={code} kind="info" label={COPY.carry.rows[code]}>
                  {picks[code] ? detailOf(code) : COPY.review.skipped}
                </ValueRow>
              ))}
            </Fieldset>
            <Fieldset title={COPY.review.team} flush>
              {catalogue.team
                .filter((m) => picks.team && carried.has(m.user_id))
                .map((m) => (
                  <ValueRow key={m.user_id} kind="info" label={m.display_name}>
                    <span className="flex items-center gap-[8px]">
                      <span>{COPY.team.roles[m.role] ?? m.role}</span>
                      <Pill variant="muted">{COPY.team.requested}</Pill>
                    </span>
                  </ValueRow>
                ))}
            </Fieldset>
          </div>
        );
    }
  })();

  const last = index === STEPS.length - 1;
  const goto = (s: StepCode | undefined): void => {
    if (s !== undefined) setStep(s);
  };
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
          const target = STEPS.find((x) => x === id);
          if (target !== undefined && STEPS.indexOf(target) <= index) setStep(target);
        }}
        aside={aside}
        {...(index > 0
          ? {
              onBack: () => {
                goto(STEPS[index - 1]);
              },
            }
          : {})}
        {...(last
          ? {}
          : {
              onNext: () => {
                goto(STEPS[index + 1]);
              },
            })}
        nextDisabled={unresolved}
        onSaveDraft={() => {
          void save({});
        }}
        {...(last
          ? {
              createLabel: COPY.create,
              createDisabled: !may || rf.creating,
              onCreate: () => {
                void create();
              },
              // e: "Create" secondary beside the primary "Create & draft letter", planned until
              // N-02 (fixture builds only); production keeps the Wizard's own primary Create.
              ...(PLANNED_VISIBLE
                ? {
                    actions: (
                      <>
                        <Button
                          variant="ghost"
                          size="lg"
                          onClick={() => {
                            void save({});
                          }}
                        >
                          {COPY.saveDraft}
                        </Button>
                        <Button
                          variant="secondary"
                          size="lg"
                          disabled={!may || rf.creating}
                          onClick={() => {
                            void create();
                          }}
                        >
                          {COPY.create}
                        </Button>
                        <Button size="lg" disabled title={COPY.createLetterHint}>
                          {COPY.createLetter}
                        </Button>
                      </>
                    ),
                  }
                : {}),
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
              void rf.discard().then(() => {
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
