// POR-20 · Transactional email templates (R-01-T25). One test per artboard (a–l) on its fixture
// scenario (R-01 Story 7.1–7.3), plus: Publish stays disabled while the lint has a finding, the
// preview is sandboxed with no fetches, and the AVOID list. The full stack on staging (Grace's
// edit, test and publish) and axe run outside this file.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
} from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { POR20 } from ".";
import { OPENS, type Por20State, SAMPLES, scenarios } from "./scenarios";

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

interface Call {
  method: string;
  path: string;
  body: unknown;
}

function show(state: Por20State): Call[] {
  const scenario: Scenario = scenarios[state];
  const calls: Call[] = [];
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  const opens = OPENS[state];
  render(
    <QueryClientProvider client={newQueryClient()}>
      <POR20
        templateKey={opens.templateKey}
        width={opens.w}
        sample={opens.sample}
        samples={SAMPLES}
      />
    </QueryClientProvider>,
  );
  return calls;
}

const frame = async (): Promise<HTMLIFrameElement> =>
  await screen.findByTitle<HTMLIFrameElement>("Email preview");
const srcdoc = async (): Promise<string> => (await frame()).getAttribute("srcdoc") ?? "";
const publishButton = (): HTMLButtonElement =>
  screen.getByRole<HTMLButtonElement>("button", { name: /^Publish/ });

