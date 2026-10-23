import { type JSX, type KeyboardEvent, useId, useState } from "react";
import { cn } from "../cn";
import { Button } from "../components/button";
import { Pill } from "../components/pill";
import { Menu } from "../components/popover";
import { StatusDisc } from "../components/status";
import { type ForceState, forceAttr } from "../force-state";
import { Icon } from "../icons";
import { Pane } from "../layout/pane";
import type { PillVariant } from "../status";
import { OverviewCard, type OverviewCardProps } from "./record-kit";
import {
  type Phase,
  type PhasePillKind,
  ROW_MENU,
  type RailLink,
  type RailSection,
  type RowMenuItem,
} from "./types";

// The C-03 Rail kit (F-05-T40): RecordRail, the 330 left pane of every record template (T2). Top
// to bottom: the 46 header, the C-04 OverviewCard, link rows, then group bands with their phase
// rows. Every row says its state in words (a pill or a live line) beside a disc; never a coloured
// row, a per-row progress bar or colour alone. The rail draws what it is given: the phases' states
// are data, and only Begin… is optimistic (Running until the data moves on).
//
// Rows hold their own buttons (Begin…, ···), so a row is a group of buttons rather than one
// `role="button"` (axe: no nested interactive). ↑ and ↓ move between the rows' main buttons and the
// bands that are visible; a collapsed group is `inert`, so its rows leave the tab order.

const PILL: Record<PhasePillKind, PillVariant> = {
  ready: "green-tint",
  progress: "amber",
  waiting: "muted",
};

// Hover nested, pressed and selected sel-bg; titles turn 500 only when selected. Focus is the
// plan's .55 outline drawn inside the row (tokens/DECISIONS.md, C-03).
const ROW_STATE =
  "hover:bg-nested data-[force=hover]:bg-nested active:bg-sel-bg data-[force=pressed]:bg-sel-bg data-[selected]:bg-sel-bg";
const FOCUS_IN = "outline-offset-[-2px]";

/** Moves focus to the previous or next rail target on ↑ or ↓. */
function moveFocus(event: KeyboardEvent<HTMLElement>): void {
  if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
  const rail = event.currentTarget.closest("[data-rail]");
  if (rail === null) return;
  const targets = Array.from(rail.querySelectorAll<HTMLElement>("[data-rail-target]")).filter(
    (el) => el.closest("[inert]") === null,
  );
  const at = targets.indexOf(event.currentTarget);
  if (at < 0) return;
  const next = targets[event.key === "ArrowDown" ? at + 1 : at - 1];
  if (next === undefined) return;
  event.preventDefault();
  next.focus();
}

// ---- Rows ---------------------------------------------------------------------------------------

export interface RailRowProps {
  link: RailLink;
  compact?: boolean;
  selected?: boolean;
  onOpen?: (link: RailLink) => void;
  forceState?: Extract<ForceState, "hover" | "focus" | "pressed">;
}

/** A link row: icon (or a to-do disc when compact), title and sub, then chevron or arrow. */
export function RailRow({
  link,
  compact = false,
  selected = false,
  onOpen,
  forceState,
}: RailRowProps): JSX.Element {
  return (
    <button
      type="button"
      data-rail-target=""
      data-rail-row="link"
      {...(selected ? { "data-selected": "", "aria-current": true } : {})}
      {...forceAttr(forceState)}
      onClick={() => {
        onOpen?.(link);
      }}
      onKeyDown={moveFocus}
      className={cn(
        "flex min-h-[38px] w-full items-center gap-[10px] px-[12px] py-[7px] text-left hairline-b",
        ROW_STATE,
        FOCUS_IN,
      )}
    >
      {compact ? (
        <StatusDisc state={link.disc ?? "todo"} />
      ) : (
        link.icon !== undefined && (
          <Icon name={link.icon} size={15} className="flex-none text-ink-3" />
        )
      )}
      <span className="flex min-w-0 flex-1 flex-col gap-[2px]">
        <span className={cn("truncate text-dense text-ink", selected && "font-medium")}>
          {link.title}
        </span>
        {link.sub !== undefined && (
          <span className="truncate text-meta text-ink-3">{link.sub}</span>
        )}
      </span>
      <Icon
        name={link.elsewhere === true ? "arrow-right" : "chevron-right"}
        size={12}
        className="flex-none text-ink-3"
      />
    </button>
  );
}

export interface PhaseRowProps {
  phase: Phase;
  /** 13px titles (the outline variant). */
  outline?: boolean;
  /** A version under its phase: padding-left 30. */
  child?: boolean;
  selected?: boolean;
  onOpen?: (phase: Phase) => void;
  onBegin?: (phase: Phase) => void;
  onMenu?: (item: RowMenuItem, phase: Phase) => void;
  forceState?: Extract<ForceState, "hover" | "focus" | "pressed">;
  /** Hold the ··· menu open for a specimen. */
  menuForceState?: "open";
}

