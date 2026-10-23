// ac-test-author: ayushkbhatia
// SPEC-025 AC-9 (TASK-044; back-filled by Q-03-T008): every new screen of Act 1 has its loading,
// empty, error and not-allowed states, and colours come only from tokens. The screens TASK-044
// owns: the setup page, the acceptance, independence and letter records, and the "Your
// confirmations" card. (The roll-forward wizard is TASK-048's, back-filled by Q-03-T023.)
import type { SetupOut } from "@abacus/api-client";
import { cleanup, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, never, renderRoutes, signInForTest } from "../testing/support";
import { EngagementRecords } from "./EngagementRecords";
import { MyConfirmations } from "./MyConfirmations";
import { Setup } from "./Setup";

const E = "e1";
const SETUP_PATH = `GET /v1/engagements/${E}/setup`;
const EMPTY: SetupOut = {
  acceptance: null,
  letter: null,
  confirmations: [],
  letter_required: false,
  blocked: "acceptance_missing",
  steps: [],
  summary: "",
};

beforeEach(async () => {
  sessionStorage.clear();
  await signInForTest();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

function loading(container: HTMLElement): Promise<void> {
  return waitFor(() => {
    expect(container.querySelector(".animate-pulse, [role='status']")).not.toBeNull();
  });
}

describe("ac9 the setup page", () => {
  const render = () => renderRoutes([{ path: "/", component: () => <Setup engagementId={E} /> }]);

  it("test_ac9_setup_loading_state", async () => {
    mockApi({ [SETUP_PATH]: never });
    const { container } = render();
    await loading(container);
  });

  it("test_ac9_setup_error_state", async () => {
    mockApi({ [SETUP_PATH]: () => json({ detail: "boom" }, 500) });
    render();
    expect(await screen.findByText("Couldn't load the setup")).toBeTruthy();
  });

  it("test_ac9_setup_not_allowed_state", async () => {
    mockApi({ [SETUP_PATH]: () => json({ detail: "forbidden" }, 403) });
    render();
    expect(await screen.findByText("Not available")).toBeTruthy();
  });
});

describe("ac9 acceptance, independence and the letter", () => {
  const render = () =>
    renderRoutes([
      {
        path: "/",
        component: () => <EngagementRecords engagementId={E} role="engagement_partner" />,
      },
    ]);

  it("test_ac9_records_loading_state", async () => {
    mockApi({ [SETUP_PATH]: never });
    const { container } = render();
    await loading(container);
  });

  it("test_ac9_records_error_state", async () => {
    mockApi({ [SETUP_PATH]: () => json({ detail: "boom" }, 500) });
    render();
    expect(await screen.findByText("Couldn't load acceptance and independence")).toBeTruthy();
  });

  it("test_ac9_records_not_allowed_state", async () => {
    mockApi({ [SETUP_PATH]: () => json({ detail: "forbidden" }, 403) });
    render();
    expect(await screen.findByText("Not available")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull(); // nothing to record
  });

  it("test_ac9_records_empty_independence_state", async () => {
    mockApi({ [SETUP_PATH]: () => json(EMPTY) });
    render();
    expect(await screen.findByText("No one on the team has been asked yet.")).toBeTruthy();
  });
});

describe("ac9 your confirmations card", () => {
  const render = () => renderRoutes([{ path: "/", component: () => <MyConfirmations /> }]);

  it("test_ac9_the_card_is_absent_while_loading_empty_or_refused", async () => {
    for (const handler of [
      never,
      () => json([]),
      () => json({ detail: "forbidden" }, 403),
      () => json({ detail: "boom" }, 500),
    ]) {
      mockApi({ "GET /v1/firm/confirmations": handler });
      render();
      await waitFor(() => {
        expect(screen.queryByText("Your independence confirmations")).toBeNull();
      });
      cleanup();
    }
  });
});

// --- colours only from tokens --------------------------------------------------------------------

type Fs = { readFileSync: (path: string, encoding: "utf8") => string };
const cwd = (globalThis as unknown as { process: { cwd: () => string } }).process.cwd();
const SCREENS = ["Setup", "EngagementRecords", "MyConfirmations"];
// As spec024states: hex, rgb/hsl, Tailwind's numbered palette, black or white, arbitrary values.
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
