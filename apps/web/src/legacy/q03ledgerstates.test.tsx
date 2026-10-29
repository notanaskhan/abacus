// ac-test-author: ayushkbhatia
// Q-03-T023 and Q-03-T024: the screen-state ACs of the back-filled tasks. SPEC-034 AC-9
// (TASK-070): the general ledger section has its loading, error and not-allowed states, and
// colours come only from tokens. SPEC-025 AC-9 (TASK-048) and SPEC-022 AC-6 (TASK-038) went
// with the roll-forward review and the Board (ENG-13 and AUD-03 carry them). Copy for the states is not fixed by the specs, so the tests assert the state
// exists (a busy indicator, an error said in words, no upload offered when refused), not its words.
import { cleanup, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, never, renderRoutes, signInForTest } from "../testing/support";
import { GlExport } from "./GlExport";

const E = "e1";
const BASE = `/v1/engagements/${E}/connection/import/gl`;
const FORMATS = [
  { id: "qbo_gl_csv", system: "QuickBooks Online", file_type: "csv", steps: ["Export it."] },
];

beforeEach(async () => {
  sessionStorage.clear();
  await signInForTest();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

function section(formats: () => Response | Promise<Response>, latest = formats): HTMLElement {
  mockApi({ [`GET ${BASE}/formats`]: formats, [`GET ${BASE}`]: latest });
  return renderRoutes([{ path: "/", component: () => <GlExport engagementId={E} /> }]).container;
}

describe("SPEC-034 ac9 the general ledger section", () => {
  it("test_ac9_gl_loading_state", async () => {
    const container = section(never);
    await waitFor(() => {
      expect(container.querySelector(".animate-pulse, [role='status']")).not.toBeNull();
    });
  });

  it("test_ac9_gl_error_state_is_said_in_words", async () => {
    const container = section(
      () => json(FORMATS),
      () => json({ detail: "boom" }, 500),
    );
    await waitFor(() => {
      const text = container.textContent;
      expect(/couldn.t|could not|try again|went wrong|unavailable/i.test(text)).toBe(true);
    });
  });

  it("test_ac9_gl_not_allowed_state_offers_no_upload", async () => {
    const container = section(() => json({ detail: "forbidden" }, 403));
    await waitFor(() => {
      expect(container.querySelector(".animate-pulse")).toBeNull();
    });
    expect(container.querySelector("input[type='file']")).toBeNull();
    expect(screen.queryByText(/QuickBooks Online/)).toBeNull();
  });
});

// --- colours only from tokens --------------------------------------------------------------------

type Fs = { readFileSync: (path: string, encoding: "utf8") => string };
const cwd = (globalThis as unknown as { process: { cwd: () => string } }).process.cwd();
// The Board was retired for AUD-03 by A-01-T21 (DEC-442; SPEC-330 section 8 maps its tests), and
// the roll-forward review for ENG-13 by P-07-T58 (DEC-904; TASK-1812 maps its tests).
const SCREENS = ["GlExport"];
// As spec024states and spec025states: hex, rgb/hsl, Tailwind's numbered palette, black or white,
// arbitrary values.
const LITERAL =
  /#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(|\b(?:text|bg|border|ring|fill|stroke)-(?:(?:red|green|blue|gray|slate|zinc|neutral|stone|amber|yellow|orange|emerald|sky|indigo|violet|purple|pink|rose)-\d{2,3}|black|white)\b|\[(?:#|rgb|hsl)/i;

describe("ac9 tokens only", () => {
  it.each(SCREENS)("test_ac9_%s_uses_no_literal_colour", async (name) => {
    const fsModule = "node:fs";
    const fs = (await import(/* @vite-ignore */ fsModule)) as Fs;
    const source = fs.readFileSync(`${cwd}/src/legacy/${name}.tsx`, "utf8");
    const found = source
      .split("\n")
      .filter((line) => !line.trimStart().startsWith("//") && LITERAL.test(line));
    expect(found).toEqual([]);
  });
});
