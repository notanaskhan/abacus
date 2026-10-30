// SIG-02's reads and writes over the generated client (N-02-T21; docs/contracts/c7-envelopes.md):
// one envelope, the firm's signing policies, the server's code-computed checks, the masked page
// images the preview draws, and the person's Save draft (PUT with If-Match), Send and Undo. Send
// is a person's click only (INV-1): the agent may draft an envelope, never send it.

import { envelopePage } from "@abacus/api-client";
import type { DraftUpdateIn, EnvelopeOut, EnvelopePolicyOut } from "@abacus/api-client";
import {
  getEnvelopeOptions,
  getEnvelopeQueryKey,
  listEnvelopePoliciesOptions,
  sendEnvelopeMutation,
  undoEnvelopeSendMutation,
  updateEnvelopeDraftMutation,
  validateEnvelopeMutation,
} from "@abacus/api-client/query";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

export type IdentityMethod = EnvelopeOut["signers"][number]["identity_method"];
export type PolicyFamily = EnvelopeOut["policy_family"];

/** Every identity method C7 knows, in the picker's order. There is no SMS-only method: the email
 * code is the one an e-file authorization may never use (SPEC-381 AC-8). */
export const IDENTITY_METHODS: readonly IdentityMethod[] = [
  "kba",
  "email_code",
  "in_person_id",
  "firm_sso",
];

export function useEnvelope(envelopeId: string) {
  return useQuery(getEnvelopeOptions({ path: { envelope_id: envelopeId } }));
}

export function usePolicy(family: PolicyFamily | undefined): EnvelopePolicyOut | undefined {
  const policies = useQuery(listEnvelopePoliciesOptions());
  return policies.data?.find((p) => p.policy_family === family);
}

/** The server's checks for this version; re-asked whenever the saved version changes. */
export function useChecks(envelopeId: string, version: number | undefined) {
  const validate = useMutation(validateEnvelopeMutation());
  const { mutate } = validate;
  useEffect(() => {
    if (version !== undefined) mutate({ path: { envelope_id: envelopeId } });
  }, [envelopeId, version, mutate]);
  return validate;
}

/** The preview's page images: the server's masked render, read as blobs (never the source file). */
export function usePageUrls(
  envelopeId: string,
  documentId: string | null,
  pages: number,
): Record<number, string> {
  const numbers = documentId === null ? [] : Array.from({ length: pages }, (_, i) => i + 1);
  const blobs = useQueries({
    queries: numbers.map((n) => ({
      queryKey: ["envelope-page", envelopeId, documentId, n],
      gcTime: 0,
      queryFn: async () =>
        (
          await envelopePage({
            path: { envelope_id: envelopeId, document_id: documentId ?? "", page_no: n },
            parseAs: "blob",
            throwOnError: true,
          })
        ).data,
    })),
  });
  const [urls, setUrls] = useState<Record<number, string>>({});
  const ready = blobs.filter((b) => b.data !== undefined).length;
  useEffect(() => {
    const made: Record<number, string> = {};
    blobs.forEach((b, i) => {
      const n = numbers[i];
      if (b.data instanceof Blob && n !== undefined) made[n] = URL.createObjectURL(b.data);
    });
    setUrls(made);
    return () => {
      for (const url of Object.values(made)) URL.revokeObjectURL(url);
    };
    // Re-made when another page arrives or the document changes.
  }, [ready, envelopeId, documentId]);
  return urls;
}

export interface EnvelopeWrites {
  save: (body: DraftUpdateIn) => Promise<EnvelopeOut>;
  send: () => Promise<unknown>;
  undoSend: () => Promise<unknown>;
}

export function useEnvelopeWrites(envelope: EnvelopeOut | undefined): EnvelopeWrites {
  const queryClient = useQueryClient();
  const id = envelope?.row.id ?? "";
  const at = { path: { envelope_id: id } };
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: getEnvelopeQueryKey(at) });
  };
  const save = useMutation({ ...updateEnvelopeDraftMutation(), onSuccess: refresh });
  const send = useMutation(sendEnvelopeMutation());
  const undo = useMutation({ ...undoEnvelopeSendMutation(), onSuccess: refresh });
  const key = (): string => globalThis.crypto.randomUUID();
  return {
    save: (body) =>
      save.mutateAsync({ ...at, body, headers: { "If-Match": String(envelope?.version ?? 0) } }),
    send: () => send.mutateAsync({ ...at, headers: { "Idempotency-Key": key() } }),
    undoSend: () => undo.mutateAsync({ ...at, headers: { "Idempotency-Key": key() } }),
  };
}
