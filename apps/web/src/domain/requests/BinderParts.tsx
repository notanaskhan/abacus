// BND-02's L3 parts (P-06 §5.2): the rail's category list with olive ticks and "n open", and the
// firm's request row (C-16 drawn inline, the README's build note): the document glyph, the title,
// the second line, the status line with the prior-year tag, and the right cluster (Eye toggle, due
// date, ···). Words beside every state; colour never alone. Data comes in through props.

import type { BinderCategoryOut, BinderRequestRowOut, LiveItemOut } from "@abacus/api-client";
import {
  CATEGORIES,
  DocGlyph,
  Icon,
  type IconName,
  Menu,
  type MenuItem,
  Pill,
  RegistryStatus,
  Spinner,
  StatusDisc,
  Tag,
  cn,
} from "@abacus/ui";
import type { JSX, ReactNode } from "react";

/** A category's glyph by its portal name (C-16's nine). */
export function categoryIcon(name: string): IconName {
  return CATEGORIES.find((c) => c.label === name)?.icon ?? "folder";
}

export interface CategoryListProps {
  title: string;
  categories: readonly BinderCategoryOut[];
  /** "1 open". */
  openLabel: (n: number) => string;
  nothingLabel: string;
  selected: string | null;
  onSelect: (id: string) => void;
}

/** "Categories" and its 39 rows: the olive tick when every request is in, "n open" when not, an
 * ink-4 dash when nothing is requested. A click jumps the canvas to the category. */
