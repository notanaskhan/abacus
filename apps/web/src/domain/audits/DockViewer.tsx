import { viewerPage } from "@abacus/api-client";
import {
  viewerManifestOptions,
  viewerRegionsOptions,
  viewerTextOptions,
} from "@abacus/api-client/query";
import {
  EmptyState,
  MatchScope,
  SourceViewer,
  type ViewerFile,
  contractMatchId,
} from "@abacus/ui";
import { useQueries, useQuery } from "@tanstack/react-query";
import { type JSX, useEffect, useMemo, useState } from "react";
import { AUDIT_MESSAGES } from "./messages";
import { MaskedTextView } from "../../app-core/masked-text";

// The cockpit dock's Viewer tab (A-01-T12; AUD-02, DV-2): SHL-08's evidence variant on the C4
// reads (`?doc=<evidenceVersionId>`), the server's masked page images read as blobs, never a
// client file. P-03-T14's EvidenceViewer replaces the body when it lands; the host stays. A reader
// the manifest gives the `text` view (DEC-369) gets the masked text instead of page images.

function usePageUrls(versionId: string, pages: readonly number[]): Record<number, string> {
  const blobs = useQueries({
    queries: pages.map((n) => ({
      queryKey: ["audit-dock-page", versionId, n],
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
  }, [ready.filter((b) => b !== undefined).length, versionId]);
  return urls;
}

function Viewer({ versionId }: { versionId: string }): JSX.Element {
  const manifest = useQuery({
    ...viewerManifestOptions({ path: { version_id: versionId } }),
    retry: false,
  });
  // DEC-369: the server decides the view; a text view never asks for a page image or a region.
  const textView = manifest.data?.view === "text";
  const regions = useQuery({
    ...viewerRegionsOptions({ path: { version_id: versionId } }),
    retry: false,
    enabled: manifest.data !== undefined && !textView,
  });
  const text = useQuery({
    ...viewerTextOptions({ path: { version_id: versionId } }),
    retry: false,
    enabled: textView && manifest.data?.status === "ready",
  });
  const pageNos = useMemo(
    () => (textView ? [] : (manifest.data?.pages ?? []).map((p) => p.n)),
    [manifest.data, textView],
  );
  const urls = usePageUrls(versionId, pageNos);
  if (manifest.isError) {
    return <EmptyState icon="file" title={AUDIT_MESSAGES.viewer.unavailable} />;
  }
  if (textView) {
    return <MaskedTextView text={text.data} width={296} />;
  }
  const file: ViewerFile = {
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
      })),
    masks: (manifest.data?.pii_masks ?? []).map((m) => ({
      id: m.id,
      page: m.page,
      rect: m.rect,
      kind: m.kind,
      display: m.display,
    })),
  };
  return (
    <SourceViewer
      file={file}
      variant="evidence"
      status={manifest.data?.status ?? "processing"}
      loading={manifest.data === undefined}
      reveal={{
        allowed: manifest.data?.allowed_actions.includes("pii.reveal") ?? false,
        onReveal: () => undefined, // the logged reveal is P-03-T16's
      }}
    />
  );
}

/** The Viewer tab's body: the open document, or a prompt to pick one. */
export function DockViewer({ versionId }: { versionId: string | null }): JSX.Element {
  if (versionId === null) {
    return <EmptyState icon="file" title={AUDIT_MESSAGES.viewer.none} />;
  }
  return (
    <div data-audit-viewer={versionId} className="flex min-h-0 flex-1 flex-col">
      <MatchScope>
        <Viewer key={versionId} versionId={versionId} />
      </MatchScope>
    </div>
  );
}
