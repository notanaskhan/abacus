import type {
  ClientIntakeDraftOut,
  ClientIntakeDraftPayload,
  ConflictResultOut,
  DedupeCandidateOut,
  IntakeProblemOut,
  ScreeningRecordIn,
} from "@abacus/api-client";
import { getIntakeDraftOptions } from "@abacus/api-client/query";
import {
  Button,
  Checkbox,
  Dialog,
  Fieldset,
  Icon,
  Menu,
  Pill,
  RadioGroup,
  Segmented,
  StatusPill,
  ValueRow,
  Wizard,
  type WizardStep,
  status,
  time,
  toast,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, type ReactNode, useEffect, useState } from "react";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { useSession } from "../../app-core/session";
import {
  INTAKE_STEPS,
  type IntakeStep,
  stepOfField,
  useConflictResults,
  useIntakeWrites,
  useStaff,
} from "../../domain/clients";
import { COPY } from "./copy";

// CLI-06 · New client / prospect intake, single client (P-07-T49; docs/screens/CLI-06.md). The O6
// Wizard over CLI-01 on the live intake routes (P-07-T42): every step autosaves the draft and Next
// validates it on the server (registered codes, words here); a problem on an earlier step's field
// jumps there and says why (i: "Required for Form 706 due date"). Step rows jump only to finished
// steps. The dedupe card offers adding the estate under the existing client (DEC-62). The conflict
// check redacts a walled match ("Match on a restricted client"); a manager clears a counterparty
// hit as not adverse; screening rows are recorded by a person (DEC-64; no automatic result).
// "Create" and "Create & start acceptance" commit in one unit of work, Prospect only; the second
// lands on CLI-07. Bulk import (g) is P-07-T54's: its option is shown disabled.

export type Cli06Target =
  | { screen: "CLI-07"; clientId: string; engagementId: string }
  | { screen: "CLI-02"; clientId: string };

export interface CLI06Props {
  /** A draft to resume; without one the wizard starts a new draft. */
  draftId?: string;
  /** The step it opens on (a resumed draft's own step otherwise). */
  step?: IntakeStep;
  /** Problems already said (i). */
  problems?: IntakeProblemOut[];
  /** a: the screening rows the person recorded earlier in this intake. */
  screened?: boolean;
  onClose?: () => void;
  onNavigate?: (target: Cli06Target) => void;
}

type Screening = ScreeningRecordIn["screening_list"];
type ScreeningResult = ScreeningRecordIn["result"];
const LISTS: readonly Screening[] = ["ofac_sdn", "adverse_media", "restricted_entities"];
const OPEN_ASSESSMENTS = new Set(["pending", "counterparty_review", "conflict"]);

function problemText(problems: readonly IntakeProblemOut[], field: string): string | undefined {
  const p = problems.find((x) => x.field === field);
  return p === undefined ? undefined : (COPY.validation[p.code] ?? COPY.validation.required);
}

function dayLabel(iso: string | null | undefined): string {
  return iso == null || iso === "" ? COPY.none : iso;
}

