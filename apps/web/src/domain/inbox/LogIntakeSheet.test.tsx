// Log received documents (DV-1; N-01-T23 makes it live at `/inbox?ov=log-intake`). The batch is
// logged first, then each file as its own raw upload with its own Idempotency-Key; "Log {n}" stays
// disabled until there is a file and a subject; the scanner's and the size limits' refusals read
// in the design's words; the footer names the viewer.
import { client } from "@abacus/api-client/client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureRequest, installFixtureMode, json } from "../../app-core/fixture-mode";
import { meHandlers } from "../../fixtures/handlers";
import { renderRoutes } from "../../testing/support";
import { LOG_COPY as COPY } from "./copy";
import { LogIntakeSheet, MAX_BYTES } from "./LogIntakeSheet";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

const MESSAGE = "00000000-0000-4000-8000-0000000000a1";

function mount(fileStatus = 201, fileBody: unknown = { id: "f1" }): FixtureRequest[] {
  const seen: FixtureRequest[] = [];
  restore = installFixtureMode({
    state: "log",
    persona: "grace-holloway",
    handlers: {
      ...meHandlers(),
      "GET /v1/clients": () => json({ items: [], next_cursor: null, total: 0 }),
      "POST /v1/inbox/intake": (req) => {
        seen.push(req);
        return json({ message_id: MESSAGE, thread_id: "t1" }, 201);
      },
      "POST /v1/inbox/intake/{message_id}/files": (req) => {
        seen.push(req);
        return json(fileBody, fileStatus);
      },
    },
  });
  renderRoutes([
    {
      path: "/",
      component: () => <LogIntakeSheet open viewer="Grace Holloway" onClose={() => undefined} />,
    },
  ]);
  return seen;
}

function pick(dialog: HTMLElement, files: File[]): void {
  const input = within(dialog).getByLabelText(COPY.files);
  fireEvent.change(input, { target: { files } });
}

function subject(dialog: HTMLElement, text: string): void {
  const row = within(dialog).getByRole("textbox", { name: COPY.subject });
  fireEvent.change(row, { target: { value: text } });
}

describe("Log received documents", () => {
  it("names the viewer and keeps Log disabled until a file and a subject", async () => {
    mount();
    const dialog = await screen.findByRole("dialog", { name: COPY.title });
    expect(within(dialog).getByText(COPY.footer("Grace Holloway"))).toBeTruthy();
    const log = within(dialog).getByRole<HTMLButtonElement>("button", { name: COPY.log(0) });
    expect(log.disabled).toBe(true);
    pick(dialog, [new File(["%PDF-1.7"], "W-2.pdf", { type: "application/pdf" })]);
    expect(
      within(dialog).getByRole<HTMLButtonElement>("button", { name: COPY.log(1) }).disabled,
    ).toBe(true);
    subject(dialog, "W-2 by mail");
    expect(
      within(dialog).getByRole<HTMLButtonElement>("button", { name: COPY.log(1) }).disabled,
    ).toBe(false);
  });

  it("logs the batch, then each file raw with its own key", async () => {
    const seen = mount();
    const dialog = await screen.findByRole("dialog", { name: COPY.title });
    pick(dialog, [
      new File(["%PDF-1.7 a"], "W-2.pdf", { type: "application/pdf" }),
      new File(["%PDF-1.7 b"], "1099.pdf", { type: "application/pdf" }),
    ]);
    subject(dialog, "Tax forms by mail");
    fireEvent.click(within(dialog).getByRole("button", { name: COPY.log(2) }));
    await waitFor(() => {
      expect(seen).toHaveLength(3);
    });
    const [batch, first, second] = seen;
    expect(batch?.path).toBe("/v1/inbox/intake");
    expect(batch?.body).toMatchObject({ subject: "Tax forms by mail", received_via: "email" });
    expect(first?.params.message_id).toBe(MESSAGE);
    expect(first?.query.get("filename")).toBe("W-2.pdf");
    expect(second?.query.get("filename")).toBe("1099.pdf");
  });

  it("says a refused file in the design's words", async () => {
    mount(503, { detail: "scanner_unavailable" });
    const dialog = await screen.findByRole("dialog", { name: COPY.title });
    pick(dialog, [new File(["%PDF-1.7"], "W-2.pdf", { type: "application/pdf" })]);
    subject(dialog, "W-2");
    fireEvent.click(within(dialog).getByRole("button", { name: COPY.log(1) }));
    expect(await within(dialog).findByText(COPY.errors.scanner)).toBeTruthy();
  });

  it("refuses a file over 50 MB and more than 20 files before sending anything", async () => {
    const seen = mount();
    const dialog = await screen.findByRole("dialog", { name: COPY.title });
    const big = new File(["x"], "big.pdf", { type: "application/pdf" });
    Object.defineProperty(big, "size", { value: MAX_BYTES + 1 });
    pick(dialog, [big]);
    expect(within(dialog).getByText(COPY.errors.size)).toBeTruthy();
    pick(
      dialog,
      Array.from(
        { length: 21 },
        (_, i) => new File(["x"], `f${String(i)}.pdf`, { type: "application/pdf" }),
      ),
    );
    expect(within(dialog).getByText(COPY.errors.count)).toBeTruthy();
    expect(seen).toHaveLength(0);
  });
});
