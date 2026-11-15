import type { InstrumentDeterminationOut, InstrumentOut } from "@abacus/api-client";
import {
  Button,
  DEFAULT_TZ,
  EmptyState,
  ErrorState,
  Icon,
  Skeleton,
  Spinner,
  date,
} from "@abacus/ui";
import { type JSX, useMemo, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useSession } from "../../app-core/session";
import {
  DETERMINATION_LABELS,
  useInstrument,
  useInstrumentClauses,
  useInstrumentText,
  useReadInstrument,
  useReturnRecord,
} from "../../domain/tax";
import { COPY } from "./copy";
import { LegalReader } from "./LegalReader";

// TXT-01 · Review › Instrument (T-07-T15; SPEC-656 AC-1.1 to AC-5.2; docs/screens/TXT-01.md). T3
// two-pane mirrored preset: the legal reader (flex) and the trust profile (490). The read model is
// the server's (`GET /v1/tax/returns/{id}/instrument`): the profile, the seven determinations with
// their clause labels, cited by, the reader's availability and the scenario lines. A chip's hover
// or focus lights and scrolls to its passage; the selected row keeps its clauses lit; a passage's
// click lists who cites it. Approve interpretation opens SHL-12 at L3 (`onApprove`). Each artboard
// is its data (fixtures/scenarios/TXT-01.ts): a proposed, b approved, c principal invaded, d
// unread, d1 agents off, d2 reading, d3 consent required; a2–a4 are interactions on a.

export interface TXT01Props {
  returnId: string;
  /** SHL-12 at L3 on the interpretation (`?ov=signoff`). */
  onApprove?: () => void;
  /** A Cited by row: TXT-02 `?row=` or a TAX-05 worksheet field. */
  onCitedBy?: (target: "trust_calculation" | "return_field", ref: string) => void;
  /** The agents-off path: record a determination (an O3 sheet with its clause). */
  onRecord?: (key: InstrumentDeterminationOut["key"]) => void;
  onDownload?: () => void;
  onOpenInFiles?: () => void;
}

const KEYS = Object.keys(DETERMINATION_LABELS) as (keyof typeof DETERMINATION_LABELS)[];
const GOVERNED = new Set([
  "grantor_status",
  "trust_type",
  "fai_definition",
  "trustee_fees",
  "principal_invaded",
]);
const onDay = (day: string): string => `${day}T12:00:00Z`;

function KV({ k, v }: { k: string; v: string }): JSX.Element {
  return (
    <div className="flex min-h-[33px] items-center justify-between gap-[12px] border-t-[0.5px] border-hair px-[12px] text-dense">
      <span className="text-ink-2">{k}</span>
      <span className="text-right">{v}</span>
    </div>
  );
}

function Chip({
  label,
  onLight,
}: {
  label: string;
  onLight: (label: string | null) => void;
}): JSX.Element {
  return (
    <button
      type="button"
      data-chip={label}
      onMouseEnter={() => {
        onLight(label);
      }}
      onMouseLeave={() => {
        onLight(null);
      }}
      onFocus={() => {
        onLight(label);
      }}
      onBlur={() => {
        onLight(null);
      }}
      onClick={() => {
        onLight(label);
      }}
      className="inline-flex h-[19px] items-center rounded-[5px] bg-nested px-[6px] text-[10.5px] font-medium hover:bg-match-soft focus-visible:bg-match-soft"
    >
      {label.replace(/^Art\. /, "")}
    </button>
  );
}

