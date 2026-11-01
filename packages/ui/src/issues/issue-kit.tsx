import { type JSX, type KeyboardEvent, type ReactNode, useRef, useState } from "react";
import { AgentText } from "../agent-text";
import { type Actor, isPerson } from "../attribution/actor";
import { AgentAvatar } from "../brand/monogram";
import { PersonAvatar } from "../brand/person";
import { cn } from "../cn";
import { Button, IconButton } from "../components/button";
import { Spinner } from "../components/motion";
import { Pill } from "../components/pill";
import { Menu } from "../components/popover";
import { EmptyState } from "../components/states";
import { StatusDisc } from "../components/status";
import { Checkbox } from "../components/toggles";
import { Icon, type IconName } from "../icons";
import { useMatch } from "../tracing/match";
import type { MatchId } from "../tracing/types";

// C-17 Issue kit (F-05-T55; Issue Kit `Pair`, `Queue`, `Detail`): the queue of issues raised on a
// return, close or audit, and the issue's detail card. Three queue variants follow the three T9
// presets:
//
//   tree      issues-individual  group rows with "1 open", rows padding 8 10 8 32 on the x26
//                                connector, a flag, the title clamped to 2 lines, the kind sub-line
//                                (ink-3 "Missing information", amber-ink "Action required") and a
//                                trailing Settings glyph when the agent can fix it
//   severity  close-review       High · Medium · Low bands with open counts, rows with a flag in
//                                red (high) or amber, the title and an "Open · account" sub-line
//   radio     issues-entity      "Waiting on the client", "Review points", "Resolved" bands, rows
//                                with a 13px ring (olive with a check once done), titles to 3 lines
//
// The detail card: the title band, the key-value rows (Assigned to with its picker, Priority,
// Severity, Status, Created by), "What it blocks", "Workbook cells" (rows that light their source,
// INV-2), "Why This Was Surfaced" under the 15px olive check disc (never Sparkles), the agent's
// explanation, and "Linked Entities" (file chips that light). Everything the agent wrote renders
// through AgentText. The footer's verbs (Resolve, Mark as Resolved, Mark Not Applicable, Reopen)
// are a person's: an agent actor gets no footer at all, though the agent can be the assignee
// (INV-1).

export type IssueQueueVariant = "tree" | "severity" | "radio";
export type IssueState = "open" | "working" | "resolved" | "na";

export interface IssueItem {
  id: string;
  title: string;
  /** "Missing information", "Action required", "Open · Amex Business Card ••1009". */
  sub?: string;
  /** Amber ink for an action the reviewer must take; ink-3 otherwise. */
  subTone?: "muted" | "amber";
  /** The flag's colour (tree and severity): red for high or action, amber for medium and low. */
  flag?: "red" | "amber";
  /** The agent can fix it: the trailing Settings glyph (tree). */
  agentFixable?: boolean;
  state?: IssueState;
  /** A class glyph in place of the flag (severity): HOME-02's "?" decision chip, the sign-off
   * ring, the amber triangle of a blocked row (I-01-T16). `label` is its accessible name. */
  glyph?: { icon: IconName; label: string; tone?: "ink" | "amber" };
  /** Select mode (HOME-02 bulk, I-01-T19): a leading checkbox beside the row, never inside it.
   * `reason` marks why a disabled box cannot be chosen (`data-issue-check`) and is its tooltip. */
  check?: {
    checked: boolean;
    label: string;
    disabled?: boolean;
    reason?: string;
    onChange: (checked: boolean) => void;
  };
}

export interface IssueGroup {
  id: string;
  label: string;
  /** "1 open", "2", "Done": the server's count, never counted here. */
  count: string;
  items: readonly IssueItem[];
  /** Default true; the Resolved band opens closed. */
  defaultOpen?: boolean;
  /** Tree: the form section the rows sit under ("Payments, Penalties & Estimates"), drawn as a
   * 12.5 sub-head between the band and its rows (TPL-09a). */
  sub?: string;
}

export const ISSUE_DONE: readonly IssueState[] = ["resolved", "na"];
const isDone = (i: IssueItem): boolean => ISSUE_DONE.includes(i.state ?? "open");

// ---- The queue ----------------------------------------------------------------------------------

