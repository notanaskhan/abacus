// The portal's documents (R-01 §5.2, L3; docs/screens/POR-03.md): the binder picker, one binder
// through the caller's grant, and the client's writes, over the generated client only (C5 section
// portal-pbc and P-06's portal routes). `binderView` turns the projection into the C-16 Request
// kit's rows: client words in, client words out; the kit never sees a firm status code.

import type {
  PortalBinderOut,
  PortalFileOut,
  PortalReturnedOut,
  PortalRowOut,
} from "@abacus/api-client";
import {
  announceUploadIntent,
  dropFile,
  ignoreRequestItem,
  markBinderDone,
  undoIgnore,
  undoMarkDone,
  upload,
  withdrawEvidenceVersion,
} from "@abacus/api-client";
import {
  getPortalBinderOptions,
  getPortalBinderQueryKey,
  listPortalBindersOptions,
} from "@abacus/api-client/query";
import {
  CATEGORIES,
  type CategoryKey,
  IGNORE_REASONS,
  type IconName,
  type RequestItem,
  type RequestSectionData,
} from "@abacus/ui";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { DOCUMENT_WORDS } from "./messages";

export function useBinders(scopeId: string | null) {
  return useQuery({
    ...listPortalBindersOptions(scopeId === null ? {} : { query: { scope_id: scopeId } }),
    retry: false,
  });
}

export function useBinder(binderId: string | undefined) {
  return useQuery({
    ...getPortalBinderOptions({ path: { binder_id: binderId ?? "" } }),
    enabled: binderId !== undefined,
    retry: false,
  });
}

/** The server's category codes onto the kit's nine rail rows. */
const CATEGORY_OF: Readonly<Record<string, CategoryKey>> = {
  personal: "personal",
  income: "income",
  home: "home",
  health: "health",
  education: "edu",
  edu: "edu",
  retirement: "retire",
  retire: "retire",
  charitable: "charity",
  charity: "charity",
  business: "business",
  other: "other",
};

function categoryOf(code: string): CategoryKey {
  return CATEGORY_OF[code] ?? "other";
}

function iconOf(category: CategoryKey): IconName {
  return CATEGORIES.find((c) => c.key === category)?.icon ?? "ellipsis";
}

/** The three Ignore reasons, in the kit's order, onto P-06's codes. */
const IGNORE_CODES = ["not_this_year", "sent_another_way", "dont_have"] as const;
export type IgnoreCode = (typeof IGNORE_CODES)[number];

export function ignoreCodeOf(label: string): IgnoreCode {
  const index = IGNORE_REASONS.findIndex((r) => r === label);
  return IGNORE_CODES[index] ?? "not_this_year";
}

export interface BinderView {
  requests: RequestItem[];
  sections: RequestSectionData[];
  /** The kit row id → the file a Withdraw withdraws (the client's own unaccepted upload). */
  withdrawable: ReadonlyMap<string, PortalFileOut>;
  /** Categories the server computed complete (every request done or ignored), including those
   * whose requests the "Requested" view does not list. */
  doneCats: CategoryKey[];
  marked: boolean;
  readOnly: boolean;
}

function receiptText(file: PortalFileOut, day: (iso: string) => string): string {
  const on = day(file.receipt.on);
  switch (file.receipt.kind) {
    case "emailed":
      return DOCUMENT_WORDS.receipt.emailed(on);
    case "uploaded_by_other_contact":
      return DOCUMENT_WORDS.receipt.otherContact(file.receipt.by_first_name ?? "", on);
    default:
      return DOCUMENT_WORDS.receipt.uploaded(on);
  }
}

function returnedText(r: PortalReturnedOut): { label: string; note: string } {
  return {
    label: DOCUMENT_WORDS.returned.pill(r.reason),
    note: r.note == null ? `— ${r.by_name}` : `${r.note} — ${r.by_name}`,
  };
}

function rowOf(
  row: PortalRowOut,
  sec: string,
  firm: string,
  day: (iso: string) => string,
): RequestItem {
  const base = { id: row.id, sec, title: row.title, req: "" };
  const files = row.files ?? [];
  const names = files.map((f) => f.name);
  const first = files[0];
  if (row.kind === "firm_provided") {
    return { ...base, st: "firm", note: DOCUMENT_WORDS.firmProvided(firm) };
  }
  if (row.kind === "provided_by_connection") {
    return { ...base, st: "up", upText: DOCUMENT_WORDS.providedByConnection };
  }
  switch (row.client_status) {
    case "to_do":
      return {
        ...base,
        st: "req",
        ...(row.due_on == null ? {} : { due: DOCUMENT_WORDS.due(day(row.due_on)) }),
        ...(row.uploading_count !== undefined && row.uploading_count > 0
          ? { uploading: DOCUMENT_WORDS.uploadingN(row.uploading_count) }
          : {}),
      };
    case "ignored":
      // The kit writes "Marked not applicable · ‹reason›"; the portal shows the day instead.
      return {
        ...base,
        st: "na",
        ...(row.ignored_on == null ? {} : { reason: day(row.ignored_on) }),
      };
    case "returned": {
      const words = row.returned == null ? null : returnedText(row.returned);
      return {
        ...base,
        st: "ret",
        ...(first === undefined ? {} : { file: first.name, files: names }),
        ...(words === null ? {} : { retLabel: words.label, note: words.note }),
      };
    }
    case "done": {
      if (first === undefined) return { ...base, st: "up", upText: DOCUMENT_WORDS.done };
      const suggested = files.some((f) => f.receipt.kind === "rule_linked_pending");
      return {
        ...base,
        st: "up",
        file: first.name,
        files: names,
        on: day(first.receipt.on),
        upText: receiptText(first, day),
        ...(suggested ? { matched: true, suggested: true } : {}),
      };
    }
  }
}

