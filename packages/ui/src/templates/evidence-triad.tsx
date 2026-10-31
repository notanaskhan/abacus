import { type JSX, type ReactNode, useState } from "react";
import { type Actor, isPerson } from "../attribution/actor";
import { HumanAction } from "../attribution/human-action";
import { cn } from "../cn";
import { Button, IconButton } from "../components/button";
import { SearchField } from "../components/inputs";
import { CheckPill, Pill } from "../components/pill";
import { type Opt, SheetTabs, type ViewOption } from "../components/tabs";
import { type ForceState, forceAttr } from "../force-state";
import { Icon } from "../icons";
import { AppShell } from "../layout/app-shell";
import { Pane } from "../layout/pane";
import { type DefaultRecordHeaderProps, RecordHeader } from "../layout/record-header";
import { SplitLayout } from "../layout/split-layout";
import type { SplitPresetName } from "../layout/split-presets";
import { Tabsbar } from "../layout/tabsbar";
import type { ToolbarProps } from "../layout/toolbar";
import { MatchScope } from "../tracing/match";
import type { MatchStore } from "../tracing/match-store";
import type { CitationPayload } from "../tracing/types";

// T3 EvidenceTriad (F-05-T53; T3 handoff, Wave 0 Foundations #t3): the source tree, the document
// and the sheet side by side in one MatchScope, so a worksheet field and its box on the page light
// together (one match per scope, E1). Under the toolbar 46, the record subbar 42 and the tabsbar 44
// with the layout ViewToggle, three presets lay out the panes (706 tall):
//
//   review   tree 452 · viewer 452 · sheet 452     (SplitLayout `review`)
//   prepare  tree 214 · viewer 571 · sheet 571     (SplitLayout `taxReview`)
//   two      sheet flex · viewer 490               (a row of its own: no chapter preset holds it)
//
// The tree's footer holds Approve Document, a HumanAction (INV-1: never on an agent's control), and
// Issue…. Document rows carry the check micro-pill (ink, never green), the amber flag pill with
// its count, or "Requested" for a document with no file yet.

export type TriadPreset = "review" | "prepare" | "two";

export const TRIAD_VIEWS: readonly ViewOption[] = [
  { v: "review", label: "Review", icon: "columns-3" },
  { v: "prepare", label: "Prepare", icon: "panel-left" },
  { v: "two", label: "Sheet and viewer", icon: "columns-2" },
];

const SPLIT: Record<Exclude<TriadPreset, "two">, SplitPresetName> = {
  review: "review",
  prepare: "taxReview",
};

/** The two-pane preset's viewer width. */
const TWO_VIEWER = 490;

// ---- The source tree --------------------------------------------------------------------------

export interface TriadDoc {
  id: string;
  label: string;
  /** No file yet: the row reads "Requested". */
  requested?: boolean;
  approved?: boolean;
  /** Issues raised on it: the amber flag pill with the count. */
  flags?: number;
  /** Where the flag pill leads (its tooltip): "Opens TAX-06 · Return issues". */
  flagsNote?: string;
  /** The ⓘ micro-pill: the row has provenance to show (SHL-09). */
  info?: boolean;
  /** Default true. A worksheet the firm prepares carries no document check (TPL-03's NYC
   * worksheet shows ⓘ only). */
  checkable?: boolean;
}

export interface TriadGroup {
  id: string;
  label: string;
  subs: readonly { id: string; label: string; docs: readonly TriadDoc[] }[];
}

export interface TriadTreeProps {
  groups: readonly TriadGroup[];
  selected?: string | null;
  onSelect?: (doc: TriadDoc) => void;
  /** Filters document rows by label. */
  query?: string;
  /** Hold one row in a state for a specimen. */
  forceState?: { doc: string; state: Extract<ForceState, "hover"> };
}

const BAND =
  "flex h-[31px] w-full items-center gap-[8px] bg-band-hd px-[12px] text-left text-section hairline-b hover:bg-nav-fill focus-visible:outline-offset-[-2px]";
const SUB =
  "flex h-[26px] w-full items-center gap-[6px] pl-[12px] text-left text-dense text-ink-2 hover:bg-nav-fill focus-visible:outline-offset-[-2px]";

