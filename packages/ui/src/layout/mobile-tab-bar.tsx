import {
  type JSX,
  type KeyboardEvent,
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
} from "react";
import { FirmMark, type FirmMarkProps } from "../brand";
import { cn } from "../cn";
import { PRESS } from "../components/control-classes";
import { Count } from "../components/pill";
import { Menu } from "../components/popover";
import { Icon } from "../icons";
import { useMotion } from "../motion";
import type { PortalNavItem, PortalUserMenu } from "./portal-toolbar";

// The portal at 390 (T7-M; DEC-45, D-DS-8): the 56px MobileHeader and the 64px MobileTabBar with
// its More sheet. The bar replaces the T7-M board's top pills: Home · Documents · Sign · Messages,
// then More for the rest (Questions, Approvals for an entity client, Deliverables). Icons 20 over an
// 11px label; the current tab is ink at 500, the others ink-3. Every target is at least 44 high
// (F-05 accessibility: 44px on portal mobile). White-labelled like the PortalToolbar: the firm's
// mark and name, never the product's.

/** The tabs the bar holds itself, in order. Anything else in the nav goes under More. */
export const MOBILE_TABS: readonly string[] = ["Home", "Documents", "Sign", "Messages"];

/** Splits the portal nav into the bar's tabs and the More sheet's items, keeping each in order. */
export function splitMobileNav(nav: readonly PortalNavItem[]): {
  tabs: PortalNavItem[];
  more: PortalNavItem[];
} {
  const tabs = MOBILE_TABS.flatMap((label) => nav.filter((item) => item.label === label));
  const more = nav.filter((item) => !MOBILE_TABS.includes(item.label));
  return { tabs, more };
}

// ---- MobileHeader ------------------------------------------------------------------------------

export interface MobileHeaderProps {
  /** The firm's name, never the product's. */
  firm: string;
  /** The signed-in person: the account button's name. */
  user?: string;
  logo?: string;
  mark?: FirmMarkProps["mark"];
  onUser?: () => void;
  /** The account button opens this menu (the PortalToolbar's user menu). */
  userMenu?: PortalUserMenu;
  className?: string;
}

/** The 56px portal header at 390: the firm's 20 mark and name (15/500), the 28 account glyph in a
 * 44 target at the right. No nav, no bell. */
export function MobileHeader({
  firm,
  user,
  logo,
  mark,
  onUser,
  userMenu,
  className,
}: MobileHeaderProps): JSX.Element {
  const account =
    user === undefined ? null : (
      <button
        type="button"
        aria-label={user}
        title={user}
        aria-haspopup="menu"
        {...(userMenu === undefined ? { onClick: onUser } : {})}
        className={cn("inline-flex size-[44px] flex-none items-center justify-center", PRESS)}
      >
        <span className="inline-flex size-[28px] items-center justify-center rounded-pill bg-nav-fill text-ink-2 shadow-e1">
          <Icon name="user" size={14} />
        </span>
      </button>
    );
  return (
    <header
      data-shell="mobile-header"
      className={cn(
        "flex h-[56px] flex-none items-center gap-[9px] bg-card pr-[10px] pl-[16px] hairline-b",
        className,
      )}
    >
      <FirmMark
        name={firm}
        size={20}
        {...(logo === undefined ? {} : { src: logo })}
        {...(mark === undefined ? {} : { mark })}
      />
      <span className="min-w-0 flex-1 truncate text-title font-medium tracking-[-0.02em] whitespace-nowrap">
        {firm}
      </span>
      {account !== null &&
        (userMenu === undefined ? (
          account
        ) : (
          <Menu
            trigger={account}
            sections={userMenu.sections}
            label={userMenu.label}
            width={260}
          />
        ))}
    </header>
  );
}

// ---- MobileTabBar ------------------------------------------------------------------------------

export interface MobileTabBarProps {
  /** The areas the person may see, as the PortalToolbar gets them. */
  nav: readonly PortalNavItem[];
  /** The current area's label. When it is under More, More reads as current. */
  active?: string;
  onNavigate?: (label: string) => void;
  /** The More sheet, controlled. Uncontrolled when left out. */
  moreOpen?: boolean;
  onMoreChange?: (open: boolean) => void;
  /** Hold the More sheet open for a specimen: drawn in place, it takes no focus. */
  forceState?: "open";
  className?: string;
}

const TAB = cn(
  "flex min-h-[44px] flex-col items-center justify-center gap-[3px] rounded-nested text-[11px] text-ink-3",
  "aria-[current=page]:font-medium aria-[current=page]:text-ink",
  PRESS,
);

const MORE_ITEM =
  "flex h-[44px] w-full items-center gap-[10px] rounded-tile px-[12px] text-left text-btn-lg outline-offset-[-2px] hover:bg-nav-fill focus-visible:bg-nav-fill";

