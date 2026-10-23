import { type JSX, type ReactNode, useId } from "react";
import { cn } from "../cn";
import { Button } from "../components/button";
import { FilterChip, type PickerOption, SearchField } from "../components/inputs";
import { StatusTile, type StatusTileVariant } from "../components/progress";
import { type EmptyContent, type ViewState, ViewStateBody } from "../components/view-state";
import { count as formatCount } from "../format";
import type { IconName } from "../icons";
import { Icon } from "../icons";

// T1 Index list (F-05-T28; plan 04 §4 templates; F-05 F1; the T1 handoff): a filter bar of split
// chips, an optional row of status tiles that filter, and one full-width pane with search, the
// count, a centred title and "+ New …" over a hairline table. Everything it shows comes from a
// typed view model over the list envelope (P-36: `{items, next_cursor, total, counts, facets}`):
// the tiles read `counts`, which the server computes over the filters minus the tile, so a tile
// never counts itself out; the count line reads `total`. The template adds nothing up.
//
// States (T1a to T1e): ready, ready with a chip and a tile set, empty (tiles and count hidden),
// filtered-empty, loading (real header and column heads, 8 skeleton rows).

/** The list envelope (P-36, plan 03 §5.2). */
export interface ListEnvelope<Row> {
  items: readonly Row[];
  next_cursor: string | null;
  total: number;
  total_capped?: boolean;
  /** Per status code, over the filters minus `tile`. */
  counts: Readonly<Record<string, number>>;
  facets?: Readonly<Record<string, readonly { value: string; label: string; n: number }[]>>;
}

export interface IndexChip {
  key: string;
  label: string;
  icon?: IconName;
  options: readonly PickerOption[];
  /** The chosen value; null is the chip's default (not filtering). */
  value: string | null;
  placeholder?: string;
}

export interface IndexTile {
  /** The status code the tile filters by, and its key in `counts`. */
  code: string;
  label: string;
  variant?: StatusTileVariant;
}

export interface IndexColumn<Row> {
  key: string;
  header: string;
  align?: "left" | "right";
  /** px; omitted is auto. */
  width?: number;
  cell: (row: Row) => ReactNode;
}

export interface IndexListProps<Row> {
  /** The pane's centred title: "Tax Returns". */
  title: string;
  /** Plural, lower case, for the search field and messages: "returns". */
  noun: string;
  /** ready (with `envelope`), loading, empty, filtered-empty, error, restricted or flag-off. */
  state: ViewState;
  envelope?: ListEnvelope<Row> | undefined;
  columns: readonly IndexColumn<Row>[];
  rowKey: (row: Row) => string;
  /** A row with a second line is 44 high instead of 38. */
  twoLine?: (row: Row) => boolean;
  selected?: string | null;
  onSelect?: (row: Row) => void;
  onOpen?: (row: Row) => void;

  chips?: readonly IndexChip[];
  onChip?: (key: string, value: string | null) => void;
  tiles?: readonly IndexTile[];
  /** The selected tile's code. */
  tile?: string | null;
  onTile?: (code: string | null) => void;
  /** A right-aligned summary at the end of the tile row: "224 returns · 79 open". */
  summary?: string;
  /** Clears every chip, the tile and the search. */
  onClear?: () => void;

  query?: string;
  onQuery?: (query: string) => void;
  /** The search field's placeholder ("Search clients, entities, contacts"); "Search" if absent. */
  searchPlaceholder?: string;
  /** "+ New Return…" */
  newLabel?: string;
  onNew?: () => void;
  /** Secondary header buttons before "+ New …" ("Import…"). */
  actions?: ReactNode;
  /** Replaces the "Showing n of total" line when the screen words its own count ("184 clients",
   * DEC-47). Shown in the same states the default line is. */
  countText?: string;
  /** Under the last row, inside the ready body: "Load more" for a keyset list. */
  footer?: ReactNode;
  /** What T1c says. */
  empty: EmptyContent;
}

