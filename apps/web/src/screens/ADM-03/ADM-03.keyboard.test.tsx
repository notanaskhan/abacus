// ADM-03 keyboard suite (G-01-T17; G-01 §9 item 4): every control Tab reaches is named (the wall
// rows' Approve and Lift say whose wall); the new-wall sheet closes on Escape while it is clean;
// the lift confirm closes on Escape without lifting. axe runs in e2e/screens/adm-03.spec.ts.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode } from "../../app-core/fixture-mode";
import { nameOf, tabOrder } from "../../testing/keyboard";
import { newQueryClient } from "../../testing/support";
import { OfficesPage } from ".";
import { type Adm03State, OPENS, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  toastStore.clear();
});

function show(state: Adm03State, initial: string = OPENS[state]): string[] {
  const scenario = scenarios[state];
  const paths: string[] = [];
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        paths.push(`${request.method} ${request.path}`);
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <OfficesPage initial={initial} />
    </QueryClientProvider>,
  );
  return paths;
}

describe("ADM-03 keyboard (G-01 §9)", () => {
  it("every control Tab reaches is named, the wall actions by whose wall", async () => {
    show("e");
    await screen.findByRole("button", { name: "Lift the wall on Lena Park" });
    expect(tabOrder().filter((el) => nameOf(el) === "")).toEqual([]);
  });

  it("the new-wall sheet closes on Escape while it is clean", async () => {
    show("a", "?ov=wall:new");
    const sheet = await screen.findByRole("dialog", { name: "New ethical wall" });
    fireEvent.keyDown(sheet, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("dialog", { name: "New ethical wall" })).toBeNull();
    });
  });

  it("the lift confirm closes on Escape and lifts nothing", async () => {
    const paths = show("e");
    fireEvent.click(await screen.findByRole("button", { name: "Lift the wall on Lena Park" }));
    const confirm = await screen.findByRole("alertdialog");
    fireEvent.keyDown(confirm, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("alertdialog")).toBeNull();
    });
    expect(paths.some((p) => p.endsWith("/remove"))).toBe(false);
  });
});