export interface IssueQueueProps {
  variant: IssueQueueVariant;
  groups: readonly IssueGroup[];
  selected?: string | null;
  onSelect?: (item: IssueItem) => void;
  /** The list's accessible name. */
  label?: string;
  className?: string;
}

const GROUP_HEAD: Record<IssueQueueVariant, string> = {
  tree: "min-h-[49px] gap-[8px] py-[6px] pr-[14px] pl-[10px] text-tab",
  severity: "h-[49px] gap-[8px] bg-band-hd px-[16px] text-tab hairline-b",
  radio: "h-[49px] gap-[8px] bg-band-hd px-[16px] text-tab font-medium hairline-b",
};

/** The issue queue (C-17 Queue): bands or groups of rows, ↑ ↓ move between rows. */
export function IssueQueue({
  variant,
  groups,
  selected,
  onSelect,
  label = "Issues",
  className,
}: IssueQueueProps): JSX.Element {
  const [shut, setShut] = useState<Readonly<Record<string, boolean>>>(() =>
    Object.fromEntries(groups.map((g) => [g.id, g.defaultOpen === false])),
  );
  const root = useRef<HTMLDivElement>(null);
  const onKey = (event: KeyboardEvent<HTMLButtonElement>): void => {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    const rows = [
      ...(root.current?.querySelectorAll<HTMLButtonElement>("[data-issue-row]") ?? []),
    ];
    const at = rows.indexOf(event.currentTarget);
    const next = rows[event.key === "ArrowDown" ? at + 1 : at - 1];
    if (next === undefined) return;
    event.preventDefault();
    next.focus();
    const id = next.getAttribute("data-issue-row");
    const item = groups.flatMap((g) => g.items).find((i) => i.id === id);
    if (item !== undefined) onSelect?.(item);
  };
  return (
    <div
      ref={root}
      role="navigation"
      aria-label={label}
      data-issue-queue={variant}
      className={cn("flex flex-col", className)}
    >
      {groups.map((g) => {
        const open = shut[g.id] !== true;
        return (
          <section
            key={g.id}
            aria-label={g.label}
            data-issue-group={g.id}
            className="flex flex-col"
          >
            <button
              type="button"
              aria-expanded={open}
              onClick={() => {
                setShut((s) => ({ ...s, [g.id]: open }));
              }}
              className={cn(
                "flex w-full items-center text-left hover:bg-nav-fill focus-visible:outline-offset-[-2px]",
                GROUP_HEAD[variant],
              )}
            >
              {variant === "tree" && (
                <Icon
                  name="chevron-down"
                  size={14}
                  className={cn("flex-none text-ink-3", !open && "-rotate-90")}
                />
              )}
              <span className="min-w-0 flex-1 leading-[1.25]">
                {g.label}
                {variant === "severity" && (
                  <span className="ml-[8px] text-dense text-ink-3">{g.count}</span>
                )}
              </span>
              {variant !== "severity" && g.count !== "" && (
                <span className="flex-none text-dense text-ink-3">{g.count}</span>
              )}
              {variant !== "tree" && (
                <Icon
                  name={variant === "radio" && !open ? "chevron-right" : "chevron-down"}
                  size={13}
                  className={cn(
                    "flex-none text-ink-3",
                    variant === "severity" && !open && "-rotate-90",
                  )}
                />
              )}
            </button>
            {open && variant === "tree" && g.sub !== undefined && (
              <p
                data-issue-sub=""
                className="flex items-center gap-[6px] py-[4px] pr-[14px] pl-[14px] text-meta text-ink-3"
              >
                <Icon name="chevron-down" size={12} className="flex-none" />
                <span className="min-w-0 truncate">{g.sub}</span>
              </p>
            )}
            {open && g.items.length > 0 && (
              <ul className={cn("relative flex flex-col", variant === "tree" && "pb-[4px]")}>
                {variant === "tree" && (
                  <span
                    aria-hidden="true"
                    className="absolute top-0 bottom-0 left-[26px] w-px bg-rule"
                  />
                )}
                {g.items.map((item) => (
                  <IssueRow
                    key={item.id}
                    item={item}
                    variant={variant}
                    selected={selected === item.id}
                    onKey={onKey}
                    {...(onSelect === undefined ? {} : { onSelect })}
                  />
                ))}
              </ul>
            )}
          </section>
        );
      })}
    </div>
  );
}