/** A phase row: the disc, the title and its second line, then Begin… and the ··· menu. */
export function PhaseRow({
  phase,
  outline = false,
  child = false,
  selected = false,
  onOpen,
  onBegin,
  onMenu,
  forceState,
  menuForceState,
}: PhaseRowProps): JSX.Element {
  const disc = phase.disc ?? "todo";
  const failed = disc === "fail";
  const showBegin = phase.begin === true && disc === "todo";
  return (
    <div
      data-rail-row="phase"
      data-phase={phase.id}
      data-disc={disc}
      {...(selected ? { "data-selected": "" } : {})}
      {...forceAttr(forceState === "focus" ? undefined : forceState)}
      className={cn(
        "group/row flex min-h-[38px] items-center gap-[9px] py-[7px] pr-[10px] hairline-b",
        child ? "pl-[30px]" : "pl-[12px]",
        ROW_STATE,
      )}
    >
      <button
        type="button"
        data-rail-target=""
        {...(selected ? { "aria-current": true } : {})}
        {...(forceState === "focus" ? { "data-force": "focus" } : {})}
        onClick={() => {
          onOpen?.(phase);
        }}
        onKeyDown={moveFocus}
        className={cn(
          "flex min-w-0 flex-1 items-center gap-[9px] self-stretch text-left",
          FOCUS_IN,
        )}
      >
        <StatusDisc state={disc} />
        <span className="flex min-w-0 flex-1 flex-col gap-[3px]">
          <span
            className={cn(
              "truncate leading-[1.3]",
              outline ? "text-body" : "text-dense",
              failed ? "text-red-ink" : "text-ink",
              selected && "font-medium",
            )}
          >
            {phase.title}
          </span>
          {phase.pill !== undefined && (
            <span>
              <Pill variant={PILL[phase.pill.kind]} size="sm">
                {phase.pill.text}
              </Pill>
            </span>
          )}
          {phase.pill === undefined && phase.live !== undefined && (
            <span
              data-line={phase.live.tone ?? "ink"}
              className={cn(
                "truncate text-meta",
                phase.live.tone === "amber" ? "text-amber-ink" : "text-ink-3",
              )}
            >
              {phase.live.text}
            </span>
          )}
        </span>
      </button>
      {showBegin && (
        <Button
          size="xs"
          variant="primary"
          className="flex-none px-[10px]"
          onClick={() => {
            onBegin?.(phase);
          }}
        >
          Begin…
        </Button>
      )}
      <Menu
        label={`${phase.title} actions`}
        width={200}
        align="end"
        {...(menuForceState === undefined ? {} : { forceState: menuForceState })}
        trigger={
          <button
            type="button"
            aria-label={`More for ${phase.title}`}
            className="flex size-[24px] flex-none items-center justify-center rounded-pill text-cell tracking-[0.06em] text-ink-3 hover:bg-sel-bg aria-expanded:bg-sel-bg"
          >
            ···
          </button>
        }
        sections={[
          ROW_MENU.map((item) => ({
            label: item,
            ...(item.endsWith("…") ? { opensDialog: true } : {}),
            onSelect: () => {
              onMenu?.(item, phase);
            },
          })),
        ]}
      />
    </div>
  );
}

// ---- Bands --------------------------------------------------------------------------------------

export interface GroupBandProps {
  title: string;
  /** Navigates (chevron-right) instead of collapsing. */
  nav?: boolean;
  /** Collapsing bands only. */
  open?: boolean;
  controls?: string;
  onToggle?: () => void;
  onNavigate?: () => void;
  forceState?: Extract<ForceState, "hover" | "focus">;
}

/** The 31px band: navigates ("Activity") or collapses its group of phases. */
export function GroupBand({
  title,
  nav = false,
  open = true,
  controls,
  onToggle,
  onNavigate,
  forceState,
}: GroupBandProps): JSX.Element {
  return (
    <button
      type="button"
      data-rail-target=""
      data-rail-band={nav ? "nav" : "collapse"}
      {...forceAttr(forceState)}
      {...(nav ? {} : { "aria-expanded": open })}
      {...(controls === undefined || nav ? {} : { "aria-controls": controls })}
      onClick={nav ? onNavigate : onToggle}
      onKeyDown={moveFocus}
      className={cn(
        "-mt-[0.5px] flex h-[31px] w-full flex-none items-center gap-[8px] bg-band-hd px-[12px] text-left text-body font-medium hairline-t hairline-b",
        "hover:bg-nested data-[force=hover]:bg-nested",
        FOCUS_IN,
      )}
    >
      <span className="min-w-0 flex-1 truncate">{title}</span>
      <Icon
        name={nav ? "chevron-right" : "chevron-down"}
        size={12}
        className={cn(
          "flex-none text-ink-3 transition-transform duration-[220ms] ease-out",
          !nav && !open && "-rotate-90",
        )}
      />
    </button>
  );
}

// ---- RecordRail ---------------------------------------------------------------------------------

