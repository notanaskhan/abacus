import type {
  StandardOut,
  StandardVersionOut,
  StandardVersionSummaryOut,
} from "@abacus/api-client";
import {
  draftVersionMutation,
  editDraftMutation,
  publishVersionMutation,
  standardDiscardDraftMutation,
  standardOptions,
  standardVersionOptions,
} from "@abacus/api-client/query";
import {
  Button,
  ConfirmDialog,
  Dialog,
  ErrorState,
  Fieldset,
  Pill,
  Skeleton,
  ValueRow,
  amount,
  cn,
  date,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type ReactNode, useEffect, useState } from "react";
import { currentRoute, signIn } from "../../app-core/auth";
import { COPY } from "./copy";

// KNW-04 i · Draft new version (K-02-T14; docs/screens/KNW-04.md i; SPEC-500 AC-52 to AC-55). The
// owner's draft of the chosen standard: typed editors per kind (AJE limits and approvers, variance
// percent and amount, materiality ranges, document confidence, SSARS early adoption), every changed
// cell amber-tinted with the prior value struck beside it, and the sticky Save bar: "Draft vN · n
// changes from vM · visible to partners only", the Effective date, Discard draft and Publish vN…
// (a ConfirmDialog; the matrix wants a fresh second factor, so a 403 opens the step-up). Saves send
// If-Match; a 409 shows the "Changed by … Reload" row instead of overwriting. Checklists, review
// levels and the return approval policy are edited as workbooks (Export, then Import…). Only the
// standard's owner sees Publish (`allowed_actions`); the Accrued Agent never drafts or publishes.

type Payload = StandardVersionOut["payload"];
type Of<K extends Payload["kind"]> = Extract<Payload, { kind: K }>;

const whole = (v: number): string => `$${amount(String(v), "whole").text}`;

/** A changed cell: amber tint, the prior value struck, then the draft's. */
function Changed({ was, now }: { was: string | null; now: string }): JSX.Element {
  if (was === null || was === now) return <span>{now}</span>;
  return (
    <span data-changed="" className="-mx-[6px] rounded-sheet bg-amber-tint px-[6px] py-[2px]">
      <s className="mr-[6px] text-ink-3">{was}</s>
      <span className="font-medium text-amber-ink">{now}</span>
    </span>
  );
}

/** An editable figure in a cell: the draft's value as text, parsed on blur. */
function Figure({
  label,
  value,
  was,
  onChange,
  format,
}: {
  label: string;
  value: string;
  was: string | null;
  onChange: (next: string) => void;
  format: (v: string) => string;
}): JSX.Element {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(value);
  useEffect(() => {
    setText(value);
  }, [value]);
  if (!editing) {
    return (
      <button
        type="button"
        aria-label={`${label}: ${format(value)}`}
        className="text-left"
        onClick={() => {
          setEditing(true);
        }}
      >
        <Changed was={was === null ? null : format(was)} now={format(value)} />
      </button>
    );
  }
  return (
    <input
      aria-label={label}
      autoFocus
      inputMode="decimal"
      className="h-[26px] w-[120px] rounded-sheet bg-nested px-[8px] text-body text-ink inset-shadow-hair focus:bg-card"
      value={text}
      onChange={(e) => {
        setText(e.target.value.replace(/[^0-9.]/g, ""));
      }}
      onBlur={() => {
        setEditing(false);
        if (text !== "" && text !== value) onChange(text);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") (e.target as HTMLInputElement).blur();
        if (e.key === "Escape") {
          setText(value);
          setEditing(false);
        }
      }}
    />
  );
}

function Table({
  head,
  rows,
  label,
}: {
  head: readonly string[];
  rows: readonly { key: string; cells: readonly ReactNode[] }[];
  label: string;
}): JSX.Element {
  const cols = `repeat(${String(head.length)}, minmax(0, 1fr))`;
  return (
    <div role="table" aria-label={label}>
      <div
        role="row"
        className="grid min-h-[30px] items-center gap-[12px] border-b-[0.5px] border-hair bg-nested px-[12px] text-th text-ink-2"
        style={{ gridTemplateColumns: cols }}
      >
        {head.map((h) => (
          <span key={h} role="columnheader">
            {h}
          </span>
        ))}
      </div>
      {rows.map((r) => (
        <div
          key={r.key}
          role="row"
          className="grid min-h-[34px] items-center gap-[12px] border-b-[0.5px] border-hair px-[12px] py-[6px] text-body"
          style={{ gridTemplateColumns: cols }}
        >
          {r.cells.map((c, i) => (
            <span key={i} role="cell">
              {c}
            </span>
          ))}
        </div>
      ))}
    </div>
  );
}

