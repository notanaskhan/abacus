// The governing instrument (T-07-T15; TXT-01; SPEC-656 AC-1.1 to AC-5.2): TXT-01's reads and its
// one write the screen starts (the reader run) over the generated client only. The read model is
// the server's: figures, clause labels and the scenario lines arrive composed; the browser never
// sums or composes a figure (INV-2). The reader's text is the masked text projection of the
// instrument's evidence version (`GET /v1/evidence-versions/{v}/text`): no clause text is stored.

import {
  returnRecordOptions,
  instrumentClausesOptions,
  instrumentOptions,
  instrumentReadMutation,
  viewerTextOptions,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export function useInstrument(returnId: string) {
  return useQuery({
    ...instrumentOptions({ path: { return_id: returnId } }),
    retry: false,
    // T-07-T21: while the reader runs, the read model is invalidated over C6 v2 SSE; this poll is
    // the fallback when the stream is down (every 3 s, only while a progress line shows).
    refetchInterval: (q) => (q.state.data?.reader?.progress_label ? 3000 : false),
  });
}

/** The return's record (TAX-02): the trust's name, the tax year and its due date. */
export function useReturnRecord(returnId: string) {
  return useQuery({ ...returnRecordOptions({ path: { return_id: returnId } }), retry: false });
}

export function useInstrumentClauses(instrumentId: string | undefined) {
  return useQuery({
    ...instrumentClausesOptions({ path: { instrument_id: instrumentId ?? "" } }),
    enabled: instrumentId !== undefined,
    retry: false,
  });
}

export function useInstrumentText(versionId: string | undefined) {
  return useQuery({
    ...viewerTextOptions({ path: { version_id: versionId ?? "" } }),
    enabled: versionId !== undefined,
    retry: false,
  });
}

/** "Read instrument": the person starts the reader (202; 409 `consent_required`,
 * `not_segmented`). The read refreshes so the band shows the run's progress. */
export function useReadInstrument(returnId: string) {
  const client = useQueryClient();
  return useMutation({
    ...instrumentReadMutation(),
    onSuccess: () => {
      void client.invalidateQueries({
        queryKey: instrumentOptions({ path: { return_id: returnId } }).queryKey,
      });
    },
  });
}

/** TXT-01's row labels for the seven determination keys (handoff copy). */
export const DETERMINATION_LABELS = {
  grantor_status: "Grantor status",
  trust_type: "Trust type this year",
  fai_definition: "Fiduciary accounting income",
  trustee_fees: "Trustee fees",
  principal_invaded: "Principal invaded in 2025",
  exemption: "Exemption",
  election_65_day: "65-day election (§663(b))",
} as const;

export type ReaderBlock =
  | { kind: "article"; label: string; heading: string }
  | { kind: "clause"; label: string; letter: string; text: string }
  | { kind: "para"; label: string | null; text: string };

const ARTICLE = /^ARTICLE\s+([IVXLC]+)\b[\s.:\-—–]*(.*)$/i;
const CLAUSE = /^\(([a-z])\)\s*(.*)$/;

/** A page's masked text as the legal reader's blocks: article headings, lettered clauses (hanging
 * indent) and paragraphs, each carrying the clause label it belongs to (the same grammar as the
 * server's segmentation, `tax/instruments/segment.py`), so a chip lights its passage. `carry` is
 * the clause the page opens inside (one whose pages run onto it). */
export function readerBlocks(text: string, carry: string | null = null): ReaderBlock[] {
  const out: ReaderBlock[] = [];
  let article: string | null = null;
  // Text before the page's first article continues the clause from the page before (`carry`).
  let current: string | null = carry;
  for (const raw of text.split("\n")) {
    const line = raw.trim();
    if (line === "") continue;
    const a = ARTICLE.exec(line);
    if (a) {
      article = `Art. ${a[1]?.toUpperCase() ?? ""}`;
      current = article;
      out.push({ kind: "article", label: article, heading: line });
      continue;
    }
    const c = article === null ? null : CLAUSE.exec(line);
    if (c && article !== null) {
      current = `${article}(${c[1] ?? ""})`;
      out.push({ kind: "clause", label: current, letter: `(${c[1] ?? ""})`, text: c[2] ?? "" });
      continue;
    }
    out.push({ kind: "para", label: current, text: line });
  }
  return out;
}
