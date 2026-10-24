import { useVirtualizer } from "@tanstack/react-virtual";
import { type RefObject, useCallback } from "react";

// E4 virtualisation (F-05-T52; plan 04 §4.3 E4 and §11 "Virtualise at ≥ 200 rows"): above 200
// rows a table renders only the rows in its scroll viewport (plus an overscan) between two spacer
// rows, on @tanstack/react-virtual. Row heights are the grammar's exact heights (the kit keeps
// them exact so a fixed-height virtualiser works), so the scrollbar is right before any row is
// seen. The header and group bands stay sticky (the grammar's classes), and `aria-rowindex` keeps
// every row's place for a screen reader.

/** At this many rows and above, a table virtualises. */
export const VIRTUAL_THRESHOLD = 200;
/** The scroll viewport of a virtualised table, unless the screen gives one. */
export const VIRTUAL_HEIGHT = 560;

export interface RowWindow {
  virtual: boolean;
  /** The indexes to render, in order. */
  indexes: readonly number[];
  /** Spacer heights above and below the rendered rows. */
  before: number;
  after: number;
  /** Bring a row into view (selection by keyboard). */
  scrollTo: (index: number) => void;
}

export function useRowWindow({
  count,
  size,
  scroller,
  enabled,
  height,
}: {
  count: number;
  /** The row's exact height. */
  size: (index: number) => number;
  scroller: RefObject<HTMLElement | null>;
  /** Default: `count` reaches VIRTUAL_THRESHOLD. */
  enabled?: boolean | undefined;
  height: number;
}): RowWindow {
  const virtual = enabled ?? count >= VIRTUAL_THRESHOLD;
  const v = useVirtualizer<HTMLElement, Element>({
    count: virtual ? count : 0,
    enabled: virtual,
    getScrollElement: () => scroller.current,
    estimateSize: size,
    overscan: 12,
    // A first render gets a viewport before the scroller is laid out.
    initialRect: { width: 0, height },
  });
  const scrollTo = useCallback(
    (index: number) => {
      if (virtual) v.scrollToIndex(index, { align: "auto" });
    },
    [v, virtual],
  );
  if (!virtual) {
    return {
      virtual,
      indexes: Array.from({ length: count }, (_, i) => i),
      before: 0,
      after: 0,
      scrollTo,
    };
  }
  const items = v.getVirtualItems();
  const first = items[0];
  const last = items[items.length - 1];
  return {
    virtual,
    indexes: items.map((i) => i.index),
    before: first?.start ?? 0,
    after: last === undefined ? 0 : v.getTotalSize() - last.end,
    scrollTo,
  };
}
