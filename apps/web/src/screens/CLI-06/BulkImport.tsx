import type { ClientImportOut, ClientImportRowOut } from "@abacus/api-client";
import {
  Button,
  type Column,
  DataTable,
  Fieldset,
  Pill,
  Segmented,
  TallyStrip,
  Wizard,
  type WizardStep,
  time,
  toast,
} from "@abacus/ui";
import { type JSX, type ReactNode, useEffect, useRef, useState } from "react";
import {
  IMPORT_STEPS,
  type ImportSource,
  type ImportStep,
  type RowDecision,
  fileProblem,
  percent,
  stepOfStage,
  toImport,
  useClientImport,
  useImportReview,
  useImportWrites,
} from "../../domain/clients";
import { COPY } from "./copy";

// CLI-06 g · Bulk import (P-07-T54; docs/screens/CLI-06.md; Story 3.2), on the live import routes
// (P-07-T52, DEC-643): Source (the file and its kind, uploaded as it is) · Map fields (the
// server's heading map, read-only: DEC-812) · Review duplicates (the tallies, and each row below
// the 90% auto-match with Merge, Keep both or Skip; a person's decision is saved as it is made) ·
// Import ("Import 210 records" runs the import; the pill says "Importing 210 records…" until the
// server is done, then the toast "210 records imported · 2 skipped · 0 new clients"). An
// undecided row is skipped at the run (DEC-643), so the count leaves it out. Every figure is the
// server's; the screen counts nothing but the run's rows left out.

const DECISIONS: readonly RowDecision[] = ["merge", "keep_both", "skip"];

export interface BulkImportProps {
  /** An import to resume (g opens on its review). */
  importId?: string;
  /** The step it opens on (the import's stage decides otherwise). */
  step?: ImportStep;
  /** The mode switch, shared with the single intake. */
  modeSwitch: ReactNode;
  onClose?: () => void;
}

function decisionWord(d: RowDecision): string {
  return COPY.import.decisions[d] ?? d;
}

function SourceStep({
  source,
  onSource,
  file,
  onFile,
  problem,
}: {
  source: ImportSource;
  onSource: (s: ImportSource) => void;
  file: File | null;
  onFile: (f: File) => void;
  problem: string | null;
}): JSX.Element {
  const input = useRef<HTMLInputElement>(null);
  const kinds = Object.entries(COPY.import.sources) as [ImportSource, string][];
  return (
    <Fieldset title={COPY.import.steps.source}>
      <div className="flex flex-col gap-[12px] px-[12px] py-[10px]">
        <Segmented
          size="small"
          label={COPY.import.sourceLabel}
          active={COPY.import.sources[source] ?? source}
          options={kinds.map(([, label]) => ({ label }))}
          onChange={(label) => {
            const found = kinds.find(([, l]) => l === label);
            if (found !== undefined) onSource(found[0]);
          }}
        />
        <span className="flex items-center gap-[8px]">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              input.current?.click();
            }}
          >
            {COPY.import.choose}
          </Button>
          {file !== null && (
            <span data-cli06="file" className="text-dense text-ink-2">
              {COPY.import.chosen(file.name)}
            </span>
          )}
        </span>
        <input
          ref={input}
          type="file"
          accept=".csv,text/csv"
          aria-label={COPY.import.choose}
          className="hidden"
          onChange={(e) => {
            const chosen = e.target.files?.[0];
            if (chosen !== undefined) onFile(chosen);
          }}
        />
        {problem !== null && (
          <p role="alert" className="text-meta text-red-ink">
            {COPY.import.fileErrors[problem] ?? COPY.failed}
          </p>
        )}
      </div>
    </Fieldset>
  );
}

function SourceLine({ data }: { data: ClientImportOut }): JSX.Element {
  return (
    <p data-cli06="source-line" className="text-dense text-ink-2">
      {COPY.import.line(
        COPY.import.sourceWords[data.source] ?? data.source,
        data.counts.rows,
        time(data.started_at),
      )}
    </p>
  );
}

function MapStep({ data }: { data: ClientImportOut }): JSX.Element {
  const rows = Object.entries(data.mapping ?? {});
  return (
    <div className="flex flex-col gap-[12px]">
      <SourceLine data={data} />
      <Fieldset title={COPY.import.mapTitle}>
        <DataTable
          label={COPY.import.mapTitle}
          dense
          rows={rows}
          rowKey={([heading]) => heading}
          columns={[
            {
              key: "column",
              header: COPY.import.mapColumns.column,
              cell: ([heading]) => heading,
            },
            {
              key: "field",
              header: COPY.import.mapColumns.field,
              cell: ([, field]) => COPY.import.fields[field] ?? field,
            },
          ]}
        />
        <p className="px-[12px] py-[8px] text-meta text-ink-3">{COPY.import.mapNote}</p>
      </Fieldset>
    </div>
  );
}

