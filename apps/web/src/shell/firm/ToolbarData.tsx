import type { ToolbarProps } from "@abacus/ui";
import { type JSX, useCallback, useState } from "react";
import { useFlag } from "../../app-core/flags";
import { NAV } from "../nav";
import { useUnreadCount } from "../NotificationPanel";
import {
  type Area,
  type ToolbarContext,
  activeArea,
  areaByLabel,
  isSettings,
} from "../../app-core/nav-areas";
import { useGoChords } from "./hotkeys";
import { InterimGo } from "./InterimGo";
import { InterimSupport } from "./InterimSupport";

// The firm toolbar's data (P-01-T02; SHL-01). The Toolbar (F-05-T18) draws; this decides what it
// draws: the 13 items of nav.ts in order, the lit item from the manifest's `navArea` (b, g) or
// none in settings (f), DF-39 with More first (e), the bell's dot from `unread_count` (a, d), and
// the Go… tooltip's second line only once the palette flag exists. It owns the interim Go… and
// Support frames and the G-chords; ⌘K reaches `onGo` through AppShell.

export interface FirmToolbarOptions {
  /** Where the toolbar is: the URL, or the open screen. */
  at: ToolbarContext;
  /** The firm's display name ("Brightwater Hale"). */
  firm: string;
  /** The full name for the pill's title, when known. */
  firmTitle?: string;
  /** The firm menu (SHL-03) is open. */
  firmMenuOpen?: boolean;
  /** The notifications drawer (SHL-04) is open. */
  bellOpen?: boolean;
  onBell?: () => void;
  onFirm?: () => void;
  /** Go to a path (the router's navigate, or an artboard's own state). */
  navigate: (path: string) => void;
  /** Bind the G-chords and ? (one toolbar per page). Default true. */
  hotkeys?: boolean;
}

export interface FirmToolbar {
  toolbar: ToolbarProps;
  /** The interim Go… and Support frames, drawn over the shell. */
  overlay: JSX.Element;
  /** Open the interim Go… frame (? and the shortcuts dialog's stand-in). */
  openGo: () => void;
}

/** Whether `unread_count` lights the dot (never a number). */
export function hasUnread(count: number): boolean {
  return count > 0;
}

export function useFirmToolbar({
  at,
  firm,
  firmTitle,
  firmMenuOpen = false,
  bellOpen = false,
  onBell,
  onFirm,
  navigate,
  hotkeys = true,
}: FirmToolbarOptions): FirmToolbar {
  const unread = useUnreadCount();
  // R2's second tooltip line names SHL-02's actions; it shows once they exist (AC 1.1.8).
  const palette = useFlag("palette") === true;
  const [go, setGo] = useState(false);
  const [support, setSupport] = useState(false);

  const goTo = useCallback(
    (area: Area) => {
      setGo(false);
      navigate(area.path);
    },
    [navigate],
  );
  const openGo = useCallback(() => {
    setGo(true);
  }, []);
  useGoChords(hotkeys, { onArea: goTo, onHelp: openGo });

  const toolbar: ToolbarProps = {
    nav: NAV,
    active: activeArea(at),
    firm,
    ...(firmTitle === undefined ? {} : { firmTitle }),
    firmPressed: firmMenuOpen || isSettings(at),
    supportPressed: support,
    bellPressed: bellOpen,
    unread: hasUnread(unread),
    moreFirst: true,
    // SHL-01a draws idle labels at their own width (Tier A).
    holdLabelWidth: false,
    goDetail: palette,
    onGo: () => {
      setGo((open) => !open);
    },
    onNavigate: (label) => {
      const area = areaByLabel(label);
      if (area !== undefined) navigate(area.path);
    },
    onSupport: () => {
      setSupport((open) => !open);
    },
    ...(onBell === undefined ? {} : { onBell }),
    ...(onFirm === undefined ? {} : { onFirm }),
  };
  const overlay = (
    <>
      <InterimGo open={go} onOpenChange={setGo} onArea={goTo} />
      <InterimSupport open={support} onOpenChange={setSupport} />
    </>
  );
  return { toolbar, overlay, openGo };
}
