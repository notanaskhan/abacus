// SHL-02 "Go…" palette (P-02-T12; P-02 §10, docs/screens/SHL-02.md): each artboard through the real
// shell, with axe (serious and critical = 0) and INV-1, INV-3 and INV-4 after every step
// (`journey.step`). In the fixture project the shell opens on SHL-02's own scenario
// (`?screen=SHL-02&st=<state>`, which turns `search.palette` on); the full stack reads the firm's
// flag and the C15 index, so only the states the seed itself produces run there (a, keyboard,
// portal). c and g stay fixture-only until W-02 and W-03 (agent mode, saved prompts).
import type { Page } from "@playwright/test";
import { DEMO_INSTANT, expect, openPalette, test } from "../harness";

declare const process: { env: Record<string, string | undefined> };

const HOSTED_URL: Readonly<Record<string, string | undefined>> = {
  staging: process.env.ABACUS_STAGING_URL,
  canary: process.env.ABACUS_CANARY_URL,
};
const SEP_28 = "2026-09-28T09:10:00-05:00";
const AGENT_RUNS =
  /\/v1\/(agent-runs|engagements\/[^/]+\/runs|workbench\/sessions\/[^/]+\/messages)/;

/** ⌘K (Ctrl+K off macOS), then the query; answers the combobox. */
async function go(page: Page, query: string) {
  const box = await openPalette(page); // a press before the shell's listener is retried (DEC-4735)
  await expect(box).toBeFocused();
  if (query !== "") await box.fill(query);
  return box;
}

const groups = (page: Page) => page.getByRole("listbox", { name: "Results" }).getByRole("group");

