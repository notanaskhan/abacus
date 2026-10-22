import {
  type JSX,
  type KeyboardEvent,
  type ReactNode,
  useEffect,
  useId,
  useMemo,
  useState,
} from "react";
import { Wordmark } from "../brand/wordmark";
import { cn } from "../cn";
import { Icon } from "../icons";
import { FrameMode, FrameTitle } from "./frame";
import { Layer } from "./layer";

// CommandPalette (O5, C-00 spec 01, SHL-02's frame): 560 wide, 96 from the top, a nested #EFEEEB
// tray of radius 15 around a white body of radius 11. A 46-high search row with an `esc` keycap, a
// list of groups (11.5 ink-3 labels) of 36-high rows (icon, label, meta), and a 32-high footer with
// the wordmark and the key hints. The app supplies the groups; typing filters them in the app (the
// palette only draws), ↑ ↓ move the highlight and stop at the ends, ↵ runs the row, Escape closes.
// It is a layer of the OverlayStack like any dialog, so Escape closes it and focus returns to
// whatever opened it (the Go… pill or ⌘K).

export interface PaletteItem {
  id: string;
  label: string;
  /** The grey words on the right: "Audit · Planning", "Page". */
  hint?: string;
  icon?: ReactNode;
  run: () => void;
}

export interface PaletteGroup {
  label: string;
  items: PaletteItem[];
}

export interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  query: string;
  onQueryChange: (query: string) => void;
  groups: PaletteGroup[];
  loading?: boolean;
  placeholder?: string;
  /** What the list says when nothing matches; the default quotes the query. */
  empty?: ReactNode;
  /** Hold the palette open in place for a specimen: no layer, no scrim, no trap. */
  forceState?: "open";
}

const BOX =
  "flex w-[560px] max-w-full flex-col gap-[4px] rounded-menu bg-nested p-[4px] shadow-menu";

function Keycap({ children }: { children: ReactNode }): JSX.Element {
  return (
    <kbd className="inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-value bg-card px-[5px] font-sans text-micro text-ink-2 shadow-e1">
      {children}
    </kbd>
  );
}

function Palette({
  query,
  onQueryChange,
  groups,
  loading,
  placeholder,
  empty,
  onPick,
  live,
}: Required<Pick<CommandPaletteProps, "query" | "onQueryChange" | "groups" | "loading">> &
  Pick<CommandPaletteProps, "placeholder" | "empty"> & {
    onPick: (item: PaletteItem) => void;
    live: boolean;
  }): JSX.Element {
  const listId = useId();
  const shown = useMemo(() => groups.filter((g) => g.items.length > 0), [groups]);
  const flat = useMemo(() => shown.flatMap((g) => g.items), [shown]);
  const [active, setActive] = useState(0);
  useEffect(() => {
    setActive(0);
  }, [query]);
  const current = flat[Math.min(active, flat.length - 1)];

  const onKey = (e: KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (flat.length === 0) return;
      const step = e.key === "ArrowDown" ? 1 : -1;
      setActive((i) => Math.min(flat.length - 1, Math.max(0, i + step)));
    } else if (e.key === "Enter" && current !== undefined) {
      e.preventDefault();
      onPick(current);
    }
  };

  return (
    <>
      <FrameTitle className="sr-only">Command palette</FrameTitle>
      <div className="overflow-hidden rounded-menu-inner bg-card">
        <div className="flex h-[46px] items-center gap-[10px] border-b-[0.5px] border-hair pr-[12px] pl-[14px]">
          <Icon name="search" size={15} className="text-ink-3" />
          <input
            role="combobox"
            aria-expanded="true"
            aria-controls={listId}
            {...(current === undefined
              ? {}
              : { "aria-activedescendant": `${listId}-${current.id}` })}
            aria-label="Search"
            value={query}
            placeholder={placeholder}
            readOnly={!live}
            onChange={(e) => {
              onQueryChange(e.target.value);
            }}
            onKeyDown={onKey}
            className="h-full min-w-0 flex-1 border-0 bg-transparent p-0 text-tab outline-none placeholder:text-ink-3"
          />
          {loading && <span className="text-meta text-ink-3">Searching…</span>}
          <Keycap>esc</Keycap>
        </div>
        <div
          id={listId}
          {...(shown.length === 0 ? {} : { role: "listbox", "aria-label": "Results" })}
          className="max-h-[360px] overflow-auto px-[4px] pt-[4px] pb-[6px]"
        >
          {shown.length === 0 ? (
            <div className="px-[12px] py-[22px] text-center text-dense text-ink-2">
              {empty ?? `No matches for “${query}”`}
            </div>
          ) : (
            shown.map((g) => (
              <div key={g.label} role="group" aria-label={g.label}>
                <div className="px-[10px] pt-[9px] pb-[4px] text-meta text-ink-3">{g.label}</div>
                {g.items.map((item) => {
                  const on = item === current;
                  return (
                    <div
                      key={item.id}
                      id={`${listId}-${item.id}`}
                      role="option"
                      aria-selected={on}
                      onMouseMove={() => {
                        setActive(flat.indexOf(item));
                      }}
                      onClick={() => {
                        onPick(item);
                      }}
                      className={cn(
                        "flex h-[36px] w-full cursor-pointer items-center gap-[10px] rounded-tile px-[10px] text-body transition-colors",
                        on && "bg-nav-fill",
                      )}
                    >
                      {item.icon !== undefined && (
                        <span aria-hidden="true" className="flex size-[14px] text-ink-2">
                          {item.icon}
                        </span>
                      )}
                      <span className="min-w-0 flex-1 truncate">{item.label}</span>
                      {item.hint !== undefined && (
                        <span className="max-w-[45%] truncate text-meta text-ink-3">
                          {item.hint}
                        </span>
                      )}
                    </div>
                  );
                })}
              </div>
            ))
          )}
        </div>
      </div>
      <div className="flex h-[32px] items-center justify-between pr-[10px] pl-[12px]">
        <Wordmark size={12.5} />
        <div className="flex items-center gap-[6px] text-meta text-ink-3">
          <Keycap>↑↓</Keycap>
          <span className="mr-[6px]">Navigate</span>
          <Keycap>↵</Keycap>
          <span>Open</span>
        </div>
      </div>
    </>
  );
}

export function CommandPalette({
  open,
  onOpenChange,
  query,
  onQueryChange,
  groups,
  loading = false,
  placeholder = "Search clients, engagements and actions",
  empty,
  forceState,
}: CommandPaletteProps): JSX.Element {
  const body = (live: boolean, onPick: (item: PaletteItem) => void): JSX.Element => (
    <Palette
      query={query}
      onQueryChange={onQueryChange}
      groups={groups}
      loading={loading}
      placeholder={placeholder}
      empty={empty}
      onPick={onPick}
      live={live}
    />
  );
  if (forceState === "open") {
    return (
      <div role="group" aria-label="Command palette" className={BOX}>
        <FrameMode live={false}>{body(false, () => undefined)}</FrameMode>
      </div>
    );
  }
  return (
    <Layer
      kind="palette"
      open={open}
      onOpenChange={onOpenChange}
      title="Command palette"
      scrim="dialog"
      centred
      scrimClassName="flex items-start justify-center pt-[96px]"
      className={BOX}
      motion="motion-reveal data-[state=closed]:motion-fade-out"
      initialFocus="field"
      noDescription
    >
      {body(true, (item) => {
        onOpenChange(false);
        item.run();
      })}
    </Layer>
  );
}
