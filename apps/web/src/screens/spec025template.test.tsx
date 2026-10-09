// SPEC-025 AC-3 (TASK-047): a new engagement starts from the firm's template for its type.
import type { TemplateVersionOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { type Handler, json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { Engagements } from "./Engagements";
import type { EngagementType } from "./engagementTypes";

const ROUTES = [
  { path: "/", component: Engagements },
  { path: "/engagements/$engagementId", component: () => <p>Engagement page</p> },
];

function template(
  id: string,
  name: string,
  types: EngagementType[] = ["audit"],
): TemplateVersionOut {
  return {
    template_id: `t-${id}`,
    template_name: name,
    version_id: id,
    version: 4,
    created_at: "2026-01-01T00:00:00Z",
    engagement_types: types,
  };
}

const CREATED = {
  id: "e9",
  name: "FY2026",
  client_name: "Acme",
  client_entity_name: "Acme Holdings",
  fiscal_period_start: "2026-01-01",
  fiscal_period_end: "2026-12-31",
  status: "active",
  type: "audit",
  created_at: "2026-01-02T00:00:00Z",
  team: [],
};

function api(templates: TemplateVersionOut[], apply: Handler = () => json({}, 201)) {
  return mockApi({
    "GET /v1/engagements": () => json([]),
    "GET /v1/methodology/templates": () => json(templates),
    "POST /v1/engagements": () => json(CREATED, 201),
    "POST /v1/engagements/e9/methodology": apply,
  });
}

async function openDialog(): Promise<void> {
  renderRoutes(ROUTES);
  await screen.findByText("No engagements yet");
  fireEvent.click(screen.getAllByRole("button", { name: /new engagement/i })[0] as HTMLElement);
  const fill = (label: string, value: string): void => {
    fireEvent.change(screen.getByLabelText(label), { target: { value } });
  };
  fill("Engagement name", "FY2026");
  fill("Client", "Acme");
  fill("Client entity", "Acme Holdings");
  fill("Fiscal year start", "2026-01-01");
  fill("Fiscal year end", "2026-12-31");
}

beforeEach(async () => {
  sessionStorage.clear();
  await signInForTest();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

describe("SPEC-025 AC-3 template for the type (TASK-047)", () => {
  it("test_ac3_the_only_template_for_the_type_is_preselected_and_applied", async () => {
    const { calls } = api([
      template("v-a", "Audit methodology"),
      template("v-r", "Review", ["review"]),
    ]);
    await openDialog();
    const select = await screen.findByLabelText<HTMLSelectElement>("Request list");
    expect(select.value).toBe("v-a");
    expect(screen.queryByText(/Review · v4/)).toBeNull(); // another type's template isn't offered
    fireEvent.click(screen.getByRole("button", { name: "Create engagement" }));
    expect(await screen.findByText("Engagement page")).toBeTruthy();
    const applied = calls.find((c) => c.path === "/v1/engagements/e9/methodology");
    expect(applied?.body).toEqual({ version_id: "v-a" });
    const listed = calls.find((c) => c.path === "/v1/methodology/templates");
    expect(listed).toBeTruthy();
  });

  it("test_ac3_with_several_templates_nothing_is_preselected", async () => {
    api([template("v-a", "Audit A"), template("v-b", "Audit B")]);
    await openDialog();
    const select = await screen.findByLabelText<HTMLSelectElement>("Request list");
    expect(select.value).toBe("");
    expect(screen.getByRole("option", { name: "Choose a template…" })).toBeTruthy();
  });

  it("test_ac3_an_empty_list_applies_nothing", async () => {
    const { calls } = api([template("v-a", "Audit methodology")]);
    await openDialog();
    fireEvent.change(await screen.findByLabelText("Request list"), { target: { value: "none" } });
    fireEvent.click(screen.getByRole("button", { name: "Create engagement" }));
    expect(await screen.findByText("Engagement page")).toBeTruthy();
    expect(calls.some((c) => c.path.endsWith("/methodology"))).toBe(false);
  });

  it("test_ac3_no_template_for_the_type_says_so", async () => {
    api([template("v-r", "Review", ["review"])]);
    await openDialog();
    expect(
      await screen.findByText(/Your firm has no template for audit engagements yet/),
    ).toBeTruthy();
    expect(screen.getByRole("link", { name: "Methodology" })).toBeTruthy();
  });

  it("test_ac3_a_failed_apply_keeps_the_engagement_and_says_why", async () => {
    api([template("v-a", "Audit methodology")], () => json({ detail: "Not allowed" }, 403));
    await openDialog();
    await screen.findByLabelText("Request list");
    fireEvent.click(screen.getByRole("button", { name: "Create engagement" }));
    expect(await screen.findByText("Created, but the template wasn't applied")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Open the engagement" }));
    expect(await screen.findByText("Engagement page")).toBeTruthy();
  });
});
