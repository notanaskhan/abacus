import type {
  AttachmentFlagOut,
  AttachmentTriageOut,
  DestinationCandidate,
  MessageTriageOut,
  TriageApplyOut,
  TriageDecisionIn,
} from "@abacus/api-client";
import { messageTriageOptions, triageApplyMutation } from "@abacus/api-client/query";
import {
  type Actor,
  DEFAULT_TZ,
  Fieldset,
  Picker,
  Segmented,
  SheetModal,
  StatusPill,
  ValueRow,
  date,
  time,
} from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useSession } from "../../app-core/session";
import { COPY } from "./copy";

// INB-02's sheet (N-01-T15; docs/screens/INB-02.md; DEC-1062): one Fieldset card per open
// attachment with what code read, the suggested destination and its confidence pill (computed by
// the server, never here), the flags, and the decision rows. A `force_hold` flag fixes the
// decision to Hold; ambiguous candidates leave Apply disabled until a person picks one; File
// needs a destination and Ignore a reason. Apply sends every decision at once; nothing is filed
// before it. Escape or ✕ on a changed sheet asks first (the O3 kit's guard).

type Decision = TriageDecisionIn["decision"];
const DECISIONS: readonly Decision[] = ["file", "ignore", "hold"];

interface CardState {
  decision: Decision;
  candidate: DestinationCandidate | null;
  rename: string;
  supersede: boolean;
  keepBoth: boolean;
  reasons: string;
  tellClient: boolean;
}

function initial(card: AttachmentTriageOut): CardState {
  const only = card.candidates.length === 1 ? (card.candidates[0] ?? null) : null;
  return {
    decision: card.defaults.decision,
    candidate: only,
    rename: card.defaults.rename_to ?? card.attachment.file_name,
    supersede: card.defaults.version_mode === "new_version_supersede",
    keepBoth: card.defaults.version_mode === "new_version",
    reasons: card.defaults.reason_codes.join(","),
    tellClient: card.defaults.tell_client,
  };
}

function day(iso: string, tz: string, withYear = false): string {
  return date(`${iso}T12:00:00Z`, { now: new Date(`${iso}T12:00:00Z`), tz, withYear });
}

function flagText(f: AttachmentFlagOut, tz: string): string {
  const facts = f.facts;
  switch (f.kind) {
    case "wrong_year":
      return COPY.flag.wrongYear(Number(facts.tax_year), Number(facts.open_year));
    case "duplicate_hash":
      return COPY.flag.duplicate(
        String(facts.file_name ?? ""),
        facts.received_on === undefined ? "" : day(String(facts.received_on), tz, true),
      );
    case "duplicate_of_notice":
      return COPY.flag.duplicateOfNotice;
    case "tin_mismatch":
      return COPY.flag.tinMismatch(String(facts.form_last4), String(facts.record_last4));
    case "ambiguous_candidates":
      return COPY.flag.ambiguous;
    case "possible_replacement":
      return facts.file_name === undefined
        ? COPY.alreadyOnFile
        : COPY.flag.replacement(
            String(facts.file_name),
            String(facts.channel ?? ""),
            facts.received_on === undefined ? "" : day(String(facts.received_on), tz, true),
          );
    default:
      return f.kind;
  }
}

function confidencePill(c: DestinationCandidate): JSX.Element {
  if (c.request_state === "on_file") {
    return (
      <StatusPill variant="neutral" size="sm">
        {COPY.alreadyOnFile}
      </StatusPill>
    );
  }
  return (
    <StatusPill variant={c.confidence >= 0.9 ? "green-tint" : "amber"} size="sm">
      {`${String(Math.round(c.confidence * 100))}%`}
    </StatusPill>
  );
}

function Path({ path }: { path: readonly string[] }): JSX.Element {
  return (
    <span className="flex min-w-0 flex-wrap items-center gap-[4px]">
      {path.map((step, i) => (
        <span key={step} className="flex items-center gap-[4px]">
          {i > 0 && <span className="text-ink-3">›</span>}
          <span className="inline-flex h-[28px] items-center rounded-full bg-card px-[10px] text-meta shadow-e1">
            {step}
          </span>
        </span>
      ))}
    </span>
  );
}