function IssueRow({
  item,
  variant,
  selected,
  onSelect,
  onKey,
}: {
  item: IssueItem;
  variant: IssueQueueVariant;
  selected: boolean;
  onSelect?: (item: IssueItem) => void;
  onKey: (event: KeyboardEvent<HTMLButtonElement>) => void;
}): JSX.Element {
  const done = isDone(item);
  const check = item.check;
  return (
    <li className="flex">
      {check !== undefined && (
        <span
          className="flex flex-none items-start pt-[9px] pl-[12px] hairline-t"
          {...(check.reason === undefined
            ? {}
            : { title: check.reason, "data-issue-check": check.reason })}
        >
          <Checkbox
            label={check.label}
            checked={check.checked}
            disabled={check.disabled === true}
            onChange={check.onChange}
          />
        </span>
      )}
      <button
        type="button"
        data-issue-row={item.id}
        data-state={item.state ?? "open"}
        {...(selected ? { "aria-current": "true" as const } : {})}
        tabIndex={selected ? 0 : -1}
        onClick={() => onSelect?.(item)}
        onKeyDown={onKey}
        className={cn(
          "flex w-full items-start text-left hover:bg-nested focus-visible:outline-offset-[-2px]",
          variant === "tree"
            ? "gap-[8px] py-[8px] pr-[10px] pl-[32px] text-dense leading-[1.32]"
            : "gap-[9px] px-[12px] pt-[8px] pb-[9px] hairline-t",
          variant === "severity" && "text-dense leading-[1.32]",
          variant === "radio" && "text-body leading-[1.35]",
          selected && "bg-sel-bg font-medium hover:bg-sel-bg",
          done && "text-ink-3",
        )}
      >
        {variant === "radio" ? (
          <span className="mt-[2px] flex-none">
            {done ? <StatusDisc state="done" size={13} /> : <StatusDisc state="todo" size={13} />}
          </span>
        ) : item.glyph !== undefined ? (
          <Icon
            name={item.glyph.icon}
            size={13}
            aria-label={item.glyph.label}
            className={cn(
              "mt-[2px] flex-none",
              item.glyph.tone === "amber" ? "text-amber" : "text-ink-3",
            )}
          />
        ) : (
          <Icon
            name="flag"
            size={12}
            aria-label={item.flag === "amber" ? "Medium or low" : "High"}
            className={cn("mt-[3px] flex-none", item.flag === "amber" ? "text-amber" : "text-red")}
          />
        )}
        <span className="flex min-w-0 flex-1 flex-col gap-[3px]">
          <span
            className={cn(
              variant === "radio" ? "line-clamp-3" : "line-clamp-2",
              done ? "text-ink-3" : "text-ink",
            )}
          >
            {item.title}
          </span>
          {item.sub !== undefined && (
            <span
              className={cn(
                "truncate font-normal",
                variant === "severity" ? "text-pill-sm" : "text-meta",
                item.subTone === "amber" && !done ? "text-amber-ink" : "text-ink-3",
              )}
            >
              {item.sub}
            </span>
          )}
        </span>
        {item.agentFixable === true && !done && (
          <Icon
            name="settings"
            size={13}
            aria-label="The agent can fix this"
            className="mt-[2px] flex-none text-ink-3"
          />
        )}
      </button>
    </li>
  );
}

// ---- The detail -----------------------------------------------------------------------------------

export const AGENT_ASSIGNEE = "Accrued Agent";

export interface IssueCell {
  /** "Leadsheet!C14", "Operating ••4410!E212". */
  ref: string;
  /** The server's formatted value. */
  value: string;
  match: MatchId;
}

export interface IssueLink {
  name: string;
  icon: "sheet" | "file" | "folder";
  match: MatchId;
}