/** How many entries differ, by position (rows keep their order in a draft). */
export function changeCount(was: Payload | undefined, now: Payload): number {
  if (was === undefined || was.kind !== now.kind) return 0;
  const a = was as Record<string, unknown>;
  const b = now as Record<string, unknown>;
  let n = 0;
  for (const key of new Set([...Object.keys(a), ...Object.keys(b)])) {
    const x = a[key];
    const y = b[key];
    if (Array.isArray(x) && Array.isArray(y)) {
      const len = Math.max(x.length, y.length);
      for (let i = 0; i < len; i += 1) {
        if (JSON.stringify(x[i]) !== JSON.stringify(y[i])) n += 1;
      }
    } else if (JSON.stringify(x) !== JSON.stringify(y)) {
      n += 1;
    }
  }
  return n;
}

function Editor({
  payload,
  prior,
  onChange,
}: {
  payload: Payload;
  prior: Payload | undefined;
  onChange: (next: Payload) => void;
}): JSX.Element {
  switch (payload.kind) {
    case "aje_thresholds": {
      const was = prior?.kind === "aje_thresholds" ? prior.rows : [];
      return (
        <Table
          label={COPY.aje.head.join(", ")}
          head={COPY.aje.head}
          rows={payload.rows.map((row, i) => ({
            key: `${row.account_class}-${String(i)}`,
            cells: [
              row.account_class,
              row.rule === "limit" ? (
                <Figure
                  label={`${row.account_class} · ${COPY.aje.head[1] ?? ""}`}
                  value={String(row.limit_usd ?? 0)}
                  was={was[i]?.limit_usd === undefined ? null : String(was[i]?.limit_usd ?? "")}
                  format={(v) => whole(Number(v))}
                  onChange={(next) => {
                    const rows = payload.rows.map((r, j) =>
                      j === i ? { ...r, limit_usd: Number(next) } : r,
                    );
                    onChange({ ...payload, rows } satisfies Of<"aje_thresholds">);
                  }}
                />
              ) : (
                <span className={cn(row.rule === "review_required" && "text-amber-ink")}>
                  {row.rule === "review_required" ? COPY.aje.reviewRequired : COPY.aje.alwaysHeld}
                </span>
              ),
              `${COPY.aje.approver[row.approver_level]}${row.batch ? COPY.aje.batch : ""}`,
            ],
          }))}
        />
      );
    }
    case "variance_thresholds": {
      const was = prior?.kind === "variance_thresholds" ? prior.rows : [];
      return (
        <Table
          label="Variance thresholds"
          head={["Context", "Percent", "Amount"]}
          rows={payload.rows.map((row, i) => ({
            key: row.context,
            cells: [
              row.context,
              <Figure
                key="p"
                label={`${row.context} percent`}
                value={String(row.pct)}
                was={was[i] === undefined ? null : String(was[i]?.pct)}
                format={(v) => `${v}%`}
                onChange={(next) => {
                  const rows = payload.rows.map((r, j) => (j === i ? { ...r, pct: next } : r));
                  onChange({ ...payload, rows } as Payload);
                }}
              />,
              <Figure
                key="a"
                label={`${row.context} amount`}
                value={String(row.amount_usd)}
                was={was[i] === undefined ? null : String(was[i]?.amount_usd)}
                format={(v) => whole(Number(v))}
                onChange={(next) => {
                  const rows = payload.rows.map((r, j) =>
                    j === i ? { ...r, amount_usd: Number(next) } : r,
                  );
                  onChange({ ...payload, rows } as Payload);
                }}
              />,
            ],
          }))}
        />
      );
    }
    case "materiality_ranges": {
      const was = prior?.kind === "materiality_ranges" ? prior.rows : [];
      return (
        <Table
          label="Materiality ranges"
          head={["Engagement", "Benchmark", "Low", "High"]}
          rows={payload.rows.map((row, i) => ({
            key: row.engagement_kind,
            cells: [
              row.engagement_kind,
              row.benchmark,
              ...(["low_pct", "high_pct"] as const).map((field) => (
                <Figure
                  key={field}
                  label={`${row.engagement_kind} ${field === "low_pct" ? "low" : "high"}`}
                  value={String(row[field])}
                  was={was[i] === undefined ? null : String(was[i]?.[field])}
                  format={(v) => `${v}%`}
                  onChange={(next) => {
                    const rows = payload.rows.map((r, j) =>
                      j === i ? { ...r, [field]: next } : r,
                    );
                    onChange({ ...payload, rows } as Payload);
                  }}
                />
              )),
            ],
          }))}
        />
      );
    }
    case "document_confidence": {
      const was = prior?.kind === "document_confidence" ? prior : undefined;
      return (
        <Table
          label="Document confidence"
          head={["Hold below", "Auto-accept above"]}
          rows={[
            {
              key: "confidence",
              cells: (["hold_below_pct", "auto_accept_above_pct"] as const).map((field) => (
                <Figure
                  key={field}
                  label={field === "hold_below_pct" ? "Hold below" : "Auto-accept above"}
                  value={String(payload[field])}
                  was={was === undefined ? null : String(was[field])}
                  format={(v) => `${v}%`}
                  onChange={(next) => {
                    onChange({ ...payload, [field]: next } as Payload);
                  }}
                />
              )),
            },
          ]}
        />
      );
    }
    case "ssars_cas_settings":
      return (
        <ValueRow
          kind="toggle"
          label="Early adopt SSARS 27"
          checked={payload.early_adopt_ssars27}
          onChange={(checked) => {
            onChange({ ...payload, early_adopt_ssars27: checked });
          }}
        />
      );
    default:
      return <p className="px-[12px] py-[10px] text-meta text-ink-3">{COPY.draft.readOnlyKind}</p>;
  }
}