export function TXT01({
  returnId,
  onApprove,
  onCitedBy,
  onRecord,
  onDownload,
  onOpenInFiles,
}: TXT01Props): JSX.Element {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const read = useInstrument(returnId);
  const record = useReturnRecord(returnId).data?.row;
  const model = read.data;
  const clauses = useInstrumentClauses(model?.instrument?.id);
  const text = useInstrumentText(model?.instrument?.evidence_version_id);
  const start = useReadInstrument(returnId);
  const [hovered, setHovered] = useState<string | null>(null);
  const [selected, setSelected] = useState<InstrumentDeterminationOut["key"] | null>("trust_type");

  const citing = useMemo(() => {
    const out: Record<string, string[]> = {};
    for (const d of model?.determinations ?? []) {
      for (const l of d.clause_labels) (out[l] ??= []).push(DETERMINATION_LABELS[d.key]);
    }
    return out;
  }, [model]);

  if (read.isError) {
    return <ErrorState noun="instrument" onRetry={() => void read.refetch()} />;
  }
  if (model === undefined) {
    return (
      <div
        className="flex min-h-0 flex-1 gap-[10px] p-[10px]"
        data-screen="TXT-01"
        data-state="loading"
      >
        <Skeleton className="h-full flex-1" />
        <Skeleton className="h-full w-[490px]" />
      </div>
    );
  }
  const interp = model.interpretation;
  const approved = interp?.status === "approved";
  const selectedRow = model.determinations.find((d) => d.key === selected);
  const lit = hovered !== null ? [hovered] : (selectedRow?.clause_labels ?? []);
  const year = record?.tax_year ?? 2025;
  const trust = record?.client_name ?? "";
  const profile = model.profile;
  const canApprove = model.allowed_actions.includes("sign_off.l3") && interp !== null && !approved;

  return (
    <div
      className="flex min-h-0 flex-1 gap-[10px] p-[10px]"
      data-screen="TXT-01"
      data-state={interp?.status ?? "unread"}
    >
      <div className="flex min-h-0 flex-1 flex-col rounded-[12px] bg-card shadow-e1">
        {model.instrument === null ? (
          <EmptyState icon="notebook-text" title={COPY.unread.title} />
        ) : (
          <LegalReader
            fileName={model.instrument.file_name}
            pageCount={model.instrument.page_count}
            pages={text.data?.items ?? []}
            clauses={clauses.data?.clauses ?? []}
            lit={interp === null ? [] : lit}
            citing={citing}
            {...(onDownload === undefined ? {} : { onDownload })}
            {...(onOpenInFiles === undefined ? {} : { onOpenInFiles })}
          />
        )}
      </div>
      <aside
        className="flex min-h-0 w-[490px] shrink-0 flex-col rounded-[12px] bg-card shadow-e1"
        aria-label={COPY.profile}
      >
        <header className="relative flex h-[46px] shrink-0 items-center justify-center">
          <span className="text-[14.5px] font-medium">{COPY.profile}</span>
          <span className="absolute right-[10px]">
            <Button
              variant="primary"
              size="sm"
              disabled={!canApprove}
              onClick={onApprove}
              data-approve
            >
              {approved ? COPY.approved : COPY.approve}
            </Button>
          </span>
        </header>
        <div className="min-h-0 flex-1 overflow-auto">
          {approved && interp.approved_by_name != null && interp.approved_on != null && (
            <div
              className="mx-[12px] mb-[8px] inline-flex rounded-pill bg-green-tint px-[10px] text-dense text-green-ink"
              data-approved-pill
            >
              {COPY.approvedBy(
                interp.approved_by_name,
                date(onDay(interp.approved_on), { tz, now }),
              )}
            </div>
          )}
          {interp?.scenario_banner != null && (
            <div
              className="mx-[12px] mb-[8px] flex h-[32px] items-center rounded-[8px] bg-amber-tint px-[10px] text-dense text-amber-ink"
              role="status"
              data-scenario-banner
            >
              {interp.scenario_banner}
            </div>
          )}
          {trust !== "" && <KV k={COPY.rows.trust} v={trust} />}
          {profile.agreement_date != null && (
            <KV
              k={COPY.rows.agreement}
              v={COPY.agreement(
                date(onDay(profile.agreement_date), { tz, now }),
                !profile.revocable,
              )}
            />
          )}
          {profile.settlor_name != null && (
            <KV
              k={COPY.rows.settlor}
              v={COPY.settlor(profile.settlor_name, profile.settlor_died_year)}
            />
          )}
          {profile.ein != null && (
            <KV k={COPY.rows.ein} v={`••-•••${profile.ein.last4 ?? "••••"}`} />
          )}
          {profile.residency_state != null && (
            <KV
              k={COPY.rows.residency}
              v={COPY.residency(profile.residency_state, profile.state_form)}
            />
          )}
          {record !== undefined && <KV k={COPY.rows.taxYear} v={COPY.taxYear(record.tax_year)} />}
          {record?.extended_due_on != null && (
            <KV
              k={COPY.rows.due}
              v={COPY.due(date(onDay(record.extended_due_on), { tz, now }), record.extended)}
            />
          )}
          <div className="mt-[8px] flex h-[31px] items-center gap-[8px] bg-band-hd px-[12px] text-[13.5px] font-medium">
            {COPY.band(year)}
            {interp !== null && !approved && (
              <span className="rounded-pill bg-amber-tint px-[8px] text-meta text-amber-ink">
                {COPY.proposedByAgent}
              </span>
            )}
            {approved && (
              <span className="rounded-pill bg-green px-[8px] text-meta text-on-dark">
                {COPY.approved}
              </span>
            )}
          </div>
          {interp === null ? (
            <Unread
              model={model}
              trust={trust}
              pending={start.isPending}
              onRead={() => {
                start.mutate({
                  path: { return_id: returnId },
                  headers: { "Idempotency-Key": `read:${returnId}` },
                });
              }}
              onRecord={onRecord}
            />
          ) : (
            <ul>
              {model.determinations.map((d) => (
                <li
                  key={d.key}
                  data-determination={d.key}
                  data-lit={selected === d.key ? "true" : "false"}
                  className={`flex min-h-[44px] items-start gap-[10px] border-t-[0.5px] border-hair px-[12px] py-[8px] ${selected === d.key ? "bg-match-soft" : ""}`}
                  onClick={() => {
                    setSelected(d.key);
                  }}
                >
                  <div className="min-w-0 flex-1">
                    <div className="text-[12.5px] font-medium">{DETERMINATION_LABELS[d.key]}</div>
                    <div className="text-[12.5px] leading-[1.45] text-ink-2">{d.value_text}</div>
                  </div>
                  <div className="flex shrink-0 flex-wrap justify-end gap-[4px]">
                    {d.clause_labels.map((l) => (
                      <Chip key={l} label={l} onLight={setHovered} />
                    ))}
                    {d.clause_required && d.clause_labels.length === 0 && (
                      <span className="text-meta text-red-ink">{COPY.clauseRequired}</span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
          {interp?.scenario_note != null && (
            <p className="mx-[12px] mt-[6px] text-dense text-ink-2" data-scenario-note>
              {interp.scenario_note}
            </p>
          )}
          {model.cited_by.length > 0 && (
            <>
              <div className="mt-[8px] flex h-[31px] items-center bg-band-hd px-[12px] text-[13.5px] font-medium">
                {COPY.citedBy}
              </div>
              <ul>
                {model.cited_by.map((c) => (
                  <li key={c.target_ref} className="border-t-[0.5px] border-hair">
                    <button
                      type="button"
                      className="flex w-full items-center gap-[8px] px-[12px] py-[8px] text-left text-dense"
                      onClick={() => onCitedBy?.(c.target, c.target_ref)}
                    >
                      <Icon name="table" size={14} className="text-ink-3" />
                      {c.label}
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
        {interp !== null && (
          <footer className="shrink-0 px-[12px] py-[8px] text-[11.5px] text-ink-3" data-footer>
            {COPY.footer(
              interp.read_run_id != null ? "Sep 3" : null,
              model.determinations.length,
              interp.clause_citation_count,
              interp.adopted_by_name != null && interp.adopted_on != null
                ? `${interp.adopted_by_name} ${date(onDay(interp.adopted_on), { tz, now }).replace(/,\s*\d{4}$/, "")}`
                : null,
            )}
          </footer>
        )}
      </aside>
    </div>
  );
}

function Unread({
  model,
  trust,
  pending,
  onRead,
  onRecord,
}: {
  model: InstrumentOut;
  trust: string;
  pending: boolean;
  onRead: () => void;
  onRecord: TXT01Props["onRecord"];
}): JSX.Element {
  const reader = model.reader;
  if (reader.availability === "agents_off") {
    // d1 (DV-16): no Read instrument; a person records each determination with its clause.
    return (
      <div data-agents-off>
        <p className="px-[12px] py-[8px] text-dense text-ink-2">{COPY.agentsOff}</p>
        <ul>
          {KEYS.map((key) => (
            <li
              key={key}
              className="flex min-h-[44px] items-center justify-between border-t-[0.5px] border-hair px-[12px]"
            >
              <span className="text-[12.5px] font-medium">{DETERMINATION_LABELS[key]}</span>
              <span className="flex items-center gap-[8px]">
                {GOVERNED.has(key) && (
                  <span className="text-meta text-ink-3">{COPY.clauseRequired}</span>
                )}
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => onRecord?.(key)}
                  disabled={onRecord === undefined}
                >
                  {COPY.record}
                </Button>
              </span>
            </li>
          ))}
        </ul>
      </div>
    );
  }
  if (reader.progress_label != null) {
    // d2: the run's progress over C6 v2 (SSE, polling fallback).
    return (
      <p
        className="flex items-center gap-[8px] px-[12px] py-[12px] text-dense text-ink-2"
        role="status"
        data-reading
      >
        <Spinner label={reader.progress_label} size={12} showLabel={false} />
        {reader.progress_label}
      </p>
    );
  }
  return (
    <div className="py-[16px]" data-unread>
      <EmptyState icon="notebook-text" title={COPY.unread.title}>
        {COPY.unread.body}
      </EmptyState>
      {reader.availability === "consent_required" ? (
        <p className="px-[12px] text-center text-dense text-red-ink" role="status" data-consent>
          {COPY.consent(trust, reader.consents_signed, reader.consents_required)}
        </p>
      ) : (
        <div className="flex justify-center">
          <Button
            variant="secondary"
            onClick={onRead}
            disabled={pending || !model.allowed_actions.includes("instrument.read_run")}
          >
            {COPY.unread.read}
          </Button>
        </div>
      )}
    </div>
  );
}