export interface IssueDetailView {
  id: string;
  title: string;
  state: IssueState;
  /** A person's name or "Accrued Agent": the agent can be assigned. */
  assignee: string;
  priority: string;
  severity: { label: string; flag?: "red" | "amber" };
  status: string;
  createdBy: string;
  /** The rows after "Assigned to", when the record draws its own (TPL-09: Priority and Created by
   * on a return; Severity, Status and Account on a close). Default: Priority, Severity, Status,
   * Created by. */
  facts?: readonly { label: string; value: string }[];
  /** The issue's body under its title, before the rows (TPL-09a); agent text, figures at 500. */
  summary?: readonly { text: string; figure?: boolean }[];
  /** "What it blocks": the server's sentence with its figures marked (drawn at 500); empty draws
   * no band. */
  blocks: readonly { text: string; figure?: boolean }[];
  cells: readonly IssueCell[];
  /** "Why This Was Surfaced": the agent's reason; empty draws no band. */
  why: string;
  links: readonly IssueLink[];
  /** Linked records named in Linked Entities above the file chips: "Operating Checking (Front
   * Range Bank) ••4410" with "1 reconciling item", flagged when it carries the issue. */
  entities?: readonly { name: string; sub?: string; flag?: boolean }[];
  /** The agent's explanation, shown when Explain… is pressed. */
  explain?: string;
  /** Agent working: the instruction it follows and how far it is (0 to 100). */
  working?: { text: string; percent: number };
}

const LINK_ICON: Record<IssueLink["icon"], IconName> = {
  sheet: "file-spreadsheet",
  file: "file-text",
  folder: "folder",
};

export interface IssueDetailProps {
  issue: IssueDetailView | null;
  /** Who the issue can be assigned to: the agent and the people on the record. */
  people?: readonly string[];
  onAssign?: (name: string) => void;
  /** The explanation is open (Explain… pressed). */
  explainOpen?: boolean;
  /** The close preset draws the title band on the shell colour. */
  titleBand?: "card" | "shell";
  className?: string;
}

const BAND = "flex h-[31px] items-center gap-[8px] bg-band-hd px-[20px] text-section hairline-t";
const KV = "flex min-h-[44px] items-center gap-[12px] px-[20px] text-body hairline-t";

function CellRow({ cell }: { cell: IssueCell }): JSX.Element {
  const { lit, bind, pin } = useMatch(cell.match, "row");
  return (
    <li
      {...bind}
      data-issue-cell={cell.ref}
      onClick={(event) => {
        pin(event.currentTarget);
      }}
      className={cn(
        "flex h-[38px] items-center gap-[10px] px-[20px] text-body hairline-t",
        "transition-[background-color,color] duration-[360ms]",
        lit ? "bg-match-bg text-match-ink" : "hover:bg-nested",
      )}
    >
      <Icon name="table" size={14} className={lit ? "text-match-ink" : "text-ink-3"} />
      <span className="min-w-0 flex-1 truncate">{cell.ref}</span>
      <span className="text-dense text-ink-3 tabular-nums">{cell.value}</span>
    </li>
  );
}

function LinkChip({ link }: { link: IssueLink }): JSX.Element {
  const { lit, bind, pin } = useMatch(link.match, "row");
  return (
    <li className="flex">
      <button
        type="button"
        {...bind}
        data-issue-link={link.name}
        onClick={(event) => {
          pin(event.currentTarget);
        }}
        className={cn(
          "inline-flex h-[28px] items-center gap-[6px] rounded-pill px-[10px] text-dense",
          "transition-[background-color,box-shadow,color] duration-[360ms]",
          lit ? "bg-match-bg text-match-ink ring-1 ring-match-line" : "bg-card shadow-e1",
        )}
      >
        <Icon name={LINK_ICON[link.icon]} size={13} className="flex-none" />
        {link.name}
      </button>
    </li>
  );
}

function Assignee({
  name,
  people,
  onAssign,
}: {
  name: string;
  people: readonly string[];
  onAssign?: (name: string) => void;
}): JSX.Element {
  const who = (
    <span className="inline-flex min-w-0 items-center gap-[8px]">
      {name === AGENT_ASSIGNEE ? <AgentAvatar /> : <PersonAvatar name={name} decorative />}
      <span className="truncate">{name}</span>
    </span>
  );
  return (
    <Menu
      label="Assign to"
      align="start"
      trigger={
        <button
          type="button"
          data-issue-assignee={name}
          aria-label={`Assigned to ${name}. Change`}
          className="inline-flex h-[28px] max-w-full items-center gap-[6px] rounded-pill pr-[8px] pl-[2px] hover:bg-nav-fill"
        >
          {who}
          <Icon name="chevron-down" size={12} className="flex-none text-ink-3" />
        </button>
      }
      sections={[
        people.map((p) => ({
          label: p,
          checked: p === name,
          onSelect: () => onAssign?.(p),
        })),
      ]}
    />
  );
}

