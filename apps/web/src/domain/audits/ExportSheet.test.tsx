// A-01-T24 (TASK-1447; DV-9, DEC-541): "Hannah exports with step-up, sees Packaging then Ready, and
// Undo within 10 s cancels the export." The O3 export sheet and the record-mode dialogs on the
// fixture routes (fixtures/handlers/exports.ts; the sheet has no artboard, so each frame it can
// show is a fixture state with a test here): step-up, Queued → Packaging… → Ready with its
// download line, Undo inside the window, Export failed, Expired (voided), no Export control without
// `export.create`, and the record dialogs' writes. The axe pass is the screen's (AUD-02).
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { type FixtureHandler, installFixtureMode } from "../../app-core/fixture-mode";
import { type ExportFrame, exportHandlers } from "../../fixtures/handlers/exports";
import { newQueryClient } from "../../testing/support";
import { ExportSheet } from "./ExportSheet";
import { AUDIT_MESSAGES } from "./messages";
import { PhaseRecordDialog } from "./RecordDialogs";

const WORK_ITEM = "0b0e5b42-0b8f-4d52-9a4e-3d1b8f1c0001";
const ENGAGEMENT = "0b0e5b42-0b8f-4d52-9a4e-3d1b8f1c0002";
const NOW = Date.parse("2026-09-14T09:41:00-05:00");
const W = AUDIT_MESSAGES.export;
const POLL = { timeout: 8_000 };

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

function install(handlers: Record<string, FixtureHandler>): Call[] {
  const calls: Call[] = [];
  const wrapped = Object.fromEntries(
    Object.entries(handlers).map(([key, handler]) => [
      key,
      ((request) => {
        calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({
    state: "export",
    persona: "hannah-leclerc",
    clock: "2026-09-14T09:41:00-05:00",
    handlers: wrapped,
  });
  return calls;
}

function sheet(
  options: { stepUp?: boolean; existing?: ExportFrame; canExport?: boolean } = {},
): Call[] {
  const calls = install(
    exportHandlers({
      workItemId: WORK_ITEM,
      engagementId: ENGAGEMENT,
      now: NOW,
      ...(options.stepUp === undefined ? {} : { stepUp: options.stepUp }),
      ...(options.existing === undefined ? {} : { existing: options.existing }),
    }),
  );
  render(
    <QueryClientProvider client={newQueryClient()}>
      <ExportSheet
        workItemId={WORK_ITEM}
        open
        onOpenChange={() => undefined}
        canExport={options.canExport ?? true}
      />
    </QueryClientProvider>,
  );
  return calls;
}

describe("A-01-T24: the export sheet", () => {
  it("Hannah exports with step-up, sees Packaging then Ready", async () => {
    const calls = sheet({ stepUp: true });
    fireEvent.click(await screen.findByRole("button", { name: W.export }));
    // A stale second factor: the shell's step-up, nothing exported.
    expect(await screen.findByText("Confirm it's you")).toBeTruthy();
    const cancels = screen.getAllByRole("button", { name: "Cancel" });
    fireEvent.click(cancels[cancels.length - 1] as HTMLElement); // the step-up's own Cancel
    fireEvent.click(screen.getByRole("button", { name: W.export }));
    await waitFor(() => {
      expect(toastStore.list()[0]?.text).toBe(W.requested);
    });
    expect(toastStore.list()[0]?.action).toBe("Undo");
    const create = calls.filter((c) => c.method === "POST" && c.path.endsWith("/exports"));
    expect(create).toHaveLength(2); // the refused one, then the one that went through
    expect(create[1]?.body).toMatchObject({
      kind: "binder",
      scope: { include_unaccepted: false, include_audit_trail: true },
    });
    expect(await screen.findByText("Packaging…", {}, POLL)).toBeTruthy();
    const ready = await screen.findByRole(
      "button",
      { name: /^Download · 12 files · .+ · expires Mon Sep 21$/ },
      POLL,
    );
    expect(ready).toBeTruthy();
    expect(screen.getByText("Ready")).toBeTruthy();
  }, 20_000);

  it("Undo within 10 s cancels the export", async () => {
    const calls = sheet();
    fireEvent.click(await screen.findByRole("button", { name: W.export }));
    await waitFor(() => {
      expect(toastStore.list()[0]?.action).toBe("Undo");
    });
    const id = toastStore.list()[0]?.id ?? "";
    toastStore.act(id);
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path.endsWith("/undo"))).toBe(true);
    });
  });

  it("an export that failed says why in words", async () => {
    sheet({ existing: "failed" });
    expect(await screen.findByText("Export failed")).toBeTruthy();
    expect(screen.getByText(W.failure.build_error)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Download/ })).toBeNull();
  });

  it("an expired export offers no download and says the 7 days passed", async () => {
    sheet({ existing: "expired" });
    expect(await screen.findByText("Expired")).toBeTruthy();
    expect(screen.getByText(W.voided.expired)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /^Download/ })).toBeNull();
  });

  it("a ready export downloads through the API", async () => {
    const calls = sheet({ existing: "ready" });
    fireEvent.click(await screen.findByRole("button", { name: /^Download · 12 files/ }));
    await waitFor(() => {
      expect(calls.some((c) => c.path.endsWith("/download"))).toBe(true);
    });
  });

  it("without export.create there is no Export control (metadata-only readers)", async () => {
    sheet({ existing: "ready", canExport: false });
    await screen.findByText("Ready");
    expect(screen.queryByRole("button", { name: W.export })).toBeNull();
    expect(screen.queryByText(W.includeUnaccepted)).toBeNull();
  });
});

describe("A-01-T24: the record-mode dialogs", () => {
  it("records the next phase as the person (never the agent)", async () => {
    const calls = install({
      "POST /v1/audits/{work_item_id}/phase": () =>
        new Response(
          JSON.stringify({
            event_id: "0b0e5b42-0b8f-4d52-9a4e-3d1b8f1c0099",
            from_phase: "planning",
            to_phase: "fieldwork",
            mode: "recorded",
            recorded_at: "2026-09-14T14:41:00Z",
            version: 2,
            work_item_id: WORK_ITEM,
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
    });
    render(
      <QueryClientProvider client={newQueryClient()}>
        <PhaseRecordDialog
          workItemId={WORK_ITEM}
          current="planning"
          open
          onOpenChange={() => undefined}
        />
      </QueryClientProvider>,
    );
    fireEvent.click(
      await screen.findByRole("button", { name: AUDIT_MESSAGES.record.phase.confirm }),
    );
    await waitFor(() => {
      expect(calls.find((c) => c.path.endsWith("/phase"))?.body).toEqual({ to: "fieldwork" });
    });
  });

  it("a refused phase reads in words", async () => {
    install({
      "POST /v1/audits/{work_item_id}/phase": () =>
        new Response(JSON.stringify({ detail: "phase_skip" }), {
          status: 409,
          headers: { "Content-Type": "application/json" },
        }),
    });
    render(
      <QueryClientProvider client={newQueryClient()}>
        <PhaseRecordDialog
          workItemId={WORK_ITEM}
          current="planning"
          open
          onOpenChange={() => undefined}
        />
      </QueryClientProvider>,
    );
    fireEvent.click(
      await screen.findByRole("button", { name: AUDIT_MESSAGES.record.phase.confirm }),
    );
    expect((await screen.findByRole("alert")).textContent).toBe(
      AUDIT_MESSAGES.record.refusals.phase_skip,
    );
  });
});
