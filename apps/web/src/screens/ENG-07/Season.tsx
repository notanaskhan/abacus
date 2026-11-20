// ENG-07 on the live client (T-08-T15): the TY's manifest (`GET /v1/seasons/{tax_year}/manifests/
// {id}`), the expanded cohort's rows, approve (a single-use grant, then the execution), withdraw,
// answers to the asks; the running pill follows the manifest's refresh (SSE invalidation).
import {
  seasonAskAnswerMutation,
  seasonCohortApproveMutation,
  seasonCohortRowsOptions,
  seasonManifestOptions,
  seasonManifestQueryKey,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { ENG07, type Eng07View } from "./index";

export function Season({
  taxYear,
  manifestId,
}: {
  taxYear: number;
  manifestId: string;
}): JSX.Element | null {
  const client = useQueryClient();
  const path = { tax_year: taxYear, manifest_id: manifestId };
  const m = useQuery(seasonManifestOptions({ path }));
  const [view, setView] = useState<Eng07View>("cohorts");
  const open = m.data?.cohorts.find(
    (c) => c.display === "review_required" || c.display === "draft",
  );
  const rows = useQuery({
    ...seasonCohortRowsOptions({ path: { cohort_id: open?.cohort_id ?? "" } }),
    enabled: open !== undefined,
  });
  const refresh = (): void => {
    void client.invalidateQueries({ queryKey: seasonManifestQueryKey({ path }) });
  };
  const approve = useMutation({ ...seasonCohortApproveMutation(), onSuccess: refresh });
  const answer = useMutation({ ...seasonAskAnswerMutation(), onSuccess: refresh });
  if (m.data === undefined) return null;
  return (
    <ENG07
      manifest={m.data}
      rows={rows.data?.items ?? []}
      view={view}
      onView={setView}
      {...(open ? { expanded: open.position } : {})}
      onApprove={(cohortId) => {
        const c = m.data.cohorts.find((x) => x.cohort_id === cohortId);
        if (!c) return;
        approve.mutate({
          path: { cohort_id: cohortId },
          body: { rows_hash: c.rows_hash, manifest_version: m.data.version },
          headers: { "Idempotency-Key": `eng07-${crypto.randomUUID()}` },
        });
      }}
      onAnswer={(ask, option) => {
        answer.mutate({
          path: { ask_id: ask.ask_id },
          body: { option },
          headers: { "Idempotency-Key": `eng07-${crypto.randomUUID()}` },
        });
      }}
    />
  );
}
