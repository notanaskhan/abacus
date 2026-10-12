import { Bell } from "@abacus/ui";
import { type JSX, useState } from "react";
import { NotificationPanel, useUnreadCount } from "./NotificationPanel";

/** SPEC-032 Q2 (TASK-063): the client portal's notifications, in its header. */
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
          <span className="absolute -top-1 -right-1 rounded-full bg-accent px-1.5 text-xs text-on-accent tabular-nums">
            {unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-10 mt-2 rounded-[var(--radius-control)] border border-line bg-surface shadow-lg">
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
