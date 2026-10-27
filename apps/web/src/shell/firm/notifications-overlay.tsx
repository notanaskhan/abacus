import { useNavigate } from "@tanstack/react-router";
import { type JSX, Suspense, lazy } from "react";
import { registerOverlay } from "../../app-core/overlays";

// SHL-04's `?ov=notifications` layer (P-01-T10). The drawer is its own chunk, loaded when the bell
// first opens it, so the firm's initial load carries only this registration (F-05-T17, TASK-1368).
// The bell's unread count is the toolbar's, not the drawer's, so it stays on the initial load.

export const NOTIFICATIONS_OVERLAY = "notifications";

const NotificationsDrawer = lazy(async () => ({
  default: (await import("./NotificationsDrawer")).NotificationsDrawer,
}));

/** The `?ov=notifications` layer: the drawer, open, closed by removing it from the URL. */
function NotificationsOverlay({ close }: { close: () => void }): JSX.Element {
  const navigate = useNavigate();
  return (
    <Suspense fallback={null}>
      <NotificationsDrawer
        open
        onOpenChange={(next) => {
          if (!next) close();
        }}
        navigate={(to) => void navigate({ to })}
      />
    </Suspense>
  );
}

registerOverlay(NOTIFICATIONS_OVERLAY, {
  layer: "drawer",
  render: ({ close }) => <NotificationsOverlay close={close} />,
});