export interface RecordRailProps {
  /** The pane header (default "Overview"; "Audit program" in the outline variant). */
  title?: string;
  /** `outline`: uppercase outline headers, 13px titles, nothing collapses. */
  variant?: "default" | "outline";
  /** Link rows lead with to-do discs instead of icons. */
  compact?: boolean;
  /** Rows only: no header, no card, no pane chrome. */
  bare?: boolean;
  card?: OverviewCardProps;
  links?: readonly RailLink[];
  sections?: readonly RailSection[];
  /** The id of the open link or phase. */
  selected?: string;
  onOpen?: (item: RailLink | Phase) => void;
  onNavigate?: (band: string) => void;
  onToggle?: (band: string, nowOpen: boolean) => void;
  onBegin?: (phase: Phase) => void;
  onMenu?: (item: RowMenuItem, phase: Phase) => void;
  className?: string;
}

function Group({
  section,
  outline,
  selected,
  pending,
  onOpen,
  onBegin,
  onMenu,
  onToggle,
  onNavigate,
}: {
  section: RailSection;
  outline: boolean;
  selected: string | undefined;
  pending: ReadonlySet<string>;
  onOpen: ((item: RailLink | Phase) => void) | undefined;
  onBegin: (phase: Phase) => void;
  onMenu: ((item: RowMenuItem, phase: Phase) => void) | undefined;
  onToggle: ((band: string, nowOpen: boolean) => void) | undefined;
  onNavigate: ((band: string) => void) | undefined;
}): JSX.Element {
  const id = useId();
  const collapsible = !outline && section.nav !== true && section.collapsible !== false;
  const [open, setOpen] = useState(section.collapsed !== true);
  const shown = !collapsible || open;
  const phases = section.phases ?? [];

  const row = (phase: Phase, child: boolean): JSX.Element => {
    const view =
      pending.has(phase.id) && (phase.disc ?? "todo") === "todo" ? running(phase) : phase;
    return (
      <div key={phase.id} className="contents">
        <PhaseRow
          phase={view}
          outline={outline}
          child={child}
          selected={selected === phase.id}
          {...(onOpen === undefined ? {} : { onOpen })}
          onBegin={onBegin}
          {...(onMenu === undefined ? {} : { onMenu })}
        />
        {(phase.children ?? []).map((version) => row(version, true))}
      </div>
    );
  };

  return (
    <div data-rail-section={section.id} className="flex flex-col">
      {outline ? (
        <h3 className="px-[12px] pt-[14px] pb-[6px] text-outline-hd text-ink-3 uppercase hairline-b">
          {section.title}
        </h3>
      ) : (
        <GroupBand
          title={section.title}
          nav={section.nav === true}
          open={open}
          controls={id}
          onToggle={() => {
            setOpen(!open);
            onToggle?.(section.title, !open);
          }}
          onNavigate={() => onNavigate?.(section.title)}
        />
      )}
      {section.nav !== true && (
        <div
          id={id}
          role="group"
          aria-label={section.title}
          {...(shown ? {} : { inert: true, "data-collapsed": "" })}
          className={cn(
            "grid transition-[grid-template-rows] duration-[340ms] ease-out",
            shown ? "grid-rows-[1fr]" : "grid-rows-[0fr]",
          )}
        >
          <div className="flex min-h-0 flex-col overflow-hidden">
            {phases.map((phase) => row(phase, false))}
          </div>
        </div>
      )}
    </div>
  );
}

/** A phase that was begun: Running, until the data says what it is now. */
function running(phase: Phase): Phase {
  return { id: phase.id, title: phase.title, disc: "run", live: { text: "Running" } };
}

/** The record's left rail: exactly 330 wide in every record template. */
export function RecordRail({
  title,
  variant = "default",
  compact = false,
  bare = false,
  card,
  links = [],
  sections = [],
  selected,
  onOpen,
  onNavigate,
  onToggle,
  onBegin,
  onMenu,
  className,
}: RecordRailProps): JSX.Element {
  const outline = variant === "outline";
  const [pending, setPending] = useState<ReadonlySet<string>>(() => new Set());
  const begin = (phase: Phase): void => {
    setPending((prev) => new Set(prev).add(phase.id));
    onBegin?.(phase);
  };
  const rows = (
    <div data-rail={variant} className="flex flex-col">
      {!bare && card !== undefined && <OverviewCard {...card} />}
      {links.length > 0 && (
        <div className={cn("flex flex-col", !bare && card !== undefined && "hairline-t")}>
          {links.map((link) => (
            <RailRow
              key={link.id}
              link={link}
              compact={compact}
              selected={selected === link.id}
              {...(onOpen === undefined ? {} : { onOpen })}
            />
          ))}
        </div>
      )}
      {sections.map((section) => (
        <Group
          key={section.id}
          section={section}
          outline={outline}
          selected={selected}
          pending={pending}
          onOpen={onOpen}
          onBegin={begin}
          onMenu={onMenu}
          onToggle={onToggle}
          onNavigate={onNavigate}
        />
      ))}
    </div>
  );
  if (bare) return rows;
  return (
    <Pane
      width={330}
      title={title ?? (outline ? "Audit program" : "Overview")}
      {...(className === undefined ? {} : { className })}
    >
      {rows}
    </Pane>
  );
}
