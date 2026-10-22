import type { RequestItemOut } from "@abacus/api-client";
import { listRequestItemsQueryKey, setDocumentKindMutation } from "@abacus/api-client/query";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { JSX } from "react";
import { errorMessage } from "../api";

// SPEC-029 AC-5 (TASK-057 D3): what the request expects decides which checks run.
const OPTIONS: [string, string][] = [
  ["bank_statement", "Bank statement"],
  ["ar_aging", "AR aging"],
  ["ap_aging", "AP aging"],
  ["schedule", "Schedule"],
  ["none", "No particular document"],
  ["rules", "Use the rules"],
];

function current(item: RequestItemOut): string {
  if (item.document_kind_source !== "override") return "rules";
  return item.document_kind ?? "none";
}

/** For partner, manager and senior: set what the item expects; checks run again. */
export function DocumentKindSelect({
  engagementId,
  item,
}: {
  engagementId: string;
  item: RequestItemOut;
}): JSX.Element {
  const queryClient = useQueryClient();
  const save = useMutation({
    ...setDocumentKindMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: listRequestItemsQueryKey({ path: { engagement_id: engagementId } }),
      });
    },
  });
  const ruled =
    item.document_kind_source === "rule" && item.document_kind != null
      ? ` (${OPTIONS.find(([v]) => v === item.document_kind)?.[1] ?? item.document_kind})`
      : "";
  return (
    <label className="flex items-center gap-2 text-meta text-ink-3">
      Expects
      <select
        className="rounded-[var(--radius-control)] border border-hair bg-surface px-2 py-1 text-body text-ink"
        value={current(item)}
        disabled={save.isPending}
        onChange={(event) => {
          const value = event.target.value;
          save.mutate({
            path: { engagement_id: engagementId, item_id: item.id },
            body:
              value === "rules"
                ? { clear: true }
                : {
                    document_kind:
                      value === "none"
                        ? null
                        : (value as NonNullable<RequestItemOut["document_kind"]>),
                  },
          });
        }}
      >
        {OPTIONS.map(([value, text]) => (
          <option key={value} value={value}>
            {value === "rules" ? `${text}${ruled}` : text}
          </option>
        ))}
      </select>
      {save.isError && <span className="text-danger">{errorMessage(save.error)}</span>}
    </label>
  );
}
