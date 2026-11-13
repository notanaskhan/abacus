// TXP-11's overlays on the selected cell (T-05-T38 rest; TASK-7635; DEC-4630; handoff TXP-11 a2,
// a3, d): SHL-09's provenance tray for `<sheet>!<cell>` on the return's workbook (a3); the cell's
// citations as SHL-07 states them, each document citation opening SHL-08's source viewer at its
// match (a2, d). Titles, locations, quotes and verification are the server's (INV-2).
import type { CitationV2Out } from "@abacus/api-client";
import { getCitationOptions } from "@abacus/api-client/query";
import { AgentText, Button, Drawer } from "@abacus/ui";
import { useQueries } from "@tanstack/react-query";
import type { JSX } from "react";
import { ProvenanceTray } from "../SHL-09";
import { COPY } from "./copy";

export function ProvenanceDrawer({
  returnId,
  address,
  onClose,
}: {
  returnId: string;
  /** `05!J12`, the field key the server writes the cell under. */
  address: string | null;
  onClose: () => void;
}): JSX.Element {
  return (
    <Drawer
      open={address !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={address ?? COPY.provenance}
      description={COPY.provenance}
      size="sm"
      peek
    >
      {address === null ? null : (
        <ProvenanceTray
          key={address}
          field={{ type: "tax_workbook", id: returnId, fieldKey: address }}
        />
      )}
    </Drawer>
  );
}

/** One citation as a row: title, location, the quote, and the source opener for a document. */
export function CitationRow({
  citation,
  onOpenSource,
}: {
  citation: CitationV2Out;
  onOpenSource?: (citation: CitationV2Out) => void;
}): JSX.Element {
  const document = citation.source.evidence_version_id !== null;
  return (
    <li className="flex flex-col gap-[4px] rounded-tile bg-nested px-[10px] py-[8px]">
      <span className="text-body font-medium text-ink">{citation.title}</span>
      <span className="text-meta text-ink-3">
        {citation.loc}
        {citation.verified ? "" : ` · ${COPY.unverified}`}
      </span>
      {citation.quote === null || citation.quote_state !== "shown" ? null : (
        <AgentText text={citation.quote} className="text-meta text-ink-2" />
      )}
      {document && onOpenSource !== undefined ? (
        <span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              onOpenSource(citation);
            }}
          >
            {COPY.seeSource}
          </Button>
        </span>
      ) : null}
    </li>
  );
}

export function CitationsDrawer({
  address,
  citationIds,
  onClose,
  onOpenSource,
}: {
  address: string | null;
  citationIds: readonly string[];
  onClose: () => void;
  onOpenSource: (citation: CitationV2Out) => void;
}): JSX.Element {
  const found = useQueries({
    queries: citationIds.map((id) => ({
      ...getCitationOptions({ path: { citation_id: id } }),
      enabled: address !== null,
    })),
  });
  const items = found.flatMap((q) => (q.data === undefined ? [] : [q.data]));
  return (
    <Drawer
      open={address !== null}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={address ?? COPY.citations(0)}
      description={COPY.citations(citationIds.length)}
      size="sm"
      peek
    >
      <ul aria-label={COPY.citations(citationIds.length)} className="flex flex-col gap-[8px]">
        {items.map((c) => (
          <CitationRow key={c.id} citation={c} onOpenSource={onOpenSource} />
        ))}
      </ul>
    </Drawer>
  );
}
