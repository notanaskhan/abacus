// F-05-T31: independent INV-1 and INV-5 tests over every /components specimen (ADR-078), from
// plan 04 rule 9 and lint L6 and F-05 H1: "A role sweep finds no approve, sign off, release, send,
// post or decide control on an agent-owned element and no row reads Approved by Accrued Agent."
// The gallery calls no API: only the dev server is needed (`make dev-fixtures`).
import { expect, test, type Page } from "@playwright/test";

const VERBS = ["Approve", "Sign off", "Release", "Send", "Post", "Decide", "Adopt"];
const VERB = new RegExp(`^(${VERBS.join("|")})\\b`, "i");

async function gallery(page: Page): Promise<void> {
  await page.goto("/components");
  await expect(page.getByRole("heading", { name: "Components", level: 1 })).toBeVisible();
}

test("INV-1: no human-only verb sits on an agent-owned element", async ({ page }) => {
  await gallery(page);
  const offenders = await page.evaluate((source) => {
    const verb = new RegExp(source, "i");
    const controls = [
      ...document.querySelectorAll<HTMLElement>(
        'section[id] :is(button, a[href], [role="button"], [role="menuitem"], [role="link"])',
      ),
    ];
    return controls
      .filter((el) => {
        const name = (el.getAttribute("aria-label") ?? el.textContent).trim();
        return verb.test(name) && el.closest('[data-actor="agent"]') !== null;
      })
      .map((el) => `${el.closest("section[id]")?.id ?? "?"}: ${el.textContent.trim()}`);
  }, VERB.source);
  expect(offenders).toEqual([]);
});

test("INV-1: every human-only verb control in the specimens is a HumanAction", async ({
  page,
}) => {
  await gallery(page);
  const loose = await page.evaluate((source) => {
    const verb = new RegExp(source, "i");
    return [...document.querySelectorAll<HTMLElement>('section[id] :is(button, [role="button"])')]
      .filter((el) => verb.test((el.getAttribute("aria-label") ?? el.textContent).trim()))
      .filter((el) => !el.hasAttribute("data-human-verb"))
      .map((el) => `${el.closest("section[id]")?.id ?? "?"}: ${el.textContent.trim()}`);
  }, VERB.source);
  expect(loose, "human verbs rendered outside HumanAction").toEqual([]);
});

test("INV-5: nothing reads that the agent approved, signed, released, sent, posted, decided or adopted", async ({
  page,
}) => {
  await gallery(page);
  const text = await page.evaluate(() => document.body.innerText);
  const banned =
    /\b(Approved|Signed off|Released|Sent|Posted|Decided|Adopted) by (the )?Accrued Agent\b/i;
  expect(text).not.toMatch(banned);
});