function EntityStep({
  payload,
  onChange,
  problems,
  candidate,
}: {
  payload: ClientIntakeDraftPayload;
  onChange: (p: ClientIntakeDraftPayload) => void;
  problems: readonly IntakeProblemOut[];
  candidate: DedupeCandidateOut | null;
}): JSX.Element {
  const entity = payload.entity ?? { mode: "new_client" as const };
  const set = (patch: Partial<NonNullable<ClientIntakeDraftPayload["entity"]>>): void => {
    onChange({ ...payload, entity: { ...entity, ...patch } });
  };
  const dod = problemText(problems, "entity.date_of_death");
  return (
    <div className="flex flex-col gap-[12px]">
      {candidate !== null && (
        <div
          data-cli06="dedupe"
          className="flex flex-col gap-[8px] rounded-nested bg-amber-tint p-[12px] text-dense text-amber-ink"
        >
          <span className="flex items-center gap-[8px]">
            <Icon name="triangle-alert" size={14} />
            <span>{COPY.dedupe.possible(candidate.display_name, candidate.score)}</span>
          </span>
          <span className="font-medium">
            {COPY.dedupe.match(candidate.score, candidate.display_name)}
          </span>
          <RadioGroup
            label={COPY.dedupe.label}
            value={entity.mode}
            options={[
              { value: "existing_client", label: COPY.dedupe.recommended },
              { value: "new_client", label: COPY.dedupe.separate },
            ]}
            onChange={(mode) => {
              set(
                mode === "existing_client"
                  ? { mode: "existing_client", client_id: candidate.client_id }
                  : { mode: "new_client", client_id: null },
              );
            }}
          />
        </div>
      )}
      <Fieldset title={COPY.entity.fieldset}>
        <ValueRow
          kind="select"
          label={COPY.entity.type}
          {...(entity.entity_type == null ? {} : { value: entity.entity_type })}
          options={Object.entries(COPY.entity.types).map(([value, label]) => ({ value, label }))}
          onChange={(v) => {
            set({ entity_type: v });
          }}
        />
        <ValueRow
          kind="text"
          label={COPY.entity.name}
          value={entity.entity_name ?? ""}
          onChange={(v) => {
            set({ entity_name: v });
          }}
          {...(problemText(problems, "entity.entity_name") === undefined
            ? {}
            : { error: problemText(problems, "entity.entity_name") ?? "" })}
        />
        <ValueRow
          kind="text"
          label={COPY.entity.decedent}
          value={entity.client_display_name ?? ""}
          onChange={(v) => {
            set({ client_display_name: v });
          }}
        />
        <ValueRow
          kind="text"
          label={COPY.entity.dod}
          placeholder={COPY.entity.dodPlaceholder}
          value={entity.date_of_death ?? ""}
          onChange={(v) => {
            set({ date_of_death: v === "" ? null : v });
          }}
          {...(dod === undefined ? {} : { error: dod })}
        />
      </Fieldset>
    </div>
  );
}

function RelationshipsStep({ payload }: { payload: ClientIntakeDraftPayload }): JSX.Element {
  const entity = payload.entity;
  const rows: string[] = [];
  if ((payload.relationships ?? []).some((r) => r.kind === "estate_of") && entity != null) {
    rows.push(
      COPY.relationships.decedent(entity.client_display_name ?? "", entity.entity_name ?? ""),
    );
  }
  for (const c of payload.contacts ?? []) {
    if ((c.roles ?? []).includes("executor"))
      rows.push(COPY.relationships.executor(c.display_name));
  }
  return (
    <Fieldset title={COPY.steps.relationships}>
      {rows.length === 0 ? (
        <ValueRow kind="info" label={COPY.steps.relationships}>
          {COPY.relationships.none}
        </ValueRow>
      ) : (
        rows.map((r) => (
          <p key={r} data-cli06="relationship" className="px-[12px] py-[8px] text-body text-ink">
            {r}
          </p>
        ))
      )}
      <p className="px-[12px] pb-[8px] text-meta text-ink-3">{COPY.relationships.note}</p>
    </Fieldset>
  );
}

function ContactsStep({
  payload,
  onChange,
}: {
  payload: ClientIntakeDraftPayload;
  onChange: (p: ClientIntakeDraftPayload) => void;
}): JSX.Element {
  const contact = payload.contacts?.[0] ?? { display_name: "", roles: [] };
  const set = (patch: Partial<typeof contact>): void => {
    onChange({
      ...payload,
      contacts: [{ ...contact, ...patch }, ...(payload.contacts ?? []).slice(1)],
    });
  };
  return (
    <Fieldset title={COPY.contacts.fieldset}>
      <ValueRow
        kind="text"
        label={COPY.contacts.name}
        value={contact.display_name}
        onChange={(v) => {
          set({ display_name: v });
        }}
      />
      <ValueRow
        kind="select"
        label={COPY.contacts.role}
        {...(contact.roles?.[0] === undefined ? {} : { value: contact.roles[0] })}
        options={Object.entries(COPY.contacts.roles).map(([value, label]) => ({ value, label }))}
        onChange={(v) => {
          set({ roles: [v] });
        }}
      />
      <ValueRow
        kind="text"
        label={COPY.contacts.email}
        value={contact.email ?? ""}
        onChange={(v) => {
          set({ email: v === "" ? null : v });
        }}
      />
      {PLANNED_VISIBLE && (
        <ValueRow
          kind="toggle"
          label={COPY.contacts.intake}
          help={COPY.contacts.intakeHelp}
          checked={false}
          disabled
        />
      )}
    </Fieldset>
  );
}

