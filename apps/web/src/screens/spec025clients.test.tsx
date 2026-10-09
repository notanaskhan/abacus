// SPEC-025 (TASK-043): picking a client the firm already has; duplicates caught.
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { Engagements } from "./Engagements";

const HALVORSEN = {
  id: "c1",
  name: "Halvorsen Inc.",
  entities: [
    { id: "e1", name: "Halvorsen Inc." },
    { id: "e2", name: "Halvorsen Logistics" },
  ],
};

const page = (): void => {
  renderRoutes([
    { path: "/", component: Engagements },
    { path: "/engagements/$engagementId", component: () => <p>Engagement</p> },
  ]);
};

const fillRest = (): void => {
  fireEvent.change(screen.getByLabelText("Engagement name"), {
    target: { value: "FY2026 audit" },
  });
  fireEvent.change(screen.getByLabelText("Fiscal year start"), {
    target: { value: "2026-01-01" },
  });
  fireEvent.change(screen.getByLabelText("Fiscal year end"), { target: { value: "2026-12-31" } });
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

describe("ac1 clients you already have", () => {
  it("finds an existing client and creates the engagement against it and its entity", async () => {
    const { calls } = mockApi({
      "GET /v1/engagements": () => json([]),
      "GET /v1/firm/onboarding": () => json({ detail: "forbidden" }, 403),
      "GET /v1/firm/clients/search": () => json([HALVORSEN]),
      "POST /v1/engagements": () => json({ id: "new", name: "FY2026 audit", team: [] }, 201),
    });
    page();
    fireEvent.click(
      (await screen.findAllByRole("button", { name: "New engagement" }))[0] as HTMLElement,
    );
    fireEvent.change(await screen.findByLabelText("Find an existing client"), {
      target: { value: "halv" },
    });
    const list = await screen.findByRole("list", { name: "Matching clients" });
    fireEvent.click(within(list).getByRole("button", { name: /Halvorsen Inc\./ }));
    fireEvent.change(screen.getByLabelText("Client entity"), { target: { value: "e2" } });
    fillRest();
    fireEvent.click(screen.getByRole("button", { name: "Create engagement" }));
    await waitFor(() => {
      expect(calls.find((c) => c.method === "POST")?.body).toMatchObject({
        client_id: "c1",
        client_entity_id: "e2",
        client_name: "Halvorsen Inc.",
        client_entity_name: "Halvorsen Logistics",
      });
    });
  });

  it("warns about a likely duplicate and creates a new client only when confirmed", async () => {
    let posts = 0;
    const { calls } = mockApi({
      "GET /v1/engagements": () => json([]),
      "GET /v1/firm/onboarding": () => json({ detail: "forbidden" }, 403),
      "GET /v1/firm/clients/search": () => json([]),
      "POST /v1/engagements": () => {
        posts += 1;
        return posts === 1
          ? json({ detail: "possible_duplicate" }, 409)
          : json({ id: "new", name: "FY2026 audit", team: [] }, 201);
      },
    });
    page();
    fireEvent.click(
      (await screen.findAllByRole("button", { name: "New engagement" }))[0] as HTMLElement,
    );
    fireEvent.change(await screen.findByLabelText("Client"), {
      target: { value: "Halvorsen LLC" },
    });
    fireEvent.change(screen.getByLabelText("Client entity"), {
      target: { value: "Halvorsen LLC" },
    });
    fillRest();
    fireEvent.click(screen.getByRole("button", { name: "Create engagement" }));
    expect(await screen.findByText("This client may already exist")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "create a new client anyway" }));
    fireEvent.click(screen.getByRole("button", { name: "Create engagement" }));
    await waitFor(() => {
      expect(calls.filter((c) => c.method === "POST")[1]?.body).toMatchObject({
        confirm_new: true,
      });
    });
  });
});