/** The T3 source tree: group bands, sub-heads and document rows with their micro-pills. */
export function TriadTree({
  groups,
  selected,
  onSelect,
  query = "",
  forceState,
}: TriadTreeProps): JSX.Element {
  const [shut, setShut] = useState<Readonly<Record<string, boolean>>>({});
  const q = query.trim().toLowerCase();
  const toggle = (id: string): void => {
    setShut((s) => ({ ...s, [id]: s[id] !== true }));
  };
  return (
    <nav aria-label="Source documents" data-triad="tree" className="flex flex-col">
      {groups.map((g) => {
        const subs = g.subs
          .map((sub) => ({
            ...sub,
            docs: sub.docs.filter((d) => q === "" || d.label.toLowerCase().includes(q)),
          }))
          .filter((sub) => q === "" || sub.docs.length > 0);
        if (q !== "" && subs.length === 0) return null;
        const open = shut[g.id] !== true;
        return (
          <section key={g.id} aria-label={g.label} className="flex flex-col">
            <button
              type="button"
              aria-expanded={open}
              className={BAND}
              onClick={() => {
                toggle(g.id);
              }}
            >
              <span className="min-w-0 flex-1 truncate">{g.label}</span>
              <Icon
                name="chevron-down"
                size={12}
                className={cn("flex-none text-ink-3 transition-transform", !open && "-rotate-90")}
              />
            </button>
            {open &&
              subs.map((sub) => {
                const subOpen = shut[sub.id] !== true;
                return (
                  <div key={sub.id} className="flex flex-col">
                    <button
                      type="button"
                      aria-expanded={subOpen}
                      className={SUB}
                      onClick={() => {
                        toggle(sub.id);
                      }}
                    >
                      <Icon
                        name="chevron-down"
                        size={12}
                        className={cn("flex-none text-ink-3", !subOpen && "-rotate-90")}
                      />
                      <span className="min-w-0 truncate">{sub.label}</span>
                    </button>
                    {subOpen && (
                      <ul className="relative flex flex-col">
                        {/* The 1px guide rail at x26. */}
                        <span
                          aria-hidden="true"
                          className="absolute top-0 bottom-0 left-[26px] w-px bg-rule"
                        />
                        {sub.docs.map((doc) => (
                          <TreeDoc
                            key={doc.id}
                            doc={doc}
                            selected={selected === doc.id}
                            {...(onSelect === undefined ? {} : { onSelect })}
                            {...(forceState?.doc === doc.id
                              ? { forceState: forceState.state }
                              : {})}
                          />
                        ))}
                      </ul>
                    )}
                  </div>
                );
              })}
          </section>
        );
      })}
    </nav>
  );
}

function TreeDoc({
  doc,
  selected,
  onSelect,
  forceState,
}: {
  doc: TriadDoc;
  selected: boolean;
  onSelect?: (doc: TriadDoc) => void;
  forceState?: "hover";
}): JSX.Element {
  const flags = doc.flags ?? 0;
  return (
    <li className="flex">
      <button
        type="button"
        data-triad-doc={doc.id}
        {...(selected ? { "aria-current": "true" as const } : {})}
        {...forceAttr(forceState)}
        onClick={() => onSelect?.(doc)}
        className={cn(
          "flex h-[29px] w-full items-center gap-[7px] pr-[8px] pl-[39px] text-left text-dense",
          "hover:bg-nested data-[force=hover]:bg-nested focus-visible:outline-offset-[-2px]",
          selected && "bg-sel-bg font-medium hover:bg-sel-bg",
        )}
      >
        <Icon name="file" size={13} className="flex-none text-ink-3" />
        <span className="min-w-0 flex-1 truncate">{doc.label}</span>
        {doc.requested === true ? (
          <Pill variant="muted" size="sm" className="flex-none">
            Requested
          </Pill>
        ) : (
          <span className="flex flex-none items-center gap-[4px]">
            {flags > 0 && (
              <Pill
                variant="amber"
                size="check"
                data-flags={flags}
                lead={<Icon name="flag" size={12} />}
                {...(doc.flagsNote === undefined ? {} : { title: doc.flagsNote })}
              >
                <span className="sr-only">Issues</span>
                {flags}
              </Pill>
            )}
            {doc.checkable !== false && (
              <CheckPill
                approved={doc.approved === true}
                {...(doc.approved === true ? { count: 1 } : {})}
              />
            )}
            {doc.info === true && (
              <Pill
                variant="outline"
                size="check"
                role="img"
                aria-label="Provenance"
                data-info=""
                className="w-[21px] justify-center p-0"
              >
                <Icon name="info" size={12} className="text-ink-3" />
              </Pill>
            )}
          </span>
        )}
      </button>
    </li>
  );
}

