import { Drawer } from "@abacus/ui";
import type { JSX } from "react";
import { EvidencePreview, type Highlight } from "./EvidencePreview";

/** TASK-110 (the plan's SHL-08 source viewer): the document a citation points to, beside the
 * claim, opened at the cited cell or page and highlighted. */
export function SourceDrawer({
  engagementId,
  itemId,
  versionId,
  cell,
  page,
  highlights,
  findText,
  title,
  onClose,
}: {
  engagementId: string;
  // TASK-334: without the request item, the version opens by itself.
  itemId?: string | undefined;
  versionId: string;
  cell?: string | undefined;
  page?: number | undefined;
  highlights?: Highlight[] | undefined;
  findText?: string | undefined;
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
            ? `Opened at page ${String(page)}${(highlights ?? []).length > 0 || findText !== undefined ? "; the line is outlined" : ""}.`
            : "The cited document."
      }
    >
      <EvidencePreview
        source={
          itemId !== undefined
            ? { kind: "upload", engagementId, itemId, versionId }
            : { kind: "version", engagementId, versionId }
        }
        highlightCell={cell}
        openAtPage={page}
        highlights={highlights}
        findText={findText}
      />
    </Drawer>
  );
}
