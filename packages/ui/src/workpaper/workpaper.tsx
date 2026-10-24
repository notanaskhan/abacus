import { type JSX, useEffect, useId, useMemo, useRef, useState } from "react";
import { cn } from "../cn";
import { Button } from "../components/button";
import { Segmented } from "../components/tabs";
import { DataGrid } from "../data/data-grid";
import type { TableRow } from "../data/types";
import {
  type CitationView,
  CitationChip,
  CitationFooter,
  CitationPopoverHost,
  CiteMarker,
  MatchScope,
  matchIdOf,
  useMatchState,
  useMatchStore,
} from "../tracing";
import type { MatchId } from "../tracing/types";
import { ScheduleBar, SectionBand } from "./bands";
import type { WorkpaperKv, WorkpaperSectionData, WorkpaperTab } from "./types";

// The C-02 Workpaper kit (F-05-T50; kit-handoffs/C-02 §1, §3 to §5): an audit workpaper body. A
// section always reads SectionBand → caption → key/value rows → ScheduleBar → evidence table →
// after-rows, and sections sit 16 apart. Every claim can carry numbered CiteMarkers (C-07) whose
// citations light their exact cell through E1; a citation in a collapsed section expands it first
// and reveals the cell 380ms later, about 96px from the top of the body. Collapsing a section
// closes a citation inside it, and switching tabs closes any. The pinned footer holds the
// "Citations (n)" and "Procedures (n)" chips. Workpaper words are the server's; the kit computes
// nothing (ADR-050).

/** After a section has to expand for a citation, the cell is revealed this much later. */
export const REVEAL_AFTER_EXPAND_MS = 380;
/** Where the revealed cell sits from the top of the body. */
const REVEAL_TOP = 96;

/** The match id of a workpaper table cell, from its typed locator (INV-2). */
export function workpaperCell(sheet: string, row: string, column: string): MatchId {
  return matchIdOf({ kind: "workpaper_cell", sheet_id: sheet, row_key: row, column_key: column });
}

/** The section that holds a match: the one whose table draws a cell with that id. */
function sectionOf(
  sheet: string,
  sections: readonly WorkpaperSectionData[],
  id: MatchId | null,
): string | undefined {
  if (id === null) return undefined;
  return sections.find((s) =>
    s.table?.rows.some((r) =>
      s.table?.columns.some((c) => workpaperCell(sheet, r.id, c.key) === id),
    ),
  )?.id;
}

// ---- Key/value rows -----------------------------------------------------------------------------

function KvRows({
  rows,
  citations,
  ruleTop = false,
}: {
  rows: readonly WorkpaperKv[];
  citations: readonly CitationView[];
  ruleTop?: boolean;
}): JSX.Element {
  return (
    <dl data-workpaper="kv" className="flex flex-col">
      {rows.map((row, i) => (
        <div
          key={row.key}
          className={cn(
            "flex gap-[16px] px-[14px] py-[10px] text-meta leading-[1.5] hairline-b",
            ruleTop && i === 0 && "hairline-t",
          )}
        >
          <dt className="w-[118px] flex-none font-medium">{row.key}</dt>
          <dd className="min-w-0 flex-1 text-pretty">
            {row.text}
            {(row.cites ?? []).map((n) => {
              const cite = citations.find((c) => c.n === n);
              return cite === undefined ? null : (
                <CiteMarker key={n} cite={cite} list={citations} />
              );
            })}
          </dd>
        </div>
      ))}
    </dl>
  );
}

// ---- WorkpaperSection ---------------------------------------------------------------------------

export interface WorkpaperSectionProps {
  section: WorkpaperSectionData;
  /** The sheet its table cells belong to (their locators' `sheet_id`). */
  sheet: string;
  /** The tab's citations: what its markers open and step through. */
  citations?: readonly CitationView[];
  /** Controlled; uncontrolled from `section.collapsed`. */
  collapsed?: boolean;
  onToggle?: (open: boolean) => void;
}

