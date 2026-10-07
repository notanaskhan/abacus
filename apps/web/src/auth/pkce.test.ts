import { describe, expect, it } from "vitest";
import { codeChallenge, randomString } from "./pkce";

describe("ac1 PKCE helpers", () => {
  it("computes the RFC 7636 appendix B challenge", async () => {
    expect(await codeChallenge("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk")).toBe(
      "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",
    );
  });

  it("has no padding and only URL-safe characters", async () => {
    for (const verifier of ["a", "ab", "abc", "x".repeat(48)]) {
      expect(await codeChallenge(verifier)).toMatch(/^[A-Za-z0-9_-]+$/);
    }
  });

  it("is base64url of a 32-byte digest: 43 characters", async () => {
    expect(await codeChallenge("anything")).toHaveLength(43);
  });

  it("gives URL-safe random strings of at least 43 characters for 32 bytes", () => {
    const value = randomString(32);
    expect(value).toMatch(/^[A-Za-z0-9_-]+$/);
    expect(value.length).toBeGreaterThanOrEqual(43);
  });

  it("gives longer strings for more bytes and does not repeat", () => {
    expect(randomString(48).length).toBeGreaterThan(randomString(32).length);
    const seen = new Set(Array.from({ length: 50 }, () => randomString(32)));
    expect(seen.size).toBe(50);
  });
});
