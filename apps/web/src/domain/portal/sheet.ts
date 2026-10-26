// The request sheet's data (R-01 §5.2, L3; docs/screens/POR-04.md): one request through the
// caller's grant (`GET /v1/portal/request-items/{id}`), its shared thread (SPEC-032) and the
// client's writes on it, over the generated client only. The room (POR-14) uploads, withdraws
// and comments through the same calls.
//
// The question (POR-04 e) and decision (f) variants have no route in R-01: they are typed slots
// that C-01 and T-06 / T-09 fill from their own routes (docs/screens/POR-04.md, Variant-slot
// contract). Their figures are computed by the caller's code, never by a model (ADR-050).

import type { CommentOut, PortalFileOut, PortalRequestOut } from "@abacus/api-client";
import {
  announceUploadIntent,
  ignoreRequestItem,
  postItemComment,
  undoIgnore,
  upload,
  withdrawEvidenceVersion,
} from "@abacus/api-client";
import {
  getPortalBinderQueryKey,
  getPortalRequestOptions,
  getPortalRequestQueryKey,
  getPortalRoomQueryKey,
  itemCommentsOptions,
  itemCommentsQueryKey,
} from "@abacus/api-client/query";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ignoreCodeOf } from "./documents";

export function useRequestSheet(requestId: string | undefined) {
  return useQuery({
    ...getPortalRequestOptions({ path: { item_id: requestId ?? "" } }),
    enabled: requestId !== undefined,
    retry: false,
  });
}

/** The request's shared thread (a client reads only shared comments; the server decides). */
export function useThread(engagementId: string | undefined, itemId: string | undefined) {
  return useQuery({
    ...itemCommentsOptions({
      path: { engagement_id: engagementId ?? "", item_id: itemId ?? "" },
    }),
    enabled: engagementId !== undefined && itemId !== undefined,
    retry: false,
  });
}

/** The question slot (POR-04 e; C-01 fills it from its transaction questions). */
export interface SheetQuestion {
  title: string;
  /** Who at the firm asked ("Raj Malhotra"): the answered line names them. */
  askedBy: string;
  /** Code-supplied key-values the firm already shows the client in its question. */
  context: readonly { label: string; value: string }[];
  note: string;
  options: readonly { code: string; label: string }[];
  selected: string;
  text: string;
  attachments: readonly { name: string; sizeBytes: number; done: boolean }[];
  answered?: { at: string; followUpBy: string };
}

/** The decision slot (POR-04 f; T-06 / T-09 fill it): firm-written text whose figures the
 * caller's code computed. */
export interface SheetDecision {
  title: string;
  dueLabel: string;
  explanation: string;
  options: readonly { code: string; label: string }[];
  footnote: string;
}

export interface QuestionAnswer {
  option: string;
  text: string;
}

/** The firm person the client's Ignore note is for: the newest firm comment's author, by first
 * name; none when the firm has not written in the thread. */
export function noteRecipient(thread: readonly CommentOut[]): string | null {
  const firm = [...thread].reverse().find((c) => c.author_side === "firm");
  const first = firm?.author_name.split(" ")[0];
  return first === undefined || first === "" ? null : first;
}

/** The file the sheet's Withdraw takes back: the client's own unaccepted upload. */
export function withdrawableFile(sheet: PortalRequestOut): PortalFileOut | undefined {
  if (!(sheet.allowed_actions ?? []).includes("withdraw")) return undefined;
  return (sheet.files ?? []).find((f) => f.withdrawable);
}

/** One request's files, sent through its own upload route after the upload intent ("Uploading n
 * files…" firm-side). Used by the sheet and the room alike. */
export async function uploadFiles(
  engagementId: string,
  itemId: string,
  files: readonly File[],
): Promise<void> {
  await announceUploadIntent({
    path: { item_id: itemId },
    body: { files_expected: files.length },
  });
  for (const file of files) {
    await upload({
      path: { engagement_id: engagementId, item_id: itemId },
      query: { filename: file.name },
      body: file as never,
      bodySerializer: null,
      headers: { "Content-Type": file.type || "application/octet-stream" },
    });
  }
}

/** Withdraw the client's own unaccepted upload (ADR P-31). */
export async function withdrawFile(engagementId: string, fileId: string): Promise<void> {
  await withdrawEvidenceVersion({
    path: { engagement_id: engagementId, version_id: fileId },
    headers: { "Idempotency-Key": crypto.randomUUID() },
  });
}

/** Post to a request's shared thread (the server makes a client's comment shared). */
export async function postComment(engagementId: string, itemId: string, text: string) {
  await postItemComment({
    path: { engagement_id: engagementId, item_id: itemId },
    body: { text },
  });
}

/** The sheet's writes, each followed by fresh reads of the sheet, the binder behind it, the room
 * and the thread. */
export function useSheetActions(sheet: PortalRequestOut | undefined) {
  const queryClient = useQueryClient();
  const engagementId = sheet?.engagement_id ?? "";
  const itemId = sheet?.id ?? "";
  const refresh = (): void => {
    void queryClient.invalidateQueries({
      queryKey: getPortalRequestQueryKey({ path: { item_id: itemId } }),
    });
    void queryClient.invalidateQueries({
      queryKey: getPortalBinderQueryKey({ path: { binder_id: sheet?.binder_id ?? "" } }),
    });
    void queryClient.invalidateQueries({ queryKey: getPortalRoomQueryKey() });
    void queryClient.invalidateQueries({
      queryKey: itemCommentsQueryKey({
        path: { engagement_id: engagementId, item_id: itemId },
      }),
    });
  };
  return {
    upload: async (files: readonly File[]): Promise<void> => {
      await uploadFiles(engagementId, itemId, files);
      refresh();
    },
    ignore: async (label: string, note: string): Promise<void> => {
      await ignoreRequestItem({
        path: { item_id: itemId },
        body: { reason: ignoreCodeOf(label), ...(note.trim() === "" ? {} : { note }) },
      });
      refresh();
    },
    undoIgnore: async (): Promise<void> => {
      await undoIgnore({
        path: { item_id: itemId },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      });
      refresh();
    },
    withdraw: async (file: PortalFileOut): Promise<void> => {
      await withdrawFile(engagementId, file.id);
      refresh();
    },
    comment: async (text: string): Promise<void> => {
      await postComment(engagementId, itemId, text);
      refresh();
    },
  };
}
