import {
  ClockProvider,
  EmptyState,
  PortalBrandProvider,
  Toaster,
  TooltipProvider,
} from "@abacus/ui";
import { type JSX, type ReactNode, Suspense, useEffect } from "react";
import { nowMs } from "../app-core/clock";
import { PLANNED_VISIBLE } from "../app-core/planned";
import { type PortalBrandingOut, brandOf, useBranding } from "../domain/portal";

// The portal's providers (P-08-T07): business time, the firm's brand from `GET /v1/portal/
// branding`, tooltips and toasts. A chunk of its own, so the portal's first load is React, the
// router and the query client only, and the design system arrives with the first screen
// (scripts/bundle-budget.mjs: 150 KB initial).

/** The tab's title and icon from the branding (never the product's name). */
export function applyBranding(branding: PortalBrandingOut, doc: Document = document): void {
  doc.title = branding.portal_name ?? branding.firm_name ?? "Client portal";
  if (branding.logo_url === null) return;
  let icon = doc.querySelector<HTMLLinkElement>("link[rel='icon']");
  if (icon === null) {
    icon = doc.createElement("link");
    icon.rel = "icon";
    doc.head.append(icon);
  }
  icon.href = branding.logo_url;
}

export function PortalRoot({ children }: { children?: ReactNode }): JSX.Element | null {
  const branding = useBranding();
  useEffect(() => {
    if (branding.data !== undefined) applyBranding(branding.data);
  }, [branding.data]);
  if (branding.data === undefined) return null;
  return (
    <ClockProvider now={nowMs}>
      <PortalBrandProvider brand={brandOf(branding.data)}>
        <TooltipProvider>
          <Suspense fallback={null}>{children}</Suspense>
          <Toaster />
        </TooltipProvider>
      </PortalBrandProvider>
    </ClockProvider>
  );
}

/** A planned landing (POR-13, 14, 15, 18, 23; POR-01 d): fixture builds only (P-08 §2.2). */
export function NotBuilt(): JSX.Element | null {
  return PLANNED_VISIBLE ? <EmptyState title="Not built yet" /> : null;
}