/** The tree pane's pinned footer: Approve Document (a HumanAction) and Issue…. */
export function TriadFooter({
  actor,
  approved,
  disabled = false,
  onApprove,
  onUnapprove,
  onIssue,
  stacked = false,
}: {
  /** Who approves: the signed-in person. An agent actor draws no Approve at all (INV-1). */
  actor: Actor;
  approved: boolean;
  /** No file to approve or raise an issue on (a requested document). */
  disabled?: boolean;
  onApprove?: () => void;
  /** Given, an approved document offers the tonal "Unapprove Document" (TPL-03c) to the person who
   * may approve it; without it the button reads "Approved", disabled. Never for an agent (INV-1). */
  onUnapprove?: () => void;
  onIssue?: () => void;
  /** The narrow tree stacks the two; the wide one sets them in a row. */
  stacked?: boolean;
}): JSX.Element {
  return (
    <div className={cn("flex w-full gap-[8px]", stacked ? "flex-col" : "flex-row")}>
      {approved && onUnapprove !== undefined && isPerson(actor) ? (
        <Button
          variant="tonal"
          size="footer"
          icon="x"
          data-unapprove=""
          className="flex-1"
          onClick={onUnapprove}
        >
          Unapprove Document
        </Button>
      ) : approved ? (
        <Button variant="primary" size="footer" icon="check" disabled className="flex-1">
          Approved
        </Button>
      ) : (
        <HumanAction
          verb="Approve"
          object="Document"
          actor={actor}
          variant="primary"
          size="footer"
          icon="check"
          disabled={disabled}
          className="flex-1"
          {...(onApprove === undefined ? {} : { onClick: onApprove })}
        />
      )}
      <Button
        variant="tonal"
        size="footer"
        icon="flag"
        opensDialog
        disabled={disabled}
        className={stacked ? "w-full" : "flex-none"}
        {...(onIssue === undefined ? {} : { onClick: onIssue })}
      >
        Issue…
      </Button>
    </div>
  );
}

// ---- The template -------------------------------------------------------------------------------

export interface TriadSheet {
  /** "Worksheets", "Leadsheets", "2-Year Comparison". */
  tabs: readonly Opt[];
  active: string;
  onTab?: (label: string) => void;
  /** The 44 bar under the tabs: search, the entity picker, Edit. */
  bar?: ReactNode;
  children?: ReactNode;
}

export interface EvidenceTriadProps {
  toolbar: ToolbarProps;
  record: Omit<DefaultRecordHeaderProps, "variant">;
  /** The tabsbar's options (Overview, Intake, Review …) and its active tab. */
  tabs: { options: readonly Opt[]; active: string; label: string; onChange?: (l: string) => void };
  preset?: TriadPreset;
  defaultPreset?: TriadPreset;
  /** The layout menu's options (default TRIAD_VIEWS); TPL-03 names each with its widths. */
  views?: readonly ViewOption[];
  onPreset?: (preset: TriadPreset) => void;
  /** The tree pane: its search, its body and its footer. */
  tree: {
    title?: string;
    search?: ReactNode;
    body: ReactNode;
    footer: (stacked: boolean) => ReactNode;
  };
  /** The viewer pane's content: a SourceViewer, which draws its own header and toolbar. */
  viewer: ReactNode;
  sheet: TriadSheet;
  /** K-01-T19 (KNW-02 c, d): one wide pane in place of the viewer and the sheet, beside the
   * tree (the Prepare preset's 214 tree), with its centred title. */
  wide?: { title: string; children: ReactNode };
  /** One store for the three panes (a test, a page that drives it). */
  store?: MatchStore<CitationPayload>;
  frame?: boolean;
  embedded?: boolean;
  height?: number;
  className?: string;
}

