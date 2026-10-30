// @vitest-environment node
// P-08-T11 CSP: the portal keeps `connect-src 'self'` (ADR-163 §4). The portal build uses the same
// `abacus-csp` plugin as the firm's (its directives are pinned by lint/fonts.test.ts), not gated by
// mode, and the portal auth client and entry name no other origin: every call is a same-origin
// path on the generated client.
import { describe, expect, it } from "vitest";
import { WEB, read } from "../../lint/ui-files";

describe("P-08-T11 the portal's CSP stays connect-src 'self'", () => {
  it("applies the abacus-csp plugin to every build, the portal's included", async () => {
    const vite = await read(`${WEB}/vite.config.ts`);
    expect(vite).toContain("\"connect-src 'self'\"");
    // The list's head, ungated by mode, whatever its line breaks: a portal-only plugin may follow
    // (`portalIcons`, DEC-1006), never precede or wrap the policy.
    expect(vite.replace(/\s+/gu, " ")).toContain(
      "plugins: [ react(), tailwindcss(), contentSecurityPolicy(), fontPreload(),",
    );
  });

  it("names no other origin in the portal auth client or the portal entry", async () => {
    for (const file of ["src/app-core/auth/bff.ts", "src/entries/portal.tsx"]) {
      const source = await read(`${WEB}/${file}`);
      expect(source, file).not.toMatch(/https?:\/\/|wss?:\/\//);
      expect(source, file).not.toMatch(/localStorage|sessionStorage\.(?:set|get)Item/);
    }
  });
});
