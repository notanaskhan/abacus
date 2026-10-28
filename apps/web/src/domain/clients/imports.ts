// CLI-06's bulk client import (P-07-T54; docs/contracts/intake-import.md, live since P-07-T52),
// over the generated client only: the upload (the file as the raw body, DEC-374), the import and
// its rows to review, a person's decision on a row, and the run (202; the screen reads the import
// again until it is done). The import's stage and a row's decision are codes; their words are the
// screen's (copy.ts).

import type { ClientImportOut, ClientImportRowOut, RowDecisionIn } from "@abacus/api-client";
import { uploadClientImport } from "@abacus/api-client";
import {
  clientImportRowsOptions,
  decideImportRowMutation,
  getClientImportOptions,
  runClientImportMutation,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type ImportSource = ClientImportOut["source"];
export type ImportStage = ClientImportOut["stage"];
export type RowDecision = RowDecisionIn["decision"];

/** The steps of the bulk import, in order (handoff g: Source · Map fields · Review · Import). */
export const IMPORT_STEPS = ["source", "map", "review", "import"] as const;
export type ImportStep = (typeof IMPORT_STEPS)[number];

/** The step an import's stage opens on. */
export function stepOfStage(stage: ImportStage): ImportStep {
  if (stage === "importing" || stage === "done" || stage === "failed") return "import";
  if (stage === "reviewing") return "review";
  return "map";
}

/** The auto-match threshold (Story 3.2): at or above it a row is merged without a person. */
export const AUTO_MATCH = 0.9;

/** A score as the screen shows it: 0.8438 → 84. */
export function percent(score: number | null | undefined): number | null {
  return score == null ? null : Math.round(score * 100);
}

/** How many records the run applies: every row but the skipped and the undecided (DEC-643: an
 * undecided row is skipped at the run, never merged or created). */
export function toImport(
  counts: ClientImportOut["counts"],
  review: readonly ClientImportRowOut[],
): number {
  const left = review.filter((r) => r.decision == null || r.decision === "skip").length;
  return counts.rows - left;
}

const POLL_MS = 1000;

export function useClientImport(importId: string | null) {
  return useQuery({
    ...getClientImportOptions({ path: { import_id: importId ?? "" } }),
    enabled: importId !== null,
    refetchInterval: (q) => (q.state.data?.stage === "importing" ? POLL_MS : false),
  });
}

export function useImportReview(importId: string | null) {
  return useQuery({
    ...clientImportRowsOptions({
      path: { import_id: importId ?? "" },
      query: { review: true, limit: 200 },
    }),
    enabled: importId !== null,
  });
}

export function useImportWrites() {
  const queryClient = useQueryClient();
  const refresh = (): void => {
    void queryClient.invalidateQueries({
      predicate: (q) => {
        const id = (q.queryKey[0] as { _id?: string } | undefined)?._id;
        return id === "getClientImport" || id === "clientImportRows";
      },
    });
  };
  const decide = useMutation({ ...decideImportRowMutation(), onSuccess: refresh });
  const run = useMutation({ ...runClientImportMutation(), onSuccess: refresh });
  const upload = useMutation({
    mutationFn: async ({ file, source }: { file: File; source: ImportSource }) => {
      const { data } = await uploadClientImport({
        query: { source, filename: file.name },
        body: file as never,
        bodySerializer: null,
        headers: { "Content-Type": file.type || "text/csv" },
        throwOnError: true,
      });
      return data;
    },
  });
  return {
    upload: (file: File, source: ImportSource) => upload.mutateAsync({ file, source }),
    decide: (importId: string, row: ClientImportRowOut, decision: RowDecision) =>
      decide.mutateAsync({
        path: { import_id: importId, row_id: row.id },
        body: {
          decision,
          ...(decision === "merge" && row.best_match_client_id != null
            ? { merge_client_id: row.best_match_client_id }
            : {}),
        },
      }),
    run: (importId: string) =>
      run.mutateAsync({
        path: { import_id: importId },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      }),
    busy: upload.isPending || decide.isPending || run.isPending,
  };
}

/** The reason code of a refused upload (422 `import_file_invalid`), or null. */
export function fileProblem(error: unknown): string | null {
  const e = error as { detail?: unknown; facts?: { reason?: unknown } } | null;
  return e?.detail === "import_file_invalid" && typeof e.facts?.reason === "string"
    ? e.facts.reason
    : null;
}
