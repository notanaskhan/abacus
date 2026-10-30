import { type JSX, type ReactNode, useId } from "react";
import { formatActor, isPerson } from "../../attribution/actor";
import { HumanAction } from "../../attribution/human-action";
import { Button } from "../../components/button";
import { Spinner } from "../../components/motion";
import { Skeleton } from "../../components/states";
import { RegistryStatus } from "../../components/status";
import { AppShell } from "../../layout/app-shell";
import { Pane } from "../../layout/pane";
import { SplitLayout } from "../../layout/split-layout";
import type { ToolbarProps } from "../../layout/toolbar";
import { MatchScope } from "../../tracing/match";
import type { MatchStore } from "../../tracing/match-store";
import type { CitationPayload } from "../../tracing/types";
import { StructurePane } from "./StructurePane";
import type { DocumentOnWellCopy, DocumentVM } from "./types";

// T10 DocumentOnWell (F-06-T14; T10 and TPL-10 handoff, Wave 0 Foundations #t10; F-06.md §3 F4,
// §5.2): under the toolbar 46, the record subbar 42 and the tabsbar 50, two panes padded 10 12 12:
// the 470 structure pane and the 896 paper pane, whose header (46) centres the title with Edit,
// Regenerate… and the approval HumanAction at its right, and whose #F8F8F6 well (padding 14)
// centres the 600 paper card (padding 20 24 24, radius 12, e2). A draft stamps the 72 px DRAFT
// watermark at 6 % espresso, hidden from assistive technology.
//
// Every state is data. Drafting (`paper` only, the agent's run): three skeleton paragraphs under
// the header spinner, Regenerate disabled and the approval control disabled, each saying why
// (INV-1: the run is the agent's, the approval a named person's). A `letter` or `email` without
// `modelTextToClients` has no agent Drafting state (ADR P-25 off): it shows the render-in-progress
// line instead. Approve only calls `onApprove`: SHL-12 is P-04's, and the kit writes nothing.
// F-06-T15 fills the paper with DocBlocks; this template takes the paper's body as children.

/** The shell's own height above and below the panes: toolbar, subbar and tabs, padding 10 + 12. */
const CHROME = 46 + 42 + 50 + 22;

export interface DocumentOnWellProps {
  document: DocumentVM;
  copy: DocumentOnWellCopy;
  toolbar: ToolbarProps;
  /** The RecordHeader (subbar 42). */
  record: ReactNode;
  /** The Tabsbar (50). */
  tabs?: ReactNode;
  /** The paper's body (F-06-T15's DocBlocks; a specimen's composed blocks). */
  children?: ReactNode;
  store?: MatchStore<CitationPayload>;
  onApprove?: () => void;
  onEdit?: () => void;
  onRegenerate?: () => void;
  onOpenLink?: (linkId: string) => void;
  onToggleSection?: (id: string, on: boolean) => void;
  onVariable?: (id: string, value: string) => void;
  frame?: boolean;
  embedded?: boolean;
  height?: number;
  className?: string;
}

/** The 72 px diagonal "DRAFT" at 6 % espresso: decoration, hidden from assistive technology. */
export function DraftWatermark({ word }: { word: string }): JSX.Element {
  return (
    <span
      aria-hidden="true"
      data-document="watermark"
      className="pointer-events-none absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 -rotate-[30deg] text-[72px] leading-none font-medium tracking-[0.08em] text-espresso/6 select-none"
    >
      {word}
    </span>
  );
}

/** The 600 paper card on the well. The paper's text is Geist; the document fonts (Arimo and
 * Gelasio, for form faces and letterheads) are the consumer's paper chunk's import of
 * `@abacus/ui/fonts-doc.css` (F-05-T04's split), never the shell's. */
export function PaperCard({
  watermark,
  children,
}: {
  watermark?: string;
  children?: ReactNode;
}): JSX.Element {
  return (
    <article
      data-document="paper"
      className="relative mx-auto w-[600px] flex-none overflow-hidden rounded-pane bg-card px-[24px] pt-[20px] pb-[24px] text-body text-ink shadow-e2"
    >
      {watermark !== undefined && <DraftWatermark word={watermark} />}
      <div className="relative">{children}</div>
    </article>
  );
}

/** Three skeleton paragraphs: a heading bar over three lines, three times (T10a). */
function DraftingSkeleton(): JSX.Element {
  const paragraph = (widths: readonly string[], key: string): JSX.Element => (
    <div key={key} className="flex flex-col gap-[8px]">
      <Skeleton immediate className="h-[11px] w-[38%]" />
      {widths.map((w) => (
        <Skeleton key={w} immediate className={`h-[8px] ${w}`} />
      ))}
    </div>
  );
  return (
    <div data-document="drafting" aria-hidden="true" className="flex flex-col gap-[20px]">
      {paragraph(["w-[92%]", "w-full", "w-[74%]"], "p1")}
      {paragraph(["w-full", "w-[86%]", "w-[62%]"], "p2")}
      {paragraph(["w-full", "w-[92%]", "w-[48%]"], "p3")}
    </div>
  );
}

/** Drafting is the agent's run only on a firm-internal paper, or where P-25 lets model text reach
 * clients; a letter or email otherwise only renders its template. */
export function agentDrafting(document: DocumentVM): boolean {
  return (
    document.status === "drafting" &&
    (document.variant === "paper" || document.modelTextToClients === true)
  );
}