function isStatus(error: unknown, code: string): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "detail" in error &&
    JSON.stringify((error as { detail: unknown }).detail).includes(code)
  );
}

export interface DraftPaneProps {
  standard: StandardOut;
  title: string;
  /** The version in effect: the prior values the changed cells strike. */
  current: StandardVersionOut | null;
  now: number;
  onClosed: () => void;
}

/** KNW-04 i: the owner's draft, its editors and the sticky Save bar. */
export function DraftPane({
  standard,
  title,
  current,
  now,
  onClosed,
}: DraftPaneProps): JSX.Element {
  const client = useQueryClient();
  const summary: StandardVersionSummaryOut | null = standard.draft_version;
  const versionQuery = useQuery({
    ...standardVersionOptions({
      path: { standard_id: standard.id, version_id: summary?.id ?? "" },
    }),
    enabled: summary !== null,
  });
  const draft = versionQuery.data;
  const [payload, setPayload] = useState<Payload | undefined>(undefined);
  const [effective, setEffective] = useState<string>(
    summary?.effective_from ?? new Date(now + 86_400_000).toISOString().slice(0, 10),
  );
  const [changeSummary, setChangeSummary] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [stepUp, setStepUp] = useState(false);
  const [stale, setStale] = useState<string | null>(null);
  useEffect(() => {
    if (draft !== undefined) setPayload(draft.payload);
  }, [draft]);

  const refresh = (): void => {
    void client.invalidateQueries({
      queryKey: standardOptions({ path: { standard_id: standard.id } }).queryKey,
    });
    void client.invalidateQueries({ predicate: (q) => q.queryKey[0] !== undefined });
  };
  const edit = useMutation({
    ...editDraftMutation(),
    onError: (error) => {
      if (isStatus(error, "stale_version")) setStale(draft?.drafted_by.name ?? "");
    },
    onSuccess: refresh,
  });
  const publish = useMutation({
    ...publishVersionMutation(),
    onError: (error) => {
      if (isStatus(error, "forbidden")) setStepUp(true);
      else if (isStatus(error, "stale_version")) setStale(draft?.drafted_by.name ?? "");
    },
    onSuccess: () => {
      refresh();
      onClosed();
    },
  });
  const discard = useMutation({
    ...standardDiscardDraftMutation(),
    onSuccess: () => {
      refresh();
      onClosed();
    },
  });

  if (summary === null) return <span />;
  if (versionQuery.isError) {
    return (
      <ErrorState
        title={COPY.error}
        retryLabel={COPY.retry}
        onRetry={() => {
          void versionQuery.refetch();
        }}
      />
    );
  }
  if (draft === undefined || payload === undefined) {
    return <Skeleton className="h-[220px]" />;
  }
  const from = current?.version ?? draft.version - 1;
  const changes = changeCount(current?.payload, payload);
  const canPublish = standard.allowed_actions.includes("firm_standard.publish");
  const canImport = standard.allowed_actions.includes("firm_standard.import");
  const dirty = JSON.stringify(payload) !== JSON.stringify(draft.payload);
  const save = (): void => {
    edit.mutate({
      path: { standard_id: standard.id, version_id: draft.id },
      headers: { "If-Match": draft.row_version },
      body: { payload, change_summary: changeSummary === "" ? null : changeSummary },
    });
  };
  const exportHref = `/v1/standards/${standard.id}/versions/${draft.id}/export.xlsx`;

  return (
    <div data-draft="" className="flex flex-col gap-[12px]">
      {stale !== null && (
        <div
          role="alert"
          className="flex items-center justify-between rounded-sheet bg-red-tint px-[12px] py-[8px] text-body text-red-ink"
        >
          <span>{COPY.draft.stale(stale)}</span>
          <Button
            variant="secondary"
            onClick={() => {
              setStale(null);
              setPayload(undefined);
              void versionQuery.refetch();
            }}
          >
            {COPY.draft.reload}
          </Button>
        </div>
      )}
      <Fieldset
        flush
        title={title.replace("{v}", String(draft.version))}
        action={<span className="text-meta text-ink-3">{COPY.draft.changes(changes, from)}</span>}
      >
        <Editor
          payload={payload}
          prior={current?.payload}
          onChange={(next) => {
            setPayload(next);
          }}
        />
        <ValueRow
          kind="text"
          label={COPY.draft.summary}
          placeholder={COPY.draft.summaryPlaceholder}
          value={changeSummary}
          onChange={setChangeSummary}
        />
      </Fieldset>
      <div
        data-save-bar=""
        className="sticky bottom-0 flex items-center justify-between gap-[12px] border-t-[0.5px] border-hair bg-card px-[12px] py-[10px]"
      >
        <span className="text-meta text-ink-2">
          {COPY.draft.bar(draft.version, changes, from)}
        </span>
        <span className="flex items-center gap-[8px]">
          {canImport && (
            <a className="text-body font-medium text-ink" href={exportHref} download>
              {COPY.draft.exportLabel}
            </a>
          )}
          <label className="flex items-center gap-[6px] text-body text-ink-2">
            {COPY.draft.effective}
            <input
              type="date"
              aria-label={COPY.draft.effective}
              className="h-[28px] rounded-full bg-nav-fill px-[10px] text-body text-ink"
              value={effective}
              min={new Date(now).toISOString().slice(0, 10)}
              onChange={(e) => {
                setEffective(e.target.value);
              }}
            />
          </label>
          {dirty && (
            <Button variant="secondary" onClick={save} disabled={edit.isPending}>
              {COPY.draft.save}
            </Button>
          )}
          <Button
            variant="secondary"
            onClick={() => {
              discard.mutate({
                path: { standard_id: standard.id, version_id: draft.id },
                headers: { "If-Match": draft.row_version },
              });
            }}
          >
            {COPY.draft.discard}
          </Button>
          {canPublish && (
            <Button
              disabled={dirty || changeSummary.trim() === ""}
              onClick={() => {
                setConfirm(true);
              }}
            >
              {COPY.draft.publish(draft.version)}
            </Button>
          )}
        </span>
      </div>
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title={COPY.draft.publishTitle(draft.version)}
        confirmLabel={COPY.draft.publishConfirm}
        destructive={false}
        initialFocus="confirm"
        onConfirm={() => {
          publish.mutate({
            path: { standard_id: standard.id, version_id: draft.id },
            headers: { "If-Match": draft.row_version },
            body: { effective_from: effective, change_summary: changeSummary },
          });
        }}
      >
        {COPY.draft.publishBody(
          draft.version,
          date(`${effective}T12:00:00Z`, { now, withYear: true }),
        )}
      </ConfirmDialog>
      <Dialog
        open={stepUp}
        onOpenChange={setStepUp}
        title={COPY.draft.stepUpTitle}
        description={COPY.draft.stepUpBody}
      >
        <div className="flex justify-end gap-2">
          <Button
            variant="secondary"
            onClick={() => {
              setStepUp(false);
            }}
          >
            {COPY.draft.cancel}
          </Button>
          <Button
            onClick={() => {
              signIn(currentRoute(), { forceLogin: true });
            }}
          >
            {COPY.draft.signInAgain}
          </Button>
        </div>
      </Dialog>
    </div>
  );
}

/** New version…: the owner's draft from the version in effect (one draft at a time). */
export function useNewVersion(standardId: string | undefined): {
  start: () => void;
  pending: boolean;
} {
  const client = useQueryClient();
  const create = useMutation({
    ...draftVersionMutation(),
    onSuccess: () => {
      void client.invalidateQueries();
    },
  });
  return {
    start: () => {
      if (standardId !== undefined) create.mutate({ path: { standard_id: standardId } });
    },
    pending: create.isPending,
  };
}

export const DRAFT_PILL = (v: number): JSX.Element => (
  <Pill variant="neutral">{COPY.draft.pill(v)}</Pill>
);
