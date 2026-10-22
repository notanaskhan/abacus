// SPEC-041 (TASK-103): review notes in a drawer: a reviewer raises one, the raiser clears it,
// a preparer responds; a row shows its open notes.
import type { NoteOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { NoteCount, NotesDrawer } from "./ReviewNotes";

const BASE = "/v1/engagements/e1/procedures/p1";
const NOTE: NoteOut = {
  id: "n1",
  item_id: "i1",
  state: "open",
  raised_by: "u-r",
  raised_by_name: "Rae Reviewer",
  raised_at: "2026-10-20T10:00:00Z",
  thread: [
    {
      kind: "raised",
      body: "Where's the approval?",
      by: "u-r",
      name: "Rae Reviewer",
      at: "2026-10-20T10:00:00Z",
    },
  ],
};

function drawer(role: string, me: string, notes: NoteOut[], extra = {}) {
  const api = mockApi({ ...extra });
  renderRoutes([
    {
      path: "/",
      component: () => (
        <NotesDrawer
          open
          onOpenChange={() => undefined}
          engagementId="e1"
          procedureId="p1"
          itemId="i1"
          title="Review notes · JE-1"
          notes={notes}
          role={role}
          me={me}
        />
      ),
    },
  ]);
  return api;
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

describe("ac1 ac2 ac3 the drawer", () => {
  it("lets a reviewer raise a note on the row", async () => {
    const { calls } = drawer("senior", "u-s", [], {
      [`POST ${BASE}/notes`]: () => json([NOTE], 201),
    });
    fireEvent.change(await screen.findByLabelText("New review note"), {
      target: { value: "Where's the approval?" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Raise note" }));
    await waitFor(() => {
      expect(calls.find((c) => c.path.endsWith("/notes"))?.body).toEqual({
        item_id: "i1",
        body: "Where's the approval?",
      });
    });
  });

  it("offers staff a response but no clear and no new note", async () => {
    drawer("staff", "u-s", [NOTE]);
    expect(await screen.findByText("Where's the approval?")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Respond" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Clear note" })).toBeNull();
    expect(screen.queryByLabelText("New review note")).toBeNull();
  });

  it("lets the raiser clear it", async () => {
    const { calls } = drawer("senior", "u-r", [NOTE], {
      [`POST ${BASE}/notes/n1/clear`]: () => json([{ ...NOTE, state: "cleared" }], 201),
    });
    fireEvent.click(await screen.findByRole("button", { name: "Clear note" }));
    await waitFor(() => {
      expect(calls.some((c) => c.path.endsWith("/notes/n1/clear"))).toBe(true);
    });
  });
});

describe("ac7 the row's count", () => {
  it("shows open notes on the row", async () => {
    renderRoutes([
      {
        path: "/",
        component: () => <NoteCount notes={[NOTE]} onOpen={() => undefined} canRaise={false} />,
      },
    ]);
    expect(await screen.findByLabelText("1 open review notes")).toBeTruthy();
  });
});