export function DocumentOnWell({
  document,
  copy,
  toolbar,
  record,
  tabs,
  children,
  store,
  onApprove,
  onEdit,
  onRegenerate,
  onOpenLink,
  onToggleSection,
  onVariable,
  frame = false,
  embedded = false,
  height,
  className,
}: DocumentOnWellProps): JSX.Element {
  const busyId = useId();
  const reasonId = useId();
  const lockedId = useId();
  const drafting = document.status === "drafting";
  const agentRun = agentDrafting(document);
  const locked = document.status === "locked";
  const busyLine = agentRun ? copy.drafting : copy.rendering;
  // Why the controls are off, said once and named by each (aria-describedby): the run while
  // drafting, the lock's reason when locked (T10d).
  const blockedBy = drafting
    ? busyId
    : locked && document.lockedReason !== undefined
      ? lockedId
      : undefined;
  const approveReason = document.actions.approve?.disabledReason;
  const readOnlyReason = locked ? document.lockedReason : drafting ? busyLine : undefined;
  const approve = document.actions.approve;

  const right = (
    <>
      {drafting && (
        <span id={busyId}>
          <Spinner label={busyLine} size={10} />
        </span>
      )}
      {document.actions.edit === true && (
        <Button
          variant="secondary"
          size="sm"
          icon="pencil"
          disabled={drafting || locked}
          {...(blockedBy === undefined ? {} : { "aria-describedby": blockedBy })}
          {...(onEdit === undefined ? {} : { onClick: onEdit })}
        >
          {copy.edit}
        </Button>
      )}
      {document.actions.regenerate === true && (
        <Button
          variant="secondary"
          size="sm"
          icon="refresh-cw"
          opensDialog
          disabled={drafting || locked}
          {...(blockedBy === undefined ? {} : { "aria-describedby": blockedBy })}
          {...(onRegenerate === undefined ? {} : { onClick: onRegenerate })}
        >
          {copy.regenerate}
        </Button>
      )}
      {approve !== undefined && document.status !== "approved" && (
        <HumanAction
          verb="Approve"
          {...(approve.object === undefined ? {} : { object: approve.object })}
          actor={approve.actor}
          opensDialog
          variant="primary"
          size="sm"
          icon="check"
          disabled={drafting || locked || approve.disabledReason !== undefined}
          {...(blockedBy !== undefined
            ? { "aria-describedby": blockedBy }
            : approveReason !== undefined
              ? { "aria-describedby": reasonId }
              : {})}
          {...(onApprove === undefined ? {} : { onClick: onApprove })}
        />
      )}
      {approve !== undefined && document.status === "approved" && (
        <Button variant="secondary" size="sm" icon="check" disabled>
          {copy.approved ?? "Approved"}
        </Button>
      )}
      {approveReason !== undefined && (
        <span id={reasonId} className="sr-only">
          {approveReason}
        </span>
      )}
      {locked && document.lockedReason !== undefined && (
        <span id={lockedId} className="sr-only">
          {document.lockedReason}
        </span>
      )}
    </>
  );

  // The header's left: the status pill and its sub-line, when the document says more than its
  // title (TPL-10: "Draft" with "Adopted by Olivia Brandt"; approved; locked). Only a person
  // approves (INV-1), so an approval naming the agent, a policy or the system names no one: no
  // approval ever reads "by Accrued Agent" (INV-5; F-06-T17).
  const approvedBy =
    document.approvedBy !== undefined && isPerson(document.approvedBy.actor)
      ? document.approvedBy
      : undefined;
  const statusLine =
    document.adoptedBy !== undefined ||
    approvedBy !== undefined ||
    document.lockedReason !== undefined ? (
      <span data-document="status" className="flex min-w-0 items-center gap-[8px] pl-[6px]">
        <RegistryStatus object="generated_document" code={document.status} withDisc={false} />
        <span className="truncate text-meta text-ink-3">
          {approvedBy !== undefined
            ? `${formatActor(approvedBy.actor)} · ${approvedBy.when}`
            : (document.lockedReason ??
              (document.adoptedBy === undefined ? "" : document.adoptedBy))}
        </span>
      </span>
    ) : undefined;

  const panes = [
    <Pane
      key="structure"
      width={470}
      header={false}
      {...(document.structure.kind === "kv" ? { scrollLabel: "Structure" } : {})}
    >
      <StructurePane
        structure={document.structure}
        variablesTitle={copy.variables}
        {...(readOnlyReason === undefined ? {} : { readOnlyReason })}
        {...(onOpenLink === undefined ? {} : { onOpenLink })}
        {...(onToggleSection === undefined ? {} : { onToggleSection })}
        {...(onVariable === undefined ? {} : { onVariable })}
      />
    </Pane>,
    <Pane
      key="paper"
      title={document.title}
      titleAlign="center"
      well
      {...(statusLine === undefined ? {} : { left: statusLine })}
      right={right}
    >
      <div
        data-document-variant={document.variant}
        aria-busy={drafting ? true : undefined}
        className="flex min-h-full flex-col p-[14px]"
      >
        <PaperCard {...(document.watermark && !drafting ? { watermark: copy.watermark } : {})}>
          {drafting ? <DraftingSkeleton /> : children}
        </PaperCard>
      </div>
    </Pane>,
  ];

  return (
    <AppShell
      toolbar={toolbar}
      frame={frame}
      embedded={embedded}
      {...(height === undefined ? {} : { height })}
      {...(className === undefined ? {} : { className })}
      record={record}
      {...(tabs === undefined ? {} : { tabs })}
    >
      <MatchScope {...(store === undefined ? {} : { store })}>
        <div
          data-template="t10"
          data-status={document.status}
          className="flex min-h-0 min-w-0 flex-1"
        >
          <SplitLayout
            preset="document"
            height={height === undefined ? "viewport" : height - CHROME}
            narrow={false}
            className="w-full bg-transparent p-0"
          >
            {panes}
          </SplitLayout>
        </div>
      </MatchScope>
    </AppShell>
  );
}
