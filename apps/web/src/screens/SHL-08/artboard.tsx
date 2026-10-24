// SHL-08's fixture artboards (gallery only; P-03-T07): each scenario drawn on the E5 SourceViewer
// shell (F-05-T47) from the C4 reads, so `/components/screens/SHL-08?st=a–f,h` renders from its
// fixtures. Interim until P-03-T14 builds the EvidenceViewer on its two hosts (drawer and dock),
// with the linked-figure card, the stacked edges, "Also cited" and the auto-highlight toggle.
// Data only through the generated client; page images are the server's masked PNGs (here the
// synthetic ones), read as blobs, never a client file.

import { viewerPage } from "@abacus/api-client";
import { viewerManifestOptions, viewerRegionsOptions } from "@abacus/api-client/query";
import {
  MatchScope,
  type MatchId,
  SourceViewer,
  type ViewerFile,
  contractMatchId,
  useMatchStore,
} from "@abacus/ui";
import { useQueries, useQuery } from "@tanstack/react-query";
import { type JSX, useEffect, useMemo, useState } from "react";
import { OPENS, type Shl08State } from "./scenarios";

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

function Viewer({ state }: { state: Shl08State }): JSX.Element {
  const opens = OPENS[state];
  const store = useMatchStore();
  const manifest = useQuery(viewerManifestOptions({ path: { version_id: opens.versionId } }));
  const regions = useQuery(viewerRegionsOptions({ path: { version_id: opens.versionId } }));
  const pageNos = useMemo(() => (manifest.data?.pages ?? []).map((p) => p.n), [manifest.data]);
  const urls = usePageUrls(opens.versionId, pageNos);
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
  const lit = opens.matchId ?? opens.hovered ?? null;
  useEffect(() => {
    if (lit === null || regions.data === undefined) return;
    store.light(lit as MatchId, null);
  }, [lit, regions.data, store]);
  return (
    <div data-screen="SHL-08" data-state={state} className="flex h-full w-[480px] flex-col">
      <SourceViewer
        file={file}
        variant={opens.host === "dock" ? "evidence" : "full"}
        status={manifest.data?.status ?? "processing"}
        loading={manifest.data === undefined}
        reveal={{
          allowed: manifest.data?.allowed_actions.includes("pii.reveal") ?? false,
          onReveal: () => undefined, // the logged reveal is P-03-T16 and T20
        }}
      />
    </div>
  );
}

/** One SHL-08 artboard on its scenario. */
export function SHL08({ state }: { state: Shl08State }): JSX.Element {
  return (
    <MatchScope>
      <Viewer state={state} />
    </MatchScope>
  );
}