export function IndexList<Row>({
  title,
  noun,
  state,
  envelope,
  columns,
  rowKey,
  twoLine,
  selected = null,
  onSelect,
  onOpen,
  chips = [],
  onChip,
  tiles,
  tile = null,
  onTile,
  summary,
  onClear,
  query = "",
  onQuery,
  searchPlaceholder,
  newLabel,
  onNew,
  actions,
  countText,
  footer,
  empty,
}: IndexListProps<Row>): JSX.Element {
  const titleId = useId();
  const isEmpty = state.kind === "empty";
  const filtering = chips.some((c) => c.value !== null) || tile !== null || query !== "";
  const items = envelope?.items ?? [];
  const showCount = !isEmpty && state.kind === "ready" && envelope !== undefined;
  const showTiles = tiles !== undefined && tiles.length > 0 && !isEmpty;
  // One column plan for the head and the body tables, so a fixed layout sizes both alike (a
  // body row's cell widths alone are not read when the table has a caption).
  const colgroup = (
    <colgroup>
      {columns.map((c) => (
        <col key={c.key} style={c.width === undefined ? undefined : { width: c.width }} />
      ))}
      <col style={{ width: 28 }} />
    </colgroup>
  );

  return (
    <div data-template="T1" className="flex min-h-0 flex-1 flex-col bg-shell">
      <div
        role="toolbar"
        aria-label="Filters"
        className="flex h-[50px] shrink-0 items-center gap-[8px] px-[12px]"
      >
        {chips.map((c) => (
          <FilterChip
            key={c.key}
            label={c.label}
            options={c.options}
            value={c.value}
            onChange={(v) => onChip?.(c.key, v)}
            {...(c.icon === undefined ? {} : { icon: c.icon })}
            {...(c.placeholder === undefined ? {} : { placeholder: c.placeholder })}
          />
        ))}
        {filtering && onClear !== undefined && (
          <Button variant="ghost" size="sm" onClick={onClear}>
            Clear
          </Button>
        )}
      </div>

      {showTiles && (
        <div
          role="group"
          aria-label="Status"
          className="flex shrink-0 items-end gap-[8px] px-[12px] pt-[4px]"
        >
          {tiles.map((t) => (
            <StatusTile
              key={t.code}
              label={t.label}
              count={envelope?.counts[t.code] ?? 0}
              selected={tile === t.code}
              onSelect={() => onTile?.(tile === t.code ? null : t.code)}
              {...(t.variant === undefined ? {} : { variant: t.variant })}
            />
          ))}
          {summary !== undefined && (
            <span className="ml-auto pb-[4px] text-dense text-ink-3">{summary}</span>
          )}
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col px-[12px] pt-[10px] pb-[12px]">
        <section
          aria-labelledby={titleId}
          className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-pane bg-card shadow-e2"
        >
          <header className="relative flex h-[46px] shrink-0 items-center gap-[10px] border-b-[0.5px] border-hair px-[10px]">
            <SearchField
              label={`Search ${noun}`}
              value={query}
              onChange={(v) => onQuery?.(v)}
              {...(searchPlaceholder === undefined ? {} : { placeholder: searchPlaceholder })}
              className="w-[220px]"
            />
            {showCount && (
              <span data-count="" className="text-dense text-ink-3">
                {countText ??
                  `Showing ${formatCount(items.length)} of ${formatCount(envelope.total)}${envelope.total_capped === true ? "+" : ""}`}
              </span>
            )}
            <h2
              id={titleId}
              className="pointer-events-none absolute inset-x-0 text-center text-pane font-medium"
            >
              {title}
            </h2>
            {actions !== undefined && (
              <span className="ml-auto flex items-center gap-[8px]">{actions}</span>
            )}
            {newLabel !== undefined && (
              <Button
                variant="primary"
                icon="plus"
                className={actions === undefined ? "ml-auto" : undefined}
                onClick={onNew}
                opensDialog
              >
                {newLabel}
              </Button>
            )}
          </header>
          <table className="w-full shrink-0 table-fixed border-collapse">
            {colgroup}
            <thead>
              <tr>
                {columns.map((c) => (
                  <th
                    key={c.key}
                    scope="col"
                    style={c.width === undefined ? undefined : { width: c.width }}
                    className={cn(
                      "h-[30px] truncate border-b-[0.5px] border-hair bg-band-hd px-[14px] text-th font-medium text-ink-2",
                      c.align === "right" ? "text-right" : "text-left",
                    )}
                  >
                    {c.header}
                  </th>
                ))}
                <th
                  aria-hidden="true"
                  className="w-[28px] border-b-[0.5px] border-hair bg-band-hd"
                />
              </tr>
            </thead>
          </table>
          <ViewStateBody state={state} rows="list" skeletonCount={8} empty={empty} noun={noun}>
            {() => (
              <>
                <table className="w-full table-fixed border-collapse">
                  <caption className="sr-only">{title}</caption>
                  {colgroup}
                  <tbody>
                    {items.map((row) => {
                      const id = rowKey(row);
                      const isSelected = id === selected;
                      return (
                        <tr
                          key={id}
                          aria-selected={isSelected}
                          data-row={id}
                          onClick={() => onSelect?.(row)}
                          onDoubleClick={() => onOpen?.(row)}
                          className={cn(
                            "group cursor-default border-b-[0.5px] border-hair text-body transition-colors duration-200",
                            twoLine?.(row) === true ? "h-[44px]" : "h-[38px]",
                            isSelected ? "bg-sel-bg font-medium" : "hover:bg-nested",
                          )}
                        >
                          {columns.map((c) => (
                            <td
                              key={c.key}
                              style={c.width === undefined ? undefined : { width: c.width }}
                              className={cn(
                                "truncate px-[14px]",
                                c.align === "right" ? "text-right tabular-nums" : "text-left",
                              )}
                            >
                              {c.cell(row)}
                            </td>
                          ))}
                          <td className="w-[28px] pr-[10px] text-ink-3">
                            {onOpen !== undefined && (
                              <button
                                type="button"
                                aria-label={`Open ${rowLabel(row, columns)}`}
                                onClick={(e) => {
                                  e.stopPropagation();
                                  onOpen(row);
                                }}
                                className="relative flex size-[24px] items-center justify-center rounded-pill opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
                              >
                                <Icon name="chevron-right" size={12} />
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
                {footer !== undefined && (
                  <div data-list="footer" className="flex shrink-0 justify-center py-[12px]">
                    {footer}
                  </div>
                )}
              </>
            )}
          </ViewStateBody>
        </section>
      </div>
    </div>
  );
}

function rowLabel<Row>(row: Row, columns: readonly IndexColumn<Row>[]): string {
  const first = columns[0]?.cell(row);
  return typeof first === "string" ? first : "row";
}