/** A server sentence in parts, its figures at 500, through AgentText. */
function Parts({ parts }: { parts: readonly { text: string; figure?: boolean }[] }): JSX.Element {
  return (
    <>
      {parts.map((part, n) => (
        <AgentText
          // The parts are a fixed sentence; their order is their identity.
          key={n}
          inline
          text={part.text}
          {...(part.figure === true ? { className: "font-medium text-ink" } : {})}
        />
      ))}
    </>
  );
}

/** The issue's detail card (C-17 Detail), or the empty card when nothing is selected. */
export function IssueDetail({
  issue,
  people = [AGENT_ASSIGNEE],
  onAssign,
  explainOpen = false,
  titleBand = "card",
  className,
}: IssueDetailProps): JSX.Element {
  if (issue === null) {
    return (
      <div data-issue-detail="empty" className={cn("flex flex-1 bg-shell", className)}>
        <EmptyState title="Nothing selected" icon="flag">
          Pick an issue to see what it blocks.
        </EmptyState>
      </div>
    );
  }
  const done = ISSUE_DONE.includes(issue.state);
  return (
    <article
      data-issue-detail={issue.id}
      data-state={issue.state}
      aria-label={issue.title}
      className={cn("flex flex-col", className)}
    >
      <header
        className={cn(
          "flex items-start gap-[10px] px-[20px] py-[12px]",
          titleBand === "shell" && "bg-shell",
        )}
      >
        <h3
          className={cn(
            "min-w-0 flex-1 text-title leading-[1.3] font-medium",
            done ? "text-ink-2" : "text-ink",
          )}
        >
          {issue.title}
        </h3>
        {issue.state === "working" && (
          <Pill
            variant="amber"
            size="sm"
            data-issue-working=""
            lead={<Spinner label="Agent working…" size={10} showLabel={false} />}
          >
            Agent working…
          </Pill>
        )}
        {done && (
          <Pill variant="muted" size="sm">
            {issue.state === "na" ? "Not applicable" : "Resolved"}
          </Pill>
        )}
      </header>
      {issue.working !== undefined && issue.state === "working" && (
        <div
          data-issue-run=""
          className="flex items-center gap-[16px] px-[20px] py-[10px] hairline-t"
        >
          <span className="flex min-w-0 flex-1 flex-col gap-[2px]">
            <span className="text-body font-medium">Accrued Agent is fixing this</span>
            <span className="truncate text-meta text-ink-3">
              Following your instructions ·{" "}
              <AgentText inline text={issue.working.text} className="text-meta text-ink-3" />
            </span>
          </span>
          <span
            role="progressbar"
            aria-label="Fix progress"
            aria-valuenow={issue.working.percent}
            aria-valuemin={0}
            aria-valuemax={100}
            className="h-[3px] w-[168px] flex-none overflow-hidden rounded-pill bg-nested"
          >
            <span
              className="block h-full rounded-pill bg-espresso"
              style={{ width: `${String(issue.working.percent)}%` }}
            />
          </span>
          <Spinner label="Running" size={15} showLabel={false} />
        </div>
      )}
      {issue.summary !== undefined && issue.summary.length > 0 && (
        <p data-issue-summary="" className="px-[20px] pt-[2px] pb-[14px] text-para text-ink-2">
          <Parts parts={issue.summary} />
        </p>
      )}
      <dl className="flex flex-col">
        <div className={KV}>
          <dt className="w-[40%] flex-none text-ink-3">Assigned to</dt>
          <dd className="min-w-0 flex-1">
            <Assignee
              name={issue.assignee}
              people={people}
              {...(onAssign === undefined ? {} : { onAssign })}
            />
          </dd>
        </div>
        {issue.facts === undefined ? (
          <>
            <div className={KV}>
              <dt className="w-[40%] flex-none text-ink-3">Priority</dt>
              <dd className="min-w-0 flex-1">{issue.priority}</dd>
            </div>
            <div className={KV}>
              <dt className="w-[40%] flex-none text-ink-3">Severity</dt>
              <dd className="flex min-w-0 flex-1 items-center gap-[8px]">
                {issue.severity.flag !== undefined && (
                  <Icon
                    name="flag"
                    size={13}
                    className={issue.severity.flag === "amber" ? "text-amber" : "text-red"}
                  />
                )}
                {issue.severity.label}
              </dd>
            </div>
            <div className={KV}>
              <dt className="w-[40%] flex-none text-ink-3">Status</dt>
              <dd className="min-w-0 flex-1" data-issue-status="">
                {issue.status}
              </dd>
            </div>
            <div className={KV}>
              <dt className="w-[40%] flex-none text-ink-3">Created by</dt>
              <dd className="min-w-0 flex-1">{issue.createdBy}</dd>
            </div>
          </>
        ) : (
          issue.facts.map((f) => (
            <div key={f.label} className={KV}>
              <dt className="w-[40%] flex-none text-ink-3">{f.label}</dt>
              <dd
                className="min-w-0 flex-1"
                {...(f.label === "Status" ? { "data-issue-status": "" } : {})}
              >
                {f.value}
              </dd>
            </div>
          ))
        )}
      </dl>
      {issue.blocks.length > 0 && (
        <>
          <h4 className={BAND}>What it blocks</h4>
          <p data-issue-blocks="" className="px-[20px] py-[14px] text-para text-ink-2 hairline-t">
            <Parts parts={issue.blocks} />
          </p>
        </>
      )}
      {issue.cells.length > 0 && (
        <>
          <h4 className={BAND}>Workbook cells</h4>
          <ul className="flex flex-col">
            {issue.cells.map((c) => (
              <CellRow key={c.ref} cell={c} />
            ))}
          </ul>
        </>
      )}
      {issue.why !== "" && (
        <>
          <h4 className={BAND}>
            <StatusDisc state="done" size={15} />
            Why This Was Surfaced
          </h4>
          <div data-issue-why="" className="px-[20px] py-[14px] hairline-t">
            <AgentText text={issue.why} />
          </div>
        </>
      )}
      {explainOpen && issue.explain !== undefined && issue.explain !== "" && (
        <>
          <h4 className={BAND}>
            <AgentAvatar />
            Accrued Agent explains
          </h4>
          <div data-issue-explain="" className="px-[20px] py-[14px] hairline-t">
            <AgentText text={issue.explain} />
          </div>
        </>
      )}
      {(issue.links.length > 0 || (issue.entities ?? []).length > 0) && (
        <>
          <h4 className={BAND}>Linked Entities</h4>
          {(issue.entities ?? []).map((e) => (
            <p
              key={e.name}
              data-issue-entity={e.name}
              className="flex items-start gap-[8px] px-[20px] pt-[12px] text-body hairline-t"
            >
              {e.flag === true && (
                <Icon name="flag" size={12} aria-label="Flagged" className="mt-[3px] text-red" />
              )}
              <span className="flex min-w-0 flex-col gap-[2px]">
                <span>{e.name}</span>
                {e.sub !== undefined && <span className="text-meta text-ink-3">{e.sub}</span>}
              </span>
            </p>
          ))}
          {issue.links.length > 0 && (
            <ul
              className={cn(
                "flex flex-wrap gap-[8px] px-[20px] py-[14px]",
                (issue.entities ?? []).length === 0 && "hairline-t",
              )}
            >
              {issue.links.map((l) => (
                <LinkChip key={l.name} link={l} />
              ))}
            </ul>
          )}
          {issue.links.length === 0 && <span className="pb-[12px]" />}
        </>
      )}
    </article>
  );
}