/** One numbered section of a workpaper. */
export function WorkpaperSection({
  section,
  sheet,
  citations = [],
  collapsed,
  onToggle,
}: WorkpaperSectionProps): JSX.Element {
  const bodyId = useId();
  const [own, setOwn] = useState(section.collapsed === true);
  const closed = section.collapsible === false ? false : (collapsed ?? own);
  const hasKv = (section.rows ?? []).length > 0;
  const table = section.table;
  return (
    <section
      data-workpaper="section"
      data-section={section.id}
      aria-label={section.title}
      className="flex flex-col"
    >
      <SectionBand
        {...(section.n === undefined ? {} : { number: section.n })}
        title={section.title}
        {...(section.label === undefined ? {} : { label: section.label })}
        {...(section.sign === undefined ? {} : { sign: section.sign })}
        collapsible={section.collapsible !== false}
        collapsed={closed}
        controls={bodyId}
        onToggle={(open) => {
          setOwn(!open);
          onToggle?.(open);
        }}
      />
      {/* The content collapses over 340ms (grid rows 1fr ↔ 0fr, as the C-03 rail does); a
          collapsed body is inert, so its markers leave the tab order. */}
      <div
        id={bodyId}
        data-workpaper="body"
        {...(closed ? { inert: true, "data-collapsed": "" } : {})}
        className={cn(
          "grid transition-[grid-template-rows] duration-[340ms] ease-out",
          closed ? "grid-rows-[0fr]" : "grid-rows-[1fr]",
        )}
      >
        <div className="min-h-0 overflow-hidden">
          {section.caption !== undefined && (
            <p
              data-workpaper="caption"
              className="px-[14px] pt-[9px] pb-[10px] text-meta leading-[1.45] text-pretty text-ink-2 italic hairline-b"
            >
              {section.caption}
            </p>
          )}
          {hasKv && <KvRows rows={section.rows ?? []} citations={citations} />}
          {section.schedule !== undefined && <ScheduleBar title={section.schedule} />}
          {table !== undefined && (
            <DataGrid
              label={section.schedule ?? section.title}
              grammar="evidence"
              pad={14}
              columns={table.columns}
              rows={table.rows}
              cellMatch={(row: TableRow, key: string) => workpaperCell(sheet, row.id, key)}
              // The table drops its top rule after a key/value row or the schedule bar.
              className={cn((hasKv || section.schedule !== undefined) && "[&_th]:border-t-0")}
            />
          )}
          {(section.after ?? []).length > 0 && (
            <KvRows
              rows={section.after ?? []}
              citations={citations}
              ruleTop={table !== undefined}
            />
          )}
        </div>
      </div>
    </section>
  );
}

// ---- WorkpaperPane ------------------------------------------------------------------------------

export interface WorkpaperPaneProps {
  /** The centred title (chrome only): "Service Organizations & SOC 1". */
  title?: string;
  tabs: readonly WorkpaperTab[];
  /** Controlled active tab label; uncontrolled from the first tab. */
  active?: string;
  /** px; default 760 with chrome, the host's height without. */
  height?: number;
  /** False: no title row, tab row, radius or shadow, for a host pane that draws its own header
   * and drives `active` (the T2 canvas). */
  chrome?: boolean;
  /** False: the pane joins the page's match scope and popover host instead of its own. */
  scoped?: boolean;
  onTab?: (label: string) => void;
  onToggle?: (sectionId: string, open: boolean) => void;
  onDownload?: () => void;
  onOpenInExcel?: () => void;
  /** The popover's open button: the CitationDialog (SHL-07). */
  onOpenCitation?: (cite: CitationView) => void;
  className?: string;
}

/** The workpaper: tabs, the scrolling sections and the pinned citation footer. */
export function WorkpaperPane({ scoped = true, ...props }: WorkpaperPaneProps): JSX.Element {
  if (!scoped) return <Pane {...props} />;
  return (
    <MatchScope>
      <Pane {...props} />
      <CitationPopoverHost
        {...(props.onOpenCitation === undefined ? {} : { onOpenDialog: props.onOpenCitation })}
      />
    </MatchScope>
  );
}

