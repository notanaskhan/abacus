import type { DisclosureItemOut, LineItemOut, StatementVersionOut } from "@abacus/api-client";
import {
  checklistAnswerMutation,
  checklistOptions,
  fsStatementsOptions,
  fsStatementsQueryKey,
  tieOutMutation,
} from "@abacus/api-client/query";
import { Button, Dialog, Pill, Segmented, Skeleton, amount, cn } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useMemo, useState } from "react";
import { useFlag } from "../../app-core/flags";
import { COPY } from "./copy";

// AUD-20 · Financial statements & disclosure checklist (A-06-T30; A-06 F7; the handoff spec): T3's
// Prepare preset under Evaluation: outline 214, FS paper 571, checklist 571. Every figure is the
// server's; the browser adds nothing (ADR-050). Purple is for tracing only. Hovering a figure fans
// its sources; the client preview (d) shows no checklist and no source link. Sending and approval
// are a person's, and studio links stay hidden until A-10.

const FLAG = "reporting.fs_disclosure";
const PANE = "flex min-h-0 flex-col overflow-hidden rounded-[12px] bg-card e2";
const HEADER =
  "flex h-[46px] shrink-0 items-center justify-between px-[12px] text-[14.5px] font-medium";
const BAND =
  "flex h-[31px] items-center justify-between bg-faint px-[12px] text-[11.5px] font-medium text-ink-3";

type Segment = keyof typeof COPY.segments;
const SEGMENTS: readonly Segment[] = ["statements", "notes", "schedules"];

// The client's figures read without a "$", and a nil reads "—" (the statement grammar).
const figure = (v: string | null | undefined): string => {
  if (v === null || v === undefined) return "";
  return Number(v) === 0 ? "—" : amount(v, "whole", { zero: "dash" }).text;
};

export interface FsDisclosureProps {
  engagementId: string;
  /** The client draft preview (d): DRAFT watermark, no checklist, no source links. */
  preview?: boolean;
  /** The O3 send sheet (a2) starts open. */
  sending?: boolean;
  /** The active segment (f is Notes). */
  segment?: Segment;
  /** The mismatch card opens AUD-16 at RJE-1. */
  onMismatch?: (focus: string) => void;
  onCockpit?: () => void;
  /** A figure opens SHL-08 at its citation. */
  onSource?: (lineId: string) => void;
}

function Figure({
  line,
  year,
  preview,
  onSource,
}: {
  line: LineItemOut;
  year: number;
  preview: boolean;
  onSource: ((lineId: string) => void) | undefined;
}): JSX.Element | null {
  const [lit, setLit] = useState(false);
  const value = line.values.find((v) => v.year === year);
  if (value === undefined) return <td />;
  if (preview) {
    return (
      <td
        data-figure={`${line.line_key}:${String(year)}`}
        className="w-[104px] text-right tabular-nums"
      >
        {figure(value.value)}
      </td>
    );
  }
  const fanned = lit && line.line_key === "total_investments" && year === 2025;
  return (
    <td className="relative w-[104px] text-right tabular-nums">
      <button
        type="button"
        data-figure={`${line.line_key}:${String(year)}`}
        {...(lit ? { "data-lit": "" } : {})}
        onMouseEnter={() => {
          setLit(true);
        }}
        onMouseLeave={() => {
          setLit(false);
        }}
        onFocus={() => {
          setLit(true);
        }}
        onBlur={() => {
          setLit(false);
        }}
        onClick={() => onSource?.(line.id)}
        className={cn(
          "rounded-[4px] px-[3px] tabular-nums",
          lit && "bg-match ring-1 ring-match-line",
        )}
      >
        {figure(value.value)}
      </button>
      {fanned && (
        <span
          data-sources
          role="tooltip"
          className="absolute right-0 top-full z-10 flex w-[280px] flex-col gap-[4px] rounded-[10px] bg-card p-[8px] text-left text-[11.5px] e3"
        >
          <span>{COPY.sources.tb}</span>
          <span>{COPY.sources.trust}</span>
        </span>
      )}
    </td>
  );
}

