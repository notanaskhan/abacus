import { viewerPage } from "@abacus/api-client";
import {
  viewerManifestOptions,
  viewerRegionsOptions,
  viewerTextOptions,
} from "@abacus/api-client/query";
import {
  EmptyState,
  type MatchId,
  MatchScope,
  SourceViewer,
  type ViewerFile,
  contractMatchId,
  useMatchStore,
} from "@abacus/ui";
import { useQueries, useQuery } from "@tanstack/react-query";
import { type JSX, type ReactNode, useEffect, useMemo, useState } from "react";
import { AUDIT_MESSAGES } from "./messages";
import { RevealStepUp, useLoggedReveal } from "./reveal";
import { MaskedTextView } from "../../app-core/masked-text";

// The cockpit dock's Viewer tab (A-01-T12; AUD-02, DV-2): SHL-08's evidence variant on the C4
// reads (`?doc=<evidenceVersionId>`), the server's masked page images read as blobs, never a
// client file. P-03-T14's EvidenceViewer replaces the body when it lands; the host stays. A reader
// the manifest gives the `text` view (DEC-369) gets the masked text instead of page images.
// AUD-03 (A-01-T15) widens it to the 490 viewer: a slot above the well (the decision strip and
// the ScreeningCard), a verified citation's region lit on open (INV-2) and the logged reveal
// (P-03-T16; "Reveal (logged)" only when the manifest grants `pii.reveal`).

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

export interface DockViewerOptions {
  /** Drawn above the well (AUD-03: the Accept / Return strip and the ScreeningCard). */
  above?: ReactNode;
  /** A verified citation's match to light on open (AUD-03 b). */
  lit?: string | null;
  /** The page's width at 100% (the kit's default in the 330 dock; AUD-03's 490 viewer is wider). */
  pageWidth?: number;
}

function Lit({ match, ready }: { match: string; ready: boolean }): null {
  const store = useMatchStore();
  useEffect(() => {
    if (ready) store.light(match as MatchId, null);
  }, [match, ready, store]);
  return null;
}

function Viewer({
  versionId,
  above,
  lit,
  pageWidth,
}: { versionId: string } & DockViewerOptions): JSX.Element {
  const reveal = useLoggedReveal(versionId);
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
    return (
      <div className="flex min-h-0 flex-1 flex-col overflow-auto">
        {above}
        <MaskedTextView text={text.data} width={pageWidth ?? 296} />
      </div>
    );
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
    <>
      {lit != null && <Lit match={lit} ready={file.regions.length > 0} />}
      <SourceViewer
        file={file}
        variant="evidence"
        status={manifest.data?.status ?? "processing"}
        loading={manifest.data === undefined}
        {...(pageWidth === undefined ? {} : { pageWidth })}
        {...(above === undefined ? {} : { aboveWell: above })}
        reveal={{
          allowed: manifest.data?.allowed_actions.includes("pii.reveal") ?? false,
          onReveal: reveal.onReveal,
          revealed: reveal.revealed,
        }}
      />
      <RevealStepUp open={reveal.stepUp} onOpenChange={reveal.setStepUp} />
    </>
  );
}

/** The Viewer tab's body: the open document, or a prompt to pick one. */
export function DockViewer({
  versionId,
  ...options
}: { versionId: string | null } & DockViewerOptions): JSX.Element {
  if (versionId === null) {
    return <EmptyState icon="file" title={AUDIT_MESSAGES.viewer.none} />;
  }
  return (
    <div data-audit-viewer={versionId} className="flex min-h-0 flex-1 flex-col">
      <MatchScope>
        <Viewer key={versionId} versionId={versionId} {...options} />
      </MatchScope>
    </div>
  );
}
