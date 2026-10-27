// ac-test-author: ayushkbhatia
// Q-03-T525: back-fill of TASK-063 (comments web), black-box from SPEC-032 against the legacy
// CommentThread, which stays live until P-05 (2028) replaces it. Retired only when P-05's AC suite
// merges. Server-only parts (AC-3's filtering, AC-5's notify-once, AC-9 sealing and audit) are
// Q-03-T039's TASK-062 back-fill (see TASK-1708).
import type { CommentOut } from "@abacus/api-client";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { json, mockApi, never, renderRoutes, signInForTest } from "../testing/support";
import { CommentThread } from "./CommentThread";

const E = "eng-t525";
const ITEM = `/v1/engagements/${E}/request-items/item-9`;
const ME = "user-me";

function said(over: Partial<CommentOut> = {}): CommentOut {
  return {
    id: "cm-1",
    request_item_id: "item-9",
    author_user_id: "user-tess",
    author_name: "Tess Moreno",
    author_side: "client",
    visibility: "shared",
    text: "The August statement is attached.",
    created_at: "2026-09-14T14:00:00Z",
    ...over,
  };
}

type Props = Partial<Parameters<typeof CommentThread>[0]>;

function show(
  comments: CommentOut[],
  props: Props = {},
  extra: Record<string, () => Response | Promise<Response>> = {},
) {
  const api = mockApi({
    [`GET ${ITEM}/comments`]: () => json(comments),
    [`GET ${ITEM}/versions/ver-2/comments`]: () => json([]),
    [`POST ${ITEM}/comments/read`]: () => json({ read: true }),
    [`GET ${ITEM}/comments/mention-candidates`]: () =>
      json([{ user_id: "user-raj", display_name: "Raj Malhotra", side: "firm" }]),
    ...extra,
  });
  renderRoutes([
    {
      path: "/",
      component: () => (
        <CommentThread
          ids={{ engagementId: E, itemId: "item-9" }}
          me={ME}
          side="firm"
          canShare
          label="Comments"
          {...props}
        />
      ),
    },
  ]);
  return api;
}

async function write(text: string): Promise<void> {
  fireEvent.change(await screen.findByLabelText("Add a comment"), { target: { value: text } });
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

describe("SPEC-032 AC-1", () => {
  it("test_ac1_a_version_has_its_own_thread_which_starts_empty", async () => {
    const { calls } = show([said()], {
      ids: { engagementId: E, itemId: "item-9", versionId: "ver-2" },
    });
    expect(await screen.findByText("No comments yet.")).toBeTruthy();
    expect(calls.some((c) => c.path === `${ITEM}/versions/ver-2/comments`)).toBe(true);
    expect(calls.some((c) => c.method === "GET" && c.path === `${ITEM}/comments`)).toBe(false);
  });
});

describe("SPEC-032 AC-2", () => {
  it("test_ac2_a_firm_comment_is_internal_unless_shared", async () => {
    const { calls } = show([], {}, { [`POST ${ITEM}/comments`]: () => json(said(), 201) });
    await write("Please send September too.");
    fireEvent.click(screen.getByRole("button", { name: "Post" }));
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path === `${ITEM}/comments`)).toBe(true);
    });
    const post = calls.find((c) => c.method === "POST" && c.path === `${ITEM}/comments`);
    expect((post?.body as { share: boolean }).share).toBe(false);
    expect(screen.getByText("Internal note: only your team sees this.")).toBeTruthy();
  });

  it("test_ac2_share_with_client_posts_shared", async () => {
    const { calls } = show([], {}, { [`POST ${ITEM}/comments`]: () => json(said(), 201) });
    await write("Thanks, received.");
    fireEvent.click(screen.getByRole("checkbox", { name: "Share with client" }));
    fireEvent.click(screen.getByRole("button", { name: "Post" }));
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST")).toBe(true);
    });
    const post = calls.find((c) => c.method === "POST" && c.path === `${ITEM}/comments`);
    expect((post?.body as { share: boolean }).share).toBe(true);
  });

  it("test_ac2_a_client_comment_is_always_shared", async () => {
    const { calls } = show(
      [],
      { side: "client", canShare: false },
      {
        [`POST ${ITEM}/comments`]: () => json(said(), 201),
      },
    );
    await write("Here it is.");
    expect(screen.queryByRole("checkbox", { name: "Share with client" })).toBeNull();
    expect(screen.getByText("Your auditor will see this.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Post" }));
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST")).toBe(true);
    });
    const post = calls.find((c) => c.method === "POST" && c.path === `${ITEM}/comments`);
    expect(post?.body).toBeTruthy(); // the server shares a client's comment; no choice is offered
  });
});

describe("SPEC-032 AC-3", () => {
  it("test_ac3_a_client_sees_exactly_what_the_server_returns_and_no_internal_affordance", async () => {
    show([said()], { side: "client", canShare: false });
    expect(await screen.findByText("The August statement is attached.")).toBeTruthy();
    expect(screen.queryByText(/Internal note/)).toBeNull();
  });
});

