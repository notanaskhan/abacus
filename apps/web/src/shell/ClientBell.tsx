import { Bell } from "@abacus/ui";
import { type JSX, useState } from "react";
import { NotificationPanel, useUnreadCount } from "./NotificationPanel";

/** SPEC-032 Q2 (TASK-063): the client portal's notifications. Retired from the portal header by
 * F-05-T23 (DEC-58 (d): no portal bell; email and the Home "your part" list instead); kept, with
 * its test, until P-08's portal shell replaces client notifications. */
export function ClientBell(): JSX.Element {
  const [open, setOpen] = useState(false);
  const unread = useUnreadCount();
  return (
    <div className="relative">
      <button
        type="button"
        aria-label={unread > 0 ? `Notifications, ${String(unread)} unread` : "Notifications"}
        aria-expanded={open}
        className="relative flex items-center rounded-[var(--radius-control)] p-2 hover:bg-sunken"
        onClick={() => {
          setOpen((o) => !o);
        }}
      >
        <Bell aria-hidden="true" className="size-5" />
        {unread > 0 && (
          <span className="absolute -top-1 -right-1 rounded-full bg-espresso px-1.5 text-meta text-on-dark tabular-nums">
            {unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-10 mt-2 rounded-[var(--radius-control)] border border-hair bg-surface shadow-pop">
          <NotificationPanel
            portal="client"
            onClose={() => {
              setOpen(false);
            }}
          />
        </div>
      )}
    </div>
  );
}
