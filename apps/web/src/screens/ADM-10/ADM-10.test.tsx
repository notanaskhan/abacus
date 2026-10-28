// ADM-10 · Portal branding & client experience (R-01-T28). One test per artboard (a–g) on its
// fixture scenario (docs/screens/ADM-10.md "States" and "Acceptance"), plus: an edit saves the
// draft with the version it read, the preview frame and the email card never name the product,
// and the AVOID list. axe runs in the Playwright screen spec (R-01-T32), not here.
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { type JSX, useState } from "react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
} from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { ADM10, type Adm10Search } from ".";
import { type Adm10State, OPENS, PREVIEW_AS, scenarios } from "./scenarios";

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

function Page({ state }: { state: Adm10State }): JSX.Element {
  const o = OPENS[state];
  const [search, setSearch] = useState<Adm10Search>({
    as: o.as,
    device: o.device,
    ...(o.ov === undefined ? {} : { ov: o.ov }),
  });
  return <ADM10 search={search} onSearch={setSearch} previewAs={PREVIEW_AS} />;
}

function show(state: Adm10State): Call[] {
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
  render(
    <QueryClientProvider client={newQueryClient()}>
      <Page state={state} />
    </QueryClientProvider>,
  );
  return calls;
}

const fieldset = async (title: string): Promise<HTMLElement> => {
  const heading = await screen.findByRole("heading", { name: title });
  const section = heading.closest("section");
  if (section === null) throw new Error(`no fieldset ${title}`);
  return section;
};
const card = async (title: string): Promise<HTMLElement> =>
  screen.findByRole("region", { name: title });
const publishButton = async (): Promise<HTMLButtonElement> =>
  screen.findByRole<HTMLButtonElement>("button", { name: "Publish" });

describe("ADM-10 Portal branding & client experience", () => {
  it("a: published settings, Publish disabled, sender verified, cadence 7, the templates footer", async () => {
    show("a");
    const brand = await fieldset("Brand");
    await within(brand).findByText("Brightwater Hale <clients@brightwaterhale.com>");
    expect(brand.textContent).toContain("Espresso");
    expect(brand.textContent).toContain("Custom domain — later");
    expect(
      within(brand).getByRole("switch", { name: "“Secured by Accrued” footer" }),
    ).toBeTruthy();
    expect((await publishButton()).disabled).toBe(true);
    const reminders = await fieldset("Reminders");
    expect(reminders.textContent).toContain("Every 7 days until done");
    expect(reminders.textContent).toContain("4, then notify the assigned preparer");
    expect(reminders.textContent).toContain("Weekdays · 9:00 AM recipient's time");
    const templates = await fieldset("Email templates");
    await within(templates).findByText("6 of 6 published · 1 with draft changes");
    const email = await card("Reminder email");
    await within(email).findByText("Next reminder Mon, Sep 21");
    await screen.findByRole("figure", { name: "Preview as Claire Feld — read only" });
  });

  it("b: a draft with cadence 5: Unsaved changes, Publish enabled, Sat Sep 19 moves to Mon Sep 21", async () => {
    show("b");
    await screen.findByText("Unsaved changes");
    await waitFor(async () => {
      expect((await publishButton()).disabled).toBe(false);
    });
    const reminders = await fieldset("Reminders");
    expect(reminders.textContent).toContain("Every 5 days until done");
    const email = await card("Reminder email");
    await within(email).findByText("Next reminder Mon, Sep 21");
    expect(email.textContent).toContain("Sat, Sep 19 moves to the next weekday");
  });

  it("c: the phone preview", async () => {
    show("c");
    const frame = await screen.findByRole("figure", {
      name: "Preview as Claire Feld — read only",
    });
    expect(frame.getAttribute("data-preview-device")).toBe("phone");
  });

  it("d: Pending DNS with the records, DMARC guidance and the neutral fallback lines", async () => {
    show("d");
    const domain = await fieldset("Sender domain");
    await within(domain).findByText("Pending DNS");
    expect(within(domain).getAllByText(/\._domainkey\.brightwaterhale\.com$/)).toHaveLength(3);
    expect(domain.textContent).toContain("bounce.brightwaterhale.com");
    expect(domain.textContent).toContain("v=spf1 include:amazonses.com ~all");
    expect(domain.textContent).toContain("_dmarc.brightwaterhale.com");
    expect(domain.textContent).toContain("Portal · brightwaterhale.example-portal.test");
    await within(domain).findByText(
      "Email · Brightwater Hale <brightwaterhale@example-mail.test>",
    );
    expect(domain.textContent.toLowerCase()).not.toContain("accrued");
  });

  it("e: the Reconnect request drawer, Publish v2 disabled until an edit", async () => {
    show("e");
    const drawer = await screen.findByRole("dialog", { name: "Reconnect request" });
    await within(drawer).findByText("Published · v1");
    const publishV2 = within(drawer).getByRole("button", { name: "Publish v2" });
    expect((publishV2 as HTMLButtonElement).disabled).toBe(true);
  });

  it("f: publishing b's draft writes a version and shows the toast", async () => {
    const calls = show("b");
    fireEvent.click(await publishButton());
    await waitFor(() => {
      expect(
        calls.some((c) => c.method === "POST" && c.path === "/v1/firm/portal-settings/publish"),
      ).toBe(true);
    });
    await screen.findByText("Portal settings published · clients see changes on next visit");
    await waitFor(() => {
      expect(screen.queryByText("Unsaved changes")).toBeNull();
    });
  });

  it("g: preview as Tess Moreno, an entity client, next reminder Fri, Sep 18", async () => {
    show("g");
    await screen.findByRole("figure", { name: "Preview as Tess Moreno — read only" });
    const email = await card("Reminder email");
    await within(email).findByText("Next reminder Fri, Sep 18");
  });

  it("an edit saves the draft with the version it read", async () => {
    const calls = show("a");
    const reminders = await fieldset("Reminders");
    fireEvent.click(
      within(reminders).getByRole("switch", {
        name: "Stop when the client marks the binder done",
      }),
    );
    await waitFor(() => {
      const put = calls.find(
        (c) => c.method === "PUT" && c.path === "/v1/firm/portal-settings/draft",
      );
      expect((put?.body as { expected_version?: number } | undefined)?.expected_version).toBe(0);
    });
  });

  it("ADM-10 avoid: no Accrued in the preview frame or the email card while the footer is off", async () => {
    show("a");
    const frame = await screen.findByRole("figure", {
      name: "Preview as Claire Feld — read only",
    });
    const email = await card("Reminder email");
    for (const region of [frame, email]) {
      expect(region.textContent.toLowerCase()).not.toContain("accrued");
    }
  });

  it("ADM-10 avoid: no gradients, emoji or lorem ipsum", async () => {
    const { container } = render(<div />);
    show("a");
    await fieldset("Brand");
    const html = document.body.innerHTML;
    expect(html).not.toMatch(/gradient/i);
    expect(html).not.toMatch(/lorem ipsum/i);
    expect(html).not.toMatch(/\p{Extended_Pictographic}/u);
    expect(container).toBeTruthy();
  });
});