function ServicesStep({
  payload,
  onChange,
  problems,
}: {
  payload: ClientIntakeDraftPayload;
  onChange: (p: ClientIntakeDraftPayload) => void;
  problems: readonly IntakeProblemOut[];
}): JSX.Element {
  const staff = useStaff();
  const chosen = new Set((payload.services ?? []).map((s) => s.type_code));
  const known = Object.keys(COPY.services.names);
  const partner = problemText(problems, "engagement_partner_user_id");
  return (
    <Fieldset title={COPY.services.fieldset}>
      <div className="flex flex-col gap-[8px] px-[12px] py-[8px]">
        {known.map((code) => (
          <Checkbox
            key={code}
            label={COPY.services.names[code] ?? code}
            showLabel
            checked={chosen.has(code)}
            onChange={(on) => {
              const rest = (payload.services ?? []).filter((s) => s.type_code !== code);
              onChange({ ...payload, services: on ? [...rest, { type_code: code }] : rest });
            }}
          />
        ))}
      </div>
      <ValueRow
        kind="select"
        label={COPY.services.partner}
        {...(payload.engagement_partner_user_id == null
          ? {}
          : { value: payload.engagement_partner_user_id })}
        options={staff.ids.map((id) => ({ value: id, label: staff.names.get(id) ?? id }))}
        onChange={(v) => {
          onChange({ ...payload, engagement_partner_user_id: v });
        }}
        {...(partner === undefined ? {} : { error: partner })}
      />
    </Fieldset>
  );
}

