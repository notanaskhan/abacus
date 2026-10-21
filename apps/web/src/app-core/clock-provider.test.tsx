import { DateText, useNow, useToday } from "@abacus/ui";
import {
  RouterProvider,
  createMemoryHistory,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import { cleanup, render, screen } from "@testing-library/react";
import { type JSX } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { rootRoute } from "../routes/root";
import { setScenarioClock } from "./clock";

// F-05-T10: the root route wraps the app in the design system's ClockProvider, fed by this
// app's browser clock, so a fixture scenario's instant reaches every screen's hooks.
afterEach(() => {
  cleanup();
  setScenarioClock(null);
});

function Probe(): JSX.Element {
  return (
    <p>
      {`${useToday()}|${useNow().toISOString()}|`}
      <DateText value="2026-09-13T20:00:00Z" kind="relative" />
    </p>
  );
}

describe("ClockProvider at the root", () => {
  it("serves the scenario clock to useNow, useToday and DateText", async () => {
    setScenarioClock("2026-09-14T09:24:00-05:00");
    const index = createRoute({ getParentRoute: () => rootRoute, path: "/", component: Probe });
    const router = createRouter({
      routeTree: rootRoute.addChildren([index]),
      history: createMemoryHistory({ initialEntries: ["/"] }),
    });
    render(<RouterProvider router={router} />);
    expect(await screen.findByText(/^2026-09-14\|2026-09-14T14:24:00.000Z\|/)).toBeTruthy();
    expect(screen.getByText("Yesterday")).toBeTruthy();
  });
});