function ReviewStep({
  data,
  rows,
  onDecide,
  locked,
}: {
  data: ClientImportOut;
  rows: readonly ClientImportRowOut[];
  onDecide: (row: ClientImportRowOut, d: RowDecision) => void;
  locked: boolean;
}): JSX.Element {
  const { counts } = data;
  const columns: Column<ClientImportRowOut>[] = [
    {
      key: "record",
      header: COPY.import.columns.record,
      width: "w-[260px]",
      cell: (r) => <span data-cli06-row={r.row_no}>{r.display_name}</span>,
    },
    {
      key: "match",
      header: COPY.import.columns.match,
      width: "w-[280px]",
      cell: (r) => r.best_match_name ?? COPY.none,
    },
    {
      key: "score",
      header: COPY.import.columns.score,
      align: "right",
      width: "w-[70px]",
      cell: (r) => {
        const p = percent(r.score);
        return p === null ? (
          COPY.none
        ) : (
          <span className="tabular-nums">{COPY.import.score(p)}</span>
        );
      },
    },
    {
      key: "decision",
      header: COPY.import.columns.decision,
      width: "w-[260px]",
      cell: (r) => {
        const options = DECISIONS.filter((d) => d !== "merge" || r.best_match_client_id != null);
        if (r.decision == null) {
          // Nothing chosen yet: a Segmented track always shows one option chosen, so the three
          // choices are plain buttons until a person picks one.
          return (
            <span
              role="group"
              aria-label={COPY.import.decisionLabel(r.display_name)}
              className="flex gap-[4px]"
            >
              {options.map((d) => (
                <Button
                  key={d}
                  variant="secondary"
                  size="sm"
                  disabled={locked}
                  onClick={() => {
                    onDecide(r, d);
                  }}
                >
                  {decisionWord(d)}
                </Button>
              ))}
            </span>
          );
        }
        return (
          <Segmented
            size="small"
            label={COPY.import.decisionLabel(r.display_name)}
            active={decisionWord(r.decision)}
            options={options.map((d) => ({
              label: decisionWord(d),
              ...(locked ? { disabled: true } : {}),
            }))}
            onChange={(label) => {
              const d = options.find((o) => decisionWord(o) === label);
              if (d !== undefined && d !== r.decision) onDecide(r, d);
            }}
          />
        );
      },
    },
    {
      key: "note",
      header: COPY.import.columns.note,
      cell: (r) => {
        if (r.error_code != null) {
          return (
            <span className="text-amber-ink">
              {COPY.import.notes[r.error_code] ?? r.error_code}
            </span>
          );
        }
        return r.decision == null ? (
          <span className="text-ink-3">{COPY.import.undecided}</span>
        ) : (
          COPY.none
        );
      },
    },
  ];
  return (
    <div className="flex flex-col gap-[12px]">
      <SourceLine data={data} />
      <TallyStrip
        label={COPY.import.tally.label}
        items={[
          { label: COPY.import.tally.matched, value: String(counts.matched) },
          {
            label: COPY.import.tally.review,
            pill: {
              text: String(counts.to_review),
              variant: counts.to_review > 0 ? "amber" : "neutral",
            },
          },
          { label: COPY.import.tally.new, value: String(counts.new) },
        ]}
      />
      {rows.length === 0 ? (
        <p className="text-dense text-ink-2">{COPY.import.noReview}</p>
      ) : (
        <DataTable
          label={COPY.import.table}
          rows={[...rows]}
          rowKey={(r) => r.id}
          columns={columns}
        />
      )}
    </div>
  );
}

function ImportStepBody({ data, count }: { data: ClientImportOut; count: number }): JSX.Element {
  const { counts } = data;
  return (
    <div className="flex flex-col gap-[12px]">
      <SourceLine data={data} />
      {data.stage === "importing" && (
        <span data-cli06="progress">
          <Pill variant="tag" spin>
            {COPY.import.progress(count)}
          </Pill>
        </span>
      )}
      {data.stage === "done" && (
        <p data-cli06="result" role="status" className="text-body text-ink">
          {COPY.import.toast(counts.imported ?? 0, counts.skipped ?? 0, counts.new)}
        </p>
      )}
      {data.stage === "failed" && (
        <p role="alert" className="text-dense text-red-ink">
          {COPY.import.failedRun}
        </p>
      )}
    </div>
  );
}

