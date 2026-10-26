// The portal PBC fixture routes (R-01-T05): C5 section portal-pbc and the P-06 portal writes the
// screens call, answering the generated shapes. One scenario holds one binder's rows in memory, so
// Ignore, Undo, Mark as Done and Withdraw change what the next read returns, as the live routes
// will (R-01-T07, T08; P-06):
// - an Ignore marks the row Ignored with the day and offers Undo; Undo makes it To do again;
// - Mark as Done marks the binder done today; Undo returns the button to tonal or ready;
// - Withdraw takes the file off its row (the row is To do again if it was the only file);
// - a drop answers 202 and the batch poll answers the scenario's outcomes;
// - the room and its suggest answer only the scenario's delegated items; anything else is 404.
// Times are the scenario's clock; nothing here reads the device clock.

import type {
  BinderMarkedDoneOut,
  CommentOut,
  DropAcceptedOut,
  DropBatchOut,
  IgnoreIn,
  IgnoreUndoneOut,
  IgnoredOut,
  MarkDoneUndoneOut,
  PortalBinderListOut,
  PortalBinderOut,
  PortalBinderRefOut,
  PortalFileOut,
  PortalRequestOut,
  PortalRoomOut,
  PortalRowOut,
  CommentIn,
  RoomSuggestIn,
  RoomSuggestOut,
  UploadIntentIn,
  UploadOut,
  UploadIntentOut,
  WithdrawalOut,
} from "@abacus/api-client";
import { type FixtureHandler, json, never } from "../../app-core/fixture-mode";
import { getSeed, meFor } from "../seed";
import { stableId } from "../seed/prng";

const NOT_FOUND = { detail: "not found" };
const DAY = 24 * 60 * 60 * 1000;

export interface PortalDocumentsOptions {
  /** The scenario's instant. */
  clock: string;
  /** The binder picker's rows. */
  binders?: PortalBinderRefOut[];
  /** The binders the persona can open, by id; `null` never answers (loading). */
  binder?: PortalBinderOut | null;
  others?: PortalBinderOut[];
  /** POR-04's requests the persona can open, by id. */
  requests?: PortalRequestOut[];
  /** Shared threads by request item id. */
  threads?: Readonly<Record<string, CommentOut[]>>;
  /** The drop batch the poll answers (POR-03 c, d). */
  drop?: DropBatchOut;
  /** The persona's third-party room; absent is 404 (POR-14 f, and every non-third-party). */
  room?: PortalRoomOut;
}

const today = (clock: string): string => clock.slice(0, 10);

function rowsOf(binder: PortalBinderOut): PortalRowOut[] {
  return [...(binder.groups ?? []), ...(binder.bands ?? [])].flatMap((g) => g.rows);
}

/** Replace one row everywhere it appears and recompute what the client reads from the rows. */
function withRow(binder: PortalBinderOut, row: PortalRowOut): PortalBinderOut {
  const swap = <G extends { rows: PortalRowOut[] }>(g: G): G => ({
    ...g,
    rows: g.rows.map((r) => (r.id === row.id ? row : r)),
  });
  const next: PortalBinderOut = {
    ...binder,
    groups: (binder.groups ?? []).map(swap),
    bands: (binder.bands ?? []).map(swap),
  };
  const open = rowsOf(next).filter(
    (r) => r.client_status === "to_do" || r.client_status === "returned",
  ).length;
  const marked = binder.mark_done.state === "marked";
  return {
    ...next,
    open_count: open,
    done_count: binder.total - open,
    mark_done: marked ? binder.mark_done : { state: open > 0 ? "tonal" : "ready" },
  };
}