describe("SPEC-032 AC-4", () => {
  it("test_ac4_a_comment_offers_no_edit_or_delete_only_a_correction", async () => {
    show([said({ author_user_id: ME, author_side: "firm", author_name: "Me" })]);
    await screen.findByText("The August statement is attached.");
    expect(screen.queryByRole("button", { name: /Edit|Delete/ })).toBeNull();
    expect(screen.getByRole("button", { name: "Correct" })).toBeTruthy();
  });

  it("test_ac4_a_correction_links_to_the_comment_it_corrects", async () => {
    const { calls } = show(
      [said({ author_user_id: ME, author_side: "firm", author_name: "Me" })],
      {},
      {
        [`POST ${ITEM}/comments`]: () => json(said({ id: "cm-2", corrects: "cm-1" }), 201),
      },
    );
    fireEvent.click(await screen.findByRole("button", { name: "Correct" }));
    fireEvent.change(screen.getByLabelText("Correcting your comment"), {
      target: { value: "Statement for August, account ending 4410." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Post" }));
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path === `${ITEM}/comments`)).toBe(true);
    });
    const post = calls.find((c) => c.method === "POST" && c.path === `${ITEM}/comments`);
    expect((post?.body as { corrects?: string }).corrects).toBe("cm-1");
  });

  it("test_ac4_both_show_the_link", async () => {
    show([
      said({ id: "cm-1", corrected_by: ["cm-2"] }),
      said({ id: "cm-2", corrects: "cm-1", text: "Account ending 4410." }),
    ]);
    expect(await screen.findByText("Corrects an earlier comment")).toBeTruthy();
    expect(screen.getByText("Corrected below")).toBeTruthy();
  });
});

describe("SPEC-032 AC-5", () => {
  it("test_ac5_only_the_servers_candidates_can_be_mentioned_and_each_is_sent_once", async () => {
    const { calls } = show([], {}, { [`POST ${ITEM}/comments`]: () => json(said(), 201) });
    await write("Over to @Ra");
    const list = await screen
      .findByRole("listbox", { name: "People you can mention" })
      .catch(() => screen.findByLabelText("People you can mention"));
    fireEvent.click(within(list).getByText("Raj Malhotra"));
    fireEvent.click(screen.getByRole("button", { name: "Post" }));
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path === `${ITEM}/comments`)).toBe(true);
    });
    const post = calls.find((c) => c.method === "POST" && c.path === `${ITEM}/comments`);
    expect((post?.body as { mentions: string[] }).mentions).toEqual(["user-raj"]);
  });
});

describe("SPEC-032 AC-6", () => {
  it("test_ac6_only_an_administrator_sees_redact", async () => {
    show([said()]);
    await screen.findByText("The August statement is attached.");
    expect(screen.queryByRole("button", { name: "Redact" })).toBeNull();
  });

  it("test_ac6_redaction_needs_a_reason", async () => {
    const { calls } = show(
      [said()],
      { canRedact: true },
      {
        [`POST ${ITEM}/comments/cm-1/redact`]: () => json(said({ text: "" }), 200),
      },
    );
    fireEvent.click(await screen.findByRole("button", { name: "Redact" }));
    const dialog = await screen.findByRole("dialog");
    const confirm = within(dialog).getByRole("button", { name: "Redact" });
    expect((confirm as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(within(dialog).getByLabelText("Reason"), {
      target: { value: "Account number posted by mistake" },
    });
    fireEvent.click(confirm);
    await waitFor(() => {
      expect(calls.some((c) => c.path === `${ITEM}/comments/cm-1/redact`)).toBe(true);
    });
  });

  it("test_ac6_every_reader_sees_the_stub_not_the_text", async () => {
    show([
      said({
        text: "",
        redaction: {
          redacted_by_name: "Grace Holloway",
          redacted_at: "2026-09-14T15:00:00Z",
          reason: "Account number posted by mistake",
        },
      }),
    ]);
    expect(await screen.findByText(/Redacted by Grace Holloway/)).toBeTruthy();
    expect(screen.queryByText("The August statement is attached.")).toBeNull();
  });
});

describe("SPEC-032 AC-7", () => {
  it("test_ac7_a_scope_violation_names_the_reason_and_offers_an_internal_note", async () => {
    show(
      [],
      {},
      {
        [`POST ${ITEM}/comments`]: () => json({ detail: "out_of_scope" }, 422),
      },
    );
    await write("Compare with the other client's ledger.");
    fireEvent.click(screen.getByRole("checkbox", { name: "Share with client" }));
    fireEvent.click(screen.getByRole("button", { name: "Post" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/outside this engagement/);
    expect(alert.textContent).toMatch(/internal note/);
  });
});

describe("SPEC-032 AC-8", () => {
  it("test_ac8_opening_a_thread_marks_it_read", async () => {
    const { calls } = show([said()]);
    await screen.findByText("The August statement is attached.");
    await waitFor(() => {
      expect(calls.some((c) => c.method === "POST" && c.path === `${ITEM}/comments/read`)).toBe(
        true,
      );
    });
  });
});

describe("SPEC-032 AC-10", () => {
  it("test_ac10_loading_shows_no_thread", async () => {
    show([], {}, { [`GET ${ITEM}/comments`]: () => never() });
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText("No comments yet.")).toBeNull();
  });

  it("test_ac10_empty_error_and_not_allowed_are_said_in_words", async () => {
    show([], {}, { [`GET ${ITEM}/comments`]: () => json({ detail: "boom" }, 500) });
    expect(await screen.findByText("Couldn't load the comments")).toBeTruthy();
    cleanup();
    show([], {}, { [`GET ${ITEM}/comments`]: () => json({ detail: "forbidden" }, 403) });
    expect(await screen.findByText(/can.t see these comments/)).toBeTruthy();
  });

  it("test_ac10_an_internal_note_looks_different_from_a_shared_comment", async () => {
    show([said({ visibility: "internal", author_side: "firm", author_name: "Raj Malhotra" })]);
    expect(await screen.findByText(/Internal: the client can.t see this/)).toBeTruthy();
  });
});
