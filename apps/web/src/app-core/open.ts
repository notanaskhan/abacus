import { type RouterHistory, useRouter } from "@tanstack/react-router";
import {
  type OverlayRef,
  decodeOverlays,
  encodeOverlays,
  layerOfKey,
  normalizeOverlays,
  openRef,
} from "./overlays";

// Opening a screen link from a control that is not an anchor (a segment, a tile, a chip): through
// the router's history where the screen is mounted under one, else the browser (the gallery's
// frames and tests). The href always comes from `hrefOf(to.<ID>(…))`, so only routed screens open.

export function useOpenHref(): (href: string) => void {
  const router = useRouter({ warn: false }) as { history: RouterHistory } | undefined;
  return (href) => {
    if (router === undefined) window.location.assign(href);
    else router.history.push(href);
  };
}

type Search = Record<string, unknown>;
interface Navigates {
  navigate: (options: { search: (prev: Search) => Search }) => Promise<void>;
}

/** Opening an overlay screen (`ov.<ID>(…)`) over the current route, as `useOverlays().open` does,
 * from a screen that may render without a router; there it does nothing (no URL to hold it). */
export function useOpenOverlay(): (ref: OverlayRef) => void {
  const router = useRouter({ warn: false }) as unknown as Navigates | undefined;
  return (ref) => {
    void router?.navigate({
      search: (prev) => {
        const current = normalizeOverlays(decodeOverlays(prev["ov"]), layerOfKey);
        const ov = encodeOverlays(openRef(current, ref, layerOfKey));
        const rest = Object.fromEntries(Object.entries(prev).filter(([key]) => key !== "ov"));
        return ov === undefined ? rest : { ...rest, ov };
      },
    });
  };
}