/** The 64px bottom tab bar: up to four tabs and More, a hairline over it. More opens a sheet of
 * the remaining areas above the bar (↑ ↓ move, Escape and a tap outside close it, focus returns
 * to More). */
export function MobileTabBar({
  nav,
  active,
  onNavigate,
  moreOpen,
  onMoreChange,
  forceState,
  className,
}: MobileTabBarProps): JSX.Element {
  const { tabs, more } = splitMobileNav(nav);
  const [ownOpen, setOwnOpen] = useState(false);
  const held = forceState === "open";
  // The 260ms reveal, only for a sheet the person opens with motion allowed.
  const animate = useMotion(held);
  const open = held || (moreOpen ?? ownOpen);
  const setOpen = useCallback(
    (next: boolean) => {
      if (moreOpen === undefined) setOwnOpen(next);
      onMoreChange?.(next);
    },
    [moreOpen, onMoreChange],
  );
  const moreRef = useRef<HTMLButtonElement>(null);
  const items = useRef<(HTMLButtonElement | null)[]>([]);
  const sheetId = useId();
  const activeInMore = more.some((item) => item.label === active);

  // Opening by the person moves focus to the first item; a held sheet takes none.
  useEffect(() => {
    if (open && !held) items.current[0]?.focus();
  }, [open, held]);

  const close = (): void => {
    setOpen(false);
    moreRef.current?.focus();
  };

  const onSheetKey = (event: KeyboardEvent<HTMLDivElement>): void => {
    const list = items.current.filter((el): el is HTMLButtonElement => el !== null);
    const at = list.findIndex((el) => el === document.activeElement);
    if (event.key === "Escape") {
      event.preventDefault();
      close();
    } else if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      const step = event.key === "ArrowDown" ? 1 : -1;
      list[(at + step + list.length) % list.length]?.focus();
    } else if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      list[event.key === "Home" ? 0 : list.length - 1]?.focus();
    }
  };

  return (
    <>
      {open && more.length > 0 && (
        <>
          {!held && (
            <div
              data-shell="more-scrim"
              aria-hidden="true"
              className="absolute inset-0 z-(--z-menu)"
              onClick={() => {
                setOpen(false);
              }}
            />
          )}
          <div
            id={sheetId}
            role="menu"
            aria-label="More"
            data-shell="more-sheet"
            onKeyDown={onSheetKey}
            className={cn(
              "absolute right-[10px] bottom-[72px] z-(--z-menu) w-[200px] rounded-menu bg-nested p-[4px] shadow-menu",
              animate && "motion-reveal",
            )}
          >
            <div className="flex flex-col gap-px rounded-menu-inner bg-card p-[4px]">
              {more.map((item, i) => (
                <button
                  key={item.label}
                  ref={(el) => {
                    items.current[i] = el;
                  }}
                  type="button"
                  role="menuitem"
                  tabIndex={-1}
                  {...(item.label === active ? { "aria-current": "page" as const } : {})}
                  className={cn(MORE_ITEM, item.label === active && "font-medium")}
                  onClick={() => {
                    setOpen(false);
                    onNavigate?.(item.label);
                  }}
                >
                  <Icon name={item.icon} size={16} className="text-ink-2" />
                  {item.label}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
      <nav
        aria-label="Portal"
        data-shell="mobile-tab-bar"
        style={{
          gridTemplateColumns: `repeat(${String(tabs.length + (more.length > 0 ? 1 : 0))}, minmax(0, 1fr))`,
        }}
        className={cn(
          "grid h-[64px] flex-none bg-card px-[6px] pt-[4px] pb-[8px] hairline-t",
          className,
        )}
      >
        {tabs.map((item) => (
          <button
            key={item.label}
            type="button"
            {...(item.label === active && !open ? { "aria-current": "page" as const } : {})}
            {...(item.count !== undefined && item.count > 0
              ? { "aria-label": item.countLabel ?? `${item.label}, ${String(item.count)}` }
              : {})}
            className={TAB}
            onClick={() => {
              setOpen(false);
              onNavigate?.(item.label);
            }}
          >
            <span className="relative inline-flex">
              <Icon name={item.icon} size={20} />
              {item.count !== undefined && item.count > 0 && (
                <Count
                  value={item.count}
                  data-part="tab-count"
                  aria-hidden="true"
                  className="absolute -top-[8px] -right-[13px] px-[6px]"
                />
              )}
            </span>
            {item.label}
          </button>
        ))}
        {more.length > 0 && (
          <button
            ref={moreRef}
            type="button"
            aria-haspopup="menu"
            aria-expanded={open}
            aria-controls={open ? sheetId : undefined}
            {...(open || activeInMore ? { "aria-current": "page" as const } : {})}
            className={TAB}
            onClick={() => {
              setOpen(!open);
            }}
          >
            <Icon name="ellipsis" size={20} />
            More
          </button>
        )}
      </nav>
    </>
  );
}
