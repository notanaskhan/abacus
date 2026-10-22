import { type JSX, type ReactNode, useState } from "react";
import { type PortalBrand, PortalBrandProvider } from "../brand";
import { Pane } from "../layout/pane";
import { PortalLayout, type PortalLayoutProps, portalNav } from "../templates/portal-layout";
import { FIRM } from "./seed-figures";

// T7 PortalLayout (F-05-T35): the frames the T7 handoff draws, white-labelled for Brightwater
// Hale. The split window (T7a to T7f's frame), the reduced 720 pane (T7g), the 390 phone with the
// bottom tab bar (T7-M, DEC-45) and its More sheet, an entity client's nav with Approvals, and the
// "Secured by" footer the firm may turn on. The panes are the frame only: the C-16 Request kit
// (F-05-T36) fills them.

/** The demo firm's brand as `GET /v1/portal/branding` would return it. */
export const BRIGHTWATER_BRAND: PortalBrand = {
  name: FIRM,
  mark: "wave",
  securedFooter: false,
  signInMethods: ["email_code", "sms_code", "passkey"],
};

/** An artboard's caption, as the canvas labels it. */
export function Artboard({
  id,
  badge,
  name,
  note,
  children,
}: {
  /** The artboard's key for tests and parity selectors: `t7a`, `tpl-07-m`. */
  id: string;
  badge: string;
  name: string;
  note: string;
  children: ReactNode;
}): JSX.Element {
  return (
    <figure data-artboard={id} className="flex flex-col gap-3">
      <figcaption className="flex items-center gap-[10px] px-[2px]">
        <span className="inline-flex h-[22px] items-center rounded-pill bg-espresso px-[8px] text-meta font-medium text-on-dark">
          {badge}
        </span>
        <span className="text-title font-medium">{name}</span>
        <span className="text-dense text-ink-2">{note}</span>
      </figcaption>
      <div className="max-w-full overflow-x-auto">{children}</div>
    </figure>
  );
}

const INDIVIDUAL = portalNav("individual");
const ENTITY = portalNav("entity");

function Frame({
  brand = BRIGHTWATER_BRAND,
  ...props
}: Omit<PortalLayoutProps, "frame"> & { brand?: PortalBrand }): JSX.Element {
  const [active, setActive] = useState(props.active ?? "Documents");
  return (
    <PortalBrandProvider brand={brand}>
      <PortalLayout
        {...props}
        active={active}
        onNavigate={setActive}
        frame
        height={props.height ?? (props.variant === "mobile" ? 844 : 860)}
      />
    </PortalBrandProvider>
  );
}

export function PortalLayoutSpecimen(): JSX.Element {
  return (
    <div className="flex flex-col gap-6">
      <Artboard
        id="t7-split"
        badge="T7"
        name="Split"
        note="Portal toolbar 46 · the 336 rail beside the pane"
      >
        <Frame
          variant="split"
          user="Dana Whitley"
          nav={INDIVIDUAL}
          rail={<Pane title="2025 Binder" />}
        >
          <Pane title="Documents" well />
        </Frame>
      </Artboard>
      <Artboard id="t7g" badge="T7g" name="Reduced" note="One centered 720 pane">
        <Frame variant="reduced" user="Claire Feld" nav={INDIVIDUAL}>
          <Pane title="Documents" well />
        </Frame>
      </Artboard>
      <div className="flex flex-wrap items-start gap-6">
        <Artboard id="t7-m" badge="T7-M" name="Mobile" note="390 wide, for Dana Whitley">
          <Frame variant="mobile" user="Dana Whitley" nav={INDIVIDUAL} />
        </Artboard>
        <Artboard
          id="t7-m-more"
          badge="T7-M"
          name="More"
          note="Questions and Deliverables under More"
        >
          <Frame variant="mobile" user="Dana Whitley" nav={INDIVIDUAL} moreForceState="open" />
        </Artboard>
        <Artboard
          id="t7-m-entity"
          badge="T7-M"
          name="Entity client"
          note="Approvals joins the More sheet"
        >
          <Frame
            variant="mobile"
            user="Dana Kowalski"
            nav={ENTITY}
            active="Approvals"
            moreForceState="open"
          />
        </Artboard>
      </div>
      <Artboard
        id="t7-entity"
        badge="T7"
        name="Entity client"
        note="Approvals in the bar, Messages 1"
      >
        <Frame
          variant="split"
          user="Dana Kowalski"
          nav={portalNav("entity", { Messages: 1 })}
          active="Approvals"
          rail={<Pane title="2025 Binder" />}
        >
          <Pane title="Approvals" well />
        </Frame>
      </Artboard>
      <Artboard
        id="t7-secured"
        badge="T7"
        name="Secured by"
        note="The firm turned the footer on (ADM-10)"
      >
        <Frame
          brand={{ ...BRIGHTWATER_BRAND, securedFooter: true }}
          variant="reduced"
          user="Claire Feld"
          nav={INDIVIDUAL}
        >
          <Pane title="Documents" well />
        </Frame>
      </Artboard>
    </div>
  );
}
