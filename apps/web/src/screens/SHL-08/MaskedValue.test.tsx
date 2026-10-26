// P-03-T20 security review L4: a reveal answer that arrives after the viewer moved to another
// version (or after Hide, or unmount) is dropped, so a value is never shown for a file no longer
// in view.
import { QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook } from "@testing-library/react";
import type { JSX, ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, newQueryClient, signInForTest } from "../../testing/support";
import { useMaskedReveal } from "./MaskedValue";

const FIRST = "11111111-1111-4111-8111-111111111111";
const SECOND = "22222222-2222-4222-8222-222222222222";
const MASK = "33333333-3333-4333-8333-333333333333";

function wrapper({ children }: { children: ReactNode }): JSX.Element {
  return <QueryClientProvider client={newQueryClient()}>{children}</QueryClientProvider>;
}

const ANSWER = {
  mask_id: MASK,
  value: "000-00-6081",
  kind: "ssn",
  expires_in: 30,
  revealed_by: "Samuel Ito",
  revealed_at: "2026-09-14T09:31:00-05:00",
};

beforeEach(async () => {
  await signInForTest();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/** The reveal route held open until `release` answers it. */
function held(): { release: () => Promise<void> } {
  let answer: (r: Response) => void = () => undefined;
  mockApi({
    [`POST /v1/evidence-versions/${FIRST}/pii-reveals`]: () =>
      new Promise<Response>((resolve) => {
        answer = resolve;
      }),
  });
  return {
    release: async () => {
      await act(async () => {
        await new Promise((r) => setTimeout(r, 0));
        answer(json(ANSWER, 201));
        await new Promise((r) => setTimeout(r, 0));
      });
    },
  };
}

describe("useMaskedReveal", () => {
  it("shows an answer for the version still in view (control)", async () => {
    const route = held();
    const { result } = renderHook(() => useMaskedReveal(FIRST, true), { wrapper });
    act(() => {
      result.current.slot?.onReveal(MASK);
    });
    await route.release();
    expect(result.current.slot?.revealed?.[MASK]?.value).toBe("000-00-6081");
  });

  it("drops an answer that arrives after the version changed", async () => {
    const route = held();
    const { result, rerender } = renderHook(
      ({ version }: { version: string }) => useMaskedReveal(version, true),
      { wrapper, initialProps: { version: FIRST } },
    );
    act(() => {
      result.current.slot?.onReveal(MASK);
    });
    rerender({ version: SECOND });
    await route.release();
    expect(result.current.slot?.revealed).toEqual({});
    expect(result.current.line).toBeNull();
  });
});