test.describe("SHL-02 palette", () => {
  test.beforeEach(({ journey }) => {
    const hosted = journey.project === "staging" || journey.project === "canary";
    test.skip(
      hosted && HOSTED_URL[journey.project] === undefined,
      `ABACUS_${journey.project.toUpperCase()}_URL is not set`,
    );
  });

  test("shl-02 a: typing feld groups results in canonical order", async ({ journey }) => {
    await journey.as("hannah-leclerc", "/", { clock: DEMO_INSTANT, scenario: "SHL-02:a" });
    await journey.step("SHL-02 a: feld", async (page) => {
      await go(page, "feld");
      await expect(groups(page).first()).toBeVisible();
      const labels = await groups(page).evaluateAll((els) =>
        els.map((e) => e.getAttribute("aria-label") ?? ""),
      );
      const canonical = ["Clients", "Returns", "Binders", "Files", "Inbox"];
      expect(labels.filter((l) => canonical.includes(l))).toEqual(canonical);
    });
  });

  test.describe("fixture states", () => {
    test.beforeEach(({ journey }) => {
      test.skip(journey.project !== "fixture", "the state is a fixture scenario (P-02-T11)");
    });

    test("shl-02 b: recents and create", async ({ journey }) => {
      await journey.as("hannah-leclerc", "/", { clock: DEMO_INSTANT, scenario: "SHL-02:b" });
      await journey.step("SHL-02 b: nothing typed", async (page) => {
        await go(page, "");
        await expect(page.getByRole("group", { name: "Recent" })).toBeVisible();
        await expect(page.getByRole("group", { name: "Create" })).toBeVisible();
      });
    });

    test("shl-02 d: no results with a visible-only suggestion", async ({ journey }) => {
      await journey.as("hannah-leclerc", "/", { clock: DEMO_INSTANT, scenario: "SHL-02:d" });
      await journey.step("SHL-02 d: pellstret", async (page) => {
        await go(page, "pellstret");
        await expect(page.getByText("No matches for 'pellstret'.")).toBeVisible();
        await expect(page.getByText("Try a client, form, period or file name.")).toBeVisible();
      });
    });

    test("shl-02 e: walled results absent and no count (INV-3)", async ({ journey }) => {
      await journey.as("hannah-leclerc", "/", { clock: DEMO_INSTANT, scenario: "SHL-02:e" });
      await journey.step(
        "SHL-02 e: feld behind a wall",
        async (page) => {
          await go(page, "feld");
          await expect(page.getByRole("group", { name: "Clients" })).toBeVisible();
          await expect(page.getByRole("group", { name: "Files" })).toHaveCount(0);
          await expect(page.getByRole("group", { name: "Inbox" })).toHaveCount(0);
          await expect(page.getByText(/hidden|walled|not shown|more you can't/i)).toHaveCount(0);
        },
        { outOfScope: ["Claire_Feld_2025_W2_MercerHill.pdf", "Re: 2025 tax documents"] },
      );
    });

    test("shl-02 a: the Actions group binds to the top client, none without one (P-02-T10)", async ({
      journey,
    }) => {
      await journey.as("hannah-leclerc", "/", { clock: DEMO_INSTANT, scenario: "SHL-02:a" });
      await journey.step("SHL-02 a: feld, then the client's actions", async (page) => {
        await go(page, "feld");
        const actions = page.getByRole("group", { name: "Actions" });
        await expect(
          actions.getByRole("option", { name: "New engagement for Jonah & Claire Feld…" }),
        ).toBeVisible();
        await expect(
          actions.getByRole("option", { name: "New to-do on Jonah & Claire Feld…" }),
        ).toBeVisible();
      });
      await journey.step("SHL-02 a: no client matched, no client actions", async (page) => {
        const box = page.getByRole("combobox", { name: "Search" });
        await box.fill("pellstret");
        await expect(page.getByText(/^New engagement for /u)).toHaveCount(0);
        await expect(page.getByText(/^New to-do on /u)).toHaveCount(0);
      });
    });

    test("shl-02 f: to-do opens SHL-17", async ({ journey }) => {
      await journey.as("hannah-leclerc", "/", { clock: SEP_28, scenario: "SHL-02:f" });
      await journey.step("SHL-02 f: granite, then a to-do", async (page) => {
        await go(page, "granite");
        const todos = page.getByRole("group", { name: "To-dos" });
        await expect(todos).toBeVisible();
        await todos.getByRole("option").first().click();
        await expect(page).toHaveURL(/[?&]ov=todos?[:%]/);
      });
    });

    test("shl-02 c: agent mode never starts a run (INV-1)", async ({ journey }) => {
      await journey.as("hannah-leclerc", "/", { clock: DEMO_INSTANT, scenario: "SHL-02:c" });
      const runs: string[] = [];
      journey.page.on("request", (r) => {
        if (r.method() === "POST" && AGENT_RUNS.test(r.url())) runs.push(r.url());
      });
      await journey.step("SHL-02 c: > lists the agents and starts nothing", async (page) => {
        await go(page, ">");
        const agents = page.getByRole("group", { name: "Run an agent" });
        await expect(agents).toBeVisible();
        await page.keyboard.press("Enter");
        expect(runs).toEqual([]);
      });
    });

    test("shl-02 g: saved prompt loads the composer and sends nothing (INV-1)", async ({
      journey,
    }) => {
      test.fixme(true, "W-03: saved prompts are gallery-only until W-03 registers them");
      await journey.as("hannah-leclerc", "/", { clock: SEP_28, scenario: "SHL-02:g" });
      await journey.step("SHL-02 g: explain", async (page) => {
        await go(page, "explain");
        await expect(page.getByRole("group", { name: "Saved prompts" })).toBeVisible();
      });
    });
  });

  test("shl-02 keyboard: ⌘K, arrows, enter, ⌘enter, esc returns focus", async ({ journey }) => {
    const scenario = journey.project === "fixture" ? { scenario: "SHL-02:a" } : {};
    await journey.as("hannah-leclerc", "/", { clock: DEMO_INSTANT, ...scenario });
    await journey.step("SHL-02 keyboard", async (page) => {
      // The shell first (a capture on an empty #root names nothing), then the element itself:
      // Esc returns focus to it, not to an element that serialises the same (DEC-4735).
      await expect(page.getByRole("navigation", { name: "Modules" })).toBeVisible();
      const before = await page.evaluateHandle(() => document.activeElement);
      const box = await go(page, "feld");
      await expect(page.getByRole("option").first()).toBeVisible();
      const first = await box.getAttribute("aria-activedescendant");
      await page.keyboard.press("ArrowDown");
      await expect(box).not.toHaveAttribute("aria-activedescendant", first ?? "");
      await page.keyboard.press("ArrowUp");
      await expect(box).toHaveAttribute("aria-activedescendant", first ?? "");
      // ⌘↵ opens in a new tab and keeps the palette open (R-5: the tab lands signed in).
      const [tab] = await Promise.all([
        page.context().waitForEvent("page"),
        page.keyboard.press("ControlOrMeta+Enter"),
      ]);
      await tab.waitForLoadState();
      await expect(tab.getByRole("navigation", { name: "Modules" })).toBeVisible();
      await tab.close();
      await expect(box).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(box).toHaveCount(0);
      expect(await page.evaluate((el) => el === document.activeElement, before)).toBe(true);
      await go(page, "feld");
      await page.keyboard.press("Enter");
      await expect(page.getByRole("combobox", { name: "Search" })).toHaveCount(0);
    });
  });

  test("shl-02 portal: no palette and search refused (INV-4)", async ({ journey }) => {
    await journey.as("claire-feld", "/");
    await journey.step(
      "SHL-02 portal: ⌘K does nothing for a client",
      async (page) => {
        await page.keyboard.press("ControlOrMeta+k");
        await expect(page.getByRole("combobox", { name: "Search" })).toHaveCount(0);
      },
      { probes: ["/v1/search/recents"] },
    );
  });
});
