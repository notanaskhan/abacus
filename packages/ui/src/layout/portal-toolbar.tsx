import type { JSX } from "react";
import { FirmMark, type FirmMarkProps, Wordmark } from "../brand";
import { cn } from "../cn";
import { PRESS } from "../components/control-classes";
import { Count } from "../components/pill";
import { Icon, type IconName } from "../icons";

// The PortalToolbar (C-00 Shell Kit spec 03; F-05-T18): the client portal's 46px bar, white-labelled
// for the firm. The firm's mark and name on the left, icon-and-word nav in the centre, the user
// chip on the right. No Go..., no Support, no bell. It never shows the Accrued name or mark: the
// "Secured by" footer (`PortalFooter`) is the one place, and the firm turns it on (ADM-10).

export interface PortalNavItem {
  label: string;
  icon: IconName;
  /** A count beside the label ("Messages 1"). */
  count?: number;
}

export interface PortalToolbarProps {
  /** The firm's name, never "Accrued". */
  firm: string;
  /** The signed-in person. */
  user: string;
  /** The areas the person may see, in order. The app decides (an individual client has no
   * Approvals); the shell only draws them. */
  nav: readonly PortalNavItem[];
  /** The current item's label. */
  active?: string;
  /** The firm's uploaded logo (ADM-10). Without one the mark is drawn from the name. */
  logo?: string;
  mark?: FirmMarkProps["mark"];
  /** The user chip reads as pressed: its menu is open, or the Account screen is showing. */
  userOn?: boolean;
  onNavigate?: (label: string) => void;
  onUser?: () => void;
  className?: string;
}

const ITEM = cn(
  "inline-flex h-[32px] flex-none items-center gap-[8px] rounded-pill px-[12px] text-nav whitespace-nowrap text-ink-2",
  "hover:bg-sel-bg hover:text-ink",
  "aria-[current=page]:bg-nav-fill aria-[current=page]:font-medium aria-[current=page]:text-ink",
);

export function PortalToolbar({
  firm,
  user,
  nav,
  active,
  logo,
  mark,
  userOn = false,
  onNavigate,
  onUser,
  className,
}: PortalToolbarProps): JSX.Element {
  return (
    <header
      data-shell="portal-toolbar"
      className={cn(
        "relative flex h-(--toolbar-h) w-full flex-none items-center gap-[8px] bg-card px-(--edge-app) text-nav hairline-b",
        className,
      )}
    >
      <div className="flex min-w-0 flex-1 items-center gap-[9px]">
        <FirmMark
          name={firm}
          size={20}
          {...(logo === undefined ? {} : { src: logo })}
          {...(mark === undefined ? {} : { mark })}
        />
        <span className="min-w-0 truncate text-brand">{firm}</span>
      </div>
      <nav aria-label="Portal" className="flex flex-none items-center gap-px">
        {nav.map((item) => (
          <button
            key={item.label}
            type="button"
            {...(item.label === active ? { "aria-current": "page" as const } : {})}
            className={cn(ITEM, PRESS)}
            onClick={() => onNavigate?.(item.label)}
          >
            <Icon name={item.icon} size={14} />
            {item.label}
            {item.count !== undefined && item.count > 0 && (
              <Count value={item.count} className="-ml-[2px] px-[6px]" />
            )}
          </button>
        ))}
      </nav>
      <div className="flex min-w-0 flex-1 items-center justify-end">
        <button
          type="button"
          aria-haspopup="menu"
          data-pressed={userOn}
          className={cn(
            "inline-flex h-[30px] flex-none items-center gap-[7px] rounded-pill bg-nav-fill pr-[9px] pl-[10px] text-nav text-ink shadow-e1 hover:bg-sel-bg data-[pressed=true]:bg-sel-bg",
            PRESS,
          )}
          onClick={onUser}
        >
          <Icon name="user" size={14} filled className="text-ink-2" />
          {user}
          <Icon name="chevron-down" size={12} className="text-ink-2" />
        </button>
      </div>
    </header>
  );
}

/** "Secured by accrued·", 34 high and pulled up 4px: the footer the firm may turn on (ADM-10,
 * default off). The one place the Accrued mark appears in the portal. */
export function PortalFooter({ className }: { className?: string }): JSX.Element {
  return (
    <footer
      data-shell="portal-footer"
      className={cn(
        "-mt-[4px] flex h-[34px] flex-none items-center justify-center gap-[5px]",
        className,
      )}
    >
      <span className="text-meta text-ink-3">Secured by</span>
      <Wordmark size={12} />
    </footer>
  );
}
