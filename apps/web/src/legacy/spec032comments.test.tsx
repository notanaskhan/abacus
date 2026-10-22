// SPEC-032 AC-1 to AC-8, AC-10 (TASK-063): the comment thread for the firm and the client,
// mentions, corrections, redaction, refusals, unread, the Board filter and the client's bell.
import type { CommentOut, NotificationOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { applyFilters } from "../board/filters";
import { ClientBell } from "../shell/ClientBell";
import { notificationHref, notificationText } from "../shell/notifications";
import { json, mockApi, renderRoutes, signInForTest } from "../testing/support";
import { CommentThread } from "./CommentThread";

const E = "e1";
const BASE = `/v1/engagements/${E}/request-items/i1`;
const ME = "u-me";

function comment(over: Partial<CommentOut> = {}): CommentOut {
  return {
    id: "c1",
    request_item_id: "i1",
    author_user_id: "u-client",
    author_name: "Rachel",
    author_side: "client",
    visibility: "shared",
    text: "Our bank only exports CSV. OK?",
    created_at: "2026-10-12T10:00:00Z",
    ...over,
  };
}

function thread(
  comments: CommentOut[],
  props: Partial<Parameters<typeof CommentThread>[0]> = {},
  extra = {},
): { calls: { method: string; path: string; body: unknown }[] } {
  const api = mockApi({
    [`GET ${BASE}/comments`]: () => json(comments),
    [`POST ${BASE}/comments/read`]: () => json({ read: true }),
    [`GET ${BASE}/comments/mention-candidates`]: () =>
      json([
        { user_id: "u-rachel", display_name: "Rachel Smoke", side: "client" },
        { user_id: "u-sam", display_name: "Sam Staff", side: "firm" },
      ]),
    ...extra,
  });
  renderRoutes([
    {
      path: "/",
      component: () => (
        <CommentThread
          ids={{ engagementId: E, itemId: "i1" }}
          me={ME}
          side="firm"
          canShare
          label="Comments on this request"
          {...props}
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

describe("ac1 ac10 the thread", () => {
  it("shows an empty thread and marks it read when opened", async () => {
    const { calls } = thread([]);
    expect(await screen.findByText("No comments yet.")).toBeTruthy();
    await waitFor(() => {
      expect(calls.some((c) => c.path === `${BASE}/comments/read`)).toBe(true);
    });
  });

  it("marks internal notes as the firm's own", async () => {
    thread([
      comment(),
      comment({ id: "c2", author_side: "firm", visibility: "internal", text: "Tie it to the TB" }),
    ]);
    expect(await screen.findByText("Tie it to the TB")).toBeTruthy();
    expect(screen.getAllByText("Internal: the client can't see this")).toHaveLength(1);
  });

  it("shows an error when the thread can't load", async () => {
    thread([], {}, { [`GET ${BASE}/comments`]: () => json({ detail: "unavailable" }, 503) });
    expect(await screen.findByText("Couldn't load the comments")).toBeTruthy();
  });

  it("renders comment text as plain text", async () => {
    thread([comment({ text: "<b>bold</b>" })]);
    expect(await screen.findByText("<b>bold</b>")).toBeTruthy();
  });
});

describe("ac2 visibility", () => {
  it("posts an internal note by default and shares only when chosen", async () => {
    const { calls } = thread([], {}, { [`POST ${BASE}/comments`]: () => json(comment(), 201) });
    const box = await screen.findByLabelText("Add a comment");
    expect(screen.getByText("Internal note: only your team sees this.")).toBeTruthy();
    fireEvent.change(box, { target: { value: "first" } });
    fireEvent.click(screen.getByRole("button", { name: "Post" }));
    await waitFor(() => {
      expect(
        calls.find((c) => c.method === "POST" && c.path === `${BASE}/comments`)?.body,
      ).toMatchObject({ share: false });
    });
    fireEvent.click(screen.getByLabelText("Share with client"));
    expect(screen.getByText("The client will see this.")).toBeTruthy();
  });

  it("gives clients no choice: their comments are shared", async () => {
    thread([], { side: "client", canShare: false });
    await screen.findByLabelText("Add a comment");
    expect(screen.queryByLabelText("Share with client")).toBeNull();
    expect(screen.getByText("Your auditor will see this.")).toBeTruthy();
  });

  it("hides sharing from roles that can't share", async () => {
    thread([], { canShare: false });
    await screen.findByLabelText("Add a comment");
    expect(screen.queryByLabelText("Share with client")).toBeNull();
  });
});

describe("ac4 ac6 corrections and redaction", () => {
  it("links a correction and offers Correct on your own comment", async () => {
    thread([
      comment({ id: "c1", author_user_id: ME, author_side: "firm", corrected_by: ["c2"] }),
      comment({
        id: "c2",
        author_user_id: ME,
        author_side: "firm",
        corrects: "c1",
        text: "fixed",
      }),
    ]);
    expect(await screen.findByText("Corrected below")).toBeTruthy();
    expect(screen.getByText("Corrects an earlier comment")).toBeTruthy();
    fireEvent.click(screen.getAllByRole("button", { name: "Correct" })[0] as HTMLElement);
    expect(screen.getByText("Correcting your comment")).toBeTruthy();
  });

  it("shows the redaction stub instead of the text", async () => {
    thread([
      comment({
        text: null,
        redaction: {
          redacted_by_name: "Ana Admin",
          redacted_at: "2026-10-12T11:00:00Z",
          reason: "A password",
        },
      }),
    ]);
    expect(
      await screen.findByText(/Redacted by Ana Admin on October 12, 2026: A password/),
    ).toBeTruthy();
  });

  it("lets only a firm administrator redact, with a reason", async () => {
    const { calls } = thread(
      [comment()],
      { canRedact: true },
      {
        [`POST ${BASE}/comments/c1/redact`]: () => json({ read: true }, 201),
      },
    );
    fireEvent.click(await screen.findByRole("button", { name: "Redact" }));
    const dialog = await screen.findByRole("dialog");
    fireEvent.change(within(dialog).getByLabelText("Reason"), {
      target: { value: "posted in error" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "Redact" }));
    await waitFor(() => {
      expect(calls.find((c) => c.path.endsWith("/redact"))?.body).toEqual({
        reason: "posted in error",
      });
    });
  });

  it("offers no Redact to others", async () => {
    thread([comment()]);
    await screen.findByText("Our bank only exports CSV. OK?");
    expect(screen.queryByRole("button", { name: "Redact" })).toBeNull();
  });
});

describe("ac5 mentions", () => {
  it("picks people as you type and sends their ids", async () => {
    const { calls } = thread([], {}, { [`POST ${BASE}/comments`]: () => json(comment(), 201) });
    const box = await screen.findByLabelText("Add a comment");
    fireEvent.change(box, { target: { value: "Thanks @Sa" } });
    const list = await screen.findByRole("list", { name: "People you can mention" });
    expect(within(list).queryByText(/Rachel/)).toBeNull();
    fireEvent.click(within(list).getByText(/Sam Staff/));
    expect(screen.getByLabelText("Will be notified").textContent).toContain("Sam Staff");
    fireEvent.click(screen.getByRole("button", { name: "Post" }));
    await waitFor(() => {
      expect(
        calls.find((c) => c.method === "POST" && c.path === `${BASE}/comments`)?.body,
      ).toMatchObject({
        text: "Thanks @Sam Staff ",
        mentions: ["u-sam"],
      });
    });
  });
});

describe("ac7 refusals", () => {
  it.each([
    ["out_of_scope", /outside this engagement/],
    ["sharing_unavailable", /Sharing with the client isn't available/],
    ["mention_not_allowed", /Someone you mentioned can't see this comment/],
  ])("explains %s", async (code, message) => {
    thread(
      [],
      {},
      {
        [`POST ${BASE}/comments`]: () =>
          json({ detail: code }, code === "mention_not_allowed" ? 422 : 409),
      },
    );
    fireEvent.change(await screen.findByLabelText("Add a comment"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Post" }));
    expect(await screen.findByText(message)).toBeTruthy();
  });
});

describe("ac8 unread on the Board", () => {
  it("filters to items with unread comments", () => {
    const row = (id: string, unread: boolean) => ({
      item: {
        id,
        engagement_id: E,
        description: id,
        audit_area: "Cash",
        status: "requested",
        created_at: "",
        unread_comments: unread,
      },
      evidence: null,
    });
    const rows = [row("a", true), row("b", false)] as unknown as Parameters<
      typeof applyFilters
    >[0];
    expect(
      applyFilters(rows, { source: "unread_comments" }, new Map()).map((r) => r.item.id),
    ).toEqual(["a"]);
  });
});

describe("q2 notifications", () => {
  const n = {
    id: "n1",
    kind: "mention",
    engagement_id: E,
    subject_type: "request_item",
    subject_id: "i1",
    created_at: "2026-10-12T10:00:00Z",
    read: false,
  } as NotificationOut;

  it("words a mention and leads each side to the request", () => {
    expect(notificationText("mention")).toBe("You were mentioned in a comment.");
    expect(notificationHref(n)).toEqual({ to: `/engagements/${E}/items/i1` });
    expect(notificationHref(n, "client")).toEqual({
      to: `/client/engagements/${E}`,
      hash: "request-i1",
    });
  });
});

describe("q2 the client's bell", () => {
  it("shows the unread count and opens the client's notifications", async () => {
    mockApi({
      "GET /v1/notifications": () =>
        json({
          items: [
            {
              id: "n1",
              kind: "mention",
              engagement_id: E,
              subject_type: "request_item",
              subject_id: "i1",
              created_at: "2026-10-12T10:00:00Z",
              read: false,
            },
          ],
          unread_count: 1,
        }),
    });
    renderRoutes([{ path: "/", component: () => <ClientBell /> }]);
    fireEvent.click(await screen.findByRole("button", { name: "Notifications, 1 unread" }));
    expect(await screen.findByText("You were mentioned in a comment.")).toBeTruthy();
  });
});
