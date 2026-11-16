// T-05-T69 (T-05 §5.4, §5.5, §10 items 3 and 4): the 57 entity-return artboards (TXP-00, 01, 02,
// 05, 06, 07, 10 and 11) at 1440×900, DPR 2, from the /components gallery on fixtures. Each one
// renders, axe finds nothing serious or critical in its frame, and the DOM grammar holds: "$" only
// on TXP-02's figures; negatives in parentheses and brick (--color-negative), never a minus; zero
// as "—" in ink-4; spinners ink-2, never amber; no zebra rows; TINs always masked.
// Run: `pnpm exec playwright test --project=chromium e2e/screens/TXP-entity.spec.ts`.
import AxeBuilder from "@axe-core/playwright";
import { type Locator, expect, test } from "@playwright/test";

const SERIOUS = new Set(["serious", "critical"]);

// One entry per artboard, in the screen contracts' order (docs/screens/TXP-xx.md, ## States).
export const ENTITY_ARTBOARDS: Readonly<Record<string, readonly string[]>> = {
  "TXP-00": ["a", "b", "c", "d", "e"],
  "TXP-01": ["a", "a2", "a3", "b", "c", "d"],
  "TXP-02": ["a", "a2", "a3", "b", "c", "d", "e", "e2", "f"],
  "TXP-05": ["a", "a2", "a3", "a4", "a5", "b", "c", "d"],
  "TXP-06": ["a", "a2", "b", "c", "c2", "d"],
  "TXP-07": ["a", "a2", "a3", "b", "b2", "c", "d", "e"],
  "TXP-10": ["a", "a2", "b", "c", "d", "e", "f"],
  "TXP-11": ["a", "a2", "a3", "b", "b2", "c", "d", "e"],
};

const NEGATIVE = "rgb(177, 51, 39)"; // --color-negative #B13327
const INK_2 = "rgba(43, 31, 23, 0.7)";
const INK_4 = "rgba(43, 31, 23, 0.3)";

test.use({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});

interface Grammar {
  dollars: number;
  minus: string[];
  negatives: string[];
  zeros: string[];
  spinners: string[];
  zebra: number;
  tins: string[];
}

/** The frame's figures and their computed colours, read in the page (DOM, not pixels). */
async function grammarOf(frame: Locator): Promise<Grammar> {
  return frame.evaluate((root) => {
    const cells = [...root.querySelectorAll<HTMLElement>("td, [role='cell'], [role='gridcell']")];
    const leaves = [...root.querySelectorAll<HTMLElement>("*")].filter(
      (el) => el.children.length === 0 && el.textContent.trim() !== "",
    );
    const text = (el: Element) => el.textContent.trim();
    const figure = /^\(?\$?[\d,]+(\.\d+)?\)?$/;
    const colour = (el: Element) => getComputedStyle(el).color;
    const rows = [...root.querySelectorAll<HTMLElement>("tbody tr, [role='row']")].filter(
      (r) => r.querySelector("td, [role='cell'], [role='gridcell']") !== null,
    );
    // Zebra: every other row painted, over six rows in a row (a total row or two between line
    // items is not a stripe).
    let zebra = 0;
    for (let i = 0; i + 5 < rows.length; i += 1) {
      const bg = rows.slice(i, i + 6).map((r) => getComputedStyle(r).backgroundColor);
      const even = bg[0] === bg[2] && bg[2] === bg[4];
      const odd = bg[1] === bg[3] && bg[3] === bg[5];
      if (even && odd && bg[0] !== bg[1]) zebra += 1;
    }
    return {
      dollars: cells.filter((c) => figure.test(text(c)) && text(c).includes("$")).length,
      minus: cells.map(text).filter((t) => /^[-−]\$?\d/.test(t)),
      negatives: leaves
        .filter((el) => /^\(\$?[\d,]+(\.\d+)?\)$/.test(text(el)))
        .map((el) => `${text(el)} ${colour(el)}`),
      zeros: leaves
        .filter((el) => el.closest("td, [role='cell'], [role='gridcell']") !== null)
        .filter((el) => text(el) === "—")
        .map(colour),
      spinners: [...root.querySelectorAll("[data-spinner]")].map(colour),
      zebra,
      tins: root.textContent.match(/\b\d{2}-\d{7}\b|\b\d{3}-\d{2}-\d{4}\b/g) ?? [],
    };
  });
}

for (const [screen, states] of Object.entries(ENTITY_ARTBOARDS)) {
  for (const st of states) {
    test(`${screen}${st}: renders, axe finds nothing serious, the grammar holds`, async ({
      page,
    }) => {
      await page.goto(`/components/screens/${screen}?st=${st}&frame=1`);
      const frame = page.locator(`[data-artboard='${st}']`);
      await expect(frame.locator("[data-shell='app']")).toBeVisible();
      await expect(frame.getByText("Ridgeline Property Partners, LP").first()).toBeVisible();
      await expect(frame.getByText("Loading the return")).toHaveCount(0);

      const { violations } = await new AxeBuilder({ page })
        .include(`[data-artboard='${st}']`)
        .analyze();
      const serious = violations
        .filter((v) => SERIOUS.has(v.impact ?? ""))
        .map((v) => `${v.id}: ${v.help} — ${v.nodes[0]?.target.join(" ") ?? ""}`);
      expect(serious, "axe serious or critical").toEqual([]);

      const g = await grammarOf(frame);
      if (screen === "TXP-02") expect(g.dollars, '"$" on TXP-02').toBeGreaterThan(0);
      else expect(g.dollars, '"$" only on TXP-02').toBe(0);
      expect(g.minus, "negatives never carry a minus").toEqual([]);
      expect(
        g.negatives.filter((n) => !n.endsWith(NEGATIVE)),
        "negatives in brick parentheses",
      ).toEqual([]);
      expect(
        g.zeros.filter((c) => c !== INK_4),
        'zero is "—" in ink-4',
      ).toEqual([]);
      expect(
        g.spinners.filter((c) => c !== INK_2),
        "spinners ink-2",
      ).toEqual([]);
      expect(g.zebra, "no zebra rows").toBe(0);
      expect(g.tins, "TINs masked").toEqual([]);
    });
  }
}