export function CategoryList({
  title,
  categories,
  openLabel,
  nothingLabel,
  selected,
  onSelect,
}: CategoryListProps): JSX.Element {
  const sorted = [...categories].sort((a, b) => a.position - b.position);
  return (
    <div data-part="categories" className="flex flex-col">
      <div className="px-[14px] pt-[12px] pb-[6px] text-section font-medium text-ink">{title}</div>
      <ul aria-label={title} className="flex flex-col px-[6px] pb-[10px]">
        {sorted.map((c, i) => {
          const on = c.id === selected;
          const open = c.total_count - c.done_count;
          const none = c.total_count === 0;
          return (
            <li key={c.id} className={cn(i !== 0 && !on && "hairline-t")}>
              <button
                type="button"
                aria-current={on ? "true" : undefined}
                title={none ? nothingLabel : undefined}
                data-done={!none && open === 0 ? "true" : "false"}
                onClick={() => {
                  onSelect(c.id);
                }}
                className={cn(
                  "flex h-[39px] w-full items-center gap-[10px] rounded-tile pr-[6px] pl-[8px] text-left text-section font-normal tracking-normal hover:bg-nav-fill",
                  on && "bg-sel-bg font-medium hover:bg-sel-bg",
                )}
              >
                <Icon name={categoryIcon(c.name)} size={15} className="text-ink-3" />
                <span className="min-w-0 flex-1 truncate">{c.name}</span>
                {none ? (
                  <span className="text-meta text-ink-4" aria-label={nothingLabel}>
                    —
                  </span>
                ) : open === 0 ? (
                  <StatusDisc state="done" size={17} />
                ) : (
                  <span className="text-dense text-ink-3">{openLabel(open)}</span>
                )}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export interface RequestLineWords {
  requested: string;
  notPublished: string;
  firmDraft: string;
  ignored: string;
  internalOnly: string;
  waiting: (n: string) => string;
  waitingHint: string;
  uploading: (n: number) => string;
  /** "Due Aug 31 · 14 days late", or null when not overdue. */
  late: string | null;
  /** "Requested Feb 3", or null. */
  requestedOn: string | null;
  /** "From 2024 return", or null. */
  tag: string | null;
  /** The client's Ignore reason in their words, or null. */
  ignoreReason: string | null;
  visibleLabel: string;
  menuLabel: string;
  /** R2: "Linked (1)", the count's accessible name; its click opens SHL-21 (planned, DV-6). */
  linked: string;
  /** R2: "Evidence screening · Passed · 2 checks" on a client upload, or null for no glyph. */
  screening: string | null;
}

export interface BinderRequestRowProps {
  row: BinderRequestRowOut;
  live: LiveItemOut | undefined;
  words: RequestLineWords;
  /** "Mar 15". */
  due: string;
  selected: boolean;
  onSelect: () => void;
  onVisible: (visible: boolean) => void;
  canChangeVisibility: boolean;
  menu: MenuItem[][];
  /** The screening glyph opens the dock's ScreeningCard (SHL-20). */
  onScreening?: () => void;
}

/** The 12px screening glyph (R2): olive ✓ Passed · amber triangle Flagged · ring Not screened. */
function ScreeningGlyph({
  status,
  label,
  onOpen,
}: {
  status: NonNullable<BinderRequestRowOut["screening"]>;
  label: string;
  onOpen: (() => void) | undefined;
}): JSX.Element {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      data-screening-glyph={status}
      onClick={(event) => {
        event.stopPropagation();
        onOpen?.();
      }}
      className="inline-flex size-[18px] items-center justify-center rounded-pill hover:bg-nested"
    >
      {status === "passed" ? (
        <StatusDisc state="done" size={13} />
      ) : status === "flagged" ? (
        <Icon name="triangle-alert" size={12} className="text-amber" />
      ) : (
        <StatusDisc state="todo" size={13} />
      )}
    </button>
  );
}

/** One request, firm side (BND-02; C-16 drawn inline). */
export function BinderRequestRow({
  row,
  live,
  words,
  due,
  selected,
  onSelect,
  onVisible,
  canChangeVisibility,
  menu,
  onScreening,
}: BinderRequestRowProps): JSX.Element {
  const satisfied = row.status === "received";
  const ignored = row.client_ignored_at != null;
  const status = statusLine(row, live, words, ignored);
  return (
    <div
      data-request={row.id}
      data-selected={selected ? "true" : undefined}
      onClick={onSelect}
      className={cn(
        "flex cursor-pointer items-start gap-[10px] pt-[10px] pr-[12px] pb-[11px] pl-[14px] hairline-t",
        selected ? "bg-sel-bg" : "hover:bg-nav-fill",
      )}
    >
      <DocGlyph filled={satisfied} />
      <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
        {/* The title selects the row for the keyboard; a click anywhere on the row does too. */}
        <button
          type="button"
          aria-pressed={selected}
          onClick={(event) => {
            event.stopPropagation();
            onSelect();
          }}
          className={cn(
            "text-left text-section font-medium outline-offset-2",
            row.status === "not_applicable" ? "text-ink-3" : "text-ink",
          )}
        >
          {row.title}
        </button>
        {words.requestedOn !== null && !satisfied && (
          <span className="text-dense text-ink-2">{words.requestedOn}</span>
        )}
        <span className="flex flex-wrap items-center gap-[8px]">
          {status}
          {row.screening != null && words.screening !== null && (
            <ScreeningGlyph status={row.screening} label={words.screening} onOpen={onScreening} />
          )}
          {words.tag !== null && <Tag>{words.tag}</Tag>}
        </span>
        {ignored && words.ignoreReason !== null && (
          <span className="text-dense text-ink-2">{words.ignoreReason}</span>
        )}
        {!row.client_visible && (
          <span data-helper="internal-only" className="text-dense text-ink-3">
            {words.internalOnly}
          </span>
        )}
      </div>
      <div className="flex flex-none items-center gap-[10px]">
        <span
          data-linked={row.linked_count ?? 0}
          aria-label={words.linked}
          title={words.linked}
          className="inline-flex items-center gap-[3px] text-cell tabular-nums"
        >
          <Icon name="link-2" size={12} className="text-ink-3" />
          {row.linked_count == null || row.linked_count === 0 ? (
            <span className="text-ink-4">—</span>
          ) : (
            <span className="text-ink-3">{row.linked_count}</span>
          )}
        </span>
        <button
          type="button"
          aria-pressed={row.client_visible}
          aria-label={words.visibleLabel}
          disabled={!canChangeVisibility}
          onClick={(event) => {
            event.stopPropagation();
            onVisible(!row.client_visible);
          }}
          className={cn(
            "flex size-[22px] items-center justify-center rounded-pill hover:bg-nested",
            row.client_visible ? "text-ink-2" : "text-ink-4",
          )}
        >
          <Icon name={row.client_visible ? "eye" : "eye-off"} size={14} />
        </button>
        <span className="w-[48px] text-right text-meta text-ink-3 tabular-nums">{due}</span>
        <Menu
          label={words.menuLabel}
          align="end"
          sections={menu}
          trigger={
            <button
              type="button"
              aria-label={words.menuLabel}
              onClick={(event) => {
                event.stopPropagation();
              }}
              className="flex size-[24px] items-center justify-center rounded-pill text-ink-3 hover:bg-nested"
            >
              <Icon name="ellipsis" size={14} />
            </button>
          }
        />
      </div>
    </div>
  );
}

/** The status line: a pill or a disc with words, plus what the live poll says. */
function statusLine(
  row: BinderRequestRowOut,
  live: LiveItemOut | undefined,
  words: RequestLineWords,
  ignored: boolean,
): ReactNode {
  if (ignored) {
    return (
      <Pill variant="muted" size="sm">
        {words.ignored}
      </Pill>
    );
  }
  if (row.status === "received" && row.kind === "firm_provided") {
    return (
      <Pill variant="amber" size="sm">
        {words.firmDraft}
      </Pill>
    );
  }
  if (row.status === "draft") {
    return (
      <span className="flex items-center gap-[6px] text-dense text-ink-3">
        <StatusDisc state="todo" size={15} />
        {words.notPublished}
      </span>
    );
  }
  if (row.status !== "requested") {
    return <RegistryStatus object="request" code={row.status} size="sm" />;
  }
  const waiting = live?.inbox_waiting ?? 0;
  const uploading = live?.uploading_files ?? 0;
  return (
    <>
      <span className="flex items-center gap-[6px] text-dense text-ink-3">
        <StatusDisc state="todo" size={15} />
        {words.requested}
      </span>
      {words.late !== null && <span className="text-dense text-red-ink">{words.late}</span>}
      {waiting > 0 && (
        <span
          data-live="waiting"
          title={words.waitingHint}
          className="flex items-center gap-[6px] text-dense text-amber-ink"
        >
          <span aria-hidden="true" className="size-[8px] rounded-pill bg-amber" />
          {words.waiting(String(waiting))}
        </span>
      )}
      {uploading > 0 && (
        <span data-live="uploading" className="flex items-center text-amber-ink">
          <Spinner size={12} label={words.uploading(uploading)} className="text-amber-ink" />
        </span>
      )}
    </>
  );
}
