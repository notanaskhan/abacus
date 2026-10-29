// FIL-01 Files browser and document drawer (N-01-T16; docs/screens/FIL-01.md; SPEC-380 Stories 7
// and 8; the FIL-01 handoff and revision R2): the T2 tree · list frame (tree 330, list 1036) with
// the O2 drawer (480) on the selected document. Read-only in N-01 (DV-10): no write control is
// drawn; the R2 control row shows the P and R slots and client access as read-only words.
//
// Data comes only through the generated client (`fileTree`, `folderItems`, `drawer`,
// `accessLog`): the tree's counts, the folder's count line and the tie total are the server's
// (N-01-T19); this screen adds nothing up. A metadata-only viewer (DV-11) gets no page count, no
// thumbnail and no reveal. `?node=` names the folder and `?doc=` the document (deep links).
import {
  accessLogOptions,
  drawerOptions,
  fileTreeOptions,
  folderItemsOptions,
} from "@abacus/api-client/query";
import type { DrawerOut, FileRow, ListPageAccessLogRow, TreeNode } from "@abacus/api-client";
import {
  Drawer,
  DrawerCard,
  EmptyState,
  Icon,
  Pill,
  RegistryStatus,
  Skeleton,
  Spinner,
  amount,
  bytes,
  date,
  time,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { type JSX, type ReactNode, useEffect, useState } from "react";
import { to } from "../../routes/to";
import { COPY } from "./copy";

const NOW = Date.parse("2026-09-14T14:24:00Z");

export interface FilesPageProps {
  clientId?: string;
  node: string;
  doc: string | null;
  viewer: string;
  onNode?: (ref: string) => void;
  onDoc?: (id: string | null) => void;
  /** The logged reveal of the masked TIN (P-03's `pii-reveals`); returns the clear value. */
  reveal?: () => Promise<string>;
  /** FIL-01f: open with this value revealed (the gallery's logged reveal). */
  revealedValue?: string | null;
  /** Hold the drawer open in place (the gallery). */
  frame?: boolean;
}

// ---- Tree --------------------------------------------------------------------------------------

function TreeRow({
  node,
  depth,
  selected,
  onSelect,
}: {
  node: TreeNode;
  depth: number;
  selected: string;
  onSelect: (ref: string) => void;
}): JSX.Element {
  const [open, setOpen] = useState(true);
  const label =
    node.kind === "folder" && node.folder_kind !== null
      ? COPY.folders[node.folder_kind]
      : node.label;
  const isSelected = node.ref === selected;
  return (
    <li>
      <button
        type="button"
        data-tree-ref={node.ref}
        {...(isSelected ? { "aria-current": "true" as const } : {})}
        onClick={() => {
          if (node.kind === "folder" || node.kind === "permanent_file") onSelect(node.ref);
          else setOpen(!open);
        }}
        style={{ paddingLeft: 12 + depth * 16 }}
        className={`flex h-[32px] w-full items-center gap-[6px] pr-[12px] text-left text-cell ${
          isSelected ? "bg-sel-bg font-medium text-ink" : "text-ink hover:bg-nav-fill"
        } ${node.kind === "client" ? "font-medium" : ""}`}
      >
        {node.has_children ? (
          <Icon name={open ? "chevron-down" : "chevron-right"} size={12} className="text-ink-3" />
        ) : (
          <span className="w-[12px]" />
        )}
        <Icon name="folder" size={14} className="text-ink-3" />
        <span className="min-w-0 flex-1 truncate">{label}</span>
        {node.locked && <Icon name="lock" size={12} className="text-ink-3" label="Locked" />}
        {node.kind !== "client" && <span className="text-meta text-ink-3">{node.count}</span>}
      </button>
      {open && node.children.length > 0 && (
        <ul>
          {node.children.map((c) => (
            <TreeRow
              key={c.ref}
              node={c}
              depth={depth + 1}
              selected={selected}
              onSelect={onSelect}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

function Tree({
  nodes,
  selected,
  onSelect,
}: {
  nodes: readonly TreeNode[];
  selected: string;
  onSelect: (ref: string) => void;
}): JSX.Element {
  const [open, ...others] = nodes;
  return (
    <nav aria-label="Folders" data-files="tree" className="flex min-h-0 flex-col overflow-y-auto">
      <ul>
        {open !== undefined && (
          <TreeRow node={open} depth={0} selected={selected} onSelect={onSelect} />
        )}
      </ul>
      {others.length > 0 && (
        <>
          <div className="flex h-[31px] items-center bg-band-hd px-[12px] text-section text-ink-2 hairline-y">
            {COPY.otherClients}
          </div>
          <ul>
            {others.map((n) => (
              <li key={n.ref}>
                <span className="flex h-[32px] items-center gap-[6px] px-[12px] text-cell text-ink">
                  <Icon name="chevron-right" size={12} className="text-ink-3" />
                  {n.label}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
    </nav>
  );
}

function findNode(nodes: readonly TreeNode[], ref: string): TreeNode | null {
  for (const n of nodes) {
    if (n.ref === ref) return n;
    const found = findNode(n.children, ref);
    if (found !== null) return found;
  }
  return null;
}

// ---- List --------------------------------------------------------------------------------------

function DocumentRow({
  row,
  selected,
  onOpen,
}: {
  row: FileRow;
  selected: boolean;
  onOpen: (row: FileRow) => void;
}): JSX.Element {
  const struck = row.status === "superseded";
  return (
    <>
      <tr
        data-files="row"
        data-status={row.status}
        aria-selected={selected}
        onClick={() => {
          onOpen(row);
        }}
        className={`min-h-[46px] cursor-pointer hairline-b ${selected ? "bg-sel-bg" : "hover:bg-nav-fill"}`}
      >
        <td className="py-[7px] pl-[12px]">
          <span className="flex items-center gap-[10px]">
            <Icon name="file" size={15} className="flex-none text-ink-3" />
            <span className="flex min-w-0 flex-col">
              <span className={`truncate text-nav text-ink ${struck ? "line-through" : ""}`}>
                {row.display_name}
              </span>
              {row.superseded_by_name !== null && row.superseded_on !== null && (
                <span className="text-cell text-ink-3">
                  {COPY.superseded(row.superseded_by_name, date(row.superseded_on, { now: NOW }))}
                </span>
              )}
            </span>
          </span>
        </td>
        <td className="text-cell text-ink-2">{row.classification_label ?? "—"}</td>
        <td className="text-cell text-ink-2">{row.received_at.slice(0, 4)}</td>
        <td className="text-cell text-ink-2">
          {row.channel === null ? "—" : COPY.channels[row.channel]}
        </td>
        <td>
          <RegistryStatus object="file_document" code={row.status} />
        </td>
        <td className="pr-[12px] text-cell text-ink-2">{row.supports ?? "—"}</td>
      </tr>
      {row.virtual_children.map((c) => (
        <tr key={c.id} data-files="virtual" className="h-[36px] hairline-b">
          <td colSpan={5} className="pl-[46px] text-dense text-ink-2">
            ↳ {c.label}
          </td>
          <td className="pr-[12px] text-right text-dense text-ink">
            {c.amount === null ? "" : amount(c.amount, "whole").text}
          </td>
        </tr>
      ))}
    </>
  );
}

// ---- Drawer ------------------------------------------------------------------------------------

function Row({ label, children }: { label: string; children: ReactNode }): JSX.Element {
  return (
    <div className="flex min-h-[34px] items-center gap-[10px] px-[12px] text-body hairline-b last:border-0">
      <span className="w-[120px] flex-none text-ink-2">{label}</span>
      <span className="min-w-0 flex-1 text-right text-ink">{children}</span>
    </div>
  );
}

function Card({ title, children }: { title: string; children: ReactNode }): JSX.Element {
  return (
    <DrawerCard>
      <h3 className="flex h-[36px] items-center px-[12px] text-body font-medium text-ink hairline-b">
        {title}
      </h3>
      {children}
    </DrawerCard>
  );
}

/** "XX-XXX0287" and the logged reveal for 10 seconds (FIL-01f). The clear value lives only in
 * this component's state: never a query cache, the URL or storage. */
function MaskedTin({
  masked,
  viewer,
  reveal,
  initiallyRevealed,
}: {
  masked: string;
  viewer: string;
  reveal: (() => Promise<string>) | undefined;
  initiallyRevealed: string | null;
}): JSX.Element {
  const [shown, setShown] = useState<string | null>(initiallyRevealed);
  useEffect(() => {
    if (shown === null) return undefined;
    const timer = window.setTimeout(() => {
      setShown(null);
    }, 10_000);
    return () => {
      window.clearTimeout(timer);
    };
  }, [shown]);
  return (
    <span className="flex flex-col items-end gap-[2px]">
      <span className="inline-flex items-center gap-[8px]">
        <span data-files="tin" className="font-mono text-cell">
          {shown ?? masked}
        </span>
        {reveal !== undefined && shown === null && (
          <button
            type="button"
            className="text-cell text-ink-2 underline-offset-2 hover:underline"
            onClick={() => {
              void reveal().then(setShown);
            }}
          >
            {COPY.revealButton}
          </button>
        )}
      </span>
      {shown !== null && <span className="text-meta text-ink-3">{COPY.revealNote(viewer)}</span>}
    </span>
  );
}

function maskedOf(drawer: DrawerOut): string | null {
  const tin = drawer.masked_tin;
  if (tin === null || tin.last4 === undefined || tin.last4 === null) return null;
  return tin.kind === "ein" ? `XX-XXX${tin.last4}` : `XXX-XX-${tin.last4}`;
}

function DocumentDrawer({
  drawer,
  log,
  viewer,
  locked,
  reveal,
  revealed,
  onClose,
  frame,
}: {
  drawer: DrawerOut;
  log: ListPageAccessLogRow | undefined;
  viewer: string;
  locked: boolean;
  reveal: (() => Promise<string>) | undefined;
  revealed: string | null;
  onClose: () => void;
  frame: boolean;
}): JSX.Element {
  const content = drawer.page_count !== null; // ADR-024: content fields only with evidence.read
  const masked = maskedOf(drawer);
  const [p, r] = drawer.sign_off_slots;
  const access = COPY.clientAccessValues[drawer.client_access];
  return (
    <Drawer
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={drawer.display_name}
      width={480}
      peek
      bare
      {...(frame ? { forceState: "open" as const } : {})}
    >
      <div
        data-files="control-row"
        className="flex h-[44px] items-center gap-[8px] bg-card px-[12px] hairline-b"
      >
        {[p, r].map((slot, i) => (
          <span
            key={i === 0 ? "p" : "r"}
            data-files="slot"
            title={
              slot !== undefined && slot.initials !== null && slot.signed_at !== null
                ? `${i === 0 ? "Prepared" : "Reviewed"} by ${slot.initials}`
                : undefined
            }
            className={`inline-flex size-[24px] items-center justify-center rounded-pill text-meta ${
              slot?.initials !== null && slot?.initials !== undefined
                ? "bg-green-tint text-green-ink"
                : "text-ink-3 inset-ring-rule"
            }`}
          >
            {slot?.initials ?? (i === 0 ? COPY.slots.preparer : COPY.slots.reviewer)}
          </span>
        ))}
        {locked && (
          <Pill variant="soon" size="state">
            {COPY.lockedBy(viewer)}
          </Pill>
        )}
        <span className="ml-auto">
          <Pill variant={drawer.client_access === "off" ? "neutral" : "amber"} size="state">
            {COPY.clientAccess(access)}
          </Pill>
        </span>
      </div>
      {drawer.status === "processing" && (
        <DrawerCard>
          <p className="flex items-center gap-[8px] p-[12px] text-body text-ink-2" role="status">
            <Spinner label={COPY.processing} size={15} />
          </p>
          <div className="flex flex-col gap-[6px] px-[12px] pb-[12px]">
            <Skeleton className="h-[12px] w-3/4" />
            <Skeleton className="h-[12px] w-1/2" />
          </div>
        </DrawerCard>
      )}
      <Card title={COPY.drawer.document}>
        {content && <Row label={COPY.drawer.pages}>{drawer.page_count}</Row>}
        <Row label={COPY.drawer.size}>{bytes(drawer.size_bytes)}</Row>
        <Row label={COPY.drawer.sha}>
          <span className="font-mono text-cell">{`${drawer.fingerprint.slice(0, 4)}…${drawer.fingerprint.slice(-4)}`}</span>
        </Row>
        {masked !== null && (
          <Row label={COPY.drawer.borrowerTin}>
            <MaskedTin
              masked={masked}
              viewer={viewer}
              reveal={content ? reveal : undefined}
              initiallyRevealed={content ? revealed : null}
            />
          </Row>
        )}
      </Card>
      {drawer.virtual_children.length > 0 && (
        <Card title={COPY.drawer.virtual}>
          {drawer.virtual_children.map((c) => (
            <Row key={c.id} label={`p. ${String(c.first_page)}–${String(c.last_page)}`}>
              {c.label}
              {c.amount === null ? "" : ` · ${amount(c.amount, "whole").text}`}
            </Row>
          ))}
          {drawer.tie !== null && (
            <div
              data-files="tie"
              className="flex h-[38px] items-center gap-[8px] px-[12px] font-medium"
            >
              <span className="flex-1">
                {amount(drawer.tie.total, "whole").text}
                {drawer.tie.account_number !== null && drawer.tie.ties === true
                  ? ` · ${COPY.tie(drawer.tie.account_number)}`
                  : ""}
              </span>
              {drawer.tie.ties === true && (
                <Pill variant="green-tint" size="micro">
                  {COPY.tiePill}
                </Pill>
              )}
            </div>
          )}
        </Card>
      )}
      {drawer.linked_to.length > 0 && (
        <Card title={COPY.drawer.linkedTo}>
          {drawer.linked_to.map((l) => (
            <Row key={l.route + l.label} label={l.kind.replace("_", " ")}>
              {l.label}
            </Row>
          ))}
        </Card>
      )}
      <Card title={COPY.drawer.versions}>
        {drawer.versions.map((v, i) => (
          <Row key={v.id} label={COPY.drawer.version(v.version_no, i === 0 && !v.superseded)}>
            {date(v.created_at, { now: NOW })}
          </Row>
        ))}
      </Card>
      {log !== undefined && log.items.length > 0 && (
        <Card title={COPY.drawer.accessLog}>
          <ol>
            {log.items.map((e) => (
              <li
                key={e.occurred_at + e.verb}
                className="px-[12px] py-[6px] text-dense text-ink-2"
              >
                {`${date(e.occurred_at, { now: NOW })}, ${time(e.occurred_at)} · ${e.actor_display} ${e.verb}`}
              </li>
            ))}
          </ol>
        </Card>
      )}
      <Card title={COPY.drawer.retention}>
        {drawer.retention.policy_label !== null && (
          <Row label={COPY.drawer.retention}>
            {drawer.retention.eligible_on === null
              ? drawer.retention.policy_label
              : COPY.drawer.eligible(
                  drawer.retention.policy_label,
                  date(drawer.retention.eligible_on, { now: NOW }),
                )}
          </Row>
        )}
        <Row label="Legal hold">{drawer.retention.hold_label ?? COPY.drawer.legalHoldNone}</Row>
      </Card>
    </Drawer>
  );
}

// ---- Page --------------------------------------------------------------------------------------

export function FilesPage({
  clientId,
  node: initialNode,
  doc: initialDoc,
  viewer,
  onNode,
  onDoc,
  reveal,
  revealedValue = null,
  frame = false,
}: FilesPageProps): JSX.Element {
  const [node, setNode] = useState(initialNode);
  const [doc, setDoc] = useState(initialDoc);
  const tree = useQuery(
    fileTreeOptions(clientId === undefined ? {} : { query: { client_id: clientId } }),
  );
  const folder = useQuery(folderItemsOptions({ path: { folder_ref: node } }));
  const drawer = useQuery({
    ...drawerOptions({ path: { item_id: doc ?? "" } }),
    enabled: doc !== null,
  });
  const log = useQuery({
    ...accessLogOptions({ path: { item_id: doc ?? "" } }),
    enabled: doc !== null,
  });
  const nodes = tree.data?.nodes ?? [];
  const current = findNode(nodes, node);
  const client = nodes[0];
  const hold = drawer.data?.retention.hold_placed_by;
  const kind = current?.folder_kind ?? null;
  const select = (ref: string): void => {
    setNode(ref);
    setDoc(null);
    onNode?.(ref);
    onDoc?.(null);
  };
  const open = (row: FileRow): void => {
    setDoc(row.evidence_item_id);
    onDoc?.(row.evidence_item_id);
  };
  return (
    <div data-screen="FIL-01" className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-[42px] items-center gap-[10px] px-[14px]">
        <Link {...to.CLI01()} className="text-nav text-ink-2 hover:text-ink">
          {COPY.allClients}
        </Link>
        <h1 className="mx-auto flex items-center gap-[8px] text-title">
          <span className="font-medium">{COPY.title}</span>
          {client !== undefined && <span className="text-ink-2">{client.label}</span>}
        </h1>
      </div>
      <div className="flex min-h-0 flex-1 gap-[10px] px-[12px] pb-[12px]">
        <section className="flex w-[330px] flex-none flex-col overflow-hidden rounded-pane bg-card shadow-e2">
          {tree.isPending ? (
            <Skeleton className="m-3 h-40" />
          ) : (
            <Tree nodes={nodes} selected={node} onSelect={select} />
          )}
        </section>
        <section
          aria-label={kind === null ? COPY.permanentFile : COPY.folders[kind]}
          className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-pane bg-card shadow-e2"
        >
          <header className="flex h-[46px] items-center justify-center px-[12px] text-title font-medium hairline-b">
            {kind === null ? COPY.permanentFile : COPY.folders[kind]}
          </header>
          {hold !== undefined && hold !== null && drawer.data !== undefined && (
            <div
              data-files="hold"
              role="status"
              className="flex h-[32px] items-center bg-amber-tint px-[12px] text-cell text-amber-ink"
            >
              {`${drawer.data.retention.hold_label ?? ""} · placed by ${hold} ${
                drawer.data.retention.hold_placed_on === null
                  ? ""
                  : date(drawer.data.retention.hold_placed_on, { now: NOW, withYear: true })
              } · destruction suspended`}
            </div>
          )}
          {current?.locked === true && (
            <div className="flex h-[32px] items-center gap-[6px] px-[12px]">
              <Pill variant="soon" size="state">
                {COPY.archiveLocked}
              </Pill>
            </div>
          )}
          {folder.data !== undefined && folder.data.items.length > 0 ? (
            <>
              <div
                data-files="band"
                className="flex h-[32px] items-center gap-[8px] bg-nested px-[12px]"
              >
                <Icon name="folder" size={14} className="text-ink-2" />
                <span className="text-dense font-medium">
                  {kind === null ? COPY.permanentFile : COPY.folders[kind]}
                </span>
                <span data-files="count" className="text-cell text-ink-3">
                  {COPY.listCount(folder.data.documents, folder.data.virtual)}
                </span>
              </div>
              <div className="min-h-0 flex-1 overflow-y-auto">
                <table className="w-full table-fixed">
                  <thead>
                    <tr className="h-[30px] bg-band-hd text-left text-meta font-medium text-ink-2">
                      <th className="pl-[12px]">{COPY.columns.document}</th>
                      <th className="w-[190px]">{COPY.columns.classification}</th>
                      <th className="w-[56px]">{COPY.columns.year}</th>
                      <th className="w-[150px]">{COPY.columns.source}</th>
                      <th className="w-[140px]">{COPY.columns.status}</th>
                      <th className="w-[210px] pr-[12px]">{COPY.columns.linkedTo}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {folder.data.items.map((row) => (
                      <DocumentRow
                        key={row.version_id}
                        row={row}
                        selected={row.evidence_item_id === doc}
                        onOpen={open}
                      />
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : folder.isPending ? (
            <Skeleton className="m-3 h-40" />
          ) : (
            <div className="flex flex-1 items-center justify-center">
              <EmptyState
                title={
                  kind === "signed_authorizations" ? COPY.emptySignedTitle : COPY.emptyFolderTitle
                }
                icon="folder"
              >
                {kind === "signed_authorizations" ? COPY.emptySignedBody : ""}
              </EmptyState>
            </div>
          )}
        </section>
      </div>
      {doc !== null && drawer.data !== undefined && (
        <DocumentDrawer
          drawer={drawer.data}
          log={log.data}
          viewer={viewer}
          locked={client?.locked === true || current?.locked === true}
          reveal={reveal}
          revealed={revealedValue}
          onClose={() => {
            setDoc(null);
            onDoc?.(null);
          }}
          frame={frame}
        />
      )}
    </div>
  );
}