export function BulkImport({
  importId: openId,
  step: openStep,
  modeSwitch,
  onClose,
}: BulkImportProps): JSX.Element {
  const writes = useImportWrites();
  const [importId, setImportId] = useState<string | null>(openId ?? null);
  const [step, setStep] = useState<ImportStep | null>(openStep ?? null);
  const [source, setSource] = useState<ImportSource>("cch_axcess_tax_export");
  const [file, setFile] = useState<File | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [running, setRunning] = useState<number | null>(null);
  const data = useClientImport(importId).data;
  const review = useImportReview(importId).data?.items ?? [];
  const current: ImportStep = step ?? (data === undefined ? "source" : stepOfStage(data.stage));
  const index = IMPORT_STEPS.indexOf(current);
  const steps: WizardStep[] = IMPORT_STEPS.map((id, i) => ({
    id,
    label: COPY.import.steps[id],
    state:
      i < index || (id === "import" && data?.stage === "done")
        ? "done"
        : i === index
          ? "current"
          : "todo",
  }));
  const locked = data !== undefined && data.stage !== "reviewing";
  const count = data === undefined ? 0 : toImport(data.counts, review);

  // The run's toast, once the server says it is done (never before).
  useEffect(() => {
    if (running === null || data?.stage !== "done") return;
    const { counts } = data;
    toast.show({
      kind: "success",
      text: COPY.import.toast(counts.imported ?? 0, counts.skipped ?? 0, counts.new),
    });
    setRunning(null);
  }, [running, data]);

  const upload = async (): Promise<void> => {
    if (file === null) return;
    setProblem(null);
    try {
      const out = await writes.upload(file, source);
      setImportId(out.id);
      setStep("map");
    } catch (error) {
      setProblem(fileProblem(error) ?? "failed");
    }
  };
  const decide = (row: ClientImportRowOut, d: RowDecision): void => {
    if (importId === null) return;
    void writes.decide(importId, row, d).catch(() => {
      toast.show({ kind: "error", text: COPY.failed });
    });
  };
  const run = async (): Promise<void> => {
    if (importId === null) return;
    try {
      setRunning(count);
      await writes.run(importId);
      setStep("import");
    } catch {
      setRunning(null);
      toast.show({ kind: "error", text: COPY.failed });
    }
  };

  let body: ReactNode = null;
  if (current === "source") {
    body = (
      <SourceStep
        source={source}
        onSource={setSource}
        file={file}
        onFile={(f) => {
          setFile(f);
          setProblem(null);
        }}
        problem={problem}
      />
    );
  } else if (data !== undefined) {
    body =
      current === "map" ? (
        <MapStep data={data} />
      ) : current === "review" ? (
        <ReviewStep data={data} rows={review} onDecide={decide} locked={locked} />
      ) : (
        <ImportStepBody data={data} count={running ?? count} />
      );
  }

  let footer: Partial<{
    onBack: () => void;
    onNext: () => void;
    nextDisabled: boolean;
    actions: ReactNode;
  }> = {};
  if (current === "source") {
    footer = { onNext: () => void upload(), nextDisabled: file === null || writes.busy };
  } else if (current === "map") {
    footer = {
      onNext: () => {
        setStep("review");
      },
    };
  } else if (current === "review") {
    footer = {
      onBack: () => {
        setStep("map");
      },
      actions: (
        <Button
          variant="primary"
          disabled={writes.busy || locked || count === 0}
          onClick={() => void run()}
        >
          {COPY.import.run(count)}
        </Button>
      ),
    };
  } else {
    footer = {
      actions: (
        <Button
          variant="primary"
          disabled={data?.stage === "importing"}
          onClick={() => {
            onClose?.();
          }}
        >
          {COPY.import.done}
        </Button>
      ),
    };
  }

  return (
    <div data-screen="CLI-06" data-cli06-mode="bulk" className="contents">
      <Wizard
        open
        onOpenChange={(open) => {
          if (!open) onClose?.();
        }}
        title={COPY.title}
        steps={steps}
        onStepChange={(id) => {
          const to = IMPORT_STEPS.find((s) => s === id);
          // Rows jump back only, and never before the upload or after the run.
          if (to !== undefined && to !== "source" && IMPORT_STEPS.indexOf(to) < index && !locked) {
            setStep(to);
          }
        }}
        aside={
          <div className="flex flex-col gap-[8px] p-[14px]">
            {modeSwitch}
            <span className="text-meta text-ink-3">
              {COPY.stepOf(index + 1, IMPORT_STEPS.length)}
            </span>
          </div>
        }
        {...footer}
      >
        <div className="mx-auto flex w-full max-w-[1100px] flex-col gap-[12px]">{body}</div>
      </Wizard>
    </div>
  );
}
