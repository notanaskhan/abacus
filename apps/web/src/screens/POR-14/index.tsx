import {
  Button,
  DEFAULT_TZ,
  EmptyState,
  Pane,
  PortalBrandProvider,
  PortalLayout,
  type PortalNavItem,
  type PortalUserMenu,
  date,
  toast,
  usePortalBrand,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { goToSignIn, portalSignOut } from "../../app-core/auth/bff";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import {
  ScopedRequestRoom,
  brandOf,
  suggestFor,
  useBranding,
  usePortalToolbar,
  useRoom,
  useRoomActions,
} from "../../domain/portal";
import { UPLOAD_ACCEPT } from "../POR-03/copy";
import { COPY } from "./copy";

// POR-14 · Third-party request room (R-01-T14; docs/screens/POR-14.md). T7 reduced (one 720 pane
// under a toolbar whose only item is Requests) and the 390 page with no tab bar, over the room
// read model (`GET /v1/portal/room`, R-01-T13): exactly the requests delegated to the person, as
// the `ScopedRequestRoom` composition A-09 reuses for POR-23. Each artboard is its data
// (fixtures/scenarios/POR-14.ts):
//
//   a  Sam Ortiz at 4 of 9, the bridge letter open: the guidance, the upload slot, the thread
//   b  Sam's upload in review: "You uploaded Sep 22 · Brightwater Hale is reviewing it", 5 of 9
//   c  returned by Marcus Delaney: "Returned · wrong period" and his note
//   d  Harborline's certifications contact: the custodian's ERISA §103(a)(3)(C) introduction
//   e  everything in: the green-tint banner
//   f  no room (an expired, used or unknown link, or nothing delegated): one neutral state
//
// The person reaches nothing else: no other request, binder, client page or party (INV-4); the
// firm's name comes from the branding, never the product's (DEC-01).

/** The reduced toolbar's one item (POR-14: no route to POR-02, POR-08 or POR-09). */
export const ROOM_NAV: readonly PortalNavItem[] = [{ label: COPY.nav, icon: "inbox" }];

export interface POR14Props {
  mobile?: boolean;
  /** Presentation only (the gallery): the 1400 window or the 390 phone. */
  frame?: boolean;
  /** The row open on arrival (a, b, c: the bridge letter; `/requests/$requestId`). */
  expanded?: string;
  /** A row opened or closed (the portal entry keeps it in the address). */
  onExpand?: (id: string | null) => void;
}

function onDay(day: string): string {
  return `${day}T12:00:00Z`;
}

function userMenu(onSignOut: () => void): PortalUserMenu {
  return {
    label: COPY.userMenu,
    sections: [
      // POR-12's security section is N-03's: drawn disabled in fixture builds, left out in
      // production until it exists (docs/screens/POR-14.md, Open gaps).
      ...(PLANNED_VISIBLE
        ? [[{ label: "Security", disabled: true, onSelect: () => undefined }]]
        : []),
      [{ label: COPY.signOut, icon: "log-out" as const, onSelect: onSignOut }],
    ],
  };
}

function isMissing(error: unknown): boolean {
  return typeof error === "object" && error !== null && "detail" in error;
}

export function POR14({
  mobile = false,
  frame = false,
  expanded,
  onExpand,
}: POR14Props): JSX.Element | null {
  const now = useNow();
  const brand = usePortalBrand();
  const firm = brand.portalName ?? brand.name;
  const bar = usePortalToolbar(null);
  const room = useRoom();
  const act = useRoomActions();
  const [open, setOpen] = useState<string | null>(expanded ?? null);
  if (bar === undefined) return null;
  const day = (iso: string): string => date(onDay(iso), { now, tz: DEFAULT_TZ });
  const settle = (work: Promise<unknown>): void => {
    work.catch(() => {
      toast.show({ kind: "error", text: COPY.failed });
    });
  };
  const data = room.data;
  const user = COPY.user(bar.user, data?.organisation_name ?? "");
  const menu = userMenu(() => {
    void portalSignOut().finally(() => {
      goToSignIn("/");
    });
  });
  let body: JSX.Element;
  if (data !== undefined) {
    body = (
      <ScopedRequestRoom
        room={data}
        firm={firm}
        day={day}
        expanded={open}
        onExpand={(id) => {
          setOpen(id);
          onExpand?.(id);
        }}
        accept={UPLOAD_ACCEPT}
        mobile={mobile}
        suggest={suggestFor}
        onUpload={(row, files) => {
          settle(act.upload(row, files));
        }}
        onWithdraw={(row, file) => {
          settle(act.withdraw(row, file));
        }}
        onComment={(row, text) => {
          settle(act.comment(row, text));
        }}
      />
    );
  } else if (room.isError && isMissing(room.error)) {
    // f: an expired, used or unknown link answers the same 404 as no room at all (no oracle).
    body = (
      <EmptyState icon="link" title={COPY.expiredTitle}>
        {COPY.expiredAction(firm)}
      </EmptyState>
    );
  } else if (room.isError) {
    body = (
      <EmptyState
        tone="error"
        icon="circle-alert"
        title={COPY.loadError}
        action={
          <Button variant="secondary" size="sm" onClick={() => void room.refetch()}>
            {COPY.retry}
          </Button>
        }
      />
    );
  } else {
    body = (
      <div role="status" aria-label={COPY.loading} className="flex flex-col gap-[8px] p-[14px]">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-[52px] rounded-nested bg-nested" />
        ))}
      </div>
    );
  }
  return (
    <div data-screen="POR-14" className="flex min-h-0 flex-1 flex-col">
      {mobile ? (
        <PortalLayout
          variant="mobile"
          user={user}
          nav={[]}
          userMenu={menu}
          frame={frame}
          {...(frame ? { height: 844 } : {})}
        >
          <div className="overflow-hidden rounded-pane bg-card shadow-e1">{body}</div>
        </PortalLayout>
      ) : (
        <PortalLayout
          variant="reduced"
          user={user}
          nav={ROOM_NAV}
          active={COPY.nav}
          userMenu={menu}
          frame={frame}
          {...(frame ? { height: 860 } : {})}
        >
          <Pane title={COPY.pane} titleAlign="center">
            {body}
          </Pane>
        </PortalLayout>
      )}
    </div>
  );
}

/** The page: the firm's branding first, then the room under its brand. */
export function PortalRoom(props: POR14Props): JSX.Element | null {
  const branding = useBranding();
  if (branding.data === undefined) return null;
  return (
    <PortalBrandProvider brand={brandOf(branding.data)}>
      <POR14 {...props} />
    </PortalBrandProvider>
  );
}