/** The T3 frame: tree, viewer and sheet in one MatchScope under three presets. */
export function EvidenceTriad({
  toolbar,
  record,
  tabs,
  preset,
  defaultPreset = "review",
  views = TRIAD_VIEWS,
  onPreset,
  tree,
  viewer,
  sheet,
  wide,
  store,
  frame = false,
  embedded = false,
  height,
  className,
}: EvidenceTriadProps): JSX.Element {
  const [own, setOwn] = useState<TriadPreset>(defaultPreset);
  const current = preset ?? own;
  const narrowTree = current === "prepare";
  const treePane = (
    <Pane
      key="tree"
      title={tree.title ?? "Review"}
      {...(tree.search === undefined ? {} : { left: tree.search })}
      right={
        <>
          <IconButton icon="chevrons-up-down" label="Expand all" variant="white" />
          <IconButton icon="chevrons-down-up" label="Collapse all" variant="white" />
        </>
      }
      footer={tree.footer(narrowTree)}
      className="min-h-0"
    >
      <div data-triad-pane="tree" className="min-h-0 flex-1 overflow-auto">
        {tree.body}
      </div>
    </Pane>
  );
  const viewerPane = (
    <Pane key="viewer" header={false} className="min-h-0">
      <div data-triad-pane="viewer" className="flex min-h-0 flex-1 flex-col">
        {viewer}
      </div>
    </Pane>
  );
  const sheetPane = (
    <Pane key="sheet" header={false} className="min-h-0">
      <div data-triad-pane="sheet" className="flex min-h-0 flex-1 flex-col">
        <div className="flex h-(--pane-hd-h) flex-none items-center px-[10px]">
          <SheetTabs
            label="Sheets"
            options={sheet.tabs}
            active={sheet.active}
            {...(sheet.onTab === undefined ? {} : { onChange: sheet.onTab })}
          />
        </div>
        {sheet.bar !== undefined && (
          <div className="flex h-[44px] flex-none items-center gap-[8px] px-[10px]">
            {sheet.bar}
          </div>
        )}
        <div className="min-h-0 flex-1 overflow-auto">{sheet.children}</div>
      </div>
    </Pane>
  );
  return (
    <AppShell
      toolbar={toolbar}
      frame={frame}
      embedded={embedded}
      {...(height === undefined ? {} : { height })}
      {...(className === undefined ? {} : { className })}
      record={<RecordHeader {...record} variant="default" />}
      tabs={
        <Tabsbar
          size="compact"
          label={tabs.label}
          options={tabs.options}
          active={tabs.active}
          {...(tabs.onChange === undefined ? {} : { onChange: tabs.onChange })}
          view={{
            view: current,
            views,
            onView: (v) => {
              const next = v as TriadPreset;
              setOwn(next);
              onPreset?.(next);
            },
          }}
        />
      }
    >
      <MatchScope {...(store === undefined ? {} : { store })}>
        <div data-triad={current} className="flex min-h-0 min-w-0 flex-1">
          {wide !== undefined ? (
            <div
              data-split="wide"
              className="flex w-full min-w-0 gap-(--gutter-pane)"
              {...(height === undefined ? {} : { style: { height: height - 154 } })}
            >
              <div data-split-pane="0" className="flex w-[298px] flex-none">
                {treePane}
              </div>
              <div data-split-pane="1" className="flex min-w-0 flex-1">
                <Pane title={wide.title} className="min-h-0">
                  <div data-triad-pane="wide" className="min-h-0 flex-1 overflow-auto">
                    {wide.children}
                  </div>
                </Pane>
              </div>
            </div>
          ) : current === "two" ? (
            <div
              data-split="two"
              className="flex w-full min-w-0 gap-(--gutter-pane)"
              {...(height === undefined ? {} : { style: { height: height - 154 } })}
            >
              <div data-split-pane="0" className="flex min-w-0 flex-1">
                {sheetPane}
              </div>
              <div data-split-pane="1" className="flex flex-none" style={{ width: TWO_VIEWER }}>
                {viewerPane}
              </div>
            </div>
          ) : (
            <SplitLayout
              key={current}
              preset={SPLIT[current]}
              height={height === undefined ? "viewport" : height - 154}
              narrow={false}
              className="w-full bg-transparent p-0"
            >
              {[treePane, viewerPane, sheetPane]}
            </SplitLayout>
          )}
        </div>
      </MatchScope>
    </AppShell>
  );
}

/** The sheet bar (T3): field search, the entity picker and the Edit pill. */
export function TriadSheetBar({
  query,
  onQuery,
  picker,
  onEdit,
}: {
  query: string;
  onQuery: (q: string) => void;
  picker: ReactNode;
  onEdit?: () => void;
}): JSX.Element {
  return (
    <>
      <SearchField
        label="Search fields"
        placeholder="Search fields"
        value={query}
        onChange={onQuery}
      />
      {picker}
      <span className="flex-1" />
      <Button
        variant="secondary"
        size="sm"
        icon="pencil"
        {...(onEdit === undefined ? {} : { onClick: onEdit })}
      >
        Edit
      </Button>
    </>
  );
}
