// TAX-14 · Firm standards run (T-08-T31; TASK-9032; DEC-6037) on T1 at `/tax-returns/standards`,
// behind `tax.standards_runs`: one versioned firm checklist over the returns a person selects.
// The run, its tiles, each row's people, status, progress and issue links, and each check's words
// are the server's (T-08-T14's run read with T-08-T31's row facts); the browser formats and never
// adds. While a run runs the read refreshes every 2 s; when it completes a toast names the counts.
// A row expands to its checks; a check opens the return's TXP-10 (C-17 opens TXP-07's capital
// sheet). "Run on selection" re-runs only the checked rows (a person's act); "Open exceptions"
// opens HOME-02. The standard chip lists the versions and links to Knowledge › Standards.
import type { TaxPracticeRunItemOut, TaxPracticeRunOut } from "@abacus/api-client";
import {
  officesOptions,
  standardsRunChecksOptions,
  standardsRunRerunMutation,
  standardsRunsOptions,
} from "@abacus/api-client/query";
import {
  Button,
  EmptyState,
  Icon,
  Menu,
  Pill,
  RegistryStatus,
  SkeletonRows,
  time,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { type JSX, useEffect, useMemo, useRef, useState } from "react";
import { to } from "../../routes/to";
import { COPY as C } from "./copy";

export interface TAX14Props {
  /** As an artboard opens: the standard picker open (D). */
  initialPicker?: boolean;
  /** As an artboard opens: nothing selected (E). */
  selectNone?: boolean;
  /** The picker's other versions (the Knowledge list in live mode). */
  versions?: readonly { label: string; state: string }[];
}

function idempotency(): { "Idempotency-Key": string } {
  return { "Idempotency-Key": `tax14-${crypto.randomUUID()}` };
}

function Disc({ status }: { status: TaxPracticeRunItemOut["status"] }): JSX.Element {
  if (status === "running") {
    return (
      <Icon
        name="rotate-cw"
        size={16}
        className="animate-spin text-ink-3"
        label={C.status.running}
      />
    );
  }
  if (status === "passed") {
    return <Icon name="circle-check" size={16} className="text-green" label={C.status.passed} />;
  }
  if (status === "exceptions" || status === "failed") {
    return <Icon name="circle-x" size={16} className="text-red-ink" label={C.status.exceptions} />;
  }
  return <Icon name="circle" size={16} className="text-ink-4" label={C.status.queued} />;
}

function Result({ item }: { item: TaxPracticeRunItemOut }): JSX.Element {
  if (item.status === "running") return <span className="text-ink-3">{C.running}</span>;
  if (item.status === "passed") return <Pill variant="green">{C.passed}</Pill>;
  if (item.status === "exceptions")
    return <Pill variant="red">{C.exceptions(item.exceptions)}</Pill>;
  if (item.status === "failed") return <Pill variant="red">{C.failed}</Pill>;
  return <Pill variant="neutral">{C.queued}</Pill>;
}

function Checks({ runId, item }: { runId: string; item: TaxPracticeRunItemOut }): JSX.Element {
  const navigate = useNavigate();
  const q = useQuery(
    standardsRunChecksOptions({ path: { run_id: runId, work_item_id: item.work_item_id } }),
  );
  const items = q.data?.items ?? [];
  return (
    <div data-tax14="checks" className="bg-nested px-[14px] py-[10px]">
      <ul className="grid grid-cols-2 gap-x-[16px]">
        {items.map((c) => (
          <li key={c.result_id} className="flex min-h-[30px] items-center gap-[8px] text-[12.5px]">
            <Icon
              name={c.outcome === "exception" ? "circle-x" : "circle-check"}
              size={15}
              className={c.outcome === "exception" ? "text-red-ink" : "text-green"}
            />
            <button
              type="button"
              data-check={c.display_code}
              className="text-left hover:underline"
              onClick={() => {
                // C-17 is the capital rollforward's tie: TXP-07; every other check: TXP-10.
                if (c.display_code === "C-17") {
                  void navigate(to.TXP07({ returnId: item.work_item_id, section: "capital" }));
                } else {
                  void navigate(to.TXP10({ returnId: item.work_item_id }));
                }
              }}
            >
              {`${c.display_code} ${c.title}`}
            </button>
            {c.linked_issue_id ? <span className="text-ink-3">{C.linkedCheck}</span> : null}
          </li>
        ))}
      </ul>
      <p className="pt-[6px] text-[11.5px] text-ink-3">{C.linkedNote}</p>
    </div>
  );
}

export function TAX14({
  initialPicker = false,
  selectNone = false,
  versions = [],
}: TAX14Props): JSX.Element {
  const navigate = useNavigate();
  const runs = useQuery({
    ...standardsRunsOptions({ query: { form: "1065" } }),
    refetchInterval: (query) => (query.state.data?.items[0]?.status === "running" ? 2_000 : false),
  });
  const offices = useQuery(officesOptions());
  const run: TaxPracticeRunOut | undefined = runs.data?.items[0];
  const [selected, setSelected] = useState<ReadonlySet<string> | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [picker, setPicker] = useState(initialPicker);
  const anchor = useRef<number | null>(null);
  const previous = useRef<string | undefined>(undefined);
  const rerun = useMutation({
    ...standardsRunRerunMutation(),
    onSuccess: () => void runs.refetch(),
    onError: () => {
      toast.show({ kind: "error", text: C.rerunFailed });
    },
  });
  useEffect(() => {
    if (run === undefined) return;
    if (previous.current === "running" && run.status === "complete") {
      toast.show({ kind: "info", text: C.complete(run.tiles.passed, run.tiles.exceptions) });
    }
    previous.current = run.status;
  }, [run]);
  const items = useMemo(() => run?.items ?? [], [run]);
  const chosen: ReadonlySet<string> =
    selected ?? (selectNone ? new Set() : new Set(items.map((i) => i.work_item_id)));
  const shown = items.filter((i) =>
    search.trim() === ""
      ? true
      : i.client_name.toLowerCase().includes(search.trim().toLowerCase()),
  );
  const officeName = (id: string | null | undefined) =>
    offices.data?.find((o) => o.id === id)?.name ?? "—";

  if (runs.isError) {
    return (
      <div
        data-screen="TAX-14"
        role="alert"
        className="flex flex-col items-start gap-[8px] p-[24px]"
      >
        <p className="text-[13px]">{C.loadFailed}</p>
        <Button variant="secondary" size="sm" onClick={() => void runs.refetch()}>
          {C.retry}
        </Button>
      </div>
    );
  }
  if (run === undefined) {
    return (
      <div data-screen="TAX-14" aria-busy="true" className="p-[12px]">
        <SkeletonRows type="table" label={C.loading} />
      </div>
    );
  }
  const toggle = (id: string, index: number, shift: boolean): void => {
    const next = new Set(chosen);
    if (shift && anchor.current !== null) {
      const [from, until] = [Math.min(anchor.current, index), Math.max(anchor.current, index)];
      const on = !chosen.has(id);
      for (const i of shown.slice(from, until + 1)) {
        if (on) next.add(i.work_item_id);
        else next.delete(i.work_item_id);
      }
    } else if (next.has(id)) next.delete(id);
    else next.add(id);
    anchor.current = index;
    setSelected(next);
  };
  const all = shown.length > 0 && shown.every((i) => chosen.has(i.work_item_id));
  const state =
    run.status === "complete" && run.completed_at
      ? C.completeAt(time(run.completed_at))
      : C.runState[run.status];
  return (
    <div data-screen="TAX-14" className="flex min-h-0 flex-1 flex-col">
      <div className="relative flex h-[46px] flex-none items-center px-[12px]">
        <button
          type="button"
          className="z-10 flex h-[29px] items-center gap-[4px] rounded-full bg-card px-[10px] text-[13px] shadow-e1"
          onClick={() => void navigate(to.TAX01())}
        >
          <Icon name="chevron-left" size={14} />
          {C.back}
        </button>
        <div className="absolute inset-x-0 flex items-center justify-center gap-[8px]">
          <h1 className="text-[15px] font-medium">{C.title}</h1>
          <Menu
            {...(initialPicker ? { open: picker, onOpenChange: setPicker } : {})}
            label={C.pickerLabel}
            sections={[
              [
                { label: C.current(run.standard_label), onSelect: () => undefined },
                ...versions.map((v) => ({
                  label: C.version(v.label, v.state),
                  onSelect: () => undefined,
                  disabled: true,
                })),
              ],
              [
                {
                  label: C.knowledge,
                  onSelect: () => void navigate(to.KNW04()),
                },
              ],
            ]}
            trigger={
              <button
                type="button"
                data-tax14="standard"
                className="z-10 flex h-[29px] items-center gap-[6px] rounded-full bg-card px-[10px] text-[13px] shadow-e1"
              >
                {C.chip(run.standard_label, run.checks_count ?? run.items[0]?.checks_total ?? 0)}
                <Icon name="chevron-down" size={12} className="text-ink-3" />
              </button>
            }
          />
          <Pill variant={run.status === "complete" ? "green" : "neutral"}>{state}</Pill>
        </div>
        <span className="ml-auto text-[13px] text-ink-3">
          {C.started(time(run.started_at), run.started_by ?? "")}
        </span>
      </div>
      <div className="flex h-[50px] flex-none items-center gap-[8px] px-[12px] text-[13px]">
        <Pill variant="amber">{C.filters.form}</Pill>
        <Pill variant="amber">{C.filters.status}</Pill>
        <Pill variant="neutral">{C.filters.office}</Pill>
        <Pill variant="neutral">{C.filters.reviewer}</Pill>
      </div>
      <div
        className="flex flex-none items-center gap-[8px] px-[12px] pb-[10px]"
        data-tax14="tiles"
      >
        {(
          [
            ["queued", run.tiles.queued],
            ["running", run.tiles.running],
            ["passed", run.tiles.passed],
            ["exceptions", run.tiles.exceptions],
          ] as const
        ).map(([key, n]) => (
          <div
            key={key}
            data-tile={key}
            className="flex h-[52px] min-w-[120px] flex-col justify-center rounded-[10px] bg-card px-[12px] shadow-e1"
          >
            <span className="text-[11.5px] text-ink-3">{C.tiles[key]}</span>
            <span className="text-[18px] tabular-nums">{n}</span>
          </div>
        ))}
        <span className="ml-auto text-[12.5px] text-ink-3">
          {C.summary(chosen.size, run.items.length)}
        </span>
      </div>
      <section
        aria-label={C.pane(items.length)}
        className="mx-[12px] mb-[12px] flex min-h-0 flex-1 flex-col overflow-hidden rounded-[12px] bg-card shadow-e1"
      >
        <div className="relative flex h-[46px] flex-none items-center gap-[8px] px-[12px] hairline-b">
          <input
            type="search"
            aria-label={C.search}
            placeholder={C.search}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
            }}
            className="h-[28px] w-[220px] rounded-pill bg-nested px-[10px] text-[13px] outline-none"
          />
          <span className="absolute inset-x-0 text-center text-[14px] font-medium pointer-events-none">
            {C.pane(items.length)}
          </span>
          <span className="ml-auto flex gap-[8px]">
            <Button variant="secondary" size="sm" onClick={() => void navigate(to.HOME02())}>
              {C.openExceptions}
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon="play"
              disabled={chosen.size === 0 || rerun.isPending || run.status === "running"}
              onClick={() => {
                rerun.mutate({
                  path: { run_id: run.run_id },
                  body: { return_ids: [...chosen] },
                  headers: idempotency(),
                });
              }}
            >
              {C.runSelection}
            </Button>
          </span>
        </div>
        {chosen.size === 0 && items.length > 0 && selectNone && selected === null ? (
          <EmptyState icon="list-checks" title={C.emptySelection}>
            {C.emptyBody}
          </EmptyState>
        ) : null}
        <div className="min-h-0 flex-1 overflow-auto">
          <table aria-label={C.pane(items.length)} className="w-full border-collapse text-[13px]">
            <thead>
              <tr className="hairline-b text-[12px] text-ink-3">
                <th className="h-[30px] w-[36px] px-[10px] text-left font-normal">
                  <input
                    type="checkbox"
                    aria-label={C.selectAll}
                    checked={all}
                    onChange={(e) => {
                      setSelected(
                        e.target.checked ? new Set(shown.map((i) => i.work_item_id)) : new Set(),
                      );
                    }}
                  />
                </th>
                {C.columns.map((h) => (
                  <th key={h} className="h-[30px] px-[10px] text-left font-normal">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {shown.map((i, index) => (
                <Row
                  key={i.work_item_id}
                  runId={run.run_id}
                  item={i}
                  office={officeName(i.office_id)}
                  checked={chosen.has(i.work_item_id)}
                  expanded={open === i.work_item_id}
                  onToggle={(shift) => {
                    toggle(i.work_item_id, index, shift);
                  }}
                  onExpand={() => {
                    setOpen(open === i.work_item_id ? null : i.work_item_id);
                  }}
                />
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function Row({
  runId,
  item,
  office,
  checked,
  expanded,
  onToggle,
  onExpand,
}: {
  runId: string;
  item: TaxPracticeRunItemOut;
  office: string;
  checked: boolean;
  expanded: boolean;
  onToggle: (shift: boolean) => void;
  onExpand: () => void;
}): JSX.Element {
  const navigate = useNavigate();
  const issues =
    item.linked_issues > 0
      ? C.linked(item.linked_issues)
      : item.created_issues > 0
        ? C.created(item.created_issues)
        : null;
  return (
    <>
      <tr data-row={item.client_name} className="hairline-b">
        <td className="h-[44px] px-[10px]">
          <input
            type="checkbox"
            aria-label={C.select(item.client_name)}
            checked={checked}
            onClick={(e) => {
              e.preventDefault();
              onToggle(e.shiftKey);
            }}
            onChange={() => undefined}
          />
        </td>
        <td className="px-[10px]">
          <Disc status={item.status} />
        </td>
        <td className="px-[10px]">
          <button
            type="button"
            className="flex flex-col text-left"
            aria-expanded={expanded}
            onClick={onExpand}
          >
            <span className="font-medium">{item.client_name}</span>
            <span className="text-[11.5px] text-ink-3">{C.form}</span>
          </button>
        </td>
        <td className="px-[10px]">{office}</td>
        <td className="px-[10px]">{`${item.preparer?.initials ?? "—"} / ${item.reviewer?.initials ?? "—"}`}</td>
        <td className="px-[10px]">
          {item.return_status ? (
            <RegistryStatus
              object="return"
              code={item.return_status as never}
              {...(item.review_level
                ? {
                    vars: {
                      level:
                        item.review_level.charAt(0).toUpperCase() + item.review_level.slice(1),
                    },
                  }
                : {})}
            />
          ) : (
            "—"
          )}
        </td>
        <td className="px-[10px]">
          <Result item={item} />
        </td>
        <td className="px-[10px] tabular-nums" data-progress={item.checks_passed}>
          {C.checks(item.checks_passed, item.checks_total)}
        </td>
        <td className="px-[10px]">
          {issues === null ? (
            "—"
          ) : (
            <button
              type="button"
              className="hover:underline"
              onClick={() => void navigate(to.TXP10({ returnId: item.work_item_id }))}
            >
              {issues} <span className="text-ink-3">→</span>
            </button>
          )}
        </td>
        <td className="px-[10px] text-ink-3">
          {item.status === "running" ? C.now : item.completed_at ? time(item.completed_at) : "—"}
        </td>
      </tr>
      {expanded ? (
        <tr>
          <td colSpan={10} className="p-0">
            <Checks runId={runId} item={item} />
          </td>
        </tr>
      ) : null}
    </>
  );
}
