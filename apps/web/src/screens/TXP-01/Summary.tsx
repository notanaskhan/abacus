// TXP-01 on the live client (T-05-T59; DEC-4939): the memo, the rail and the opportunities, read
// through the generated client. Adopt (L1) and Approve (L2) open SHL-12 on the memo
// (`preparer_memo`) and sign through the memo's own routes; Edit saves one section as the
// person's (`expected_version`, 409 on a newer version); Regenerate redrafts the memo, or only the
// sections whose figures moved (the Stale banner's).
import {
  entityGeneralInformationOptions,
  entityMemoAdoptMutation,
  entityMemoApproveMutation,
  entityMemoDraftMutation,
  entityMemoOptions,
  entityMemoSectionMutation,
  entityOpportunitiesOptions,
} from "@abacus/api-client/query";
import { signOffLadder } from "@abacus/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useSession } from "../../app-core/session";
import type { SignOffWriter } from "../../domain/review/signoffs";
import { SignOffSheet } from "../SHL-12";
import { TXP01 } from "./index";

export function Summary({ returnId }: { returnId: string }): JSX.Element {
  const path = { return_id: returnId };
  const client = useQueryClient();
  const session = useSession();
  const memo = useQuery(entityMemoOptions({ path }));
  const general = useQuery(entityGeneralInformationOptions({ path }));
  const opportunities = useQuery({
    ...entityOpportunitiesOptions({ path }),
    enabled: memo.data?.status === "approved",
  });
  const refresh = () => void client.invalidateQueries({ queryKey: entityMemoOptions({ path }).queryKey });
  const draft = useMutation({ ...entityMemoDraftMutation(), onSuccess: refresh });
  const section = useMutation({ ...entityMemoSectionMutation(), onSuccess: refresh });
  const adopt = useMutation(entityMemoAdoptMutation());
  const approve = useMutation(entityMemoApproveMutation());
  const [signing, setSigning] = useState<"L1" | "L2" | null>(null);
  const m = memo.data;
  // The memo's own routes record P-04's sign-off and answer its id; the sheet reads it back.
  const writer =
    (level: "L1" | "L2"): SignOffWriter =>
    async (e) => {
      const route = level === "L1" ? adopt : approve;
      const done = await route.mutateAsync({
        path,
        body: { seen_hash: e.target.content_hash },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      });
      const { data: ladder } = await signOffLadder({
        query: { target_type: e.target.target_type, target_id: e.target.target_id },
        throwOnError: true,
      });
      const signed = ladder.levels.find((l) => l.latest?.id === done.sign_off_id)?.latest;
      if (signed == null) throw new Error("sign_off_not_found");
      return signed;
    };
  return (
    <>
      {signing !== null && m?.memo_id ? (
        <SignOffSheet
          target={{ type: "preparer_memo", id: m.memo_id }}
          level={signing}
          open
          onOpenChange={(next) => {
            if (!next) setSigning(null);
          }}
          write={writer(signing)}
          onSigned={refresh}
        />
      ) : null}
      <TXP01
        memo={m}
        general={general.data}
        opportunities={opportunities.data?.items ?? []}
        {...(session.user === null ? {} : { viewerName: session.user.displayName })}
        onAdopt={() => {
          setSigning("L1");
        }}
        onApprove={() => {
          setSigning("L2");
        }}
        onRegenerate={(affectedOnly) => {
          const stale = affectedOnly ? [] : (m?.sections.map((s) => s.key) ?? []);
          draft.mutate({
            path,
            body: { sections: stale },
            headers: { "Idempotency-Key": crypto.randomUUID() },
          });
        }}
        onSaveSection={(key, body) => {
          if (m === undefined) return;
          section.mutate({
            path: { ...path, key },
            body: { body, expected_version: m.version ?? 0 },
            headers: { "Idempotency-Key": crypto.randomUUID() },
          });
        }}
      />
    </>
  );
}
