// SHL-18 f live (A-09-T32 rest, S48): a shared thread read from the server names its outside
// organisation from the anchor's facts, with no frame prop: "Visible to Pruett & Lang LLP".
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, expect, it } from "vitest";
import { installFixtureMode, json } from "../../app-core/fixture-mode";
import { IDS, P, componentThread } from "../../fixtures/seed/collaboration";
import { newQueryClient } from "../../testing/support";
import { LiveCommentThread } from "./CommentThread";
import { COPY } from "./copy";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

it("a shared thread names the organisation it is visible to", async () => {
  restore = installFixtureMode({
    state: "f",
    persona: "omar-haddad",
    clock: "2026-09-23T09:00:00-05:00",
    handlers: {
      "GET /v1/comment-threads": () => json({ items: [componentThread()] }),
      "GET /v1/engagements/{engagement_id}/mention-candidates": () => json({ items: [] }),
    },
  });
  render(
    <QueryClientProvider client={newQueryClient()}>
      <LiveCommentThread
        variant="popover"
        anchor={{ anchor_kind: "component_thread", anchor_id: IDS.componentRoom }}
        anchorLabel="Pruett & Lang LLP"
        engagementId={IDS.harlow}
        engagementLabel="Harlow & Pike FY2026"
        viewerId={P.omar.user_id}
      />
    </QueryClientProvider>,
  );
  expect(await screen.findByText(COPY.visibleTo("Pruett & Lang LLP"))).toBeTruthy();
});
