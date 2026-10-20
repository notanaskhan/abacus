import { Drawer } from "@abacus/ui";
import type { JSX } from "react";
import { EvidencePreview } from "./EvidencePreview";

/** TASK-110 (the plan's SHL-08 source viewer): the document a citation points to, beside the
 * claim, opened at the cited cell or page and highlighted. */
export function SourceDrawer({
  engagementId,
  itemId,
  versionId,
  cell,
  page,
  title,
  onClose,
}: {
  engagementId: string;
  itemId: string;
  versionId: string;
  cell?: string;
  page?: number;
  title: string;
  onClose: () => void;
}): JSX.Element {
  return (
    <Drawer
      open
      width={560}
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={title}
      description={
        cell !== undefined
          ? `The cited cell, ${cell}, is highlighted.`
          : page !== undefined
            ? `Opened at page ${String(page)}.`
            : "The cited document."
      }
    >
      <EvidencePreview
        source={{ kind: "upload", engagementId, itemId, versionId }}
        highlightCell={cell}
        openAtPage={page}
      />
    </Drawer>
  );
}