function Card({
  card,
  state,
  tz,
  onChange,
}: {
  card: AttachmentTriageOut;
  state: CardState;
  tz: string;
  onChange: (next: CardState) => void;
}): JSX.Element {
  const c = card.classification;
  const a = card.attachment;
  const forced = card.defaults.decision_forced;
  const sha = a.fingerprint.replace(/^sha256:/, "");
  const replacement = a.flags.some((f) => f.kind === "possible_replacement");
  const reasonOptions = [
    ...(card.defaults.reason_codes.length > 1
      ? [
          {
            value: card.defaults.reason_codes.join(","),
            label: card.defaults.reason_codes
              .map((r) => COPY.reasons[r])
              .join(" · ")
              .replace(/^./, (m) => m.toUpperCase()),
          },
        ]
      : []),
    ...Object.entries(COPY.reasons).map(([value, label]) => ({
      value,
      label: label.replace(/^./, (m) => m.toUpperCase()),
    })),
  ];
  return (
    <Fieldset title={a.file_name} flush>
      <div className="flex gap-[12px] px-[12px] py-[10px] text-meta text-ink-2 hairline-b">
        <span
          aria-hidden="true"
          className="h-[80px] w-[64px] shrink-0 rounded-tile bg-nested inset-shadow-hair"
        />
        <span className="flex flex-col">
          {c?.form_code != null && (
            <span>{COPY.formNames[c.form_code] ?? `Form ${c.form_code}`}</span>
          )}
          <span>{COPY.strip(c?.page_count ?? null, Math.round(a.size_bytes / 1024), sha)}</span>
        </span>
      </div>
      {c?.form_code != null && (
        <ValueRow kind="value" label={COPY.rows.form}>
          {c.form_code}
        </ValueRow>
      )}
      {c?.tax_year != null && (
        <ValueRow kind="value" label={COPY.rows.taxYear}>
          {String(c.tax_year)}
        </ValueRow>
      )}
      {c?.issuer_name != null && (
        <ValueRow kind="value" label={COPY.rows.issuer}>
          {c.issuer_name}
        </ValueRow>
      )}
      {c?.taxpayer_tin?.last4 != null && (
        <ValueRow kind="value" label={COPY.rows.taxpayer}>
          {`•••-••-${c.taxpayer_tin.last4}${c.taxpayer_matches_client === true ? ` · ${COPY.rows.matches}` : ""}`}
        </ValueRow>
      )}
      <div className="px-[12px] py-[8px] font-medium hairline-t">{COPY.destination}</div>
      {card.candidates.length > 1 && (
        <div className="px-[12px] text-meta text-ink-3">{COPY.candidates}</div>
      )}
      {card.candidates.map((cand) => {
        const chosen = state.candidate?.id === cand.id;
        return (
          <button
            type="button"
            key={cand.id}
            aria-pressed={chosen}
            disabled={card.candidates.length === 1}
            onClick={() => {
              onChange({ ...state, candidate: cand });
            }}
            className={
              chosen && card.candidates.length > 1
                ? "flex w-full items-center justify-between gap-[8px] bg-sel-bg px-[12px] py-[6px] text-left"
                : "flex w-full items-center justify-between gap-[8px] px-[12px] py-[6px] text-left"
            }
          >
            <span className="flex flex-col gap-[4px]">
              <Path path={cand.path} />
              {cand.request_state === "open" && cand.requested_on !== null && (
                <span className="text-meta text-ink-3">
                  {COPY.openRequest(day(cand.requested_on, tz))}
                </span>
              )}
            </span>
            {confidencePill(cand)}
          </button>
        );
      })}
      <div className="px-[12px] py-[8px] font-medium hairline-t">{COPY.flags}</div>
      {a.flags.length === 0 ? (
        <p className="px-[12px] pb-[8px] text-meta text-ink-2">{COPY.noFlags}</p>
      ) : (
        a.flags.map((f) => (
          <p
            key={f.kind}
            className={
              f.severity === "info"
                ? "mx-[12px] mb-[6px] rounded-tile bg-amber-tint px-[10px] py-[6px] text-meta text-amber-ink"
                : "mx-[12px] mb-[6px] rounded-tile bg-red-tint px-[10px] py-[6px] text-meta text-red-ink"
            }
          >
            {flagText(f, tz)}
          </p>
        ))
      )}
      {state.decision === "file" && !replacement && (
        <ValueRow
          kind="toggle"
          label={COPY.rows.supersede}
          checked={state.supersede}
          disabled={card.supersede_candidate_version_id === null}
          help={
            card.supersede_candidate_version_id === null
              ? COPY.rows.supersedeNone(c?.tax_year ?? null, c?.form_code ?? null)
              : undefined
          }
          onChange={(on) => {
            onChange({ ...state, supersede: on });
          }}
        />
      )}
      {state.decision === "file" && replacement && (
        <ValueRow
          kind="toggle"
          label={
            card.defaults.version_mode === "new_version_supersede"
              ? COPY.rows.supersede
              : COPY.rows.keepBoth
          }
          checked={
            card.defaults.version_mode === "new_version_supersede"
              ? state.supersede
              : state.keepBoth
          }
          onChange={(on) => {
            onChange(
              card.defaults.version_mode === "new_version_supersede"
                ? { ...state, supersede: on }
                : { ...state, keepBoth: on },
            );
          }}
        />
      )}
      {state.decision === "file" && (
        <ValueRow
          kind="text"
          label={COPY.rows.renameTo}
          value={state.rename}
          onChange={(rename) => {
            onChange({ ...state, rename });
          }}
        />
      )}
      <div className="flex min-h-[34px] items-center justify-between gap-[10px] px-[12px] text-body">
        <span className="text-ink-2">{COPY.rows.decision}</span>
        <Segmented
          label={COPY.rows.decision}
          size="small"
          options={(forced
            ? (["hold"] as const)
            : DECISIONS.filter((d) => d !== "hold" || card.defaults.decision === "hold")
          ).map((d) => ({ label: COPY.decisions[d] }))}
          active={COPY.decisions[state.decision]}
          onChange={(label) => {
            const next = DECISIONS.find((d) => COPY.decisions[d] === label);
            if (next !== undefined && !forced) onChange({ ...state, decision: next });
          }}
        />
      </div>
      {state.decision === "ignore" && (
        <div className="flex min-h-[34px] items-center justify-between gap-[10px] px-[12px] text-body">
          <span className="text-ink-2">{COPY.rows.reason}</span>
          <Picker
            label={COPY.rows.reason}
            options={reasonOptions}
            value={state.reasons}
            onChange={(reasons) => {
              onChange({ ...state, reasons });
            }}
          />
        </div>
      )}
      {state.decision !== "file" && (
        <ValueRow
          kind="toggle"
          label={COPY.rows.tellClient}
          checked={state.tellClient}
          help={state.tellClient ? undefined : COPY.rows.tellClientOff}
          onChange={(on) => {
            onChange({ ...state, tellClient: on });
          }}
        />
      )}
      {state.decision === "hold" && state.tellClient && card.defaults.template_key !== null && (
        <p className="mx-[12px] mb-[8px] text-meta text-ink-2">{COPY.holdPreview}</p>
      )}
    </Fieldset>
  );
}