function StatementRows({
  lines,
  years,
  preview,
  onSource,
  onMismatch,
}: {
  lines: readonly LineItemOut[];
  years: readonly number[];
  preview: boolean;
  onSource: ((lineId: string) => void) | undefined;
  onMismatch: ((focus: string) => void) | undefined;
}): JSX.Element {
  return (
    <>
      {lines.map((line) => {
        const off = line.values.find((v) => v.ties === false);
        const total = line.section_key === "total";
        const grand = line.section_key === "grand";
        return (
          <tr
            key={line.id}
            data-line={line.line_key}
            className={cn(
              "h-[26px] text-[12px]",
              total && "border-t-[0.5px] border-stroke font-medium",
              grand && "border-t-[3px] border-double border-ink font-medium",
            )}
          >
            <td className={cn(!total && !grand && "pl-[12px]")}>
              {line.label}
              {off != null && !preview && (
                <button
                  type="button"
                  data-off
                  onClick={() => onMismatch?.("RJE-1")}
                  className="ml-[8px]"
                >
                  <Pill size="micro" variant="amber">
                    {COPY.off(figure(off.off_by))}
                  </Pill>
                </button>
              )}
            </td>
            {years.map((year) => (
              <Figure key={year} line={line} year={year} preview={preview} onSource={onSource} />
            ))}
          </tr>
        );
      })}
    </>
  );
}

function Paper({
  version,
  preview,
  onSource,
  onMismatch,
}: {
  version: StatementVersionOut;
  preview: boolean;
  onSource: ((lineId: string) => void) | undefined;
  onMismatch: ((focus: string) => void) | undefined;
}): JSX.Element {
  const net = version.lines.filter((l) => l.statement_key === "net_assets");
  const changes = version.lines.filter((l) => l.statement_key === "changes");
  const off = version.tie_out?.off ?? [];
  return (
    <div className="relative rounded-[12px] bg-card p-[24px] e2" data-paper>
      {preview && (
        <div
          aria-hidden
          data-watermark
          className="pointer-events-none absolute inset-0 flex items-center justify-center text-[72px] font-medium text-ink/[.06] [transform:rotate(-30deg)]"
        >
          {COPY.previewMark}
        </div>
      )}
      <p className="text-center text-[11px] font-medium tracking-[.06em] text-ink-2">
        {COPY.plan}
      </p>
      <h3 className="text-center text-[16px] font-medium">{COPY.netAssets.head}</h3>
      <p className="mb-[8px] text-center text-[12px] text-ink-2">{COPY.netAssets.period}</p>
      <table className="w-full" data-statement="net_assets">
        <thead>
          <tr className="text-right text-[11.5px] text-ink-3">
            <th scope="col" />
            <th scope="col">2025</th>
            <th scope="col">2024</th>
          </tr>
        </thead>
        <tbody>
          <StatementRows
            lines={net}
            years={[2025, 2024]}
            preview={preview}
            onSource={onSource}
            onMismatch={onMismatch}
          />
        </tbody>
      </table>
      <h3 className="mt-[20px] text-center text-[16px] font-medium">{COPY.changes.head}</h3>
      <p className="mb-[8px] text-center text-[12px] text-ink-2">{COPY.changes.period}</p>
      <table className="w-full" data-statement="changes">
        <tbody>
          <StatementRows
            lines={changes}
            years={[2025]}
            preview={preview}
            onSource={onSource}
            onMismatch={onMismatch}
          />
        </tbody>
      </table>
      {off.length > 0 && !preview && (
        <div
          data-mismatch
          className="mt-[12px] rounded-[10px] bg-amber-tint p-[12px] text-[12.5px]"
        >
          <p>{COPY.mismatch.card}</p>
          <button type="button" className="underline" onClick={() => onMismatch?.("RJE-1")}>
            {COPY.mismatch.open}
          </button>
        </div>
      )}
    </div>
  );
}

