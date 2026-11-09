// T-04-T12: the review workspace frame over T-02's components. The tabs and chips read one
// workspace request; the routes are new files behind `tax.review_workspace`.
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode } from "../../app-core/fixture-mode";
import { REVIEW_FLAG, taxReviewRoutes } from "../../routes/firm/tax-review";
import { newQueryClient } from "../../testing/support";
import { OPENS, scenarios } from "../TAX-02/scenarios";
import { WORKSPACE_COPY, WorkspaceFrame } from "./frame";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(override: Record<string, FixtureHandler> = {}): string[] {
  const calls: string[] = [];
  const scenario = scenarios.a;
  const handlers = Object.fromEntries(
    Object.entries({ ...scenario.handlers, ...override }).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push(`${request.method} ${request.path}`);
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <WorkspaceFrame returnId={OPENS.a} tab="review" title="Review" />
    </QueryClientProvider>,
  );
  return calls;
}

describe("T-04-T12 review workspace frame", () => {
  it("Review 36 and Issues 4 come from one workspace request; the chip reads No changes needed", async () => {
    const calls = show();
    expect(await screen.findByText(WORKSPACE_COPY.noChanges)).toBeTruthy();
    expect(screen.getByText("36")).toBeTruthy();
    expect(screen.getByText("4")).toBeTruthy();
    expect(calls.filter((c) => c.endsWith("/workspace"))).toHaveLength(1);
    expect(screen.getByText("Assistant")).toBeTruthy();
  });

  it("a proposed checkpoint reads n proposed", async () => {
    show({
      "GET /v1/tax/returns/{return_id}/workspace": ({ params }) =>
        Response.json({
          return_id: params.return_id,
          review_count: 36,
          issues_open: 4,
          checkpoints_proposed: 1,
          assistant: "available",
          allowed_actions: [],
        }),
    });
    expect(await screen.findByText(WORKSPACE_COPY.proposed(1))).toBeTruthy();
  });

  it("with agents off the Assistant chip is absent", async () => {
    show({
      "GET /v1/tax/returns/{return_id}/workspace": ({ params }) =>
        Response.json({
          return_id: params.return_id,
          review_count: 0,
          issues_open: 0,
          assistant: "agents_off",
          allowed_actions: [],
        }),
    });
    await waitFor(() => {
      expect(screen.getByText(WORKSPACE_COPY.noChanges)).toBeTruthy();
    });
    expect(screen.queryByText("Assistant")).toBeNull();
  });

  it("the new routes are the workspace's, behind tax.review_workspace", () => {
    expect(REVIEW_FLAG).toBe("tax.review_workspace");
    expect(taxReviewRoutes.map((r) => r.options.path)).toEqual([
      "/tax-returns/$returnId/review/$section",
      "/tax-returns/$returnId/issues",
      "/tax-returns/$returnId/activity",
      "/tax-returns/$returnId/k1-resolver/$activityId",
      "/tax-returns/$returnId/residency",
    ]);
  });
});
