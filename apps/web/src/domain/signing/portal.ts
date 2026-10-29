// POR-06's data (N-02-T26; docs/screens/POR-06.md; C7 `docs/contracts/c7-envelopes.md` §2): the
// signer's envelopes, one envelope's view, its page images and the signer's writes (viewed,
// progress, the ERSD consent, the provider's one-time view, decline and its withdrawal), over the
// generated client. The provider's return is a hint (ADR-041 pattern): after it, the view is read
// again until the server says the signer signed; nothing here concludes "signed" on its own.

import type { PortalEnvelopeView, SignerDeclineIn } from "@abacus/api-client";
import {
  portalConsent,
  portalDecline,
  portalDeclineWithdraw,
  portalPage,
  portalProgress,
  portalSigningSession,
  portalViewed,
} from "@abacus/api-client";
import {
  portalListOptions,
  portalSigningReturnOptions,
  portalViewOptions,
  portalViewQueryKey,
} from "@abacus/api-client/query";
import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

/** While the provider's return waits on the server, the view is read again this often. */
export const RETURN_POLL_MS = 3_000;

export function usePortalEnvelopes() {
  return useQuery({ ...portalListOptions(), retry: false });
}

/** One envelope; after the provider's return (`returned`), read again until the viewer signed. */
export function usePortalEnvelope(envelopeId: string, returned = false) {
  return useQuery({
    ...portalViewOptions({ path: { envelope_id: envelopeId } }),
    retry: false,
    refetchInterval: (query) =>
      returned && (query.state.data as PortalEnvelopeView | undefined)?.row.my_status !== "signed"
        ? RETURN_POLL_MS
        : false,
  });
}

/** The provider sent the signer back: the server's view of the session (never the URL's word). */
export function useSigningReturn(envelopeId: string, sessionId: string | undefined) {
  const queryClient = useQueryClient();
  const answer = useQuery({
    ...portalSigningReturnOptions({
      path: { envelope_id: envelopeId, session_id: sessionId ?? "" },
    }),
    enabled: sessionId !== undefined,
    retry: false,
    staleTime: Infinity,
  });
  useEffect(() => {
    if (answer.data !== undefined) {
      queryClient.setQueryData(
        portalViewQueryKey({ path: { envelope_id: envelopeId } }),
        answer.data,
      );
    }
  }, [answer.data, envelopeId, queryClient]);
  return answer;
}

/** The pages of one document as blob URLs (the page route needs the portal's bearer token, which
 * an `<img>` cannot send), revoked when they change or the screen leaves. */
export function usePageUrls(
  envelopeId: string,
  documentId: string | undefined,
  pageCount: number,
): Readonly<Record<number, string>> {
  const pages = documentId === undefined ? [] : Array.from({ length: pageCount }, (_, i) => i + 1);
  const blobs = useQueries({
    queries: pages.map((n) => ({
      queryKey: ["por06-page", envelopeId, documentId, n],
      gcTime: 0,
      queryFn: async () =>
        (
          await portalPage({
            path: { envelope_id: envelopeId, document_id: documentId ?? "", page_no: n },
            parseAs: "blob",
            throwOnError: true,
          })
        ).data,
    })),
  });
  const [urls, setUrls] = useState<Record<number, string>>({});
  const ready = blobs.map((b) => b.data);
  const count = ready.filter((b) => b !== undefined).length;
  useEffect(() => {
    const made: Record<number, string> = {};
    ready.forEach((blob, i) => {
      const n = pages[i];
      if (blob instanceof Blob && n !== undefined) made[n] = URL.createObjectURL(blob);
    });
    setUrls(made);
    return () => {
      for (const url of Object.values(made)) URL.revokeObjectURL(url);
    };
    // `count` stands for the blobs: a new one arrives, the URLs are made again.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [envelopeId, documentId, count]);
  return urls;
}

/** The signer's writes on one envelope; each answers the fresh view (or row), kept in the cache. */
export function useEnvelopeActions(envelopeId: string) {
  const queryClient = useQueryClient();
  const key = portalViewQueryKey({ path: { envelope_id: envelopeId } });
  const path = { envelope_id: envelopeId };
  const keep = (view: PortalEnvelopeView): PortalEnvelopeView => {
    queryClient.setQueryData(key, view);
    return view;
  };
  return {
    viewed: async (): Promise<void> => {
      await portalViewed({ path, throwOnError: true });
    },
    progress: async (lastPageSeen: number): Promise<void> => {
      await portalProgress({ path, body: { last_page_seen: lastPageSeen }, throwOnError: true });
    },
    /** ERSD accepted for this disclosure version, then the provider's one-time view. */
    consentAndOpen: async (disclosureVersionId: string | null): Promise<void> => {
      if (disclosureVersionId !== null) {
        keep(
          (
            await portalConsent({
              path,
              body: { disclosure_version_id: disclosureVersionId },
              throwOnError: true,
            })
          ).data,
        );
      }
      const session = (await portalSigningSession({ path, throwOnError: true })).data;
      const current = queryClient.getQueryData<PortalEnvelopeView>(key);
      if (current !== undefined) keep({ ...current, signing_session: session });
    },
    decline: async (reason: SignerDeclineIn["reason"], note: string): Promise<void> => {
      keep(
        (
          await portalDecline({
            path,
            body: { reason, note: note === "" ? null : note },
            throwOnError: true,
          })
        ).data,
      );
    },
    withdraw: async (): Promise<void> => {
      keep((await portalDeclineWithdraw({ path, throwOnError: true })).data);
    },
  };
}
