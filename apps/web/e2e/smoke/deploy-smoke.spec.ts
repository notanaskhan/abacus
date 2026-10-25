// The deploy smoke (Q-01-T32; Q-01 F5 and §10): after each staging batch deploy and each
// production promotion, against the deployed hosts. Edge first (no session needed): the response
// headers of chapter 04 §1.4, the operational routes blocked at the edge, and the release's
// runtime-config.json. Then, signed in as the smoke user (`@signed-in`, SMOKE_SIGN_IN=on): the
// engagements list, with axe on each page (serious and critical = 0).
//
// Not yet here (TASK-1238): "clean upload is scanned and previewed", "EICAR is refused" and
// "simulator email recorded" need the smoke user's binder on the canary firm and the sink mailbox
// reader (F-04-T22); they join this file with them.
import { expect, test } from "@playwright/test";
import { axeStep } from "../harness/axe";
import { signInAsSmokeUser } from "./sign-in";

declare const process: { env: Record<string, string | undefined> };

function environment(): "staging" | "production" {
  const value = test.info().project.metadata.environment as unknown;
  if (value === "staging" || value === "production") return value;
  throw new Error(`project "${test.info().project.name}" names no smoke environment`);
}

test("smoke: edge headers and blocked operational routes", async ({ request }) => {
  const landing = await request.get("/");
  expect(landing.status()).toBe(200);
  const headers = landing.headers();
  expect(headers["strict-transport-security"]).toMatch(/max-age=63072000/);
  expect(headers["strict-transport-security"]).toMatch(/includeSubDomains/);
  expect(headers["x-content-type-options"]).toBe("nosniff");
  expect(headers["referrer-policy"]).toBeTruthy();
  expect(headers["content-security-policy"]).toMatch(/connect-src 'self'/);
  for (const path of ["/healthz", "/readyz"]) {
    expect((await request.get(path)).status(), path).toBe(403);
  }
});

test("smoke: runtime config names this environment and release", async ({ request }) => {
  const response = await request.get("/runtime-config.json");
  expect(response.status()).toBe(200);
  expect(response.headers()["cache-control"] ?? "").toMatch(/no-cache/);
  const config = (await response.json()) as Record<string, unknown>;
  expect(config.environment).toBe(environment());
  const release = process.env.SMOKE_RELEASE;
  if (release !== undefined && release !== "") expect(config.release).toBe(release);
});

test("smoke: sign in through WorkOS @signed-in", async ({ page }) => {
  await signInAsSmokeUser(page, environment());
  await expect(page.getByRole("heading", { name: "Engagements" })).toBeVisible();
  await axeStep(page, "signed in");
});

test("smoke: engagements list loads @signed-in", async ({ page }) => {
  await signInAsSmokeUser(page, environment());
  await page.goto("/engagements");
  await expect(page.getByRole("heading", { name: "Engagements" })).toBeVisible();
  await axeStep(page, "engagements list");
});