function ClearDialog({
  result,
  onClose,
  onClear,
}: {
  result: ConflictResultOut | null;
  onClose: () => void;
  onClear: (reason: string) => void;
}): JSX.Element {
  const [reason, setReason] = useState("");
  return (
    <Dialog
      open={result !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={COPY.conflicts.clearTitle}
    >
      <div className="flex flex-col gap-[12px]">
        <ValueRow
          kind="paragraph"
          label={COPY.conflicts.clearReason}
          value={reason}
          onChange={setReason}
        />
        <div className="flex justify-end gap-[8px]">
          <Button variant="secondary" onClick={onClose}>
            {COPY.conflicts.cancel}
          </Button>
          <Button
            variant="primary"
            disabled={reason.trim() === ""}
            onClick={() => {
              onClear(reason.trim());
            }}
          >
            {COPY.conflicts.clearConfirm}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

function assessmentWord(r: ConflictResultOut): { label: string; variant: string } {
  const word = status("conflict_assessment", r.assessment);
  // The counterparty's relationship is not served: the words without it (docs/screens/CLI-06.md).
  return {
    label: word.label.replace(" · {relationship}", ""),
    variant: word.variant ?? "neutral",
  };
}

function ConflictsStep({
  draftId,
  payload,
  onChecked,
  screened,
}: {
  draftId: string;
  payload: ClientIntakeDraftPayload;
  onChecked: (checkId: string) => void;
  screened: boolean;
}): JSX.Element {
  const writes = useIntakeWrites();
  const me = useSession().user?.displayName ?? "";
  const check = useConflictResults(payload.conflict_check_id);
  const [clearing, setClearing] = useState<ConflictResultOut | null>(null);
  const [records, setRecords] = useState<Partial<Record<Screening, ScreeningResult>>>(
    screened
      ? { ofac_sdn: "no_match", adverse_media: "no_match", restricted_entities: "not_applicable" }
      : {},
  );
  const results = check.data?.results ?? [];
  const open = results.some((r) => OPEN_ASSESSMENTS.has(r.assessment));
  const names = [
    payload.entity?.entity_name,
    payload.entity?.client_display_name,
    ...(payload.contacts ?? []).map((c) => c.display_name),
  ].filter((n): n is string => typeof n === "string" && n !== "");
  const run = async (): Promise<void> => {
    try {
      const out = await writes.runCheck(draftId, names);
      onChecked(out.id);
    } catch {
      toast.show({ kind: "error", text: COPY.failed });
    }
  };
  const record = async (list: Screening, result: ScreeningResult): Promise<void> => {
    try {
      await writes.recordScreening({
        screening_list: list,
        result,
        subject: { kind: "client_intake_draft", id: draftId },
      });
      setRecords({ ...records, [list]: result });
    } catch {
      toast.show({ kind: "error", text: COPY.failed });
    }
  };
  return (
    <div className="flex flex-col gap-[12px]">
      <Fieldset title={COPY.conflicts.band}>
        {check.data === undefined ? (
          <div className="flex justify-end px-[12px] py-[8px]">
            <Button
              variant="secondary"
              size="sm"
              disabled={writes.busy}
              onClick={() => void run()}
            >
              {COPY.conflicts.run}
            </Button>
          </div>
        ) : (
          <div data-cli06="conflicts" className="flex flex-col gap-[8px] px-[12px] py-[8px]">
            <div className="flex items-center gap-[8px]">
              <span className="min-w-0 flex-1 text-dense text-ink-2">
                {COPY.conflicts.line(check.data.names_count, time(check.data.run_at))}
              </span>
              {!open && <Pill variant="green-tint">{COPY.conflicts.none}</Pill>}
            </div>
            {results.map((r) => {
              const word = assessmentWord(r);
              return (
                <div
                  key={r.id}
                  data-cli06-result={r.assessment}
                  className="flex items-center gap-[8px]"
                >
                  <span className="min-w-0 flex-1 text-body text-ink">
                    {r.redacted ? COPY.conflicts.restricted : (r.matched_name ?? COPY.none)}
                  </span>
                  <StatusPill variant={word.variant as "neutral"}>{word.label}</StatusPill>
                  {(r.allowed_actions ?? []).includes("conflict.clear") && (
                    <Button
                      variant="secondary"
                      size="sm"
                      opensDialog
                      onClick={() => {
                        setClearing(r);
                      }}
                    >
                      {COPY.conflicts.clear}
                    </Button>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Fieldset>
      <Fieldset title={COPY.conflicts.screening}>
        {LISTS.map((list) => {
          const done = records[list];
          return (
            <ValueRow key={list} kind="info" label={COPY.conflicts.lists[list] ?? list}>
              {done === undefined ? (
                <Menu
                  label={COPY.conflicts.lists[list] ?? list}
                  sections={[
                    (["no_match", "match", "not_applicable"] as const).map((result) => ({
                      label: COPY.conflicts.results[result] ?? result,
                      onSelect: () => void record(list, result),
                    })),
                  ]}
                  trigger={
                    <Button variant="secondary" size="sm">
                      {COPY.conflicts.record}
                    </Button>
                  }
                />
              ) : (
                <span data-cli06-screening={done}>
                  {`${COPY.conflicts.results[done] ?? done} · ${COPY.conflicts.recordedBy(me)}`}
                </span>
              )}
            </ValueRow>
          );
        })}
      </Fieldset>
      <ClearDialog
        key={clearing?.id ?? "none"}
        result={clearing}
        onClose={() => {
          setClearing(null);
        }}
        onClear={(reason) => {
          const target = clearing;
          const checkId = payload.conflict_check_id;
          setClearing(null);
          if (target === null || checkId == null) return;
          void writes.clearHit(checkId, target.id, reason).catch(() => {
            toast.show({ kind: "error", text: COPY.failed });
          });
        }}
      />
    </div>
  );
}

function ReviewStep({ payload }: { payload: ClientIntakeDraftPayload }): JSX.Element {
  const k = COPY.review.keys;
  const services = (payload.services ?? []).map(
    (s) => COPY.services.names[s.type_code] ?? s.type_code,
  );
  return (
    <Fieldset title={COPY.review.title}>
      <ValueRow kind="info" label={k.client}>
        {payload.entity?.client_display_name ?? COPY.none}
      </ValueRow>
      <ValueRow kind="info" label={k.entity}>
        {payload.entity?.entity_name ?? COPY.none}
      </ValueRow>
      <ValueRow kind="info" label={k.dod}>
        {dayLabel(payload.entity?.date_of_death)}
      </ValueRow>
      <ValueRow kind="info" label={k.contact}>
        {payload.contacts?.[0]?.display_name ?? COPY.none}
      </ValueRow>
      <ValueRow kind="info" label={k.services}>
        {services.length === 0 ? COPY.none : services.join(" · ")}
      </ValueRow>
    </Fieldset>
  );
}

function useDraft(draftId: string | undefined): {
  draft: ClientIntakeDraftOut | undefined;
  setDraft: (d: ClientIntakeDraftOut) => void;
} {
  const writes = useIntakeWrites();
  const [created, setCreated] = useState<ClientIntakeDraftOut | undefined>(undefined);
  const loaded = useQuery({
    ...getIntakeDraftOptions({ path: { draft_id: draftId ?? "" } }),
    enabled: draftId !== undefined,
  });
  useEffect(() => {
    if (draftId !== undefined) return;
    let live = true;
    void writes.start().then((d) => {
      if (live) setCreated(d);
    });
    return () => {
      live = false;
    };
  }, [draftId]);
  return { draft: created ?? loaded.data, setDraft: setCreated };
}

export function CLI06({
  draftId,
  step: openStep,
  problems: openProblems = [],
  screened = false,
  onClose,
  onNavigate,
}: CLI06Props): JSX.Element | null {
  const writes = useIntakeWrites();
  const { draft, setDraft } = useDraft(draftId);
  const [step, setStep] = useState<IntakeStep | null>(openStep ?? null);
  const [payload, setPayload] = useState<ClientIntakeDraftPayload | null>(null);
  const [problems, setProblems] = useState<IntakeProblemOut[]>(openProblems);
  const [candidate, setCandidate] = useState<DedupeCandidateOut | null>(null);
  const current = step ?? draft?.step ?? "entity";
  const data = payload ?? draft?.payload ?? null;
  const name = data?.entity?.entity_name ?? data?.entity?.client_display_name ?? "";
  useEffect(() => {
    if (current !== "entity" || name === "") return;
    let live = true;
    void writes
      .dedupe(name)
      .then((out) => {
        if (live) setCandidate(out.candidates?.[0] ?? null);
      })
      .catch(() => undefined);
    return () => {
      live = false;
    };
  }, [current, name]);
  if (draft === undefined || data === null) return null;
  const index = INTAKE_STEPS.indexOf(current);
  const steps: WizardStep[] = INTAKE_STEPS.map((id, i) => ({
    id,
    label: COPY.steps[id],
    state: i < index ? "done" : i === index ? "current" : "todo",
  }));

  const save = async (
    base: ClientIntakeDraftOut,
    to: IntakeStep,
  ): Promise<ClientIntakeDraftOut> => {
    const saved = await writes.save(base, to, data);
    setDraft(saved);
    return saved;
  };
  const next = async (): Promise<void> => {
    try {
      const saved = await save(draft, current);
      const found = await writes.validate(saved.id, current);
      setProblems(found);
      const first = found[0];
      if (first !== undefined) {
        const at = stepOfField(first.field);
        if (at !== current) setStep(at);
        return;
      }
      const to = INTAKE_STEPS[index + 1];
      if (to !== undefined) {
        await save(saved, to);
        setStep(to);
      }
    } catch {
      toast.show({ kind: "error", text: COPY.failed });
    }
  };
  const create = async (startAcceptance: boolean): Promise<void> => {
    try {
      const saved = await save(draft, "review");
      const found = await writes.validate(saved.id, "review");
      setProblems(found);
      const first = found[0];
      if (first !== undefined) {
        setStep(stepOfField(first.field));
        return;
      }
      const out = await writes.commit(saved.id, startAcceptance);
      const engagement = out.engagement_ids?.[0];
      if (startAcceptance && engagement !== undefined) {
        onNavigate?.({ screen: "CLI-07", clientId: out.client_id, engagementId: engagement });
      } else {
        onNavigate?.({ screen: "CLI-02", clientId: out.client_id });
      }
    } catch {
      toast.show({ kind: "error", text: COPY.failed });
    }
  };

  const change = (p: ClientIntakeDraftPayload): void => {
    setPayload(p);
  };
  let body: ReactNode;
  switch (current) {
    case "entity":
      body = (
        <EntityStep payload={data} onChange={change} problems={problems} candidate={candidate} />
      );
      break;
    case "relationships":
      body = <RelationshipsStep payload={data} />;
      break;
    case "contacts":
      body = <ContactsStep payload={data} onChange={change} />;
      break;
    case "services":
      body = <ServicesStep payload={data} onChange={change} problems={problems} />;
      break;
    case "conflicts":
      body = (
        <ConflictsStep
          draftId={draft.id}
          payload={data}
          screened={screened}
          onChecked={(checkId) => {
            setPayload({ ...data, conflict_check_id: checkId });
          }}
        />
      );
      break;
    default:
      body = <ReviewStep payload={data} />;
  }
  const last = current === "review";
  const gateProblem = problemText(problems, "conflict_check_id");
  return (
    <div data-screen="CLI-06" className="contents">
      <Wizard
        open
        onOpenChange={(open) => {
          if (!open) onClose?.();
        }}
        title={COPY.title}
        steps={steps}
        onStepChange={(id) => {
          const to = INTAKE_STEPS.find((s) => s === id);
          if (to !== undefined && INTAKE_STEPS.indexOf(to) < index) setStep(to);
        }}
        aside={
          <div className="flex flex-col gap-[8px] p-[14px]">
            <Segmented
              size="small"
              label={COPY.mode.label}
              active={COPY.mode.single}
              options={[{ label: COPY.mode.single }, { label: COPY.mode.bulk, disabled: true }]}
            />
            <span className="text-meta text-ink-3">
              {COPY.stepOf(index + 1, INTAKE_STEPS.length)}
            </span>
          </div>
        }
        {...(index > 0
          ? {
              onBack: () => {
                const prev = INTAKE_STEPS[index - 1];
                if (prev !== undefined) setStep(prev);
              },
            }
          : {})}
        {...(last ? {} : { onNext: () => void next() })}
        nextDisabled={writes.busy}
        {...(last
          ? {
              actions: (
                <span className="flex items-center gap-[8px]">
                  <Button
                    variant="secondary"
                    disabled={writes.busy}
                    onClick={() => void create(false)}
                  >
                    {COPY.review.create}
                  </Button>
                  <Button
                    variant="primary"
                    disabled={writes.busy}
                    onClick={() => void create(true)}
                  >
                    {COPY.review.createStart}
                  </Button>
                </span>
              ),
            }
          : {})}
      >
        <div className="mx-auto flex w-full max-w-[760px] flex-col gap-[12px]">
          {body}
          {gateProblem !== undefined && (
            <p role="alert" className="text-meta text-red-ink">
              {gateProblem}
            </p>
          )}
        </div>
      </Wizard>
    </div>
  );
}

/** The routed page and the gallery's artboard. */
export function IntakePage(props: CLI06Props): JSX.Element | null {
  return <CLI06 {...props} />;
}
