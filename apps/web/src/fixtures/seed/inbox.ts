// The firm inbox at E0 (N-01-T10; INB-01 spec; blueprint 01 §9): the docs@ mailbox's 17 threads,
// word for word from the File Kit's W0 dataset that TPL-08 mounts (`@abacus/ui/specimens`,
// F-05-T58), shaped as C5's intake read models (`InboxThreadRow`, `InboxThreadDetail`). 23
// attachments wait and 4 threads match no client; `filed` is W0-filed (INB-01 d: the Feld 2025
// form filed, the 2024 one ignored). Dev and test only (never in the production bundle).
import type {
  InboundMessageOut,
  InboxAttachmentOut,
  InboxThreadDetail,
  InboxThreadRow,
} from "@abacus/api-client";
import { type Tpl08Message, tpl08Messages } from "@abacus/ui/specimens";
import { stableId } from "./prng";

const E0 = Date.parse("2026-09-14T09:24:00-05:00");
const STATUS = { new: "new", wait: "waiting", filed: "filed", ignored: "ignored" } as const;

function at(m: Tpl08Message): string {
  return new Date(E0 - m.daysAgo * 86_400_000).toISOString();
}

function attachments(m: Tpl08Message): InboxAttachmentOut[] {
  return m.attachments.map((a) => ({
    id: stableId(`inbox-attachment:${m.id}:${a.name}`),
    file_name: a.name,
    media_type: "application/pdf",
    size_bytes: 0,
    fingerprint: "0".repeat(64),
    status: STATUS[a.state],
    flags:
      a.tag === undefined
        ? []
        : [
            {
              kind: "wrong_year",
              severity: "block_bulk",
              ref_evidence_version_id: null,
              facts: {},
            },
          ],
    filed: null,
    ignored_reason: a.state === "ignored" ? "wrong_year" : null,
    held_at: null,
    thumbnail_ref: null,
    allowed_actions: a.state === "wait" || a.state === "new" ? ["inbox.file", "inbox.triage"] : [],
  }));
}

function message(m: Tpl08Message): InboundMessageOut {
  return {
    id: stableId(`inbox-message:${m.id}`),
    channel: "email",
    received_via: "email",
    sender_display: m.from,
    logged_by_name: null,
    subject_display: m.subject,
    received_at: at(m),
    body: m.body === "" ? null : m.body,
    attachments: attachments(m),
  };
}

function messagesOf(m: Tpl08Message): Tpl08Message[] {
  return m.replies !== undefined && m.replies.length > 0 && m.body === "" ? [...m.replies] : [m];
}

function waiting(m: Tpl08Message): number {
  return messagesOf(m).reduce(
    (n, x) => n + x.attachments.filter((a) => a.state === "wait").length,
    0,
  );
}

export function threadRow(m: Tpl08Message): InboxThreadRow {
  return {
    id: stableId(`inbox-thread:${m.id}`),
    source_kind: "mailbox",
    channel: "email",
    match_state: m.client === null ? "unmatched" : "matched",
    client_id: m.client === null ? null : stableId(`client:${m.client}`),
    client_name: m.client,
    subject_display: m.subject,
    sender_display: m.from,
    last_received_at: at(m),
    status: STATUS[m.state],
    waiting: waiting(m),
    message_count: messagesOf(m).length,
  };
}

export function threadDetail(m: Tpl08Message): InboxThreadDetail {
  return {
    thread: threadRow(m),
    match_method: m.client === null ? "none" : "contact_email",
    work_item_label: m.context ?? null,
    messages: messagesOf(m).map(message),
    allowed_actions: ["inbox.match_sender", "inbox.triage", "inbox.file"],
    version: 1,
  };
}

/** The 17 threads, newest first; `filed` is INB-01 d's W0-filed. */
export function inboxThreads(filed = false): readonly Tpl08Message[] {
  return tpl08Messages(filed);
}
