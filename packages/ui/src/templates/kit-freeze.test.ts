// F-06-T22 freeze check (F-06.md §10 "confirm no live-path kit diff after Sep 1"): the T6 and T10
// kits that tax and audit screens draw during the Sep 1 – Oct 20 change window are pinned by hash
// in docs/design/kit-freeze.json. Inside the window a pinned file that changed fails; outside it
// the test only checks that every pinned file reads, so the pins can be refreshed in the last
// batch before the window opens.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "../../../..");
const PINS = JSON.parse(readFileSync(join(ROOT, "docs/design/kit-freeze.json"), "utf8")) as {
  from: string;
  until: string;
  files: Record<string, string>;
};

async function hashOf(path: string): Promise<string> {
  const bytes = new TextEncoder().encode(readFileSync(join(ROOT, path), "utf8"));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** Inside the window (the day's date in UTC, both ends included). */
function frozen(today: string, from = PINS.from, until = PINS.until): boolean {
  return today >= from && today <= until;
}

describe("kit freeze (F-06-T22)", () => {
  it("the window is Sep 1 – Oct 20, 2027 inclusive", () => {
    expect(frozen("2027-08-31")).toBe(false);
    expect(frozen("2027-09-01")).toBe(true);
    expect(frozen("2027-10-20")).toBe(true);
    expect(frozen("2027-10-21")).toBe(false);
  });

  it("no pinned kit file changes inside the window", async () => {
    const now: Record<string, string> = {};
    for (const path of Object.keys(PINS.files)) now[path] = await hashOf(path);
    if (frozen(new Date().toISOString().slice(0, 10))) expect(now).toEqual(PINS.files);
    else expect(Object.keys(now)).toEqual(Object.keys(PINS.files));
  });
});
