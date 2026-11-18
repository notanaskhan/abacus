// G-04-T14: the console entry. The staff sign-in gate navigates to the console BFF with a
// same-origin return path only (DEC-5528); scripts/console-dist-check.mjs refuses a console build
// that carries a firm, portal or fixture chunk, or that lost the CSP (synthetic builds here; the
// real one runs after `build:console`).
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { STAFF_SIGN_IN_PATH, StaffAuth, staffSignInUrl } from "./StaffAuth";

interface Check {
  consoleProblems: (
    manifest: Record<string, { file: string; src?: string }>,
    files: Record<string, string>,
  ) => string[];
}

const cwd = (globalThis as unknown as { process: { cwd: () => string } }).process.cwd();
let check: Check;

beforeAll(async () => {
  check = (await import(/* @vite-ignore */ `${cwd}/scripts/console-dist-check.mjs`)) as Check;
});

const PAGE =
  '<meta http-equiv="Content-Security-Policy" content="default-src &#39;self&#39;; frame-ancestors &#39;none&#39;">';

describe("staff sign-in gate", () => {
  it("returns only to a same-origin path", () => {
    expect(staffSignInUrl("/tenants?ov=provision")).toBe(
      `${STAFF_SIGN_IN_PATH}?return_to=%2Ftenants%3Fov%3Dprovision`,
    );
    expect(staffSignInUrl("//evil.example/x")).toBe(`${STAFF_SIGN_IN_PATH}?return_to=%2F`);
    expect(staffSignInUrl("https://evil.example")).toBe(`${STAFF_SIGN_IN_PATH}?return_to=%2F`);
  });

  it("signed out, it shows only the sign-in frame and navigates to the BFF", () => {
    const navigate = vi.fn();
    render(
      <StaffAuth signedIn={false} navigate={navigate}>
        <p>console body</p>
      </StaffAuth>,
    );
    expect(screen.queryByText("console body")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(navigate).toHaveBeenCalledWith(
      expect.stringMatching(/^\/v1\/platform\/auth\/sign-in\?/),
    );
  });

  it("signed in, it renders the console", () => {
    render(
      <StaffAuth signedIn>
        <p>console body</p>
      </StaffAuth>,
    );
    expect(screen.getByText("console body")).toBeTruthy();
  });
});

describe("console dist check", () => {
  const clean = { "console.html": { file: "console.html", src: "console.html" } };

  it("a console with its CSP and no foreign chunk is clean", () => {
    expect(check.consoleProblems(clean, { "console.html": PAGE })).toEqual([]);
  });

  it("a firm, portal or fixture chunk, or a lost CSP, is refused", () => {
    const manifest = {
      ...clean,
      "src/shell/firm/AppShell.tsx": { file: "assets/a.js", src: "src/shell/firm/AppShell.tsx" },
      "src/portal/PortalShell.tsx": { file: "assets/b.js", src: "src/portal/PortalShell.tsx" },
      "src/screens/PLT-01/index.tsx": { file: "assets/c.js", src: "src/screens/PLT-01/index.tsx" },
    };
    const problems = check.consoleProblems(manifest, {
      "console.html": "<html></html>",
      "assets/c.js": "Brightwater Hale",
    });
    expect(problems).toHaveLength(5);
  });
});
