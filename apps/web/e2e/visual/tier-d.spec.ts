// Tier D: exact computed styles of the specimens (F-05-T16; chapter 04 §9.3). Not pixels, so it is
// robust to rasterisation and needs no baseline: it blocks everywhere the gallery runs. Each row is
// a number the kit handoff states (C-06 "Pill sizes", chapter 04's Tier D list) and the live
// element must compute to exactly. The templates' geometry (toolbar 46, subbar 42, audit bar 59,
// pane header 46, nav item 32) joins this table as each template merges.
import { expect, test } from "@playwright/test";
import { openGallery, specimen } from "./support";

type Expected = {
  height: string;
  fontSize: string;
  fontWeight: string;
  paddingLeft: string;
  paddingRight: string;
};

// Pill sizes, from the C-06 handoff sheet "02 Pill sizes": height, padding and type per size. The
// word picks the pill in the "Pill sizes" sheet of /components (`nth` where the word also appears
// on the variants sheet above it).
const PILLS: readonly {
  size: string;
  selector: string;
  expected: Expected;
}[] = [
  {
    size: "state",
    selector: 'span:text-is("In review") >> nth=-1',
    expected: {
      height: "21px",
      fontSize: "12px",
      fontWeight: "500",
      paddingLeft: "8px",
      paddingRight: "8px",
    },
  },
  {
    size: "card-state",
    selector: 'span:text-is("Planning")',
    expected: {
      height: "21px",
      fontSize: "11.5px",
      fontWeight: "500",
      paddingLeft: "9px",
      paddingRight: "9px",
    },
  },
  {
    size: "sm",
    selector: 'span:text-is("Matched") >> nth=-1',
    expected: {
      height: "19px",
      fontSize: "11px",
      fontWeight: "500",
      paddingLeft: "8px",
      paddingRight: "8px",
    },
  },
  {
    size: "micro",
    selector: 'span:text-is("MS")',
    expected: {
      height: "18px",
      fontSize: "10.5px",
      fontWeight: "500",
      paddingLeft: "5px",
      paddingRight: "6px",
    },
  },
  {
    size: "status",
    selector: 'span:text-is("Not started") >> nth=1',
    expected: {
      height: "25px",
      fontSize: "12.5px",
      fontWeight: "500",
      paddingLeft: "13px",
      paddingRight: "11px",
    },
  },
  {
    size: "outline",
    selector: 'span:text-is("Available") >> nth=-1',
    expected: {
      height: "22px",
      fontSize: "11.5px",
      fontWeight: "500",
      paddingLeft: "9px",
      paddingRight: "9px",
    },
  },
  {
    size: "tally",
    selector: 'span:text-is("tie")',
    expected: {
      height: "17px",
      fontSize: "10.5px",
      fontWeight: "500",
      paddingLeft: "6px",
      paddingRight: "6px",
    },
  },
  {
    size: "tag",
    selector: 'span:text-is("Factual") >> nth=-1',
    expected: {
      height: "23px",
      fontSize: "11.5px",
      fontWeight: "500",
      paddingLeft: "9px",
      paddingRight: "9px",
    },
  },
];

test.describe("tier D: computed styles", () => {
  test.beforeEach(async ({ page }) => {
    await openGallery(page);
  });

  for (const { size, selector, expected } of PILLS) {
    test(`pill size ${size}`, async ({ page }) => {
      const style = await specimen(page, "c-06-status-pill", selector).evaluate((el) => {
        const c = getComputedStyle(el);
        return {
          height: c.height,
          fontSize: c.fontSize,
          fontWeight: c.fontWeight,
          paddingLeft: c.paddingLeft,
          paddingRight: c.paddingRight,
          borderRadius: c.borderRadius,
          fontFamily: c.fontFamily,
        };
      });
      expect(style).toMatchObject(expected);
      expect(style.borderRadius, "pills are radius 999").toBe("999px");
      expect(style.fontFamily, "Geist").toMatch(/^Geist\b/);
    });
  }

  test("the page type is Geist 13 at 400", async ({ page }) => {
    const body = await page.evaluate(() => {
      const c = getComputedStyle(document.body);
      return { fontSize: c.fontSize, fontWeight: c.fontWeight, fontFamily: c.fontFamily };
    });
    expect(body).toMatchObject({ fontSize: "13px", fontWeight: "400" });
    expect(body.fontFamily).toMatch(/^Geist\b/);
  });

  test("the page type has the plan's 15.6px line", async ({ page }) => {
    // An open decision (tokens/DECISIONS.md, "body line height"): the body keeps 1.45 until
    // F-05-T05's question is closed. Expected to fail; when the decision lands this starts to pass
    // and Playwright reports the unexpected pass, which is the prompt to drop this marker.
    test.fail(true, "open decision: body line height 1.45 against the plan's 15.6px");
    const lineHeight = await page.evaluate(() => getComputedStyle(document.body).lineHeight);
    expect(lineHeight).toBe("15.6px");
  });

  test("a pane (the specimen sheets) has radius 12", async ({ page }) => {
    const radius = await specimen(page, "c-06-status-pill", "section >> nth=0").evaluate(
      (el) => getComputedStyle(el).borderRadius,
    );
    expect(radius).toBe("12px");
  });
});
