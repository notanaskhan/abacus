import * as PopoverPrimitive from "@radix-ui/react-popover";
import { type JSX, type ReactNode, useMemo } from "react";
import { cn } from "../cn";
import { useMotion } from "../motion";
import { useOverlayLayer } from "../overlays/stack-react";
import type { MatchState, MatchStore } from "./match-store";
import { useMatchState, useMatchStore } from "./match";
import type { CitationPayload } from "./types";

// E2 AnchoredPopoverHost (F-05-T41; plan 04 §4.3 E2): one per page or scope. It reads the match
// store and, while the active match carries a payload, opens a Radix popover whose anchor is a
// virtual element: `MatchStore.anchorFor()`, the lit cell, not the trigger (a citation with nothing
// lit on the page anchors to its marker). It sits 8px to the right, top-aligned, flips left when
// there is no room, and enters with a 4px rise over 260ms. It is a layer of the OverlayStack, so
// Escape reaches it in order; closing returns focus to where the match came from. No direct
// floating-ui dependency.

export interface AnchoredPopoverHostProps {
  /** What the popover holds for the active payload (the C-07 CitationPopover, SHL-09, C-37 ...). */
  render: (payload: CitationPayload, state: MatchState<CitationPayload>) => ReactNode;
  /** Width in px: 372 for a citation. */
  width?: number;
  side?: "right" | "left";
  /** The popover's accessible name. */
  label?: string;
}

function virtualAnchor(store: MatchStore<CitationPayload>): {
  current: { getBoundingClientRect: () => DOMRect };
} {
  return {
    current: {
      getBoundingClientRect: () => {
        const el = store.anchorFor();
        return el === null ? new DOMRect(0, 0, 0, 0) : el.getBoundingClientRect();
      },
    },
  };
}

export function AnchoredPopoverHost({
  render,
  width = 372,
  side = "right",
  label = "Citation",
}: AnchoredPopoverHostProps): JSX.Element {
  const store = useMatchStore();
  const state = useMatchState();
  const animate = useMotion();
  const open = state.payload !== null;
  const anchor = useMemo(() => virtualAnchor(store), [store]);
  const layer = useOverlayLayer({
    kind: "popover",
    modal: false,
    open,
    onOpenChange: (next) => {
      if (!next) store.escape();
    },
  });
  const anchored = open ? store.anchorFor() : null;
  return (
    <PopoverPrimitive.Root open={open} onOpenChange={layer.onRootOpenChange}>
      <PopoverPrimitive.Anchor virtualRef={anchor} />
      <PopoverPrimitive.Portal>
        {state.payload !== null && (
          <PopoverPrimitive.Content
            // A new anchor (a step to the next source) measures afresh.
            key={state.id ?? "origin"}
            data-overlay="popover"
            data-popover="anchored"
            data-anchored={anchored === state.origin ? "origin" : "match"}
            side={side}
            align="start"
            sideOffset={8}
            collisionPadding={8}
            aria-label={label}
            style={{ width, zIndex: layer.panelZ }}
            className={cn(
              "max-w-[calc(100vw-16px)] overflow-hidden rounded-pane bg-card shadow-pop outline-none",
              animate && "motion-cite-in",
            )}
            onOpenAutoFocus={(event) => {
              event.preventDefault();
            }}
            onCloseAutoFocus={(event) => {
              event.preventDefault();
            }}
            onEscapeKeyDown={layer.onEscape}
            onPointerDownOutside={layer.onlyTop}
            onPointerEnter={store.hold}
            onPointerLeave={() => {
              store.release("marker");
            }}
          >
            {render(state.payload, state)}
          </PopoverPrimitive.Content>
        )}
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  );
}
