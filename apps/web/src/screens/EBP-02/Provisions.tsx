import type { PlanReviewOut, ProvisionOut } from "@abacus/api-client";
import {
  ebpPlanReviewOptions,
  ebpPlanReviewQueryKey,
  fieldTickMutation,
} from "@abacus/api-client/query";
import {
  type CockpitCanvas,
  Icon,
  PaneAction,
  Pill,
  type ViewState,
  cn,
  date as formatDate,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useFlag } from "../../app-core/flags";
import { COPY } from "./copy";

// EBP-02 · Plan provisions review (A-05-T17; A-05 §3 F2; the handoff spec.md): the cockpit's
// Fieldwork › Plan Review canvas over `GET …/ebp/plan-reviews/current` (A-05-T16). States: a
// (verified), b (agent draft: nothing verified), b2 (`?version=1`: the 18 rows read before the 2024
// amendment, read-only, the "+2 rows" ribbon), c (SPD conflict: the band, Raise exception…, and the
// row opens the SPD in the viewer dock), d (amendment tag), e (signed off).
// Verifying is a C3 field tick (L1) on the provision's value cell, signed over the hash the server
// sent; Sign off… stays disabled until every row is verified (the server answers 409 too). The
// browser computes nothing: counts, conflicts and tags are the server's.

const BLOCK = "overflow-hidden rounded-pane bg-card shadow-e1";
const HEAD = "flex h-[32px] items-center px-[12px] text-section font-medium hairline-b";
const GRID = "grid grid-cols-[1fr_190px_76px_14px] items-center gap-[8px]";

function Row({
  provision,
  now,
  lit,
  readOnly,
  onLight,
  onPin,
  onTick,
  onRaise,
}: {
  provision: ProvisionOut;
  now: Date;
  lit: boolean;
  readOnly: boolean;
  onLight: (key: string | null) => void;
  onPin: (key: string) => void;
  onTick: (p: ProvisionOut) => void;
  onRaise?: (() => void) | undefined;
}): JSX.Element {
  const conflict = provision.conflict ?? null;
  const source = provision.conflict_source ?? null;
  return (
    <>
      {/* biome-ignore lint/a11y/useSemanticElements: a grid row, not a table */}
      <div
        role="group"
        data-provision={provision.key}
        data-verified={provision.verified ? "true" : "false"}
        data-lit={lit ? "true" : "false"}
        className={cn(
          GRID,
          "mx-[5px] h-[30px] rounded-[7px] px-[8px] text-body",
          lit ? "bg-match-mark" : "hover:bg-tonal-hover",
        )}
        onPointerEnter={() => {
          onLight(provision.key);
        }}
        onPointerLeave={() => {
          onLight(null);
        }}
        onClick={() => {
          onPin(provision.key);
        }}
      >
        <span className="flex min-w-0 items-center gap-[6px] truncate">
          {conflict !== null && (
            <Icon name="triangle-alert" size={12} className="text-amber-ink" />
          )}
          <span className="truncate">{provision.label}</span>
          {provision.amended_on != null && (
            <Pill variant="neutral" size="micro">
              {`Amended ${formatDate(provision.amended_on, { now, withYear: true })}`}
            </Pill>
          )}
        </span>
        <span className="flex min-w-0 items-center gap-[6px]" title={provision.value}>
          <span className="truncate">{provision.value}</span>
          {conflict !== null && (
            <Pill variant="amber" size="micro">
              {conflict}
            </Pill>
          )}
        </span>
        <span className="truncate text-ink-3">{provision.reference ?? ""}</span>
        <button
          type="button"
          aria-label={COPY.verify(provision.label)}
          aria-pressed={provision.verified}
          disabled={readOnly || provision.verified || provision.value_hash == null}
          className="flex h-[14px] w-[14px] items-center justify-center"
          onClick={(event) => {
            event.stopPropagation();
            onTick(provision);
          }}
        >
          <Icon
            name={provision.verified ? "check" : "circle-dashed"}
            size={12}
            className={provision.verified ? "text-green" : "text-ink-4"}
          />
        </button>
      </div>
      {source !== null && (
        <div
          data-ebp02="conflict"
          className="mx-[5px] flex items-center gap-[8px] rounded-[7px] bg-amber-tint px-[8px] py-[6px] text-body text-amber-ink"
        >
          <span className="flex-1">{source.note}</span>
          {!readOnly && (
            <PaneAction
              label={COPY.raise}
              {...(onRaise === undefined ? {} : { onClick: onRaise })}
            />
          )}
        </div>
      )}
    </>
  );
}

