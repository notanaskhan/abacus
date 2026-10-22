import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  PORTAL_BRAND_SLOTS,
  type PortalBrand,
  PortalBrandProvider,
  usePortalBrand,
} from "../brand/portal-brand";
import { MobileTabBar, splitMobileNav } from "../layout/mobile-tab-bar";
import { Pane } from "../layout/pane";
import { PortalLayout, type PortalLayoutProps, portalNav } from "./portal-layout";

// F-05-T35 acceptance: "T7g and T7-M at 390px with the 64px bottom tab bar render, Approvals hides
// for an individual client, and the brand type has no colour fields." Plus the white label
// (DEC-59): no product name unless the firm turns the footer on, and no default brand.

const BRAND: PortalBrand = {
  name: "Brightwater Hale",
  mark: "wave",
  securedFooter: false,
  signInMethods: ["email_code", "sms_code", "passkey"],
};

afterEach(cleanup);

function renderLayout(
  props: Partial<PortalLayoutProps> & Pick<PortalLayoutProps, "variant">,
  brand: PortalBrand = BRAND,
) {
  return render(
    <PortalBrandProvider brand={brand}>
      <PortalLayout
        user="Claire Feld"
        nav={portalNav("individual")}
        active="Documents"
        {...props}
      />
    </PortalBrandProvider>,
  );
}

describe("PortalBrand: slots only", () => {
  it("the brand type has no colour fields", () => {
    // Type level: the slot list is exactly the type's keys, both ways.
    type Slots = (typeof PORTAL_BRAND_SLOTS)[number];
    const everyKey: Record<keyof PortalBrand, true> = {
      name: true,
      portalName: true,
      logo: true,
      mark: true,
      addressLine: true,
      helpUrl: true,
      privacyUrl: true,
      supportContactName: true,
      securedFooter: true,
      signInMethods: true,
      maintenanceBanner: true,
    } satisfies Record<Slots, true>;
    expect(Object.keys(everyKey).sort()).toEqual([...PORTAL_BRAND_SLOTS].sort());
    for (const slot of PORTAL_BRAND_SLOTS) {
      expect(slot).not.toMatch(/colou?r|accent|theme|css|hex|palette|tint|ink|style/i);
    }
  });

  it("has no default: a portal surface outside the provider throws", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    function Probe(): null {
      usePortalBrand();
      return null;
    }
    expect(() => render(<Probe />)).toThrow(/PortalBrandProvider/);
    vi.restoreAllMocks();
  });
});

describe("portalNav: Approvals hides for an individual client", () => {
  it("an individual client's areas", () => {
    expect(portalNav("individual").map((i) => i.label)).toEqual([
      "Home",
      "Documents",
      "Questions",
      "Sign",
      "Messages",
      "Deliverables",
    ]);
  });

  it("an entity client sees Approvals after Questions", () => {
    expect(portalNav("entity").map((i) => i.label)).toEqual([
      "Home",
      "Documents",
      "Questions",
      "Approvals",
      "Sign",
      "Messages",
      "Deliverables",
    ]);
  });

  it("counts sit beside their area", () => {
    const messages = portalNav("individual", { Messages: 1 }).find((i) => i.label === "Messages");
    expect(messages?.count).toBe(1);
  });

  it("the toolbar of an individual client has no Approvals; an entity client's has", () => {
    renderLayout({ variant: "split" });
    const bar = screen.getByRole("navigation", { name: "Portal" });
    expect(within(bar).queryByRole("button", { name: /Approvals/ })).toBeNull();
    cleanup();
    renderLayout({ variant: "split", nav: portalNav("entity") });
    expect(
      within(screen.getByRole("navigation", { name: "Portal" })).getByRole("button", {
        name: /Approvals/,
      }),
    ).toBeTruthy();
  });

  it("at 390 the More sheet of an individual client has no Approvals; an entity client's has", () => {
    expect(splitMobileNav(portalNav("individual")).more.map((i) => i.label)).toEqual([
      "Questions",
      "Deliverables",
    ]);
    expect(splitMobileNav(portalNav("entity")).more.map((i) => i.label)).toEqual([
      "Questions",
      "Approvals",
      "Deliverables",
    ]);
  });
});

