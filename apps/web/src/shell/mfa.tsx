import { Button, Dialog } from "@abacus/ui";
import type { JSX } from "react";
import { signIn } from "../auth/session";

/** A 403 on an action that needs recent MFA (ADR-030): offer a fresh sign-in, then return here. */
export function isForbidden(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "detail" in error &&
    error.detail === "forbidden"
  );
}

export function ConfirmItsYou({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}): JSX.Element {
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Confirm it's you"
      description="This action needs a recent sign-in. Sign in again, then try once more. If it still isn't allowed, your role doesn't permit it."
    >
      <div className="flex justify-end gap-2">
        <Button
          variant="outline"
          onClick={() => {
            onOpenChange(false);
          }}
        >
          Cancel
        </Button>
        <Button
          onClick={() => {
            void signIn(window.location.pathname, { forceLogin: true });
          }}
        >
          Sign in again
        </Button>
      </div>
    </Dialog>
  );
}
