import type { DiffRowOut, VersionStateOut } from "@abacus/api-client";
import {
  methodologyVersionActivityOptions,
  methodologyVersionDiffOptions,
  standardsMappingMutation,
  versionStateQueryKey,
} from "@abacus/api-client/query";
import {
  Button,
  DEFAULT_TZ,
  Menu,
  Pill,
  Skeleton,
  Toggle,
  cn,
  date,
  time,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { JSX } from "react";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { COPY } from "./copy";

// KNW-02 c, d and the Activity tab (K-01-T19; K-01 §3.6 AC6.1 to AC6.4; the handoff's KNW-02 c and
// d), on K-01-T18's reads. Every count and every row is the server's code-computed diff; the
// screen draws it: the four tiles (Added green, Changed amber, Removed red, Unchanged white), the
// rows with their tag, "<program> · step <n>" and the text, a changed step's v2 text struck in
// ink-3 over its new text in green ink with a 2 px olive rule. Standards mapping shows the set,
// the QM reference, the engagement types and the default toggle (the person's write, at the row
// version seen); the Change pickers wait for the platform's standards list (planned). Activity
// lists each version event with its named actor and time.

const short = (code: string): string => code.replace(/^BH-[A-Z]+-/u, "");

const TILE: Readonly<Record<"added" | "changed" | "removed" | "unchanged", string>> = {
  added: "bg-green-tint text-green-ink",
  changed: "bg-amber-tint text-amber-ink",
  removed: "bg-red-tint text-red-ink",
  unchanged: "bg-card text-ink-2 shadow-e1",
};

const TAG: Readonly<Record<DiffRowOut["kind"], "green-tint" | "amber" | "red-tint">> = {
  added: "green-tint",
  changed: "amber",
  removed: "red-tint",
};

export function DiffView({
  versionId,
  against,
  label,
  againstLabel,
}: {
  versionId: string;
  against: string | undefined;
  label: string;
  againstLabel: string;
}): JSX.Element {
  const diff = useQuery({
    ...methodologyVersionDiffOptions({
      path: { version_id: versionId },
      ...(against === undefined ? {} : { query: { against } }),
    }),
    retry: false,
  });
  if (diff.isError) return <p className="p-[14px] text-dense text-ink-3">{COPY.diff.failed}</p>;
  const d = diff.data;
  if (d === undefined) return <Skeleton />;
  const t = d.tiles;
  const tiles = [
    ["added", COPY.diff.added, t.added],
    ["changed", COPY.diff.changed, t.changed],
    ["removed", COPY.diff.removed, t.removed],
    ["unchanged", COPY.diff.unchanged, t.unchanged],
  ] as const;
  return (
    <div data-knw02="diff" className="flex flex-col">
      <div className="flex items-center gap-[10px] px-[18px] py-[16px] hairline-b">
        {tiles.map(([key, word, n]) => (
          <div
            key={key}
            data-tile={key}
            className={cn(
              "flex h-[100px] w-[168px] flex-col justify-between rounded-nested p-[14px]",
              TILE[key],
            )}
          >
            <span className="text-kpi-label uppercase">{word}</span>
            <span className="text-dashboard tabular-nums">{n}</span>
          </div>
        ))}
        <span className="ml-auto text-meta text-ink-3">
          {COPY.diff.totals(
            label,
            t.added + t.changed + t.unchanged,
            d.against_label ?? againstLabel,
            t.removed + t.changed + t.unchanged,
          )}
        </span>
      </div>
      {d.rows.length === 0 ? (
        <p className="p-[14px] text-dense text-ink-3">{COPY.diff.none}</p>
      ) : (
        <ul aria-label={COPY.diff.title(d.against_label ?? againstLabel)}>
          {d.rows.map((r) => (
            <li
              key={`${r.kind}:${r.step_key}`}
              data-diff={r.kind}
              className="flex min-h-[62px] items-center gap-[16px] px-[18px] py-[10px] hairline-b"
            >
              <Pill variant={TAG[r.kind]} size="sm" className="w-[70px] justify-center">
                {COPY.diff.kind[r.kind] ?? r.kind}
              </Pill>
              <span className="w-[120px] flex-none text-body text-ink-3">
                {COPY.diff.where(short(r.program_code), r.number)}
              </span>
              {r.kind === "changed" ? (
                <span className="flex min-w-0 flex-1 flex-col gap-[4px]">
                  <del className="text-dense text-ink-3">{r.before_text}</del>
                  <ins className="border-l-2 border-green pl-[12px] text-body text-green-ink no-underline">
                    {r.after_text}
                  </ins>
                </span>
              ) : (
                <span
                  className={cn(
                    "min-w-0 flex-1 text-body",
                    r.kind === "removed" && "text-ink-3 line-through",
                  )}
                >
                  {r.after_text ?? r.before_text}
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function StandardsView({
  state,
  family,
  priorLabel,
}: {
  state: VersionStateOut;
  family: string;
  priorLabel: string;
}): JSX.Element {
  const queryClient = useQueryClient();
  const save = useMutation({
    ...standardsMappingMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: versionStateQueryKey({ path: { version_id: state.version_id } }),
      });
    },
    onError: () => {
      toast.show({ kind: "error", text: COPY.standards.failed });
    },
  });
  const editable =
    state.allowed_actions.includes("manage") &&
    (state.status === "draft" || state.status === "needs_review");
  const types = state.engagement_types.map((t) => COPY.standards.typeWords[t] ?? t).join(" · ");
  const rows: readonly (readonly [string, string])[] = [
    [COPY.standards.set, state.standards_set_label ?? COPY.standards.none],
    [COPY.standards.quality, state.quality_management_ref ?? COPY.standards.none],
    [COPY.standards.types, types === "" ? COPY.standards.none : types],
  ];
  const change = PLANNED_VISIBLE ? (
    // The pickers wait for the platform standards list (planned).
    <Button variant="ghost" size="sm" iconAfter="chevrons-up-down" disabled>
      {COPY.standards.change}
    </Button>
  ) : null;
  return (
    <div data-knw02="standards" className="flex justify-center px-[18px] py-[24px]">
      <dl className="flex w-full max-w-[1000px] flex-col">
        {rows.map(([key, value]) => (
          <div key={key} className="flex min-h-[61px] items-center gap-[16px] hairline-b">
            <dt className="w-[290px] flex-none text-body text-ink-2">{key}</dt>
            <dd className="flex-1 text-body">{value}</dd>
            {change}
          </div>
        ))}
        <div className="flex min-h-[61px] items-center gap-[16px] hairline-b">
          <dt className="w-[290px] flex-none text-body text-ink-2">
            {COPY.standards.default(family)}
          </dt>
          <dd className="flex-1 text-body">
            {state.default_for_new_engagements
              ? COPY.standards.defaultOn(family, state.label)
              : COPY.standards.defaultOff}
          </dd>
          <Toggle
            label={COPY.standards.default(family)}
            checked={state.default_for_new_engagements}
            disabled={!editable || save.isPending}
            onChange={(on) => {
              save.mutate({
                path: { version_id: state.version_id },
                body: {
                  standards_set_id: state.standards_set_id,
                  quality_management_ref: state.quality_management_ref ?? null,
                  engagement_types: state.engagement_types,
                  default_for_new_engagements: on,
                  row_version: state.row_version,
                },
              });
            }}
          />
        </div>
        <p className="pt-[12px] text-meta text-ink-3">{COPY.standards.note(family, priorLabel)}</p>
      </dl>
    </div>
  );
}

export function ActivityView({ versionId }: { versionId: string }): JSX.Element {
  const now = useNow();
  const list = useQuery({
    ...methodologyVersionActivityOptions({ path: { version_id: versionId } }),
    retry: false,
  });
  const items = list.data?.items ?? [];
  if (list.data === undefined) return <Skeleton />;
  if (items.length === 0)
    return <p className="p-[14px] text-dense text-ink-3">{COPY.activity.empty}</p>;
  return (
    <ol data-knw02="activity" aria-label={COPY.activity.title}>
      {items.map((e) => (
        <li key={e.seq} className="flex min-h-[44px] items-center gap-[12px] px-[18px] hairline-b">
          <span className="text-body">
            <span className="font-medium">{e.actor_name ?? COPY.activity.system}</span>{" "}
            {COPY.activity.kinds[e.kind] ?? e.kind}
          </span>
          <span className="ml-auto text-meta text-ink-3">
            {date(e.at, { now, tz: DEFAULT_TZ, withYear: true })} {time(e.at, { tz: DEFAULT_TZ })}
          </span>
        </li>
      ))}
    </ol>
  );
}

/** "Compare with v2 ⌄": the template's other versions to diff against. */
export function CompareMenu({
  label,
  versions,
  onPick,
}: {
  label: string;
  versions: readonly { id: string; label: string; current: boolean }[];
  onPick: (versionId: string) => void;
}): JSX.Element {
  return (
    <Menu
      label={COPY.compare(label)}
      align="end"
      sections={[
        versions.map((v) => ({
          label: COPY.compare(v.label),
          checked: v.current,
          onSelect: () => {
            onPick(v.id);
          },
        })),
      ]}
      trigger={
        <Button variant="secondary" size="sm" iconAfter="chevron-down">
          {COPY.compare(label)}
        </Button>
      }
    />
  );
}
