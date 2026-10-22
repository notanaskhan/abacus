import { Drawer, DrawerCard, Icon } from "@abacus/ui";
import type { JSX } from "react";
import { INTERIM_SUPPORT } from "./copy";

// The interim Support frame (P-01-T02; P-01 §2.2, AC 1.1.8): until SHL-05 ships with G-04, the
// Support pill opens an O2 drawer with the Accrued Support contact and a link to the System status
// page (Q-01-T41). Both addresses are deployment settings, never constants: without them the
// contact line and the link's target are left out. Undesigned, composed from the O2 kit.

export interface InterimSupportProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Defaults to VITE_SUPPORT_EMAIL. */
  email?: string | undefined;
  /** Defaults to VITE_STATUS_PAGE_URL. */
  statusUrl?: string | undefined;
}

export function InterimSupport({
  open,
  onOpenChange,
  email = import.meta.env.VITE_SUPPORT_EMAIL,
  statusUrl = import.meta.env.VITE_STATUS_PAGE_URL,
}: InterimSupportProps): JSX.Element {
  return (
    <Drawer open={open} onOpenChange={onOpenChange} title={INTERIM_SUPPORT.title}>
      <DrawerCard className="flex flex-col gap-[4px] px-[14px] py-[12px]">
        <p className="text-body font-medium text-ink">{INTERIM_SUPPORT.contact}</p>
        {email !== undefined && email !== "" && (
          <a href={`mailto:${email}`} className="text-body text-ink-2 underline">
            {INTERIM_SUPPORT.contactLine(email)}
          </a>
        )}
      </DrawerCard>
      <DrawerCard className="px-[14px] py-[12px]">
        <a
          {...(statusUrl === undefined || statusUrl === ""
            ? { "aria-disabled": "true" as const }
            : { href: statusUrl, target: "_blank", rel: "noreferrer" })}
          className="inline-flex items-center gap-[6px] text-body text-ink"
        >
          {INTERIM_SUPPORT.status}
          <Icon name="arrow-up-right" size={12} className="text-ink-3" />
        </a>
      </DrawerCard>
    </Drawer>
  );
}