describe("POR-20 Transactional email templates", () => {
  it("a: the six templates with their pills, and the v4 draft previewed for Claire at 600", async () => {
    const calls = show("a");
    const list = await screen.findByRole("list", { name: "Templates" });
    const rows = within(list).getAllByRole("listitem");
    expect(rows).toHaveLength(6);
    const reminder = rows.find((r) => r.textContent.includes("Reminder"));
    expect(reminder?.textContent).toContain("Used by Binders, close requests, PBC");
    expect(reminder?.textContent).toContain("Published · v3");
    expect(reminder?.textContent).toContain("Draft changes · v4");
    expect(rows[0]?.textContent).toContain("Used by CLI-04 invites, prospect intake");
    const doc = await srcdoc();
    expect(doc).toContain("Hi Claire, we&#x27;re working on your 2025 tax return.");
    expect(doc).toContain("Form 1095-C From Mercer Hill Health");
    expect(doc).toContain("Open your portal");
    expect(screen.getByTestId("por20-subject").textContent).toBe(
      "2 items still needed for your 2025 tax return",
    );
    expect(await screen.findByText("Every 7 days until done")).toBeTruthy();
    expect(screen.getByText("claire.feld@gmail.com")).toBeTruthy();
    expect(publishButton().textContent).toBe("Publish v4");
    expect(publishButton().disabled).toBe(false);
    const preview = calls.find((c) => c.path.endsWith("/reminder/preview"));
    expect(preview?.body).toMatchObject({ source: "draft", width: 600 });
  });

  it("b: clicking the body opens inline editing; a variable goes in at the caret", async () => {
    show("b");
    await frame();
    fireEvent.click(
      screen.getByRole("button", {
        name: "Editing · choose a variable on the left to insert it at the cursor",
      }),
    );
    const intro = await screen.findByRole<HTMLTextAreaElement>("textbox", { name: "Block intro" });
    expect(screen.getByRole("status").textContent).toContain("Editing ·");
    intro.focus();
    intro.setSelectionRange(3, 3);
    fireEvent.keyUp(intro);
    fireEvent.click(screen.getByRole("button", { name: "firm name, variable" }));
    expect(intro.value.startsWith("Hi {firm_name}{client_first_name},")).toBe(true);
    expect(screen.getAllByLabelText("client first name, variable").length).toBeGreaterThan(0);
  });

  it("c: 390 asks the server for the 390 rendering, with the full-width button", async () => {
    const calls = show("c");
    expect((await srcdoc()).includes("width:100%;box-sizing:border-box")).toBe(true);
    expect(calls.find((c) => c.path.endsWith("/preview"))?.body).toMatchObject({ width: 390 });
  });

  it("d: the phone frame shows the inbox line, subject and sender", async () => {
    show("d");
    await frame();
    const phone = document.querySelector("[data-frame='phone']");
    expect(phone?.textContent).toContain("Inbox");
    expect(phone?.textContent).toContain("2 items still needed for your 2025 tax return");
    expect(phone?.textContent).toContain("Brightwater Hale · to me");
  });

  const others: [Por20State, string, string][] = [
    [
      "e",
      "Brightwater Hale invited you to upload documents",
      "asked Keystone Retirement Services for 9 items",
    ],
    [
      "f",
      "Please sign: engagement letter — cost segregation and section 754 analysis",
      "Due September 24, 2026.",
    ],
    ["g", "Your 2025 K-1 from Ridgeline Property Partners, LP is ready", "View your K-1"],
    [
      "h",
      "Confirmation request — balance at June 30, 2026 (reference C2)",
      "using the number on our website",
    ],
    [
      "i",
      "Please reconnect American Express for your monthly close",
      "Reconnect American Express",
    ],
  ];
  it.each(others)(
    "%s: the published key previews for its sample; Publish disabled, no Discard",
    async (state, subject, line) => {
      show(state);
      await waitFor(() => {
        expect(screen.getByTestId("por20-subject").textContent).toBe(subject);
      });
      expect(await srcdoc()).toContain(line);
      expect(publishButton().disabled).toBe(true);
      expect(screen.queryByRole("button", { name: "Discard" })).toBeNull();
      expect(screen.queryByText("Every 7 days until done")).toBeNull(); // no Reminder schedule
    },
  );

  it("j: Send test… opens the sheet: Grace's own address, read-only, and Claire selected", async () => {
    show("j");
    await frame();
    fireEvent.click(screen.getByRole("button", { name: "Send test…" }));
    const sheet = await screen.findByRole("dialog", { name: "Send a test email" });
    // Read-only: a value row, never a field the recipient could be typed into.
    expect(within(sheet).queryByRole("textbox")).toBeNull();
    expect(within(sheet).getByTestId("por20-send-to").textContent).toBe(
      "grace.holloway@brightwaterhale.com",
    );
    const claire = within(sheet).getByRole("radio", { name: /Claire Feld/ });
    expect(claire.getAttribute("aria-checked")).toBe("true");
    expect(sheet.textContent).toContain(
      "The test fills in this person's details and goes only to you.",
    );
  });

  it("k: the test goes to Grace only and the toast says so; no address leaves the screen", async () => {
    const calls = show("k");
    await frame();
    fireEvent.click(screen.getByRole("button", { name: "Send test…" }));
    const sheet = await screen.findByRole("dialog", { name: "Send a test email" });
    fireEvent.click(within(sheet).getByRole("button", { name: "Send test" }));
    await waitFor(() => {
      expect(toastStore.list().map((t) => t.text)).toContain(
        "Test sent to grace.holloway@brightwaterhale.com",
      );
    });
    const sent = calls.find((c) => c.path.endsWith("/test-send"));
    expect(Object.keys(sent?.body as object)).toEqual(["sample_contact_id"]);
  });

  it("l: v4 published by Grace at 9:27: the header pill, Publish disabled, no Discard", async () => {
    show("l");
    expect(await screen.findByText("Published · v4 · Sep 14 by Grace Holloway")).toBeTruthy();
    expect(publishButton().disabled).toBe(true);
    expect(screen.queryByRole("button", { name: "Discard" })).toBeNull();
    const list = await screen.findByRole("list", { name: "Templates" });
    expect(list.textContent).toContain("Published · v4");
  });

  it("acceptance: Publish stays disabled while the lint has a finding ($3,200)", async () => {
    show("a");
    await frame();
    await waitFor(() => {
      expect(publishButton().disabled).toBe(false);
    });
    fireEvent.click(
      screen.getByRole("button", {
        name: "Editing · choose a variable on the left to insert it at the cursor",
      }),
    );
    const drop = await screen.findByRole<HTMLTextAreaElement>("textbox", { name: "Block drop" });
    fireEvent.change(drop, { target: { value: "Your balance due is $3,200." } });
    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(
      await screen.findByText(/Remove the amount: emails never include tax amounts\./),
    ).toBeTruthy();
    expect(publishButton().disabled).toBe(true);
  });

  it("the preview is sandboxed and fetches nothing: an empty sandbox and a CSP of 'none'", async () => {
    show("a");
    const el = await frame();
    expect(el.getAttribute("sandbox")).toBe("");
    expect(await srcdoc()).toContain("default-src 'none'");
  });

  it("POR-20 avoid: no Accrued, no image, one button in the email", async () => {
    show("a");
    const doc = await srcdoc();
    expect(doc.toLowerCase()).not.toContain("accrued");
    expect(doc).not.toContain("<img");
    expect(doc.match(/<a /g)?.length).toBe(1);
  });
});