// ---- The footer and the composer ----------------------------------------------------------------

/** Who raised it and so who moves it: the agent can fix it, it is a review point, or it waits on
 * the client. */
export type IssueKind = "agent" | "review" | "client";

export interface IssueFooterProps {
  /** The signed-in viewer. An agent actor draws no footer: these are a person's verbs (INV-1). */
  actor: Actor;
  kind: IssueKind;
  state: IssueState;
  onSetFix?: () => void;
  onExplain?: () => void;
  explainOpen?: boolean;
  onResolve?: () => void;
  onNotApplicable?: () => void;
  onAsk?: () => void;
  /** "Request sent Sep 14": the client was asked; the button is spent. */
  asked?: string;
  onReopen?: () => void;
}

/** The detail's pinned footer (C-17): the person's actions for this issue in its state. */
export function IssueFooter({
  actor,
  kind,
  state,
  onSetFix,
  onExplain,
  explainOpen = false,
  onResolve,
  onNotApplicable,
  onAsk,
  asked,
  onReopen,
}: IssueFooterProps): JSX.Element | null {
  if (!isPerson(actor)) return null;
  const on = (fn: (() => void) | undefined) => (fn === undefined ? {} : { onClick: fn });
  let body: ReactNode;
  if (state === "working") {
    body = (
      <Button variant="tonal" size="footer" disabled className="w-full">
        Waiting on the agent
      </Button>
    );
  } else if (ISSUE_DONE.includes(state)) {
    body = (
      <Button variant="secondary" size="footer" className="w-full" {...on(onReopen)}>
        Reopen
      </Button>
    );
  } else if (kind === "agent") {
    body = (
      <>
        <Button variant="primary" size="footer" className="w-full" {...on(onSetFix)}>
          Set Fix Instructions
        </Button>
        <span className="flex gap-[8px]">
          <Button
            variant="tonal"
            size="footer"
            aria-pressed={explainOpen}
            className="flex-1"
            {...on(onExplain)}
          >
            Explain…
          </Button>
          <Button
            variant="secondary"
            size="footer"
            data-human-only=""
            className="flex-1"
            {...on(onResolve)}
          >
            Mark as Resolved
          </Button>
        </span>
      </>
    );
  } else if (kind === "review") {
    body = (
      <span className="flex gap-[8px]">
        <Button
          variant="primary"
          size="footer"
          icon="check"
          data-human-only=""
          className="flex-1"
          {...on(onResolve)}
        >
          Resolve
        </Button>
        <Button
          variant="secondary"
          size="footer"
          data-human-only=""
          className="flex-1"
          {...on(onNotApplicable)}
        >
          Mark Not Applicable
        </Button>
      </span>
    );
  } else {
    body = (
      <span className="flex gap-[8px]">
        <Button
          variant="primary"
          size="footer"
          disabled={asked !== undefined}
          className="flex-1"
          {...on(onAsk)}
        >
          {asked ?? "Ask the client…"}
        </Button>
        <Button
          variant="secondary"
          size="footer"
          data-human-only=""
          className="flex-1"
          {...on(onResolve)}
        >
          Mark as Resolved
        </Button>
      </span>
    );
  }
  return (
    <div data-issue-footer={kind} className="flex flex-col gap-[8px]">
      {body}
    </div>
  );
}

