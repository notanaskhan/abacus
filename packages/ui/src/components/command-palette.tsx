import * as DialogPrimitive from "@radix-ui/react-dialog";
import { Search } from "lucide-react";
import { type JSX, type KeyboardEvent, type ReactNode, useEffect, useMemo, useState } from "react";
import { cn } from "../cn";

// Command palette (SHL-02, overlay O5): 640 wide, 88 from the top, a 46-high search, 40-high
// rows in groups, and a footer of key hints. The app supplies the groups; ↑↓ move, Enter runs,
// Escape closes.

export type PaletteItem = {
  id: string;
  label: string;
  hint?: string;
  icon?: ReactNode;
  run: () => void;
};

export type PaletteGroup = { label: string; items: PaletteItem[] };

export function CommandPalette({
  open,
  onOpenChange,
  query,
  onQueryChange,
  groups,
  loading = false,
  placeholder = "Search or jump to…",
  empty,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  query: string;
  onQueryChange: (query: string) => void;
  groups: PaletteGroup[];
  loading?: boolean;
  placeholder?: string;
  empty?: ReactNode;
}): JSX.Element {
  const shown = useMemo(() => groups.filter((g) => g.items.length > 0), [groups]);
  const flat = useMemo(() => shown.flatMap((g) => g.items), [shown]);
  const [active, setActive] = useState(0);
  useEffect(() => {
    setActive(0);
  }, [query]);
  const current = flat[Math.min(active, flat.length - 1)];
  const choose = (item: PaletteItem): void => {
    onOpenChange(false);
    item.run();
  };
  const onKey = (e: KeyboardEvent<HTMLInputElement>): void => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (flat.length === 0) return;
      const step = e.key === "ArrowDown" ? 1 : -1;
      setActive((i) => (i + step + flat.length) % flat.length);
    } else if (e.key === "Enter" && current !== undefined) {
      e.preventDefault();
      choose(current);
    }
  };
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-[rgba(43,31,23,.22)]" />
        <DialogPrimitive.Content
          aria-describedby={undefined}
          className="fixed top-[88px] left-1/2 z-50 flex max-h-[calc(100vh-120px)] w-[calc(100%-2rem)] max-w-[640px] -translate-x-1/2 flex-col overflow-hidden rounded-dialog bg-card shadow-modal"
        >
          <DialogPrimitive.Title className="sr-only">Command palette</DialogPrimitive.Title>
          <div className="flex h-[46px] shrink-0 items-center gap-2.5 border-b-[0.5px] border-hair px-4">
            <Search aria-hidden="true" className="size-4 text-ink-3" />
            <input
              autoFocus
              role="combobox"
              aria-expanded="true"
              aria-controls="palette-results"
              aria-activedescendant={current ? `palette-${current.id}` : undefined}
              aria-label="Search"
              value={query}
              placeholder={placeholder}
              onChange={(e) => {
                onQueryChange(e.target.value);
              }}
              onKeyDown={onKey}
              className="h-full flex-1 border-0 bg-transparent text-[14.5px] outline-none placeholder:text-ink-4"
            />
            {loading && <span className="text-[11.5px] text-ink-3">Searching…</span>}
          </div>
          <div
            id="palette-results"
            role="listbox"
            className="min-h-0 flex-1 overflow-y-auto py-1.5"
          >
            {shown.length === 0 ? (
              <div className="px-4 py-8 text-center text-[13px] text-ink-3">
                {empty ?? "No results"}
              </div>
            ) : (
              shown.map((g) => (
                <div key={g.label} role="group" aria-label={g.label}>
                  <div className="px-4 pt-2 pb-1 text-[11px] font-medium tracking-[0.02em] text-ink-3 uppercase">
                    {g.label}
                  </div>
                  {g.items.map((item) => {
                    const on = item === current;
                    return (
                      <div
                        key={item.id}
                        id={`palette-${item.id}`}
                        role="option"
                        aria-selected={on}
                        onMouseMove={() => {
                          setActive(flat.indexOf(item));
                        }}
                        onClick={() => {
                          choose(item);
                        }}
                        className={cn(
                          "mx-1.5 flex h-10 cursor-pointer items-center gap-2.5 rounded-[7px] px-2.5 text-[13.5px]",
                          on && "bg-sel-bg",
                        )}
                      >
                        {item.icon !== undefined && (
                          <span aria-hidden="true" className="flex size-4 text-ink-3">
                            {item.icon}
                          </span>
                        )}
                        <span className="min-w-0 flex-1 truncate">{item.label}</span>
                        {item.hint !== undefined && (
                          <span className="max-w-[45%] truncate text-[12px] text-ink-3">
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
          <div className="flex h-9 shrink-0 items-center gap-4 border-t-[0.5px] border-hair bg-shell px-4 text-[11.5px] text-ink-3">
            <span>↑↓ to move</span>
            <span>↵ to open</span>
            <span>esc to close</span>
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
