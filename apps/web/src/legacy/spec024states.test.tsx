// ac-test-author: ayushkbhatia
// SPEC-024 AC-8 (TASK-040, TASK-041; back-filled by Q-03-T006 and T008): every new screen of
// Act 0 has its loading, empty, error and not-allowed states, and colours come only from tokens.
// The screens: sign-up, the onboarding checklist page (/admin/setup) and Autonomy (People is
// ADM-02's since G-01-T17).
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, never, renderRoutes, signInForTest } from "../testing/support";
import { Autonomy } from "./Autonomy";
import { Onboarding } from "./Onboarding";
import { Signup } from "./Signup";

const ME = {
  user_id: "00000000-0000-4000-8000-000000000001",
  display_name: "Sam Patel",
  email: "sam@whitfield.example",
  memberships: [],
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

// G-01-T17 (DEC-594): "ac8 People" (the retired FirmPeople screen's loading, error, not-allowed
// and empty states) moved to screens/ADM-02/ADM-02.test.tsx, mapped one for one in DEC-594.

describe("ac8 Autonomy", () => {
  const render = () => renderRoutes([{ path: "/", component: () => <Autonomy canSet /> }]);

  it("test_ac8_autonomy_loading_state", async () => {
    mockApi({ "GET /v1/firm/autonomy": never });
    const { container } = render();
    await loading(container);
  });

  it("test_ac8_autonomy_error_state", async () => {
    mockApi({ "GET /v1/firm/autonomy": () => json({ detail: "boom" }, 500) });
    render();
    expect(await screen.findByText("Couldn't load autonomy")).toBeTruthy();
  });

  it("test_ac8_autonomy_not_allowed_state_offers_no_choice", async () => {
    mockApi({ "GET /v1/firm/autonomy": () => json({ detail: "forbidden" }, 403) });
    render();
    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeTruthy();
    });
    expect(screen.queryByRole("radio")).toBeNull();
    expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
  });
});

describe("ac8 the onboarding checklist page", () => {
  const render = () => renderRoutes([{ path: "/", component: () => <Onboarding always /> }]);

  it("test_ac8_checklist_loading_state", async () => {
    mockApi({ "GET /v1/firm/onboarding": never });
    const { container } = render();
    await loading(container);
  });

  it("test_ac8_checklist_error_state", async () => {
    mockApi({ "GET /v1/firm/onboarding": () => json({ detail: "boom" }, 500) });
    render();
    expect(await screen.findByText("Couldn't load the checklist")).toBeTruthy();
  });

  it("test_ac8_checklist_not_allowed_state", async () => {
    mockApi({ "GET /v1/firm/onboarding": () => json({ detail: "forbidden" }, 403) });
    render();
    expect(await screen.findByText("Not available")).toBeTruthy();
    expect(screen.queryByText("Get your firm ready")).toBeNull();
  });
});

describe("ac8 sign-up", () => {
  it("test_ac8_signup_shows_why_a_sign_up_was_refused", async () => {
    mockApi({
      "POST /v1/signup": () => json({ detail: "signup_code_invalid" }, 409),
    });
    renderRoutes([{ path: "/", component: () => <Signup /> }]);
    const name = await screen.findByLabelText(/Firm name/i);
    const code = screen.getByLabelText(/code/i);
    fireEvent.change(name, { target: { value: "Whitfield & Lane" } });
    fireEvent.change(code, { target: { value: "ABCD-EFGH-JKMN-PQRS" } });
    fireEvent.click(screen.getByRole("button", { name: "Create firm" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
  });
});

// --- colours only from tokens --------------------------------------------------------------------

type Fs = { readFileSync: (path: string, encoding: "utf8") => string };
const cwd = (globalThis as unknown as { process: { cwd: () => string } }).process.cwd();
// FirmPeople retired (G-01-T17, DEC-594); ADM-02 is held to tokens by eslint's token rule.
const SCREENS = ["Signup", "Onboarding", "Autonomy"];
// A literal colour: hex, rgb/hsl functions, Tailwind's default numbered palette, black or white
// (the tokens name neither), or an arbitrary value. Token names such as `green-tint` pass.
const LITERAL =
  /#[0-9a-f]{3,8}\b|rgba?\(|hsla?\(|\b(?:text|bg|border|ring|fill|stroke)-(?:(?:red|green|blue|gray|slate|zinc|neutral|stone|amber|yellow|orange|emerald|sky|indigo|violet|purple|pink|rose)-\d{2,3}|black|white)\b|\[(?:#|rgb|hsl)/i;

describe("ac8 tokens only", () => {
  it.each(SCREENS)("test_ac8_%s_uses_no_literal_colour", async (name) => {
    const fsModule = "node:fs";
    const fs = (await import(/* @vite-ignore */ fsModule)) as Fs;
    const source = fs.readFileSync(`${cwd}/src/legacy/${name}.tsx`, "utf8");
    const found = source
      .split("\n")
      .filter((line) => !line.trimStart().startsWith("//") && LITERAL.test(line));
    expect(found).toEqual([]);
  });
});