export interface IssueComposerProps {
  value: string;
  onChange: (value: string) => void;
  /** Send the instruction to the agent (Enter, or the send button). */
  onSend: (text: string) => void;
  className?: string;
}

/** The entity preset's instruction composer: 44 high on the nested fill. */
export function IssueComposer({
  value,
  onChange,
  onSend,
  className,
}: IssueComposerProps): JSX.Element {
  const empty = value.trim() === "";
  return (
    <div
      data-issue-composer=""
      className={cn(
        "flex h-[44px] flex-none items-center gap-[8px] rounded-pane bg-nested pr-[8px] pl-[14px] inset-shadow-hair focus-within:inset-ring-1 focus-within:inset-ring-stroke",
        className,
      )}
    >
      <input
        type="text"
        aria-label="Fix instructions for the agent"
        placeholder="Tell the agent how to fix this…"
        value={value}
        onChange={(e) => {
          onChange(e.target.value);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !empty) {
            e.preventDefault();
            onSend(value.trim());
          }
        }}
        className="min-w-0 flex-1 self-stretch bg-transparent text-body outline-none placeholder:text-ink-3"
      />
      <IconButton
        icon="arrow-up"
        label="Give the agent fix instructions"
        variant="dark"
        disabled={empty}
        onClick={() => {
          if (!empty) onSend(value.trim());
        }}
      />
    </div>
  );
}