function Note3(): JSX.Element {
  return (
    <div className="rounded-[12px] bg-card p-[24px] e2" data-note="3">
      <h4 className="mb-[8px] text-[13.5px] font-medium">{COPY.note3.head}</h4>
      <table className="w-full text-[12px]">
        <tbody>
          {COPY.note3.rows.map(([label, value]) => (
            <tr key={label} className="h-[26px]">
              <td>{label}</td>
              <td className="text-right tabular-nums">{figure(value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ChecklistRow({
  item,
  documentId,
}: {
  item: DisclosureItemOut;
  documentId: string;
}): JSX.Element {
  const client = useQueryClient();
  const [typed, setTyped] = useState(item.reason ?? "");
  // A-06-T34: N/A needs its reason (422 `reason_required` server side); ask for it first.
  const [asking, setAsking] = useState(false);
  const answer = useMutation({
    ...checklistAnswerMutation(),
    onSuccess: () => {
      void client.invalidateQueries({
        queryKey: checklistOptions({ path: { document_id: documentId } }).queryKey,
      });
    },
  });
  const words = COPY.checklist.answers;
  return (
    <div
      data-item={item.item_key}
      className="flex min-h-[44px] flex-col gap-[4px] px-[12px] py-[6px] hairline-t"
    >
      <div className="flex items-start justify-between gap-[8px]">
        <p className="text-[12.5px]">{item.text}</p>
        <span className="flex shrink-0 items-center gap-[6px]">
          <Segmented
            label={item.text}
            size="small"
            active={item.answer == null ? "" : words[item.answer]}
            options={[words.yes, words.no, words.na]}
            onChange={(label) => {
              const next = label === words.yes ? "yes" : label === words.no ? "no" : "na";
              if (next === "na" && typed.trim() === "") {
                setAsking(true);
                return;
              }
              setAsking(false);
              answer.mutate({
                path: { document_id: documentId, item_key: item.item_key },
                body: {
                  answer: next,
                  ...(next === "na" ? { reason: typed } : {}),
                  note_ref: item.note_ref ?? null,
                },
                headers: { "If-Match": item.version },
              });
            }}
          />
          {item.note_ref != null && (
            <Pill size="chip" variant="neutral">
              {item.note_ref}
            </Pill>
          )}
        </span>
      </div>
      {(item.reason != null || asking) && (
        <input
          data-reason={item.item_key}
          aria-label={item.text}
          value={typed}
          onChange={(e) => {
            setTyped(e.target.value);
          }}
          className="bg-transparent text-[11.5px] text-ink-3"
        />
      )}
    </div>
  );
}

function Checklist({
  documentId,
  enabled,
}: {
  documentId: string;
  enabled: boolean;
}): JSX.Element {
  const found = useQuery({
    ...checklistOptions({ path: { document_id: documentId } }),
    enabled,
    retry: false,
  });
  const items = useMemo(() => found.data?.items ?? [], [found.data]);
  const count = (answer: DisclosureItemOut["answer"]): number =>
    items.filter((i) => i.answer === answer).length;
  const sections = useMemo(() => [...new Set(items.map((i) => i.section))], [items]);
  return (
    <section data-pane="checklist" className={PANE}>
      <div className={HEADER}>
        <span className="text-[12.5px] font-normal">{COPY.checklist.picker}</span>
        <span>{COPY.checklist.head}</span>
        <span className="text-[12.5px] font-normal text-ink-2">{COPY.checklist.excel}</span>
      </div>
      <div data-summary className="flex h-[40px] shrink-0 items-center gap-[6px] px-[12px]">
        <Pill size="chip" variant="neutral">
          {COPY.checklist.items(found.data?.total ?? 0)}
        </Pill>
        <Pill size="chip" variant="green-tint">
          {COPY.checklist.yes(count("yes"))}
        </Pill>
        <Pill size="chip" variant="neutral">
          {COPY.checklist.na(count("na"))}
        </Pill>
        <Pill size="chip" variant="neutral">
          {COPY.checklist.no(count("no"))}
        </Pill>
        <span className="ml-auto text-[11.5px] text-ink-3">{COPY.checklist.completed}</span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {sections.map((section) => (
          <div key={section}>
            <p className={BAND}>{section}</p>
            {items
              .filter((i) => i.section === section)
              .map((item) => (
                <ChecklistRow key={item.item_key} item={item} documentId={documentId} />
              ))}
          </div>
        ))}
      </div>
    </section>
  );
}

function SendSheet({ onClose }: { onClose: () => void }): JSX.Element {
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={COPY.send.title}
      size="sm"
    >
      <div data-sheet="send-draft" className="flex flex-col gap-[8px] text-[12.5px]">
        <p>{COPY.send.recipient}</p>
        <p className="text-ink-2">{COPY.send.watermark}</p>
        <p className="text-ink-2">{COPY.send.comments}</p>
        <p className="text-ink-3">{COPY.send.unavailable}</p>
        <div className="flex justify-end gap-[8px]">
          <Button variant="secondary" onClick={onClose}>
            {COPY.send.cancel}
          </Button>
          <Button disabled>{COPY.send.send}</Button>
        </div>
      </div>
    </Dialog>
  );
}

export function FsDisclosurePane({
  engagementId,
  preview = false,
  sending = false,
  segment: initialSegment = "statements",
  onMismatch,
  onCockpit,
  onSource,
}: FsDisclosureProps): JSX.Element {
  const on = useFlag(FLAG) === true;
  const client = useQueryClient();
  const [segment, setSegment] = useState<Segment>(initialSegment);
  const [sheet, setSheet] = useState(sending);
  const options = fsStatementsOptions({ path: { engagement_id: engagementId } });
  const found = useQuery({
    ...options,
    enabled: on,
    retry: false,
    // The draft runs in the background (FsDraftWorkflow): poll until its version lands.
    refetchInterval: (q) => (q.state.data != null && q.state.data.current == null ? 5000 : false),
  });
  const tieOut = useMutation({
    ...tieOutMutation(),
    onSuccess: () => {
      void client.invalidateQueries({
        queryKey: fsStatementsQueryKey({ path: { engagement_id: engagementId } }),
      });
    },
  });
  const view = found.data;
  const version = view?.current;
  const tied = version?.tie_out;
  const documentId = view?.statement_document_id;
  const can = view?.allowed_actions ?? [];
  if (!on) {
    return (
      <div data-screen="AUD-20" data-off className="p-[24px] text-[12.5px] text-ink-2">
        <p className="font-medium">{COPY.off_.title}</p>
        <p>{COPY.off_.body}</p>
      </div>
    );
  }
  return (
    <div data-screen="AUD-20" data-segment={segment} className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-[44px] shrink-0 items-center justify-between px-[12px]">
        <button type="button" onClick={onCockpit} className="text-[12.5px] text-ink-2">
          {COPY.cockpit}
        </button>
        <Segmented
          label={COPY.groups.statements}
          active={COPY.segments[segment]}
          options={SEGMENTS.map((s) => COPY.segments[s])}
          onChange={(label) => {
            const next = SEGMENTS.find((s) => COPY.segments[s] === label);
            if (next !== undefined) setSegment(next);
          }}
        />
        <span />
      </div>
      <div
        className={cn(
          "grid min-h-0 flex-1 gap-[8px] px-[12px] pb-[12px]",
          preview ? "grid-cols-[214px_1fr]" : "grid-cols-[214px_1fr_1fr]",
        )}
      >
        <aside data-pane="outline" className={PANE}>
          <div className={cn(HEADER, "justify-center")}>{COPY.contents}</div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            <p className={BAND}>{COPY.groups.statements}</p>
            <p className="flex h-[29px] items-center px-[12px] text-[12.5px]">
              {COPY.outline.netAssets}
            </p>
            <p className="flex h-[29px] items-center px-[12px] text-[12.5px]">
              {COPY.outline.changes}
            </p>
            <p className={BAND}>{COPY.groups.notes}</p>
            {COPY.outline.notes.map((n) => (
              <p key={n} className="flex h-[29px] items-center px-[12px] text-[12.5px]">
                {n}
              </p>
            ))}
            <p className={BAND}>{COPY.groups.schedules}</p>
            <p className="px-[12px] py-[4px] text-[12.5px]">{COPY.outline.line4a}</p>
            <p className="px-[12px] py-[4px] text-[12.5px]">{COPY.outline.line4i}</p>
          </div>
          {!preview && (
            <div className="flex flex-col gap-[8px] p-[10px]">
              {can.includes("statement.send_draft") && (
                <Button
                  onClick={() => {
                    setSheet(true);
                  }}
                >
                  {COPY.sendDraft}
                </Button>
              )}
              {version != null && can.includes("statement.tie_out") && (
                <Button
                  variant="tonal"
                  disabled={tieOut.isPending}
                  onClick={() => {
                    tieOut.mutate({
                      path: { version_id: version.id },
                      headers: { "Idempotency-Key": crypto.randomUUID() },
                    });
                  }}
                >
                  {COPY.runTieOut}
                </Button>
              )}
            </div>
          )}
        </aside>
        <section data-pane="paper" className={PANE}>
          <div className={HEADER}>
            <span />
            <span>{version == null ? COPY.draft : COPY.paperTitle(version.version_no)}</span>
            <span className="flex items-center gap-[6px]">
              {view?.management_approval === "approved_by_management" ? (
                <Pill size="chip" variant="green-tint">
                  {COPY.approved}
                </Pill>
              ) : (
                <Pill size="chip" variant="neutral">
                  {COPY.draft}
                </Pill>
              )}
              {tied != null && !preview && (
                <Pill data-tie size="tally" variant={tied.tied === tied.total ? "green" : "amber"}>
                  {COPY.ties(tied.tied, tied.total)}
                </Pill>
              )}
            </span>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto bg-shell p-[14px]">
            {view !== undefined && version == null ? (
              <div data-drafting role="status" className="flex flex-col gap-[8px]">
                <Skeleton className="h-[120px]" />
                <Skeleton className="h-[120px]" />
                <p className="text-[12.5px] text-ink-2">{COPY.drafting}</p>
              </div>
            ) : version == null ? (
              <Skeleton className="h-[240px]" />
            ) : segment === "notes" ? (
              <Note3 />
            ) : (
              <Paper
                version={version}
                preview={preview}
                onSource={onSource}
                onMismatch={onMismatch}
              />
            )}
          </div>
        </section>
        {!preview && documentId != null && <Checklist documentId={documentId} enabled={on} />}
      </div>
      {sheet && (
        <SendSheet
          onClose={() => {
            setSheet(false);
          }}
        />
      )}
    </div>
  );
}