function initialsOf(review: PlanReviewOut, level: number): string | null {
  const chip = (review.sign_offs ?? []).find((s) => s.level === level && !s.stale);
  return chip === undefined ? null : chip.initials;
}

export function useProvisionsCanvas(
  workItemId: string,
  {
    active,
    version,
    onOpenVersion,
    onDock,
    onSignOff,
    onRaise,
  }: {
    active: boolean;
    version?: number;
    /** The route's `?version=`: null is the current version. */
    onOpenVersion?: (version: number | null) => void;
    /** The viewer dock on a document version (c: the SPD). */
    onDock?: (versionId: string) => void;
    /** SHL-12 on the paper. */
    onSignOff?: (workpaperId: string) => void;
    /** SHL-15, a new issue (c). */
    onRaise?: () => void;
  },
): CockpitCanvas {
  const on = useFlag("ebp.modules") === true;
  const path = {
    path: { work_item_id: workItemId },
    ...(version === undefined ? {} : { query: { version } }),
  };
  const review = useQuery({ ...ebpPlanReviewOptions(path), enabled: active && on });
  const queryClient = useQueryClient();
  const [lit, setLit] = useState<string | null>(null);
  const [pinned, setPinned] = useState<string | null>(null);
  const tick = useMutation({
    ...fieldTickMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ebpPlanReviewQueryKey(path) });
    },
  });

  let state: ViewState = { kind: "ready" };
  if (!on) state = { kind: "flag-off", flag: "ebp.modules" };
  else if (review.isError) {
    const status = (review.error as { status?: number } | null)?.status;
    state =
      status === 404
        ? { kind: "restricted", reason: "walled" }
        : { kind: "error", retry: () => void review.refetch() };
  } else if (review.data === undefined) state = { kind: "loading" };
  else if (review.data.total === 0) state = { kind: "empty" };

  const data = review.data;
  const readOnly = version !== undefined;
  const all = data !== undefined && data.total > 0 && data.verified === data.total;
  const l1 = data === undefined ? null : initialsOf(data, 1);
  const l2 = data === undefined ? undefined : (data.sign_offs ?? []).find((s) => s.level >= 2);
  const now = useNow();
  const shown = lit ?? pinned;
  return {
    title: COPY.title,
    well: true,
    state,
    empty: { title: COPY.empty, body: COPY.emptyBody },
    actions: (
      <>
        {data !== undefined && (
          // The rail has no Version 1 child row yet (DV-EBP-02-5): the pill opens the earlier one.
          <button
            type="button"
            data-ebp02="version"
            disabled={readOnly || data.version_no <= 1}
            aria-label={
              readOnly || data.version_no <= 1
                ? COPY.version(data.version_no)
                : COPY.openVersion(data.version_no - 1)
            }
            onClick={() => {
              onOpenVersion?.(data.version_no - 1);
            }}
          >
            <Pill variant="neutral" size="micro">
              {COPY.version(data.version_no)}
            </Pill>
          </button>
        )}
        {readOnly && (
          <Pill variant="muted" size="micro">
            {COPY.readOnly}
          </Pill>
        )}
        {l1 !== null && (
          <span
            data-chip="l1"
            className="rounded-full bg-green-tint px-[6px] text-micro text-green-ink"
          >
            {`✓ ${l1}`}
          </span>
        )}
        {!readOnly && <PaneAction icon="pencil" label={COPY.edit} />}
        {readOnly ? null : l2 === undefined ? (
          <PaneAction
            label={COPY.signOff}
            disabled={!all}
            {...(all ? {} : { title: COPY.signOffReason })}
            onClick={() => {
              if (data?.workpaper_id != null) onSignOff?.(data.workpaper_id);
            }}
          />
        ) : (
          <span data-reviewed="true" className="text-body text-ink-3">
            {COPY.reviewed(l2.initials, formatDate(l2.at, { now }))}
          </span>
        )}
        <PaneAction icon="file" label={COPY.sourceDocs} />
      </>
    ),
    footer:
      data === undefined ? null : (
        <div className="flex items-center gap-[8px]">
          <PaneAction
            label={COPY.citations(data.provisions.reduce((n, p) => n + p.citation_count, 0))}
          />
          <PaneAction label={COPY.procedures} />
        </div>
      ),
    children:
      data === undefined ? null : (
        <div
          data-screen="EBP-02"
          data-version={String(data.version_no)}
          className="flex flex-col gap-[10px] p-[12px]"
        >
          {readOnly && data.version_diff != null && (
            <div
              data-ebp02="snapshot"
              className="flex items-center gap-[10px] rounded-pane bg-card px-[12px] py-[8px] text-body shadow-e1"
            >
              {data.version_diff.added_labels.length > 0 && (
                <>
                  <Pill variant="green-tint" size="micro">
                    {COPY.diff(data.version_diff.added_labels.length)}
                  </Pill>
                  <span className="min-w-0 flex-1 text-ink-2">
                    {COPY.adds(
                      data.version_diff.current_version_no,
                      data.version_diff.added_labels,
                    )}
                  </span>
                </>
              )}
              <button
                type="button"
                className="ml-auto flex shrink-0 items-center gap-[4px] font-medium"
                onClick={() => {
                  onOpenVersion?.(null);
                }}
              >
                {COPY.openVersion(data.version_diff.current_version_no)}
                <Icon name="arrow-right" size={12} className="text-ink-3" />
              </button>
            </div>
          )}
          <section data-ebp02="provisions" aria-label={COPY.block} className={BLOCK}>
            <h3 className={HEAD}>
              <span className="flex-1">{COPY.block}</span>
              {data.verified === 0 && !readOnly && (
                <Pill variant="neutral" size="micro" className="mr-[8px]">
                  {COPY.agentDraft}
                </Pill>
              )}
              <span data-ebp02="count" className="text-body text-ink-3">
                {COPY.verified(data.verified, data.total)}
              </span>
            </h3>
            {/* biome-ignore lint/a11y/useSemanticElements: the bento rows, not a table */}
            <div role="grid" aria-label={COPY.block} className="py-[4px]">
              <div
                role="group"
                className={cn(
                  GRID,
                  "mx-[5px] h-[26px] px-[8px] text-micro font-medium text-ink-3",
                )}
              >
                <span>{COPY.columns.provision}</span>
                <span>{COPY.columns.election}</span>
                <span>{COPY.columns.reference}</span>
                <span />
              </div>
              {data.provisions.map((p) => (
                <Row
                  key={p.key}
                  provision={p}
                  now={now}
                  lit={shown === p.key}
                  readOnly={readOnly}
                  onLight={setLit}
                  onPin={(key) => {
                    setPinned((was) => (was === key ? null : key));
                    const source = p.conflict_source ?? null;
                    if (source !== null) onDock?.(source.evidence_version_id);
                  }}
                  onRaise={onRaise}
                  onTick={(row) => {
                    if (data.workpaper_id == null || row.cell == null || row.value_hash == null) {
                      return;
                    }
                    tick.mutate({
                      path: {
                        target_type: "workpaper_cell",
                        target_id: data.workpaper_id,
                        field_key: row.cell,
                      },
                      headers: { "Idempotency-Key": crypto.randomUUID() },
                      body: { level: "L1_preparer", seen_hash: row.value_hash },
                    });
                  }}
                />
              ))}
            </div>
          </section>
        </div>
      ),
  };
}
