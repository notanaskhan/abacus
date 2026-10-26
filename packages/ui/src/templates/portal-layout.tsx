import type { JSX, ReactNode } from "react";
import { usePortalBrand } from "../brand";
import { cn } from "../cn";
import { AppShell } from "../layout/app-shell";
import { MobileHeader, MobileTabBar } from "../layout/mobile-tab-bar";
import { PortalFooter, type PortalNavItem, type PortalUserMenu } from "../layout/portal-toolbar";

// T7 PortalLayout (F-05-T35; T7 and T7-M handoff, DEC-45): the client portal's frame in three
// variants.
//   split    the PortalToolbar over the 336 rail beside a flex pane (T7a to T7f, POR-03).
//   reduced  the PortalToolbar over one centred 720 pane (T7g).
//   mobile   the 56 MobileHeader, one scrolling column, the 64 MobileTabBar (T7-M, 390 wide).
// The firm's brand comes from `PortalBrandProvider`, never a prop default, so no portal surface
// can draw the product's name; the "Secured by" footer shows only when the brand turns it on. The
// nav is the app's (`portalNav` gives the handoff's set for a client kind); the layout draws it.

export type PortalVariant = "split" | "reduced" | "mobile";

export const PORTAL_VARIANTS: readonly PortalVariant[] = ["split", "reduced", "mobile"];

/** Who the portal is for: an individual client (a household) or an entity client. */
export type PortalClientKind = "individual" | "entity";

/** The portal's areas in bar order (T7 spec): Approvals only for an entity client. */
export const PORTAL_AREAS: readonly PortalNavItem[] = [
  { label: "Home", icon: "house" },
  { label: "Documents", icon: "file-text" },
  { label: "Questions", icon: "circle-help" },
  { label: "Approvals", icon: "circle-check" },
  { label: "Sign", icon: "signature" },
  { label: "Messages", icon: "message-circle" },
  { label: "Deliverables", icon: "download" },
];

/** The nav for a client kind: an individual client never sees Approvals. `counts` puts a count
 * beside an area ("Messages 1"). */
export function portalNav(
  kind: PortalClientKind,
  counts: Readonly<Record<string, number>> = {},
): PortalNavItem[] {
  return PORTAL_AREAS.filter((item) => kind === "entity" || item.label !== "Approvals").map(
    (item) => {
      const count = counts[item.label];
      return count === undefined ? item : { ...item, count };
    },
  );
}

export interface PortalLayoutProps {
  variant: PortalVariant;
  /** The signed-in person. */
  user: string;
  nav: readonly PortalNavItem[];
  active?: string;
  onNavigate?: (label: string) => void;
  onUser?: () => void;
  /** The user chip's menu (the toolbar's, or the 390 header's account button). */
  userMenu?: PortalUserMenu;
  /** The 336 rail beside the main pane (split only): a `Pane`. */
  rail?: ReactNode;
  /** The main pane (split, reduced), or the column's content (mobile). */
  children?: ReactNode;
  /** Mobile: pinned under the column, over the tab bar (the "Mark as Done" bar). */
  mobileFooter?: ReactNode;
  /** Mobile: the More sheet, controlled. */
  moreOpen?: boolean;
  onMoreChange?: (open: boolean) => void;
  /** Mobile: hold the More sheet open for a specimen. */
  moreForceState?: "open";
  /** Presentation only (the gallery): a 1400 window, or a 390 phone, on the presentation ground. */
  frame?: boolean;
  /** A fixed frame height in px, framed only (860 for the window, 844 for the phone). */
  height?: number;
  className?: string;
}

/** The T7 frame: brand, nav and panes, white-labelled for the firm. */
export function PortalLayout(props: PortalLayoutProps): JSX.Element {
  const brand = usePortalBrand();
  const { variant, user, nav, active, onNavigate, onUser, frame = false, height } = props;
  if (variant === "mobile") return <MobileFrame {...props} />;
  const toolbar = {
    firm: brand.portalName ?? brand.name,
    user,
    nav,
    ...(active === undefined ? {} : { active }),
    ...(brand.logo === undefined ? {} : { logo: brand.logo }),
    ...(brand.mark === undefined ? {} : { mark: brand.mark }),
    ...(onNavigate === undefined ? {} : { onNavigate }),
    ...(onUser === undefined ? {} : { onUser }),
    ...(props.userMenu === undefined ? {} : { userMenu: props.userMenu }),
  };
  return (
    <AppShell
      variant="portal"
      toolbar={toolbar}
      securedFooter={brand.securedFooter}
      frame={frame}
      {...(height === undefined ? {} : { height })}
      {...(props.className === undefined ? {} : { className: props.className })}
    >
      {variant === "split" ? (
        <>
          {props.rail !== undefined && (
            <div data-portal="rail" className="flex w-(--rail-w-portal) flex-none flex-col">
              {props.rail}
            </div>
          )}
          <div data-portal="main" className="flex min-w-0 flex-1 flex-col">
            {props.children}
          </div>
        </>
      ) : (
        <div
          data-portal="main"
          className="mx-auto flex w-[720px] max-w-full min-w-0 flex-none flex-col"
        >
          {props.children}
        </div>
      )}
    </AppShell>
  );
}

function MobileFrame({
  user,
  nav,
  active,
  onNavigate,
  onUser,
  userMenu,
  children,
  mobileFooter,
  moreOpen,
  onMoreChange,
  moreForceState,
  frame = false,
  height,
  className,
}: PortalLayoutProps): JSX.Element {
  const brand = usePortalBrand();
  const phone = (
    <div
      data-shell="app"
      data-variant="portal-mobile"
      {...(frame ? { "data-frame": "phone" } : {})}
      style={frame ? { height: height ?? 844 } : undefined}
      className={cn(
        "relative flex flex-col overflow-hidden bg-shell",
        frame ? "w-[390px] flex-none rounded-phone shadow-e1" : "h-dvh w-full",
        className,
      )}
    >
      <MobileHeader
        firm={brand.portalName ?? brand.name}
        user={user}
        {...(brand.logo === undefined ? {} : { logo: brand.logo })}
        {...(brand.mark === undefined ? {} : { mark: brand.mark })}
        {...(onUser === undefined ? {} : { onUser })}
        {...(userMenu === undefined ? {} : { userMenu })}
      />
      <main
        data-portal="column"
        className="flex min-h-0 flex-1 flex-col gap-[10px] overflow-y-auto px-[12px] pt-[14px] pb-[16px]"
      >
        {children}
        {brand.securedFooter && <PortalFooter className="mt-auto" />}
      </main>
      {mobileFooter !== undefined && (
        <div
          data-portal="mobile-footer"
          className="flex-none bg-card px-[16px] py-[10px] hairline-t"
        >
          {mobileFooter}
        </div>
      )}
      {/* A room of one area (a third party's, POR-14 at 390) has no tab bar. */}
      {nav.length > 0 && (
        <MobileTabBar
          nav={nav}
          {...(active === undefined ? {} : { active })}
          {...(onNavigate === undefined ? {} : { onNavigate })}
          {...(moreOpen === undefined ? {} : { moreOpen })}
          {...(onMoreChange === undefined ? {} : { onMoreChange })}
          {...(moreForceState === undefined ? {} : { forceState: moreForceState })}
        />
      )}
    </div>
  );
  if (!frame) return phone;
  return (
    <div
      data-shell="stage"
      className="flex items-start justify-center bg-presentation px-[40px] pt-[28px] pb-[28px]"
    >
      {phone}
    </div>
  );
}
