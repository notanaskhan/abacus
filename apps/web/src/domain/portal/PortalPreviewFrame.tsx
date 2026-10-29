// ADM-10's live preview column (R-01-T28; R-01 §5.1, Story 8.2; DEC-20, ADR-024): a portal
// rendering inside the firm app, never an iframe or a portal session. The frame scales it (the
// split layout at 0.4, the phone at 0.7), makes everything in it inert (no focus, no clicks: the
// preview reaches no route and writes nothing), and labels it for assistive tech.

import type { PortalBrandOut } from "@abacus/api-client";
import { type PortalBrand, PortalBrandProvider } from "@abacus/ui";
import type { JSX, ReactNode } from "react";

export type PreviewDevice = "desktop" | "phone";

const SCALE: Readonly<Record<PreviewDevice, number>> = { desktop: 0.4, phone: 0.7 };
/** The portal frames the preview scales: T7 at 1424 × 860 and T7-M at 390 × 844. */
const SIZE: Readonly<Record<PreviewDevice, { width: number; height: number }>> = {
  desktop: { width: 1424, height: 860 },
  phone: { width: 390, height: 844 },
};

/** The preview's brand as the design system's portal brand: the firm's name, the portal's name,
 * its logo and the footer toggle. Sign-in methods play no part in a preview. */
export function previewBrand(brand: PortalBrandOut): PortalBrand {
  return {
    name: brand.sender_display_name,
    portalName: brand.portal_name,
    ...(brand.logo_url == null ? {} : { logo: brand.logo_url }),
    securedFooter: brand.secured_footer ?? false,
    signInMethods: [],
  };
}

export interface PortalPreviewFrameProps {
  brand: PortalBrandOut;
  device: PreviewDevice;
  /** "Preview as Claire Feld — read only". */
  label: string;
  children: ReactNode;
}

export function PortalPreviewFrame({
  brand,
  device,
  label,
  children,
}: PortalPreviewFrameProps): JSX.Element {
  const scale = SCALE[device];
  const { width, height } = SIZE[device];
  return (
    <figure
      aria-label={label}
      data-preview-device={device}
      className="relative m-0 overflow-hidden rounded-tile border border-hair bg-nested"
      style={{ height: Math.round(height * scale) }}
    >
      <div
        inert
        aria-hidden="true"
        className="pointer-events-none origin-top-left select-none"
        style={{
          width,
          height,
          transform: `scale(${String(scale)})`,
          ...(device === "phone"
            ? { marginLeft: `calc(50% - ${String(Math.round((width * scale) / 2))}px)` }
            : {}),
        }}
      >
        <PortalBrandProvider brand={previewBrand(brand)}>{children}</PortalBrandProvider>
      </div>
    </figure>
  );
}
