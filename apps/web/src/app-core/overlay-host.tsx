// OverlayHost and useOverlays (F-05-T20; plan 04 section 2.4): the ?ov= layers, read from the URL
// and drawn from the registry. Opening pushes a history entry, so Back closes the layer; Escape and
// the close button close with `replace`, so the entry the layer was opened from is not left behind
// as a second copy. A reload draws the same layers again, because the URL holds them.
import { useNavigate, useSearch } from "@tanstack/react-router";
import { Fragment, type JSX, useCallback, useMemo } from "react";
import {
  type OverlayRef,
  closeRef,
  decodeOverlays,
  encodeOverlays,
  encodeRef,
  layerOfKey,
  normalizeOverlays,
  openRef,
  overlayEntry,
} from "./overlays";

type Search = Record<string, unknown>;

export interface UseOverlays {
  /** The layers the URL names that the registry knows, drawer first. */
  refs: readonly OverlayRef[];
  /** Open a layer. Pushes a history entry; a second drawer replaces the first. */
  open: (key: string, ...args: string[]) => void;
  /** Close the layer at `index` (the topmost by default). Replaces the history entry. */
  close: (index?: number) => void;
}

export function useOverlays(): UseOverlays {
  const search: Search = useSearch({ strict: false });
  const navigate = useNavigate();
  const raw = search["ov"];
  // `raw` is the router's own value for the parameter; it changes only when the URL does.
  const refs = useMemo(() => normalizeOverlays(decodeOverlays(raw), layerOfKey), [raw]);

  const write = useCallback(
    (next: (current: OverlayRef[]) => OverlayRef[], replace: boolean): void => {
      void navigate({
        search: ((prev: Search): Search => {
          const ov = encodeOverlays(
            next(normalizeOverlays(decodeOverlays(prev["ov"]), layerOfKey)),
          );
          const rest = Object.fromEntries(Object.entries(prev).filter(([key]) => key !== "ov"));
          return ov === undefined ? rest : { ...rest, ov };
        }) as never,
        replace,
      });
    },
    [navigate],
  );

  const open = useCallback(
    (key: string, ...args: string[]): void => {
      write((current) => openRef(current, { key, args }, layerOfKey), false);
    },
    [write],
  );

  const close = useCallback(
    (index?: number): void => {
      write((current) => closeRef(current, index ?? current.length - 1), true);
    },
    [write],
  );

  return { refs, open, close };
}

/** Draws the layers in the URL. Mount it once, inside the router, under the app's providers. */
export function OverlayHost(): JSX.Element {
  const { refs, close } = useOverlays();
  return (
    <>
      {refs.map((ref, index) => {
        const entry = overlayEntry(ref.key);
        if (entry === undefined) return null;
        return (
          <Fragment key={encodeRef(ref)}>
            {entry.render({
              ref,
              index,
              close: () => {
                close(index);
              },
            })}
          </Fragment>
        );
      })}
    </>
  );
}
