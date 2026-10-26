// POR-14 · Third-party request room (R-01-T14). One test per artboard on its fixture scenario
// (a–f), the contract's acceptance and AVOID lines, and the task's acceptance: "Six scenarios
// pass, the reduced toolbar offers only Requests, and full stack Sam cannot reach any route
// outside the room." The server half of the last clause is R-01-T13's
// (backend/tests/integration/backfill/test_r01t13_third_party_room.py: every other portal read
// answers 404 to Sam); the full-stack walk and axe are R-01-T21's Playwright spec.
import { Toaster } from "@abacus/ui";
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode } from "../../app-core/fixture-mode";
import { freshScenario } from "../../fixtures/scenarios/POR-14";
import { BRIDGE_ID } from "../../fixtures/seed/portal-documents";
import { renderRoutes } from "../../testing/support";
import { PortalRoom } from ".";
import { ARTBOARD, type Por14State, STATES, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

interface Seen {
  calls: { method: string; path: string; body: unknown }[];
}

function show(
  state: Por14State,
  options: { mobile?: boolean; expanded?: string | null } = {},
): Seen {
  const seen: Seen = { calls: [] };
  const scenario = freshScenario(state);
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  const expanded = options.expanded === undefined ? ARTBOARD[state].expanded : options.expanded;
  renderRoutes([
    {
      path: "/",
      component: () => (
        <>
          <PortalRoom
            mobile={options.mobile === true}
            {...(expanded == null ? {} : { expanded })}
          />
          <Toaster />
        </>
      ),
    },
  ]);
  return seen;
}

async function row(title: string): Promise<HTMLElement> {
  const text = await screen.findByText(title);
  const el = text.closest<HTMLElement>("[data-request]");
  if (el === null) throw new Error(`no row ${title}`);
  return el;
}

const BRIDGE = "Bridge letter — Oct 1 to Dec 31, 2025";

// Never the product, the agent, a firm status, the rest of the PBC list or another party.
const BANNED = [
  /Accrued/,
  /\bAgent\b/,
  /Uploaded – needs review/,
  /Received ✓/,
  /confidence/i,
  /materiality/i,
  /sample/i,
  /\b9\d{2}-\d{2}-\d{4}\b/, // no participant SSN
  /Census/,
  /PayGrid/,
  /Summit/,
  /Dana Kowalski/,
];

function avoid(others: readonly RegExp[] = []): void {
  const text = document.body.textContent;
  for (const word of [...BANNED, ...others]) expect(text).not.toMatch(word);
}

describe("POR-14 artboards", () => {
  it("defines a to f: Sam Ortiz's, and Harborline's certifications contact at d", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f"]);
    for (const s of ["a", "b", "c", "e", "f"] as const) {
      expect(scenarios[s].persona).toBe("sam-ortiz");
    }
    expect(scenarios.d.persona).toBe("harborline-certifications");
  });

  it("POR-14a default: 4 of 9, two bands, the bridge letter open with its guidance and thread", async () => {
    show("a");
    expect(await screen.findByText("Northwind Robotics 401(k) Plan · 2025 audit")).toBeTruthy();
    expect(
      screen.getByText(
        "Brightwater Hale LLP asked Keystone Retirement Services for these items. You can only see and upload to these requests.",
      ),
    ).toBeTruthy();
    expect(screen.getByText("4 of 9 uploaded")).toBeTruthy();
    expect(screen.getByRole("progressbar", { name: "4 of 9 uploaded" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Drop files here" })).toBeTruthy();
    const bands = screen.getAllByRole("region").filter((b) => b.dataset.part === "band");
    expect(bands.map((b) => b.getAttribute("aria-label"))).toEqual([
      "Recordkeeper reports",
      "SOC 1 & fees",
    ]);
    expect(within(bands[0] as HTMLElement).getByText("3 of 5")).toBeTruthy();
    expect(within(bands[1] as HTMLElement).getByText("1 of 4")).toBeTruthy();
    expect(screen.getAllByText("Uploaded Sep 2")).toHaveLength(4);
    expect(screen.getAllByText("Due Sep 18")).toHaveLength(2);
    expect((await row(BRIDGE)).getAttribute("aria-expanded")).toBe("true");
    expect(
      screen.getByText(/Your SOC 1 Type 2 report covers October 1, 2024 to September 30, 2025/),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: /Drop the letter here or Upload…/ })).toBeTruthy();
    expect(await screen.findByText("Marcus Delaney · Brightwater Hale · Sep 1")).toBeTruthy();
    expect(screen.getByText("A signed PDF on Keystone letterhead is fine.")).toBeTruthy();
    expect(screen.getByText("Sam Ortiz · Sep 10")).toBeTruthy();
    expect(screen.getByPlaceholderText("Comment…")).toBeTruthy();
    avoid([/Harborline/]);
  });

  it("R-01-T14 acceptance: the reduced toolbar offers only Requests, and the chip is Sam · Keystone", async () => {
    show("a");
    await screen.findByText("4 of 9 uploaded");
    for (const area of [
      "Home",
      "Documents",
      "Questions",
      "Approvals",
      "Sign",
      "Messages",
      "Deliverables",
    ]) {
      expect(screen.queryByRole("button", { name: area })).toBeNull();
      expect(screen.queryByRole("link", { name: area })).toBeNull();
    }
    expect(screen.getAllByText("Requests").length).toBeGreaterThan(0);
    expect(screen.getByText("Sam Ortiz · Keystone")).toBeTruthy();
  });

  it("POR-14b uploaded, in review: You uploaded Sep 22, and 5 of 9", async () => {
    show("b");
    expect(await screen.findByText("5 of 9 uploaded")).toBeTruthy();
    expect(
      screen.getByText("You uploaded Sep 22 · Brightwater Hale is reviewing it"),
    ).toBeTruthy();
    expect((await row(BRIDGE)).dataset.state).toBe("in_review");
    avoid();
  });

  it("POR-14c returned: red-tint Returned · wrong period with Marcus Delaney's note", async () => {
    show("c");
    expect(await screen.findByText("Returned · wrong period")).toBeTruthy();
    expect(
      screen.getByText(
        "This letter covers Jan–Jun 2025. We need Oct 1 to Dec 31, 2025. — Marcus Delaney",
      ),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: /Drop the letter here or Upload…/ })).toBeTruthy();
    avoid();
  });

  it("POR-14d custodian: Harborline's two items and the §103(a)(3)(C) certification line", async () => {
    show("d");
    expect(
      await screen.findByText(
        /Under ERISA section 103\(a\)\(3\)\(C\), Brightwater Hale relies on your certification/,
      ),
    ).toBeTruthy();
    expect(screen.getByText("1 of 2 uploaded")).toBeTruthy();
    expect(
      screen.getByText("Certification of investment information — 12/31/2025, signed"),
    ).toBeTruthy();
    expect(
      screen.getByText("You uploaded Sep 11 · Brightwater Hale is reviewing it"),
    ).toBeTruthy();
    expect(screen.getByText("Trust statement — 12/31/2025")).toBeTruthy();
    expect(screen.getByText("Due Sep 18")).toBeTruthy();
    avoid([/Keystone/, /Sam Ortiz/]);
  });

  it("POR-14e all complete: the green-tint banner", async () => {
    show("e");
    expect(
      await screen.findByText("Everything Brightwater Hale asked Keystone for is in. Thank you."),
    ).toBeTruthy();
    expect(screen.getByText("9 of 9 uploaded")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Drop files here" })).toBeNull();
    avoid();
  });

  it("POR-14f expired or used link: one neutral state with Ask for a new link", async () => {
    show("f");
    expect(await screen.findByText("This link has expired or was already used")).toBeTruthy();
    expect(screen.getByText("Ask Brightwater Hale for a new link")).toBeTruthy();
    avoid([/Keystone Retirement Services asked/, /Bridge letter/]);
  });
});