export function portalDocumentsHandlers(
  options: PortalDocumentsOptions,
): Record<string, FixtureHandler> {
  const { clock } = options;
  const on = today(clock);
  const binders = new Map<string, PortalBinderOut>();
  for (const b of [options.binder ?? undefined, ...(options.others ?? [])]) {
    if (b !== undefined) binders.set(b.binder.id, b);
  }
  const requests = new Map((options.requests ?? []).map((r) => [r.id, r]));
  const threads = new Map(Object.entries(options.threads ?? {}).map(([k, v]) => [k, [...v]]));
  const ignoredBefore = new Map<string, PortalRowOut>();
  let room = options.room;
  const withdrawn = (versionId: string, itemId: string): WithdrawalOut => ({
    evidence_version_id: versionId,
    request_item_id: itemId,
    withdrawn_at: clock,
    erase_after: new Date(Date.parse(clock) + 30 * DAY).toISOString(),
  });

  const findRow = (itemId: string): [PortalBinderOut, PortalRowOut] | undefined => {
    for (const b of binders.values()) {
      const row = rowsOf(b).find((r) => r.id === itemId);
      if (row !== undefined) return [b, row];
    }
    return undefined;
  };
  const put = (binder: PortalBinderOut, row: PortalRowOut): void => {
    binders.set(binder.binder.id, withRow(binder, row));
    const sheet = requests.get(row.id);
    if (sheet !== undefined) {
      requests.set(row.id, {
        ...sheet,
        client_status: row.client_status,
        files: row.files ?? [],
        allowed_actions: row.allowed_actions ?? [],
      });
    }
  };

  return {
    "GET /v1/portal/binders": () => {
      const items = options.binders ?? [...binders.values()].map((b) => b.binder);
      const body: PortalBinderListOut = { items, total: items.length };
      return json(body);
    },
    "GET /v1/portal/binders/{binder_id}": ({ params }) => {
      if (options.binder === null) return never();
      const binder = binders.get(params.binder_id ?? "");
      return binder === undefined ? json(NOT_FOUND, 404) : json(binder);
    },
    "GET /v1/portal/request-items/{item_id}": ({ params }) => {
      const sheet = requests.get(params.item_id ?? "");
      return sheet === undefined ? json(NOT_FOUND, 404) : json(sheet);
    },
    "POST /v1/portal/request-items/{item_id}/ignore": ({ params, body }) => {
      const found = findRow(params.item_id ?? "");
      if (found === undefined) return json(NOT_FOUND, 404);
      const [binder, row] = found;
      // The note becomes a shared comment firm-side (R-01-T08); the fixture keeps the reason only.
      const given = body as IgnoreIn;
      if (given.reason.length === 0) return json({ detail: "reason_required" }, 422);
      ignoredBefore.set(row.id, row);
      put(binder, {
        ...row,
        client_status: "ignored",
        ignored_on: on,
        allowed_actions: ["undo_ignore", "comment"],
      });
      const out: IgnoredOut = {
        request_item_id: row.id,
        status: "requested",
        client_ignored_at: clock,
      };
      return json(out);
    },
    "POST /v1/portal/request-items/{item_id}/ignore/undo": ({ params }) => {
      const found = findRow(params.item_id ?? "");
      const before = ignoredBefore.get(params.item_id ?? "");
      if (found === undefined) return json(NOT_FOUND, 404);
      if (before === undefined) return json({ detail: "firm_already_acted" }, 409);
      put(found[0], before);
      ignoredBefore.delete(before.id);
      const out: IgnoreUndoneOut = {
        request_item_id: before.id,
        client_status: before.client_status,
        undone_at: clock,
      };
      return json(out);
    },
    "POST /v1/portal/binders/{binder_id}/mark-done": ({ params }) => {
      const binder = binders.get(params.binder_id ?? "");
      if (binder === undefined) return json(NOT_FOUND, 404);
      binders.set(binder.binder.id, {
        ...binder,
        mark_done: { state: "marked", marked_on: on, marked_by_name: null },
        allowed_actions: ["undo_mark_done"],
      });
      const out: BinderMarkedDoneOut = {
        binder_id: binder.binder.id,
        status: "complete",
        marked_done_at: clock,
        open_count: binder.open_count,
      };
      return json(out);
    },
    "POST /v1/portal/binders/{binder_id}/mark-done/undo": ({ params }) => {
      const binder = binders.get(params.binder_id ?? "");
      if (binder === undefined) return json(NOT_FOUND, 404);
      if (binder.mark_done.state !== "marked") return json({ detail: "firm_already_acted" }, 409);
      const state = binder.open_count > 0 ? "tonal" : "ready";
      binders.set(binder.binder.id, {
        ...binder,
        mark_done: { state },
        allowed_actions: ["upload", "mark_done"],
      });
      const out: MarkDoneUndoneOut = {
        binder_id: binder.binder.id,
        mark_done: state,
        undone_at: clock,
      };
      return json(out);
    },
    "POST /v1/engagements/{engagement_id}/evidence-versions/{version_id}/withdraw": ({
      params,
    }) => {
      const versionId = params.version_id ?? "";
      for (const binder of binders.values()) {
        const row = rowsOf(binder).find((r) => (r.files ?? []).some((f) => f.id === versionId));
        const versionFile = row?.files?.find((f) => f.id === versionId);
        if (row === undefined || versionFile === undefined) continue;
        if (!versionFile.withdrawable) return json({ detail: "evidence_accepted" }, 409);
        const files = (row.files ?? []).filter((f) => f.id !== versionId);
        put(binder, {
          ...row,
          files,
          client_status: files.length === 0 ? "to_do" : row.client_status,
          allowed_actions:
            files.length === 0 ? ["upload", "ignore", "comment"] : (row.allowed_actions ?? []),
        });
        const out: WithdrawalOut = {
          evidence_version_id: versionId,
          request_item_id: row.id,
          withdrawn_at: clock,
          erase_after: new Date(Date.parse(clock) + 30 * DAY).toISOString(),
        };
        return json(out);
      }
      // The sheet's own file (POR-04 c, portal-upload variant) or a room row's (POR-14).
      for (const sheet of requests.values()) {
        const own = (sheet.files ?? []).find((f) => f.id === versionId);
        if (own === undefined) continue;
        if (!own.withdrawable) return json({ detail: "evidence_accepted" }, 409);
        const files = (sheet.files ?? []).filter((f) => f.id !== versionId);
        requests.set(sheet.id, {
          ...sheet,
          files,
          client_status: files.length === 0 ? "to_do" : sheet.client_status,
          allowed_actions:
            files.length === 0 ? ["upload", "ignore", "comment"] : (sheet.allowed_actions ?? []),
        });
        return json(withdrawn(versionId, sheet.id));
      }
      const roomRow = room?.bands
        .flatMap((b) => b.rows)
        .find((r) => (r.files ?? []).some((f) => f.id === versionId));
      if (room !== undefined && roomRow !== undefined) {
        room = withoutRoomFile(room, roomRow.id, versionId);
        return json(withdrawn(versionId, roomRow.id));
      }
      return json(NOT_FOUND, 404);
    },
    "POST /v1/portal/request-items/{item_id}/upload-intents": ({ params, body }) => {
      const given = body as UploadIntentIn;
      const out: UploadIntentOut = {
        request_item_id: params.item_id ?? "",
        files_expected: given.files_expected,
        expires_at: new Date(Date.parse(clock) + 90_000).toISOString(),
      };
      return json(out, 201);
    },
    "POST /v1/portal/binders/{binder_id}/drops": ({ params }) => {
      if (!binders.has(params.binder_id ?? "")) return json(NOT_FOUND, 404);
      const batch = options.drop;
      if (batch === undefined) return json(NOT_FOUND, 404);
      const out: DropAcceptedOut = {
        batch_id: batch.batch_id,
        file_id: batch.files[0]?.file_id ?? batch.batch_id,
      };
      return json(out, 202);
    },
    "GET /v1/portal/drops/{batch_id}": ({ params }) =>
      options.drop !== undefined && options.drop.batch_id === params.batch_id
        ? json(options.drop)
        : json(NOT_FOUND, 404),
    "GET /v1/portal/room": () => (room === undefined ? json(NOT_FOUND, 404) : json(room)),
    "POST /v1/portal/room/suggest": ({ body }) => {
      if (room === undefined) return json(NOT_FOUND, 404);
      // Code-only, file names only: a word of the name in exactly one open delegated title.
      const open = room.bands.flatMap((b) => b.rows).filter((r) => r.state === "due");
      const words = (s: string) =>
        new Set(
          s
            .toLowerCase()
            .split(/[^a-z0-9]+/)
            .filter((w) => w.length > 3),
        );
      const given = body as RoomSuggestIn;
      const out: RoomSuggestOut = {
        suggestions: given.file_names.map((name) => {
          const mine = words(name);
          const hits = open.filter((r) => [...words(r.title)].some((w) => mine.has(w)));
          return {
            file_name: name,
            request_item_id: hits.length === 1 ? (hits[0]?.id ?? null) : null,
          };
        }),
      };
      return json(out);
    },
    "GET /v1/engagements/{engagement_id}/request-items/{item_id}/comments": ({ params }) =>
      json(threads.get(params.item_id ?? "") ?? []),
    // R-01-T12, T14: a client's comment joins the shared thread (SPEC-032: always shared).
    "POST /v1/engagements/{engagement_id}/request-items/{item_id}/comments": ({
      params,
      body,
      persona,
    }) => {
      const itemId = params.item_id ?? "";
      const given = body as CommentIn;
      const me = meFor(getSeed(), persona ?? "claire-feld");
      const thread = threads.get(itemId) ?? [];
      const out: CommentOut = {
        id: stableId(`portal-pbc:comment:${itemId}:${String(thread.length)}`),
        request_item_id: itemId,
        author_user_id: me?.user_id ?? "",
        author_name: me?.display_name ?? "",
        author_side: "client",
        created_at: clock,
        text: given.text,
        visibility: "shared",
      };
      threads.set(itemId, [...thread, out]);
      return json(out, 201);
    },
    // R-01-T12, T14: a request's own upload ("Upload…" on the sheet or a room row): the file is
    // the client's own and unaccepted, so it reads "You uploaded" with Withdraw.
    "POST /v1/engagements/{engagement_id}/request-items/{item_id}/uploads": ({
      params,
      query,
      persona,
    }) => {
      const itemId = params.item_id ?? "";
      const name = query.get("filename") ?? "upload";
      const fileId = stableId(`portal-pbc:upload:${itemId}:${name}`);
      const uploaded: PortalFileOut = {
        id: fileId,
        name,
        receipt: { kind: "uploaded", on },
        withdrawable: true,
      };
      const sheet = requests.get(itemId);
      if (sheet !== undefined) {
        requests.set(itemId, {
          ...sheet,
          client_status: "done",
          files: [uploaded, ...(sheet.files ?? [])],
          returned: null,
          allowed_actions: ["withdraw", "comment"],
        });
      }
      if (room !== undefined) room = withRoomUpload(room, itemId, uploaded, on);
      const me = meFor(getSeed(), persona ?? "claire-feld");
      const out: UploadOut = {
        evidence_version_id: fileId,
        file_name: name,
        media_type: "application/pdf",
        size_bytes: 0,
        uploaded_at: clock,
        uploaded_by: me?.user_id ?? null,
        uploaded_by_name: me?.display_name ?? "",
      };
      return json(out, 201);
    },
  };
}

