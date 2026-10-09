// SPEC-023 (TASK-039): the inbox, suggestions and matching.
import type { InboxFileOut, RequestItemOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { InboxPanel } from "./InboxPanel";

const E = "e1";

function item(id: string, description: string, status = "open"): RequestItemOut {
  return {
    id,
    engagement_id: E,
    description,
    audit_area: "Cash",
    status: status as RequestItemOut["status"],
    created_at: "2026-10-01T00:00:00Z",
    evidence_version_id: null,
    retrievability_tier: null,
    client_visible: true,
    client_assignee_user_id: null,
  };
}

const ITEMS = [item("i1", "Bank statements for December"), item("i2", "Payroll summary")];

function file(over: Partial<InboxFileOut> = {}): InboxFileOut {
  return {
    id: "f1",
    file_name: "Bank_Statements_Dec.pdf",
    media_type: "application/pdf",
    size_bytes: 1200,
    uploaded_by: "u-c",
    uploaded_by_name: "Cara Client",
    uploaded_by_staff: false,
    note: null,
    created_at: "2026-10-09T10:00:00Z",
    suggestions: [{ request_item_id: "i1", score: 67, matched: ["bank", "statement"] }],
    ...over,
  };
}

const panel = (): void => {
  renderRoutes([{ path: "/", component: () => <InboxPanel engagementId={E} items={ITEMS} /> }]);
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

describe("ac2 adding files", () => {
  it("adds each file and explains a refusal in plain words", async () => {
    let posts = 0;
    mockApi({
      [`GET /v1/engagements/${E}/inbox`]: () => json([]),
      [`POST /v1/engagements/${E}/inbox`]: () => {
        posts += 1;
        return posts === 1 ? json(file(), 201) : json({ detail: "duplicate_upload" }, 409);
      },
    });
    panel();
    expect(await screen.findByText("Nothing waiting to be matched.")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Add several files at once"), {
      target: { files: [new File(['"a"'], "a.pdf"), new File(['"b"'], "b.pdf")] },
    });
    const progress = await screen.findByRole("list", { name: "Files being added" });
    expect(await within(progress).findByText("Added")).toBeTruthy();
    expect(await within(progress).findByText(/already waiting here/)).toBeTruthy();
  });
});

describe("ac3 ac4 matching", () => {
  it("shows a suggestion with its score and assigns it as a followed suggestion", async () => {
    const { calls } = mockApi({
      [`GET /v1/engagements/${E}/inbox`]: () => json([file()]),
      [`POST /v1/engagements/${E}/inbox/f1/assign`]: () =>
        json({ evidence_version_id: "v1" }, 201),
    });
    panel();
    const suggestions = await screen.findByLabelText("Suggestions for Bank_Statements_Dec.pdf");
    const button = within(suggestions).getByRole("button", {
      name: "Bank statements for December · 67%",
    });
    expect(button.getAttribute("title")).toBe("Matched: bank, statement");
    fireEvent.click(button);
    await waitFor(() => {
      expect(calls.find((c) => c.path.endsWith("/assign"))?.body).toEqual({
        request_item_id: "i1",
        followed_suggestion: true,
      });
    });
  });

  it("matches by choosing a request when there is no suggestion, and removes a file", async () => {
    const { calls } = mockApi({
      [`GET /v1/engagements/${E}/inbox`]: () =>
        json([file({ file_name: "scan0001.pdf", suggestions: [] })]),
      [`POST /v1/engagements/${E}/inbox/f1/assign`]: () =>
        json({ evidence_version_id: "v1" }, 201),
      [`POST /v1/engagements/${E}/inbox/f1/discard`]: () => json({ id: "f1" }),
    });
    panel();
    expect(await screen.findByText(/No suggestion/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Request for scan0001.pdf"), {
      target: { value: "i2" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Match" }));
    await waitFor(() => {
      expect(calls.find((c) => c.path.endsWith("/assign"))?.body).toEqual({
        request_item_id: "i2",
        followed_suggestion: false,
      });
    });
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() => {
      expect(calls.some((c) => c.path.endsWith("/discard"))).toBe(true);
    });
  });

  it("says when someone else already matched the file", async () => {
    mockApi({
      [`GET /v1/engagements/${E}/inbox`]: () => json([file()]),
      [`POST /v1/engagements/${E}/inbox/f1/assign`]: () =>
        json({ detail: "inbox_file_gone" }, 409),
    });
    panel();
    fireEvent.click(
      await screen.findByRole("button", { name: "Bank statements for December · 67%" }),
    );
    expect(await screen.findByText("Someone already matched or removed this file.")).toBeTruthy();
  });
});

describe("ac6 not allowed", () => {
  it("shows nothing when the inbox is refused", async () => {
    mockApi({ [`GET /v1/engagements/${E}/inbox`]: () => json({ detail: "forbidden" }, 403) });
    panel();
    await waitFor(() => {
      expect(screen.queryByText("Inbox")).toBeNull();
    });
  });
});