function ready(card: AttachmentTriageOut, state: CardState): boolean {
  if (card.defaults.decision_forced && state.decision !== card.defaults.decision) return false;
  if (state.decision === "file") return state.candidate !== null;
  if (state.decision === "ignore") return state.reasons !== "";
  return true;
}

function decisionOf(card: AttachmentTriageOut, s: CardState): TriageDecisionIn {
  const replacing = card.supersede_candidate_version_id;
  return {
    attachment_id: card.attachment.id,
    decision: s.decision,
    destination:
      s.decision === "file" && s.candidate !== null
        ? { kind: s.candidate.kind, id: s.candidate.id }
        : null,
    version_mode:
      s.decision !== "file"
        ? null
        : replacing !== null && s.supersede
          ? "new_version_supersede"
          : replacing !== null && !s.keepBoth
            ? "new_version"
            : "new_document",
    supersede_version_id: s.decision === "file" && replacing !== null ? replacing : null,
    keep_both: s.keepBoth,
    rename_to: s.decision === "file" && s.rename !== card.attachment.file_name ? s.rename : null,
    reason_codes:
      s.decision === "ignore"
        ? (s.reasons.split(",").filter((r) => r !== "") as NonNullable<
            TriageDecisionIn["reason_codes"]
          >)
        : [],
    tell_client: s.decision !== "file" && s.tellClient,
  };
}

