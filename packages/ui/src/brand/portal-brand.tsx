import { type JSX, type ReactNode, createContext, useContext } from "react";

// PortalBrand (F-05-T35; DEC-59, ADR-163): the firm's brand as the client portal draws it. It is
// the view model of `GET /v1/portal/branding` (P-08-T05 owns the endpoint and the logo re-encoding)
// and it carries slots only (ADR-163 decision 7): the firm's name, its portal name, logo, address
// line, help and privacy links, support contact, the "Secured by" footer switch, the sign-in
// methods and the maintenance banner. There is no colour, accent or CSS field: the accent is locked
// to espresso and a firm cannot override CSS variables (ADR-155). There is no default brand either:
// a portal surface outside a `PortalBrandProvider` throws, so it can never fall back to a product
// name.

/** How a client may confirm it is them (T15, TPL-15c, POR-01c). The card offers the methods the
 * branding returns, never constants (F-05 R11). */
export type SignInMethod = "email_code" | "sms_code" | "totp" | "passkey";

export const SIGN_IN_METHODS: readonly SignInMethod[] = [
  "email_code",
  "sms_code",
  "totp",
  "passkey",
];

export interface PortalBrand {
  /** The firm's name (`firm_name`): "Brightwater Hale". */
  readonly name: string;
  /** The portal's own name (`portal_name`) when the firm sets one; else the firm's name shows. */
  readonly portalName?: string;
  /** The firm's uploaded logo (`logo_url`), re-encoded and served same-origin (ADM-10). */
  readonly logo?: string;
  /** Without a logo the mark is drawn: the firm's initials, or the demo firm's wave. */
  readonly mark?: "initials" | "wave";
  /** The firm's address line for footers and letterheads (`address_line`). */
  readonly addressLine?: string;
  readonly helpUrl?: string;
  readonly privacyUrl?: string;
  /** Who a locked-out client should ask (`support_contact_name`). */
  readonly supportContactName?: string;
  /** "Secured by" under the portal (`secured_footer`), which the firm turns on in ADM-10. Default
   * off (DEC-59). */
  readonly securedFooter: boolean;
  /** The second steps the firm offers, in its order (`sign_in.methods`). */
  readonly signInMethods: readonly SignInMethod[];
  /** A banner the firm or the platform shows over the portal (`maintenance_banner`). */
  readonly maintenanceBanner?: string;
}

/** Every slot of `PortalBrand`, in order. The test holds this list to the type, so a new field
 * (and a colour field above all) cannot arrive unnoticed. */
export const PORTAL_BRAND_SLOTS = [
  "name",
  "portalName",
  "logo",
  "mark",
  "addressLine",
  "helpUrl",
  "privacyUrl",
  "supportContactName",
  "securedFooter",
  "signInMethods",
  "maintenanceBanner",
] as const satisfies readonly (keyof PortalBrand)[];

const BrandContext = createContext<PortalBrand | null>(null);

export interface PortalBrandProviderProps {
  brand: PortalBrand;
  children?: ReactNode;
}

/** Provides the firm's brand to every portal surface under it (PortalLayout, AuthCard). */
export function PortalBrandProvider({ brand, children }: PortalBrandProviderProps): JSX.Element {
  return <BrandContext.Provider value={brand}>{children}</BrandContext.Provider>;
}

/** The firm's brand. Throws outside a `PortalBrandProvider`: the portal has no default brand. */
export function usePortalBrand(): PortalBrand {
  const brand = useContext(BrandContext);
  if (brand === null) {
    throw new Error("usePortalBrand: wrap portal surfaces in a PortalBrandProvider");
  }
  return brand;
}