function Pane({
  title,
  tabs,
  active,
  height,
  chrome = true,
  onTab,
  onToggle,
  onDownload,
  onOpenInExcel,
  className,
}: Omit<WorkpaperPaneProps, "scoped">): JSX.Element {
  const store = useMatchStore();
  const match = useMatchState();
  const body = useRef<HTMLDivElement>(null);
  const [ownTab, setOwnTab] = useState(tabs[0]?.label ?? "");
  const label = active ?? ownTab;
  const tab = tabs.find((t) => t.label === label) ?? tabs[0];
  const sections = useMemo(() => tab?.sections ?? [], [tab]);
  const sheet = tab?.sheet ?? "";
  const [collapsed, setCollapsed] = useState<Readonly<Record<string, boolean>>>(() =>
    Object.fromEntries(
      tabs.flatMap((t) => t.sections.map((s) => [`${t.label}/${s.id}`, s.collapsed === true])),
    ),
  );
  const isCollapsed = (id: string): boolean => collapsed[`${label}/${id}`] === true;

  // A citation lands in a collapsed section: expand it, then reveal the cell 380ms later.
  const lit = match.id;
  useEffect(() => {
    const target = sectionOf(sheet, sections, lit);
    if (lit === null || target === undefined) return;
    if (collapsed[`${label}/${target}`] !== true) return;
    setCollapsed((c) => ({ ...c, [`${label}/${target}`]: false }));
    const timer = setTimeout(() => {
      const root = body.current;
      if (root === null) return;
      const cell = root.querySelector<HTMLElement>(
        `[data-match="${lit.replaceAll("\\", "\\\\").replaceAll('"', '\\"')}"]`,
      );
      if (cell === null) return;
      const top = cell.getBoundingClientRect().top - root.getBoundingClientRect().top;
      if (top < 0 || top > root.clientHeight - cell.offsetHeight) {
        root.scrollTop += top - REVEAL_TOP;
      }
    }, REVEAL_AFTER_EXPAND_MS);
    return () => {
      clearTimeout(timer);
    };
  }, [lit, sheet, sections, label, collapsed]);

  const toggle = (id: string, open: boolean): void => {
    setCollapsed((c) => ({ ...c, [`${label}/${id}`]: !open }));
    // Collapsing a section closes the citation that lights inside it.
    if (!open && sectionOf(sheet, sections, store.get().id) === id) store.clear();
    onToggle?.(id, open);
  };

  const switchTab = (next: string): void => {
    store.clear();
    setOwnTab(next);
    onTab?.(next);
  };

  const citations = tab?.citations ?? [];
  const procedures = tab?.procedures ?? [];
  const fixed = height ?? (chrome ? 760 : undefined);
  return (
    <div
      data-workpaper="pane"
      data-chrome={chrome ? "" : undefined}
      className={cn(
        "relative flex min-h-0 flex-col overflow-hidden bg-card",
        chrome ? "rounded-pane shadow-e2" : "flex-1",
        className,
      )}
      {...(fixed === undefined ? {} : { style: { height: fixed } })}
    >
      {chrome && (
        <>
          <h2 className="flex h-[46px] flex-none items-center justify-center truncate px-[12px] text-pane font-medium tracking-[-0.012em] whitespace-nowrap hairline-b">
            {title ?? tab?.label}
          </h2>
          <div
            data-workpaper="tabs"
            className="flex h-[46px] flex-none items-center gap-[6px] px-[12px]"
          >
            <Segmented
              size="small"
              label="Workpaper"
              options={tabs.map((t) => t.label)}
              active={label}
              onChange={switchTab}
            />
            <span className="flex-1" />
            <Button variant="ghost" size="sm" icon="download" {...clickProp(onDownload)}>
              Download
            </Button>
            <Button
              variant="ghost"
              size="sm"
              icon="file-spreadsheet"
              {...clickProp(onOpenInExcel)}
            >
              Open in Excel
            </Button>
          </div>
        </>
      )}
      <div
        ref={body}
        data-workpaper="scroll"
        className="relative flex min-h-0 flex-1 flex-col gap-[16px] overflow-auto"
      >
        {sections.map((section) => (
          <WorkpaperSection
            key={`${label}/${section.id}`}
            section={section}
            sheet={sheet}
            citations={citations}
            collapsed={isCollapsed(section.id)}
            onToggle={(open) => {
              toggle(section.id, open);
            }}
          />
        ))}
      </div>
      {(citations.length > 0 || procedures.length > 0) && (
        <CitationFooter>
          {citations.length > 0 && <CitationChip kind="citations" citations={citations} />}
          {procedures.length > 0 && <CitationChip kind="procedures" procedures={procedures} />}
        </CitationFooter>
      )}
    </div>
  );
}

function clickProp(fn: (() => void) | undefined): { onClick?: () => void } {
  return fn === undefined ? {} : { onClick: fn };
}