describe("POR-14 behaviour", () => {
  it("Upload… on the open row sends the file to that request, which reads in review", async () => {
    const seen = show("a");
    await row(BRIDGE);
    const input = document.querySelector<HTMLInputElement>("[data-room] input[type='file']");
    fireEvent.click(screen.getByRole("button", { name: /Drop the letter here or Upload…/ }));
    const file = new File(["%PDF-1.4"], "Keystone_Bridge_Letter.pdf", { type: "application/pdf" });
    fireEvent.change(input as HTMLInputElement, { target: { files: [file] } });
    await waitFor(() => {
      expect(seen.calls.some((c) => c.path.endsWith(`/request-items/${BRIDGE_ID}/uploads`))).toBe(
        true,
      );
    });
    expect(await screen.findByText("5 of 9 uploaded")).toBeTruthy();
    // Withdraw while in review asks with the DF-15 words.
    fireEvent.click(await screen.findByRole("button", { name: "Withdraw" }));
    const confirm = await screen.findByRole("alertdialog");
    expect(
      within(confirm).getByText(
        "Withdraw this file? Brightwater Hale's team won't use it. It's kept securely for 30 days, then erased.",
      ),
    ).toBeTruthy();
    fireEvent.click(within(confirm).getByRole("button", { name: "Withdraw" }));
    await waitFor(() => {
      expect(seen.calls.some((c) => c.path.endsWith("/withdraw"))).toBe(true);
    });
    expect(await screen.findByText("4 of 9 uploaded")).toBeTruthy();
  });

  it("files on Drop files here ask Which request is this for?, pre-selected by the names", async () => {
    const seen = show("a", { expanded: null });
    await screen.findByText("4 of 9 uploaded");
    const pill = screen.getByRole("button", { name: "Drop files here" });
    const file = new File(["%PDF-1.4"], "Keystone_Bridge_Letter_Q4.pdf", {
      type: "application/pdf",
    });
    fireEvent.drop(pill, { dataTransfer: { files: [file] } });
    const picker = await screen.findByRole("dialog", { name: "Which request is this for?" });
    await waitFor(() => {
      expect(
        within(picker).getByRole("radio", { name: BRIDGE }).getAttribute("aria-checked"),
      ).toBe("true");
    });
    expect(seen.calls.some((c) => c.path === "/v1/portal/room/suggest")).toBe(true);
    // Only the requests still owed are offered: never a done one.
    expect(within(picker).queryByRole("radio", { name: /SOC 1 Type 2 report/ })).toBeNull();
    fireEvent.click(within(picker).getByRole("button", { name: "Upload" }));
    await waitFor(() => {
      expect(seen.calls.some((c) => c.path.endsWith(`/request-items/${BRIDGE_ID}/uploads`))).toBe(
        true,
      );
    });
  });

  it("a comment joins the open row's shared thread", async () => {
    const seen = show("a");
    const composer = await screen.findByPlaceholderText("Comment…");
    fireEvent.change(composer, { target: { value: "Uploading it on the 22nd." } });
    fireEvent.keyDown(composer, { key: "Enter" });
    await waitFor(() => {
      const post = seen.calls.find((c) => c.method === "POST" && c.path.endsWith("/comments"));
      expect(post?.body).toEqual({ text: "Uploading it on the 22nd." });
    });
    expect(await screen.findByText("Uploading it on the 22nd.")).toBeTruthy();
  });

  it("a row expands and folds on click", async () => {
    show("a", { expanded: null });
    const fees = await row("ERISA 408(b)(2) fee disclosure");
    expect(fees.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(fees);
    expect(fees.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByRole("button", { name: /Drop the file here or Upload…/ })).toBeTruthy();
    fireEvent.click(fees);
    expect(fees.getAttribute("aria-expanded")).toBe("false");
  });

  it("390: a single page with no tab bar; an open row is shown alone, full screen", async () => {
    show("a", { mobile: true });
    expect(await screen.findByText(BRIDGE)).toBeTruthy();
    expect(screen.queryByRole("tablist")).toBeNull();
    expect(document.querySelector("[data-shell='mobile-tab-bar']")).toBeNull();
    expect(
      screen.queryByText("Schedule of account balances — every participant, 12/31/2025"),
    ).toBeNull();
  });
});
