import { describe, expect, it } from "vitest";
import { errorMessage, shouldRetry } from "./api";

describe("ac1 shouldRetry", () => {
  it("never retries an authorisation or client error", () => {
    for (const status of [400, 401, 403, 404, 409, 422, 499]) {
      expect(shouldRetry(0, { status }), String(status)).toBe(false);
    }
  });

  it("retries a transient failure once", () => {
    expect(shouldRetry(0, { status: 500 })).toBe(true);
    expect(shouldRetry(0, { status: 503 })).toBe(true);
    expect(shouldRetry(0, new Error("network"))).toBe(true);
    expect(shouldRetry(1, { status: 500 })).toBe(false);
    expect(shouldRetry(1, new Error("network"))).toBe(false);
  });
});

describe("ac18 errorMessage", () => {
  it("shows a short API detail and never raw or long server text", () => {
    expect(errorMessage({ detail: "Not allowed" })).toBe("Not allowed");
    expect(errorMessage({ detail: "x".repeat(500) })).toBe("Something went wrong. Try again.");
    expect(errorMessage({ detail: [{ msg: "bad" }] })).toBe("Something went wrong. Try again.");
    expect(errorMessage("<html>500</html>")).toBe("Something went wrong. Try again.");
    expect(errorMessage(null)).toBe("Something went wrong. Try again.");
  });
});
