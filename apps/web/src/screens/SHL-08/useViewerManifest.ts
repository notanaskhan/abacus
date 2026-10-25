// The SHL-08 data path (P-03-T14; C4 §3.3, §3.4): the manifest, the regions and the server's
// masked page images, through the generated client only. A version still being processed answers
// `status=processing`; the manifest is polled every 3 s until it is not (AC3.4, the legacy
// EvidencePreview pattern). Pages are read as blobs and shown through object URLs that are revoked
// when they change or the viewer closes: never a client file, never a document to parse.

import { type ViewerManifestOut, viewerPage } from "@abacus/api-client";
import { viewerManifestOptions, viewerRegionsOptions } from "@abacus/api-client/query";
import { type ViewerFile, type ViewerStatus, contractMatchId } from "@abacus/ui";
import { useQueries, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

/** AC3.4: a processing manifest is asked again every 3 s. */
export const PROCESSING_POLL_MS = 3000;

export function pollWhileProcessing(data: ViewerManifestOut | undefined): number | false {
  return data?.status === "processing" ? PROCESSING_POLL_MS : false;
}

function usePageUrls(versionId: string, pages: readonly number[]): Record<number, string> {
  const blobs = useQueries({
    queries: pages.map((n) => ({
      queryKey: ["shl08-page", versionId, n],
      gcTime: 0,
      queryFn: async () =>
        (
          await viewerPage({
            path: { version_id: versionId, page_no: n },
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
    // The blobs are re-read only when one more arrives or the version changes.
  }, [count, versionId]);
  return urls;
}

export interface ViewerData {
  manifest: ViewerManifestOut | undefined;
  file: ViewerFile;
  status: ViewerStatus;
  /** The manifest has not answered, or the version is still processing: skeleton pages. */
  loading: boolean;
}

/** One version's viewer data, mapped onto the E5 shell's own shapes. */
export function useViewerData(versionId: string): ViewerData {
  const manifest = useQuery({
    ...viewerManifestOptions({ path: { version_id: versionId } }),
    refetchInterval: (query) => pollWhileProcessing(query.state.data),
  });
  const status = manifest.data?.status ?? "processing";
  const regions = useQuery({
    ...viewerRegionsOptions({ path: { version_id: versionId } }),
    enabled: status === "ready",
  });
  const pageNos = useMemo(
    () => (status === "ready" ? (manifest.data?.pages ?? []).map((p) => p.n) : []),
    [manifest.data, status],
  );
  const urls = usePageUrls(versionId, pageNos);
  const file = useMemo<ViewerFile>(
    () => ({
      name: manifest.data?.file_name ?? "",
      pages: (manifest.data?.pages ?? []).map((p) => ({
        n: p.n,
        width_pt: p.width_pt,
        height_pt: p.height_pt,
        rotation: p.rotation,
        src: urls[p.n] ?? "",
      })),
      regions: (regions.data?.items ?? [])
        .filter((r) => r.page !== null)
        .map((r) => ({
          match: contractMatchId({ match_id: r.match_id, rects: r.rects }),
          page: r.page ?? 1,
          rects: r.rects,
          label: r.label,
          cited: r.citation_id !== null,
        })),
      masks: (manifest.data?.pii_masks ?? []).map((m) => ({
        id: m.id,
        page: m.page,
        rect: m.rect,
        kind: m.kind,
        display: m.display,
      })),
    }),
    [manifest.data, regions.data, urls],
  );
  return {
    manifest: manifest.data,
    file,
    status,
    loading: manifest.data === undefined || status === "processing",
  };
}
