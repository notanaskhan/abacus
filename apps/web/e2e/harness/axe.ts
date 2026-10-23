// axeStep (F-04-T21; F-04 §5 Accessibility; ch. 04 §9.5): axe after every journey step and on
// every open overlay. Serious or critical findings = 0 (FE-02). There is no rule-disable list and
// no way to pass one (AGENTS.md rule 13). Each run attaches its findings to the test report, so a
// CI job can publish them (F-04-T28).
import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const BLOCKING = new Set(["serious", "critical"]);

export interface AxeStepOptions {
  /** Scope axe to a region (an open overlay, an artboard); the whole page by default. */
  include?: string;
  /** Also run under forced-colors emulation (the first step of each journey). */
  forcedColors?: boolean;
}

/** Let one-off entrance animations finish (axe measures a fade mid-flight otherwise); looping
 * ones (spinners, skeleton pulse) keep running. Waits on state, never on time. */
export async function settle(page: Page): Promise<void> {
  await page.waitForFunction(() =>
    document
      .getAnimations()
      .every(
        (a) => a.playState !== "running" || a.effect?.getComputedTiming().iterations === Infinity,
      ),
  );
}

async function blocking(page: Page, include: string | undefined): Promise<string[]> {
  await settle(page);
  let builder = new AxeBuilder({ page });
  if (include !== undefined) builder = builder.include(include);
  const { violations } = await builder.analyze();
  return violations
    .filter((v) => BLOCKING.has(v.impact ?? ""))
    .map(
      (v) =>
        `${v.id} (${v.impact ?? "?"}): ${v.help} — ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`,
    );
}

/** axe on the page as it stands after `step`; fails naming the step and every blocking finding. */
export async function axeStep(
  page: Page,
  step: string,
  options: AxeStepOptions = {},
): Promise<void> {
  const findings = await blocking(page, options.include);
  let forced: string[] = [];
  if (options.forcedColors === true) {
    await page.emulateMedia({ forcedColors: "active" });
    try {
      forced = (await blocking(page, options.include)).map((f) => `forced colors: ${f}`);
    } finally {
      await page.emulateMedia({ forcedColors: "none" });
    }
  }
  const all = [...findings, ...forced];
  await test.info().attach(`axe · ${step}`, {
    body: JSON.stringify({ step, url: page.url(), findings: all }, null, 2),
    contentType: "application/json",
  });
  expect(all, `${step}: serious or critical accessibility findings`).toEqual([]);
}

/** Under reduced motion nothing animates once the step has settled (F-04 §5). */
export async function assertStill(page: Page, step: string): Promise<void> {
  await settle(page);
  const running = await page.evaluate(
    () => document.getAnimations().filter((a) => a.playState === "running").length,
  );
  expect(running, `${step}: animations running under reduced motion`).toBe(0);
}