describe("T7 variants", () => {
  it("split: the toolbar, the 336 rail and the main pane", () => {
    const { container } = renderLayout({
      variant: "split",
      rail: <Pane title="2025 Binder" />,
      children: <Pane title="Documents" well />,
    });
    expect(container.querySelector('[data-shell="portal-toolbar"]')).not.toBeNull();
    const rail = container.querySelector('[data-portal="rail"]');
    expect(rail?.className).toContain("w-(--rail-w-portal)");
    expect(screen.getByRole("heading", { name: "2025 Binder" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Documents" })).toBeTruthy();
  });

  it("T7g reduced: one centred 720 pane, no rail", () => {
    const { container } = renderLayout({
      variant: "reduced",
      rail: <Pane title="2025 Binder" />,
      children: <Pane title="Documents" well />,
    });
    expect(container.querySelector('[data-portal="rail"]')).toBeNull();
    const main = container.querySelector('[data-portal="main"]');
    expect(main?.className).toContain("w-[720px]");
    expect(main?.className).toContain("mx-auto");
  });

  it("T7-M renders at 390 with the 56 header and the 64 bottom tab bar", () => {
    const { container } = renderLayout({ variant: "mobile", frame: true });
    const phone = container.querySelector('[data-variant="portal-mobile"]');
    expect(phone?.className).toContain("w-[390px]");
    expect(phone?.className).toContain("rounded-phone");
    expect((phone as HTMLElement).style.height).toBe("844px");
    expect(container.querySelector('[data-shell="mobile-header"]')?.className).toContain(
      "h-[56px]",
    );
    const bar = container.querySelector('[data-shell="mobile-tab-bar"]');
    expect(bar?.className).toContain("h-[64px]");
    expect(container.querySelector('[data-shell="portal-toolbar"]')).toBeNull();
    const tabs = within(bar as HTMLElement).getAllByRole("button");
    expect(tabs.map((t) => t.textContent)).toEqual([
      "Home",
      "Documents",
      "Sign",
      "Messages",
      "More",
    ]);
    expect(
      within(bar as HTMLElement)
        .getByRole("button", { name: "Documents" })
        .getAttribute("aria-current"),
    ).toBe("page");
  });

  it("T7-M targets are at least 44 high", () => {
    const { container } = renderLayout({ variant: "mobile" });
    for (const tab of within(
      container.querySelector('[data-shell="mobile-tab-bar"]') as HTMLElement,
    ).getAllByRole("button")) {
      expect(tab.className).toContain("min-h-[44px]");
    }
    expect(screen.getByRole("button", { name: "Claire Feld" }).className).toContain("size-[44px]");
  });
});

describe("MobileTabBar: the More sheet", () => {
  it("opens on More, moves with the arrows, closes on Escape and returns focus", () => {
    const onNavigate = vi.fn();
    render(
      <div className="relative">
        <MobileTabBar nav={portalNav("entity")} active="Documents" onNavigate={onNavigate} />
      </div>,
    );
    const more = screen.getByRole("button", { name: "More" });
    expect(more.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(more);
    const sheet = screen.getByRole("menu", { name: "More" });
    const items = within(sheet).getAllByRole("menuitem");
    expect(items.map((i) => i.textContent)).toEqual(["Questions", "Approvals", "Deliverables"]);
    expect(document.activeElement).toBe(items[0]);
    fireEvent.keyDown(sheet, { key: "ArrowDown" });
    expect(document.activeElement).toBe(items[1]);
    fireEvent.keyDown(sheet, { key: "ArrowUp" });
    fireEvent.keyDown(sheet, { key: "ArrowUp" });
    expect(document.activeElement).toBe(items[2]);
    fireEvent.keyDown(sheet, { key: "Escape" });
    expect(screen.queryByRole("menu")).toBeNull();
    expect(document.activeElement).toBe(more);
  });

  it("an item navigates and closes the sheet; More reads current for an area under it", () => {
    const onNavigate = vi.fn();
    const { rerender } = render(
      <MobileTabBar nav={portalNav("individual")} active="Documents" onNavigate={onNavigate} />,
    );
    fireEvent.click(screen.getByRole("button", { name: "More" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Deliverables" }));
    expect(onNavigate).toHaveBeenCalledWith("Deliverables");
    expect(screen.queryByRole("menu")).toBeNull();
    rerender(
      <MobileTabBar nav={portalNav("individual")} active="Deliverables" onNavigate={onNavigate} />,
    );
    expect(screen.getByRole("button", { name: "More" }).getAttribute("aria-current")).toBe("page");
  });

  it("a tap outside closes it", () => {
    const { container } = render(<MobileTabBar nav={portalNav("individual")} />);
    fireEvent.click(screen.getByRole("button", { name: "More" }));
    fireEvent.click(container.querySelector('[data-shell="more-scrim"]') as HTMLElement);
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("forceState open draws the sheet in place and takes no focus", () => {
    render(<MobileTabBar nav={portalNav("individual")} forceState="open" />);
    expect(screen.getByRole("menu", { name: "More" })).toBeTruthy();
    expect(document.activeElement).toBe(document.body);
  });
});

describe("white label (DEC-59)", () => {
  it.each(["split", "reduced", "mobile"] as const)(
    "%s shows the firm's name and never the product's",
    (variant) => {
      const { container } = renderLayout({ variant, frame: true });
      expect(container.textContent).toContain("Brightwater Hale");
      expect(container.textContent).not.toMatch(/accrued/i);
      expect(container.querySelector('[data-shell="portal-footer"]')).toBeNull();
    },
  );

  it.each(["split", "reduced", "mobile"] as const)(
    "%s draws the Secured by footer only when the firm turns it on",
    (variant) => {
      const { container } = renderLayout(
        { variant, frame: true },
        { ...BRAND, securedFooter: true },
      );
      expect(container.querySelector('[data-shell="portal-footer"]')).not.toBeNull();
    },
  );
});