/** The projection as the kit draws it. `day` formats a server date on the scenario's clock. */
export function binderView(
  binder: PortalBinderOut,
  firm: string,
  day: (iso: string) => string,
): BinderView {
  const sections: RequestSectionData[] = [];
  const requests: RequestItem[] = [];
  const withdrawable = new Map<string, PortalFileOut>();
  // Folder bands (the audit variant, POR-03 i) carry no category: the rail has nothing to tick.
  const groups: { code: string; label: string; category: string; rows: PortalRowOut[] }[] =
    binder.layout === "bands"
      ? (binder.bands ?? []).map((b) => ({ ...b, category: "other" }))
      : (binder.groups ?? []).map((g) => ({ ...g, category: g.category_code }));
  for (const group of groups) {
    const category = categoryOf(group.category);
    sections.push({ key: group.code, category, title: group.label, icon: iconOf(category) });
    for (const row of group.rows) {
      requests.push(rowOf(row, group.code, firm, day));
      const own = (row.files ?? []).find((f) => f.withdrawable);
      if (own !== undefined && (row.allowed_actions ?? []).includes("withdraw")) {
        withdrawable.set(row.id, own);
      }
    }
  }
  return {
    requests,
    sections,
    withdrawable,
    doneCats: binder.categories.filter((c) => c.complete).map((c) => categoryOf(c.code)),
    marked: binder.mark_done.state === "marked",
    readOnly: binder.binder.read_only,
  };
}

/** An upload the policy refused at the door: its name and the contract's code. */
export interface RefusedFile {
  name: string;
  code: "file_too_large" | "type_not_allowed";
}

export interface SendResult {
  /** The drop's batch to poll; null for a request's own upload or when every file was refused. */
  batch: string | null;
  refused: readonly RefusedFile[];
}

/** The C5 refusal code of a failed drop (413 `file_too_large`, 415 `type_not_allowed`). */
export function refusalOf(error: unknown): RefusedFile["code"] | null {
  const detail =
    typeof error === "object" && error !== null && "detail" in error ? error.detail : null;
  return detail === "file_too_large" || detail === "type_not_allowed" ? detail : null;
}

/** The client's writes, each followed by a fresh read of the binder (the kit shows the change at
 * once; the next read replaces it). */
export function useBinderActions(binder: PortalBinderOut | undefined) {
  const queryClient = useQueryClient();
  const binderId = binder?.binder.id ?? "";
  const refresh = (): void => {
    void queryClient.invalidateQueries({
      queryKey: getPortalBinderQueryKey({ path: { binder_id: binderId } }),
    });
  };
  const rowOfId = (id: string): PortalRowOut | undefined =>
    [...(binder?.groups ?? []), ...(binder?.bands ?? [])]
      .flatMap((g) => g.rows)
      .find((r) => r.id === id);
  const key = (): string => crypto.randomUUID();

  return {
    ignore: async (id: string, label: string, note: string): Promise<void> => {
      await ignoreRequestItem({
        path: { item_id: id },
        body: { reason: ignoreCodeOf(label), ...(note === "" ? {} : { note }) },
      });
      refresh();
    },
    undoIgnore: async (id: string): Promise<void> => {
      await undoIgnore({ path: { item_id: id }, headers: { "Idempotency-Key": key() } });
      refresh();
    },
    markDone: async (): Promise<void> => {
      await markBinderDone({ path: { binder_id: binderId } });
      refresh();
    },
    undoMarkDone: async (): Promise<void> => {
      await undoMarkDone({ path: { binder_id: binderId }, headers: { "Idempotency-Key": key() } });
      refresh();
    },
    withdraw: async (row: string, file: PortalFileOut): Promise<void> => {
      const engagement = rowOfId(row)?.engagement_id ?? "";
      await withdrawEvidenceVersion({
        path: { engagement_id: engagement, version_id: file.id },
        headers: { "Idempotency-Key": key() },
      });
      refresh();
    },
    /** Files for one request ("Upload…"), or dropped anywhere (null): the drop goes to the
     * engagement drop zone in one batch for the code-rule sort (DEC-58 a). Answers the drop's
     * batch id, which the screen polls (`useDropBatch`; null for a request's own upload), and the
     * files the upload policy refused at the door (413, 415). */
    send: async (files: readonly File[], requestId: string | null): Promise<SendResult> => {
      if (requestId !== null) {
        const row = rowOfId(requestId);
        await announceUploadIntent({
          path: { item_id: requestId },
          body: { files_expected: files.length },
        });
        for (const file of files) {
          await upload({
            path: { engagement_id: row?.engagement_id ?? "", item_id: requestId },
            query: { filename: file.name },
            body: file as never,
            bodySerializer: null,
            headers: { "Content-Type": file.type || "application/octet-stream" },
          });
        }
        refresh();
        return { batch: null, refused: [] };
      }
      const batch = key();
      const refused: RefusedFile[] = [];
      // The server names the batch it sorts (`DropAcceptedOut.batch_id`); the poll reads that one.
      let accepted: string | null = null;
      for (const file of files) {
        try {
          const answer = await dropFile({
            path: { binder_id: binderId },
            query: { filename: file.name },
            body: file as never,
            bodySerializer: null,
            headers: {
              "Content-Type": file.type || "application/octet-stream",
              "X-Drop-Batch": batch,
              "Idempotency-Key": key(),
            },
          });
          accepted = answer.data?.batch_id ?? accepted;
        } catch (error) {
          const code = refusalOf(error);
          if (code === null) throw error;
          refused.push({ name: file.name, code });
        }
      }
      refresh();
      return { batch: accepted, refused };
    },
  };
}