export interface TriageSheetProps {
  messageId: string | null;
  subject: string;
  sender: string;
  viewer: Actor;
  onClose: () => void;
  onApplied: (result: TriageApplyOut, notified: readonly string[]) => void;
  /** a2: the sheet opens already edited (its guard then asks before closing). */
  startDirty?: boolean;
}

export function TriageSheet({
  messageId,
  subject,
  sender,
  viewer,
  onClose,
  onApplied,
  startDirty = false,
}: TriageSheetProps): JSX.Element {
  const tz = useSession().tz ?? DEFAULT_TZ;
  const open = messageId !== null;
  const bundle = useQuery({
    ...messageTriageOptions({ path: { message_id: messageId ?? "" } }),
    enabled: open,
  });
  const [states, setStates] = useState<Record<string, CardState>>({});
  const [dirty, setDirty] = useState(startDirty);
  const apply = useMutation({
    ...triageApplyMutation(),
    onSuccess: (result) => {
      onApplied(result, bundle.data?.notify_names ?? []);
    },
  });
  const data: MessageTriageOut | undefined = bundle.data;
  const cards = data?.attachments ?? [];
  const stateOf = (card: AttachmentTriageOut): CardState =>
    states[card.attachment.id] ?? initial(card);
  const allReady = cards.length > 0 && cards.every((c) => ready(c, stateOf(c)));
  const viewerName = viewer.kind === "human" ? viewer.name : "";
  const classified = data?.classified_at == null ? null : time(data.classified_at, { tz });
  return (
    <SheetModal
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title={COPY.title}
      description={COPY.subtitle(subject, sender)}
      dirty={dirty}
      action={
        <button
          type="button"
          disabled={!allReady || apply.isPending || viewer.kind !== "human"}
          onClick={() => {
            if (messageId === null || data === undefined) return;
            apply.mutate({
              path: { message_id: messageId },
              body: {
                decisions: cards.map((c) => decisionOf(c, stateOf(c))),
                seen_proposals: data.seen_proposals,
              },
              headers: { "Idempotency-Key": crypto.randomUUID() },
            });
          }}
          className="inline-flex h-[30px] items-center rounded-full bg-ink px-[14px] text-body font-medium text-card disabled:opacity-40"
        >
          {COPY.apply(cards.length)}
        </button>
      }
    >
      <div className="flex flex-col gap-[12px] p-[12px]">
        {cards.map((card) => (
          <Card
            key={card.attachment.id}
            card={card}
            state={stateOf(card)}
            tz={tz}
            onChange={(next) => {
              setStates({ ...states, [card.attachment.id]: next });
              setDirty(true);
            }}
          />
        ))}
        {classified !== null && (
          <p className="text-meta text-ink-3">
            {COPY.footer(classified, viewerName, data?.notify_names ?? [])}
          </p>
        )}
        {apply.isError && <p className="text-meta text-red-ink">{COPY.changed}</p>}
      </div>
    </SheetModal>
  );
}