/** A room after the client's upload to one row: in review, with Withdraw on the file. */
function withRoomUpload(
  room: PortalRoomOut,
  itemId: string,
  file: PortalFileOut,
  on: string,
): PortalRoomOut {
  const bands = room.bands.map((band) => {
    const rows = band.rows.map((r) =>
      r.id === itemId
        ? {
            ...r,
            state: "in_review" as const,
            state_on: on,
            disc: "done" as const,
            files: [file, ...(r.files ?? [])],
            returned: null,
            allowed_actions: ["withdraw" as const, "comment" as const],
          }
        : r,
    );
    return { ...band, rows, uploaded: rows.filter((r) => r.disc === "done").length };
  });
  const uploaded = bands.reduce((n, b) => n + b.uploaded, 0);
  return { ...room, bands, uploaded_count: uploaded };
}

/** A room after the client withdrew one of its files: the row is due again when it was the
 * only file. */
function withoutRoomFile(room: PortalRoomOut, itemId: string, versionId: string): PortalRoomOut {
  const bands = room.bands.map((band) => {
    const rows = band.rows.map((r) => {
      if (r.id !== itemId) return r;
      const files = (r.files ?? []).filter((f) => f.id !== versionId);
      return files.length > 0
        ? { ...r, files }
        : {
            ...r,
            files,
            state: "due" as const,
            disc: "ring" as const,
            allowed_actions: ["upload" as const, "comment" as const],
          };
    });
    return { ...band, rows, uploaded: rows.filter((r) => r.disc === "done").length };
  });
  return { ...room, bands, uploaded_count: bands.reduce((n, b) => n + b.uploaded, 0) };
}
