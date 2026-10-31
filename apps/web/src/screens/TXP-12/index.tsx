import type { K1PackageOut, K1RelatedReturnOut, TaxReturnRowOut } from "@abacus/api-client";
import {
  acceptDetailsChangeMutation,
  detailsChangesOptions,
  k1PackageOptions,
  k1ReleaseCheckOptions,
  listContactsOptions,
  listK1PackagesOptions,
  listReturnsOptions,
  rejectDetailsChangeMutation,
  releaseK1Mutation,
  resendK1Mutation,
  returnRecordOptions,
  shareK1Mutation,
  undoK1ReleaseMutation,
} from "@abacus/api-client/query";
import {
  Button,
  Checkbox,
  Dialog,
  Icon,
  type IndexColumn,
  IndexList,
  type IndexTile,
  type ListEnvelope,
  RadioGroup,
  RecordHeader,
  RegistryStatus,
  Tag,
  Tooltip,
  type ViewState,
  amount,
  date as formatDate,
  einMask,
  period as formatPeriod,
  ssnMask,
  status,
  time as formatTime,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useId, useState } from "react";
import { nowMs, useNow } from "../../app-core/clock";
import { COPY, FAILING } from "./copy";

// TXP-12 · K-1 package (T-02-T25; docs/screens/TXP-12.md) on T1's IndexList, over T-02-T20's and
// T21's routes. Every artboard is a data condition or a person's interaction:
//
//   A  drafts; Release disabled with a Lock naming every failing check
//   A2 a row expanded (boxes, state lines, documents; the masked TIN from the detail, ADR-031)
//   A3 the K-3 tooltip      A4 Share draft internally…      A5 Release K-1s… (after approval)
//   B  released (Viewed, Downloaded, Bounced; finals replaced the shared drafts)
//   B2 Resend… on the bounced row      C 1120-S (?return=)      D 1041      E superseded
//   F  no K-1 set imported yet
//
// Release is a person's act: a single-use grant held ten seconds for Undo (T-02-T21), then the
// workflow delivers. The agent holds none of these controls. The Recipient, Status and Delivery
// chips, the tiles and the search narrow the few rows of one return in the browser; the server
// sends every row and its counts.

const TILE_ORDER = [
  "not_prepared",
  "draft",
  "released",
  "viewed",
  "downloaded",
  "bounced",
] as const;
const TILE_VARIANTS: Readonly<
  Record<(typeof TILE_ORDER)[number], NonNullable<IndexTile["variant"]>>
> = {
  not_prepared: "neutral",
  draft: "amber",
  released: "green-tint",
  viewed: "green-tint",
  downloaded: "green-tint",
  bounced: "red-tint",
};
const TILES: readonly IndexTile[] = TILE_ORDER.map((code) => ({
  code,
  label: COPY.tiles[code],
  variant: TILE_VARIANTS[code],
}));
const RELEASED = new Set(["released", "viewed", "downloaded", "bounced"]);
const ISSUING = ["1065", "1120s", "1041"] as const;
const SHARE = "k1_package.share_internal";
const RESEND = "k1_package.resend";
const REVIEW = "k1_recipient.review_details";

export interface Txp12Opening {
  /** A recipient whose row opens expanded (A2). */
  expand?: string;
  /** The K-3 tooltip held open (A3). */
  tooltip?: boolean;
  dialog?: "share" | "release" | "resend";
  /** The recipient Resend… opens for (B2). */
  resendFor?: string;
}

export interface TXP12Props {
  returnId: string;
  /** The Return chip switches the issuing return (`?return=`). */
  onReturn?: (returnId: string) => void;
  /** The back chip: the return's overview (TAX-02). */
  onBack?: () => void;
  opening?: Txp12Opening;
}

function short(name: string): string {
  return name.split(" ").at(-1) ?? name;
}

function targets(names: readonly string[]): string {
  const unique = [...new Set(names)];
  if (unique.length === 0) return "";
  const head =
    unique.length === 1
      ? unique[0]
      : `${unique.slice(0, -1).join(", ")} and ${unique.at(-1) ?? ""}`;
  return `${head ?? ""} 1040${unique.length === 1 ? "" : "s"}`;
}

function signerOf(row: TaxReturnRowOut | undefined): string {
  return row?.signer?.name ?? "the signing partner";
}

export function TXP12({ returnId, onReturn, onBack, opening = {} }: TXP12Props): JSX.Element {
  const now = useNow();
  const queryClient = useQueryClient();
  const k3TipId = useId();
  const lockId = useId();
  const record = useQuery(returnRecordOptions({ path: { return_id: returnId } }));
  const list = useQuery(listK1PackagesOptions({ path: { return_id: returnId } }));
  const check = useQuery(k1ReleaseCheckOptions({ path: { return_id: returnId } }));
  const issuing = useQuery(
    listReturnsOptions({ query: { tax_year: 2025, form: [...ISSUING], sort: "client" } }),
  );
  const [expanded, setExpanded] = useState<string | null>(null);
  const [tile, setTile] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [recipient, setRecipient] = useState<string | null>(null);
  const [statusChip, setStatusChip] = useState<string | null>(null);
  const [dialog, setDialog] = useState<Txp12Opening["dialog"] | "details" | null>(
    opening.dialog ?? null,
  );
  const [target, setTarget] = useState<K1PackageOut | null>(null);
  const [chosen, setChosen] = useState<ReadonlySet<string> | null>(null);
  const [contact, setContact] = useState<string | undefined>(undefined);
  const share = useMutation(shareK1Mutation());
  const release = useMutation(releaseK1Mutation());
  const undo = useMutation(undoK1ReleaseMutation());
  const resend = useMutation(resendK1Mutation());
  const accept = useMutation(acceptDetailsChangeMutation());
  const reject = useMutation(rejectDetailsChangeMutation());

  const rows = list.data?.items ?? [];
  const row = record.data?.row;
  const opened = rows.find((r) => r.recipient_name === opening.expand)?.id ?? null;
  const open = expanded ?? (opening.expand !== undefined ? opened : null);
  const resendRow =
    target ??
    rows.find((r) => r.recipient_name === opening.resendFor && r.status === "bounced") ??
    null;
  const refresh = (): void => {
    void queryClient.invalidateQueries();
  };

  const visibleRows = rows.filter(
    (r) =>
      (tile === null || r.status === tile) &&
      (statusChip === null || r.status === statusChip) &&
      (recipient === null || r.recipient_name === recipient) &&
      (query === "" || r.recipient_name.toLowerCase().includes(query.toLowerCase())),
  );
  const envelope: ListEnvelope<K1PackageOut> | undefined =
    list.data === undefined
      ? undefined
      : {
          items: visibleRows,
          next_cursor: null,
          total: visibleRows.length,
          counts: list.data.counts ?? {},
        };
  const viewState: ViewState = list.isPending
    ? { kind: "loading" }
    : list.isError
      ? {
          kind: "error",
          retry: () => {
            void list.refetch();
          },
        }
      : rows.length === 0
        ? { kind: "empty" }
        : { kind: "ready" };

  const drafts = rows.filter((r) => r.status === "draft");
  const released = rows.filter((r) => RELEASED.has(r.status));
  const sharedDrafts = drafts.filter((r) =>
    (r.handoffs ?? []).some((h) => h.status === "draft_shared"),
  );
  const sharedNames = sharedDrafts.flatMap((r) =>
    (r.handoffs ?? []).filter((h) => h.target_form !== null).map((h) => short(h.target_name)),
  );
  const failing = check.data?.failing ?? [];
  const eligible = check.data?.eligible === true;
  const named = failing.map((code) =>
    code === "not_final_approved" ? COPY.finalApprovalBy(signerOf(row)) : (FAILING[code] ?? code),
  );
  const firstRelease = released
    .map((r) => r.released_at)
    .filter((at): at is string => at !== null)
    .sort()[0];
  const bounced = rows.filter((r) => r.status === "bounced").length;
  const summary =
    rows.length === 0
      ? undefined
      : firstRelease !== undefined && drafts.length === 0
        ? COPY.releasedSummary(
            `${formatDate(firstRelease, { now })}, ${formatTime(firstRelease)}`,
            bounced,
          )
        : eligible
          ? COPY.readySummary
          : COPY.releaseBlocked(named.join(" · "));
  const lockReason =
    failing.length === 1 && failing[0] === "not_final_approved"
      ? COPY.requiresApproval(signerOf(row))
      : COPY.requires(named.join(", "));

  // A3: why every partner gets a K-3 (DV-9), on the column header's info trigger.
  const k3Tip = rows.some((r) => r.k3_status === "included") ? (
    <Tooltip
      content={COPY.k3Tip}
      {...(opening.tooltip === true ? { forceState: "open" as const } : {})}
    >
      <button
        type="button"
        aria-label={COPY.k3Info}
        aria-describedby={k3TipId}
        className="inline-flex size-[16px] items-center justify-center rounded-pill text-ink-3"
      >
        <Icon name="info" size={12} />
        <span id={k3TipId} className="sr-only">
          {COPY.k3Tip}
        </span>
      </button>
    </Tooltip>
  ) : null;

  // --- columns ---------------------------------------------------------------------------------
  const k3Cell = (r: K1PackageOut): JSX.Element => {
    if (r.k3_status === "not_required")
      return <span className="text-ink-2">{COPY.k3NotRequired}</span>;
    if (r.k3_status === "not_included") return <span className="text-ink-4">—</span>;
    const draft = (r.documents ?? []).some((d) => d.kind === "k3" && d.is_draft);
    return (
      <span className="inline-flex items-center gap-[4px] text-dense text-ink-2">
        <Icon name="check" size={12} className="text-ink-3" />
        {draft ? COPY.k3Draft : COPY.k3}
      </span>
    );
  };
  const tick = (r: K1PackageOut, kind: "k1" | "letter"): JSX.Element => {
    const doc = (r.documents ?? []).find((d) => d.kind === kind);
    if (doc === undefined) return <span className="text-ink-4">—</span>;
    return (
      <Icon
        name="check"
        size={13}
        className={doc.is_draft ? "text-ink-3" : "text-green-ink"}
        aria-label={kind === "k1" ? COPY.columns.k1 : COPY.columns.letter}
      />
    );
  };
  const statusCell = (r: K1PackageOut): JSX.Element => (
    <span className="flex min-w-0 flex-col items-start gap-[2px]">
      <span className={r.status === "superseded" ? "line-through" : undefined}>
        <RegistryStatus
          object="k1_package"
          code={r.status}
          {...(r.released_at === null
            ? {}
            : { vars: { date: formatDate(r.released_at, { now }) } })}
        />
      </span>
      {r.status === "bounced" && (
        <span className="text-meta whitespace-normal text-red-ink">{COPY.bounced}</span>
      )}
      {r.details_change != null && (
        <span className="text-meta text-ink-3">
          {COPY.detailsChange(
            r.details_change.kind,
            formatDate(r.details_change.submitted_at, { now }),
          )}
        </span>
      )}
    </span>
  );
  const handoffCell = (r: K1PackageOut): JSX.Element => {
    const h = (r.handoffs ?? [])[0];
    if (h === undefined) return <span className="text-ink-4">—</span>;
    const name = COPY.handoffTarget(h.target_name, h.target_form ?? null);
    const replaced = h.status === "final_replaced";
    return (
      <span
        className={`inline-flex min-w-0 items-center gap-[4px] ${replaced ? "text-green-ink" : "text-ink"}`}
      >
        <Icon name="arrow-right" size={12} className="flex-none text-ink-3" />
        <span className="truncate">
          {replaced
            ? COPY.handoffReplaced(name)
            : COPY.handoffShared(name, formatDate(h.shared_at, { now }))}
        </span>
      </span>
    );
  };
  const rowActions = (r: K1PackageOut): JSX.Element | null => {
    if (r.status === "bounced" && r.allowed_actions.includes(RESEND)) {
      return (
        <Button
          size="sm"
          variant="secondary"
          aria-haspopup="dialog"
          onClick={(e) => {
            e.stopPropagation();
            setTarget(r);
            setDialog("resend");
          }}
        >
          {COPY.resend}
        </Button>
      );
    }
    if (r.details_change != null && r.allowed_actions.includes(REVIEW)) {
      return (
        <Button
          size="sm"
          variant="secondary"
          aria-haspopup="dialog"
          onClick={(e) => {
            e.stopPropagation();
            setTarget(r);
            setDialog("details");
          }}
        >
          {COPY.reviewDetails}
        </Button>
      );
    }
    return null;
  };

  const columns: IndexColumn<K1PackageOut>[] = [
    {
      key: "expand",
      header: COPY.columns.expand,
      width: 32,
      cell: (r) => {
        const isOpen = open === r.id;
        return (
          <button
            type="button"
            aria-expanded={isOpen}
            aria-controls={`k1-row-${r.id}`}
            aria-label={
              isOpen ? COPY.collapseRow(r.recipient_name) : COPY.expandRow(r.recipient_name)
            }
            onClick={(e) => {
              e.stopPropagation();
              setExpanded(isOpen ? "" : r.id);
            }}
            className="flex size-[22px] items-center justify-center rounded-pill text-ink-3 hover:bg-nested"
          >
            <Icon name={isOpen ? "chevron-down" : "chevron-right"} size={12} />
          </button>
        );
      },
    },
    {
      key: "recipient",
      header: COPY.columns.recipient,
      width: 230,
      cell: (r) => (
        <span className="flex min-w-0 flex-col">
          <span
            className={`truncate font-medium text-ink ${r.status === "superseded" ? "line-through" : ""}`}
          >
            {r.recipient_name}
          </span>
          {(r.ownership_note ?? r.locality) != null && (
            <span className="truncate text-meta text-ink-3">{r.ownership_note ?? r.locality}</span>
          )}
        </span>
      ),
    },
    {
      key: "type",
      header: COPY.columns.type,
      width: 56,
      cell: (r) => (
        <Tag title={COPY.kindName[r.recipient_kind]}>{COPY.kind[r.recipient_kind]}</Tag>
      ),
    },
    {
      key: "period",
      header: COPY.columns.period,
      width: 140,
      cell: (r) =>
        r.period_start != null && r.period_end != null
          ? formatPeriod(r.period_start, r.period_end)
          : COPY.fullYear,
    },
    { key: "k1", header: COPY.columns.k1, width: 50, cell: (r) => tick(r, "k1") },
    {
      key: "k3",
      header: COPY.columns.k3,
      ...(k3Tip === null ? {} : { headerAfter: k3Tip }),
      width: 120,
      cell: k3Cell,
    },
    {
      key: "states",
      header: COPY.columns.states,
      width: 100,
      cell: (r) => (r.state_codes.length === 0 ? "—" : r.state_codes.join(" · ")),
    },
    { key: "letter", header: COPY.columns.letter, width: 56, cell: (r) => tick(r, "letter") },
    { key: "status", header: COPY.columns.status, width: 190, cell: statusCell },
    { key: "handoff", header: COPY.columns.handoff, width: 200, cell: handoffCell },
    {
      key: "delivery",
      header: COPY.columns.delivery,
      cell: (r) => (
        <span className="flex min-w-0 items-center gap-[8px]">
          <span className="flex min-w-0 flex-col">
            <span>{COPY.portal}</span>
            {r.delivery_contact_name != null && (
              <span className="truncate text-meta text-ink-3">{r.delivery_contact_name}</span>
            )}
          </span>
          {rowActions(r)}
        </span>
      ),
    },
  ];

  // --- header and actions ----------------------------------------------------------------------
  const pill =
    firstRelease !== undefined && drafts.length === 0
      ? {
          label: COPY.releasedPill(formatDate(firstRelease, { now })),
          tone: "green-tint" as const,
        }
      : drafts.length > 0
        ? { label: COPY.tiles.draft, tone: undefined }
        : null;
  const header = (
    <RecordHeader
      title={COPY.title}
      context={row?.client_name ?? ""}
      {...(pill === null ? {} : { state: pill.label })}
      {...(pill?.tone === undefined ? {} : { stateTone: pill.tone })}
      checkpoints={false}
      sync={null}
      assistant={false}
      left={
        row === undefined ? undefined : (
          <Button variant="secondary" size="sm" icon="chevron-left" onClick={onBack}>
            {COPY.back(row.tax_year, row.form)}
          </Button>
        )
      }
      right={
        row === undefined ? undefined : (
          <span className="text-dense text-ink-3">
            {row.status === "filed" || row.status === "accepted"
              ? COPY.returnFiled
              : COPY.returnDue(
                  formatDate(row.extended_due_on ?? row.original_due_on ?? "", {
                    now,
                    withYear: true,
                  }),
                )}
          </span>
        )
      }
    />
  );
  const shareable = drafts.filter(
    (r) => r.allowed_actions.includes(SHARE) && (r.related_returns ?? []).length > 0,
  );
  const actions = (
    <>
      {drafts.length > 0 && (
        <Button
          variant="secondary"
          disabled={shareable.length === 0}
          opensDialog
          onClick={() => {
            setDialog("share");
          }}
        >
          {COPY.shareDraft}
        </Button>
      )}
      {drafts.length > 0 ? (
        eligible ? (
          <Button
            variant="primary"
            opensDialog
            onClick={() => {
              setDialog("release");
            }}
          >
            {COPY.releaseK1s}
          </Button>
        ) : (
          <Tooltip content={lockReason}>
            <span>
              <Button variant="primary" icon="lock" disabled aria-describedby={lockId} opensDialog>
                {COPY.releaseK1s}
              </Button>
              <span id={lockId} className="sr-only">
                {lockReason}
              </span>
            </span>
          </Tooltip>
        )
      ) : bounced > 0 ? (
        <Button
          variant="primary"
          aria-haspopup="dialog"
          onClick={() => {
            setTarget(rows.find((r) => r.status === "bounced") ?? null);
            setDialog("resend");
          }}
        >
          {COPY.resend}
        </Button>
      ) : null}
    </>
  );
  // --- the return switch ------------------------------------------------------------------------
  const options = (issuing.data?.items ?? []).map((r) => ({
    value: r.id,
    label: COPY.returnOption(r.tax_year, r.form, r.client_name),
  }));
  if (row !== undefined && !options.some((o) => o.value === row.id)) {
    options.unshift({
      value: row.id,
      label: COPY.returnOption(row.tax_year, row.form, row.client_name),
    });
  }

  return (
    <div data-screen="TXP-12" className="relative flex min-h-0 flex-1 flex-col">
      <IndexList<K1PackageOut>
        header={header}
        title={COPY.paneTitle(rows.filter((r) => r.status !== "superseded").length)}
        noun={COPY.noun}
        state={viewState}
        envelope={envelope}
        columns={columns}
        rowKey={(r) => r.id}
        twoLine={() => true}
        onSelect={(r) => {
          setExpanded(open === r.id ? "" : r.id);
        }}
        expansion={{
          open,
          id: (r) => `k1-row-${r.id}`,
          render: (r) => <Expanded pkg={r} />,
        }}
        chips={[
          {
            key: "return",
            label: COPY.filters.return,
            icon: "file-text",
            options,
            value: returnId,
          },
          {
            key: "recipient",
            label: COPY.filters.recipient,
            icon: "users-round",
            options: rows.map((r) => ({ value: r.recipient_name, label: r.recipient_name })),
            value: recipient,
            placeholder: COPY.all,
          },
          {
            key: "status",
            label: COPY.filters.status,
            icon: "circle-check",
            options: TILE_ORDER.map((code) => ({ value: code, label: COPY.tiles[code] })),
            value: statusChip,
            placeholder: COPY.all,
          },
          {
            key: "delivery",
            label: COPY.filters.delivery,
            icon: "send",
            options: [{ value: "portal", label: COPY.portal }],
            value: "portal",
          },
        ]}
        onChip={(key, value) => {
          if (key === "return" && value !== null && value !== returnId) onReturn?.(value);
          if (key === "recipient") setRecipient(value);
          if (key === "status") setStatusChip(value);
        }}
        tiles={TILES}
        tile={tile}
        onTile={setTile}
        {...(summary === undefined ? {} : { summary })}
        onClear={() => {
          setTile(null);
          setRecipient(null);
          setStatusChip(null);
          setQuery("");
        }}
        query={query}
        onQuery={setQuery}
        searchPlaceholder={COPY.search}
        countText=""
        actions={actions}
        {...(sharedDrafts.length > 0
          ? { banner: COPY.draftsBanner(sharedDrafts.length, targets(sharedNames)) }
          : {})}
        empty={{ title: COPY.emptyTitle, body: COPY.emptyBody }}
      />

      {dialog === "share" && (
        <ShareDialog
          drafts={shareable}
          chosen={chosen}
          onChosen={setChosen}
          busy={share.isPending}
          onClose={() => {
            setDialog(null);
            setChosen(null);
          }}
          onShare={(pairs) => {
            void (async () => {
              let made = 0;
              try {
                for (const [pkg, ret] of pairs) {
                  const out = await share.mutateAsync({
                    path: { return_id: returnId },
                    body: { package_ids: [pkg], target_return_ids: [ret] },
                  });
                  made += out.shared;
                }
                setDialog(null);
                setChosen(null);
                if (made > 0) toast.show(COPY.share.done(made));
              } catch {
                // A refusal part-way: what was shared stays shared; the rows say which.
                toast.show(made > 0 ? COPY.share.partial(made) : COPY.share.failed);
              } finally {
                refresh();
              }
            })();
          }}
        />
      )}

      {dialog === "release" && (
        <Dialog
          open
          onOpenChange={(o) => {
            if (!o) setDialog(null);
          }}
          title={COPY.release.title}
          size="lg"
          action={
            <Button
              variant="primary"
              icon="send"
              loading={release.isPending}
              onClick={() => {
                const ids = check.data?.package_ids ?? [];
                const version = Math.max(1, ...drafts.map((r) => r.version_no));
                const template = check.data?.email_template_version_id;
                if (ids.length === 0 || template == null) return;
                setDialog(null);
                release.mutate(
                  {
                    path: { return_id: returnId },
                    headers: { "Idempotency-Key": crypto.randomUUID() },
                    body: {
                      package_ids: ids,
                      channel: "portal",
                      email_template_version_id: template,
                      seen_version: version,
                    },
                  },
                  {
                    onSuccess: (out) => {
                      toast.undoable({
                        text: COPY.release.releasing(ids.length),
                        windowMs: Math.max(0, Date.parse(out.not_before) - nowMs()),
                        commit: refresh,
                        undo: () => {
                          undo.mutate(
                            { path: { release_id: out.release_id } },
                            {
                              onSuccess: () => {
                                toast.show(COPY.release.undone);
                                refresh();
                              },
                            },
                          );
                        },
                      });
                    },
                  },
                );
              }}
            >
              {COPY.release.confirm}
            </Button>
          }
        >
          <ReleaseBody rows={drafts} targets={targets(sharedNames)} />
        </Dialog>
      )}

      {dialog === "resend" && resendRow !== null && row !== undefined && (
        <ResendDialog
          pkg={resendRow}
          clientId={row.client_id}
          contact={contact}
          onContact={setContact}
          busy={resend.isPending}
          onClose={() => {
            setDialog(null);
            setTarget(null);
          }}
          onResend={(contactId) => {
            resend.mutate(
              {
                path: { package_id: resendRow.id },
                headers: { "Idempotency-Key": crypto.randomUUID() },
                body: { contact_id: contactId },
              },
              {
                onSuccess: () => {
                  toast.show(COPY.resendDialog.sent(resendRow.recipient_name));
                  setDialog(null);
                  setTarget(null);
                  refresh();
                },
              },
            );
          }}
        />
      )}

      {dialog === "details" && target !== null && (
        <DetailsDialog
          pkg={target}
          busy={accept.isPending || reject.isPending}
          onClose={() => {
            setDialog(null);
            setTarget(null);
          }}
          onDecide={(id, ok) => {
            const done = {
              onSuccess: () => {
                setDialog(null);
                setTarget(null);
                refresh();
              },
            };
            if (ok) accept.mutate({ path: { change_id: id }, body: {} }, done);
            else reject.mutate({ path: { change_id: id }, body: {} }, done);
          }}
        />
      )}
    </div>
  );
}

/** A2: the package's boxes, state lines and documents, and the masked TIN (the detail's). */
function Expanded({ pkg }: { pkg: K1PackageOut }): JSX.Element {
  const detail = useQuery(k1PackageOptions({ path: { package_id: pkg.id } }));
  const lines = detail.data?.lines ?? [];
  const boxes = lines.filter((l) => l.document_kind === "k1");
  const states = lines.filter((l) => l.document_kind === "state_k1");
  const docs = pkg.documents ?? [];
  const tin = detail.data?.tin;
  const draft = docs.some((d) => d.is_draft);
  const stateDocs = docs.filter((d) => d.kind === "state_k1").length;
  // "Box 2 307,900", or the item's own words ("Item K 2,762,075").
  const figure = (code: string, label: string, value: string): string =>
    `${/^[0-9]/.test(code) ? `Box ${code}` : label} ${amount(value, "whole").text}`;
  return (
    <div className="flex flex-col gap-[8px] px-[46px] py-[12px] text-dense text-ink-2">
      {tin?.last4 != null && (
        <p>
          <span className="text-ink-3">{COPY.expanded.tin} </span>
          {tin.kind === "ein" ? einMask(tin.last4) : ssnMask(tin.last4)}
        </p>
      )}
      {boxes.length > 0 ? (
        <p className="text-ink">
          {boxes.map((l) => figure(l.box_code, l.description, l.amount)).join(" · ")}
          {draft && <span className="text-ink-3"> {COPY.expanded.asDrafted}</span>}
        </p>
      ) : (
        detail.isSuccess && <p className="text-ink-3">{COPY.expanded.noFigures}</p>
      )}
      {states.length > 0 && (
        <p>
          {states.map((l) => `${l.description} ${amount(l.amount, "whole").text}`).join(" · ")}
        </p>
      )}
      <div className="flex flex-wrap gap-[6px]" aria-label={COPY.expanded.attachments}>
        {docs.some((d) => d.kind === "k1") && <Chip>{COPY.documents.k1(draft)}</Chip>}
        {docs.some((d) => d.kind === "k3") && <Chip>{COPY.documents.k3(draft)}</Chip>}
        {docs.some((d) => d.kind === "letter") && <Chip>{COPY.documents.letter(draft)}</Chip>}
        {stateDocs > 0 && <Chip>{COPY.documents.states(stateDocs)}</Chip>}
      </div>
    </div>
  );
}

function Chip({ children }: { children: string }): JSX.Element {
  return (
    <span className="inline-flex h-[24px] items-center gap-[5px] rounded-pill bg-card px-[9px] text-dense text-ink shadow-e1">
      <Icon name="paperclip" size={12} className="text-ink-3" />
      {children}
    </span>
  );
}

/** A4: the related returns each draft can go to, already-shared ones marked. */
function ShareDialog({
  drafts,
  chosen,
  onChosen,
  busy,
  onClose,
  onShare,
}: {
  drafts: readonly K1PackageOut[];
  chosen: ReadonlySet<string> | null;
  onChosen: (next: ReadonlySet<string>) => void;
  busy: boolean;
  onClose: () => void;
  onShare: (pairs: readonly (readonly [string, string])[]) => void;
}): JSX.Element {
  const now = useNow();
  const options: {
    pkg: K1PackageOut;
    ret: K1RelatedReturnOut;
    key: string;
    sharedOn: string | null;
  }[] = drafts.flatMap((pkg) =>
    (pkg.related_returns ?? []).map((ret) => {
      const h = (pkg.handoffs ?? []).find((x) => x.target_return_id === ret.return_id);
      return {
        pkg,
        ret,
        key: `${pkg.id}:${ret.return_id}`,
        sharedOn: h === undefined ? null : h.shared_at,
      };
    }),
  );
  const picked = chosen ?? new Set(options.map((o) => o.key));
  const fresh = options.filter((o) => picked.has(o.key) && o.sharedOn === null);
  return (
    <Dialog
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={COPY.share.title}
      size="md"
      action={
        <Button
          variant="primary"
          disabled={picked.size === 0}
          loading={busy}
          onClick={() => {
            if (fresh.length === 0) {
              onClose();
              return;
            }
            onShare(fresh.map((o) => [o.pkg.id, o.ret.return_id] as const));
          }}
        >
          {COPY.share.confirm(picked.size)}
        </Button>
      }
    >
      <div className="flex flex-col gap-[12px] p-[16px] text-paragraph text-ink-2">
        <p>{COPY.share.body}</p>
        {options.length === 0 ? (
          <p className="text-ink-3">{COPY.share.none}</p>
        ) : (
          <ul className="flex flex-col rounded-nested bg-card shadow-e1">
            {options.map((o) => (
              <li
                key={o.key}
                className="flex items-center gap-[10px] px-[12px] py-[8px] hairline-b last:shadow-none"
              >
                <Checkbox
                  label={COPY.share.target(o.ret.client_name, o.pkg.tax_year, o.ret.form)}
                  checked={picked.has(o.key)}
                  onChange={(on) => {
                    const next = new Set(picked);
                    if (on) next.add(o.key);
                    else next.delete(o.key);
                    onChosen(next);
                  }}
                />
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-body font-medium text-ink">
                    {COPY.share.target(o.ret.client_name, o.pkg.tax_year, o.ret.form)}
                  </span>
                  <span className="truncate text-meta text-ink-3">
                    {`${status("return", o.ret.status as TaxReturnRowOut["status"]).label} · ${COPY.share.from(o.pkg.recipient_name)}`}
                  </span>
                </span>
                {o.sharedOn !== null && (
                  <span className="rounded-pill bg-nested px-[8px] text-meta text-ink-2">
                    {COPY.share.sharedOn(formatDate(o.sharedOn, { now }))}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
        <p className="flex items-center gap-[8px] rounded-nested bg-amber-tint px-[12px] py-[8px] text-amber-ink">
          <Icon name="triangle-alert" size={13} />
          {COPY.share.warning}
        </p>
      </div>
    </Dialog>
  );
}

/** A5: the five recipients, the channel and the invite email. */
function ReleaseBody({
  rows,
  targets: shared,
}: {
  rows: readonly K1PackageOut[];
  targets: string;
}): JSX.Element {
  return (
    <div className="flex flex-col gap-[12px] p-[16px] text-paragraph text-ink-2">
      <p className="text-meta text-ink-3">{COPY.release.recipients(rows.length)}</p>
      <ul className="flex flex-col rounded-nested bg-card shadow-e1">
        {rows.map((r) => (
          <li key={r.id} className="flex items-center gap-[10px] px-[12px] py-[8px] hairline-b">
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="truncate text-body font-medium text-ink">{r.recipient_name}</span>
              <span className="truncate text-meta text-ink-3">
                {COPY.release.portalTo(r.delivery_contact_name ?? null)}
              </span>
            </span>
            <span className="text-dense text-ink-2">
              {COPY.release.contents(
                r.k3_status === "included",
                (r.documents ?? []).filter((d) => d.kind === "state_k1").length,
              )}
            </span>
          </li>
        ))}
      </ul>
      <dl className="grid grid-cols-[140px_1fr] gap-x-[12px] gap-y-[8px] rounded-nested bg-card px-[12px] py-[10px] shadow-e1">
        <dt className="text-ink-3">{COPY.release.delivery}</dt>
        <dd className="text-ink">{COPY.release.deliveryValue}</dd>
        <dt className="text-ink-3">{COPY.release.email}</dt>
        <dd className="text-ink">{COPY.release.emailValue}</dd>
      </dl>
      <p className="text-meta text-ink-3">{COPY.release.note(shared)}</p>
    </div>
  );
}

/** B2: choose the contact who receives the invite again. */
function ResendDialog({
  pkg,
  clientId,
  contact,
  onContact,
  busy,
  onClose,
  onResend,
}: {
  pkg: K1PackageOut;
  clientId: string;
  contact: string | undefined;
  onContact: (id: string) => void;
  busy: boolean;
  onClose: () => void;
  onResend: (contactId: string) => void;
}): JSX.Element {
  const contacts = useQuery(listContactsOptions({ path: { client_id: clientId } }));
  const options = (contacts.data?.items ?? []).map((c) => ({ value: c.id, label: c.name }));
  return (
    <Dialog
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={COPY.resendDialog.title}
      size="md"
      action={
        <Button
          variant="primary"
          icon="send"
          disabled={contact === undefined}
          loading={busy}
          onClick={() => {
            if (contact !== undefined) onResend(contact);
          }}
        >
          {COPY.resendDialog.confirm}
        </Button>
      }
    >
      <div className="flex flex-col gap-[12px] p-[16px] text-paragraph text-ink-2">
        <p>{COPY.resendDialog.body(pkg.recipient_name)}</p>
        <RadioGroup
          label={COPY.resendDialog.recipient}
          options={options}
          {...(contact === undefined ? {} : { value: contact })}
          onChange={onContact}
        />
      </div>
    </Dialog>
  );
}

/** DV-10: a recipient's pending W-9, W-8 or address change, accepted or rejected by a person. */
function DetailsDialog({
  pkg,
  busy,
  onClose,
  onDecide,
}: {
  pkg: K1PackageOut;
  busy: boolean;
  onClose: () => void;
  onDecide: (changeId: string, accept: boolean) => void;
}): JSX.Element {
  const now = useNow();
  const changes = useQuery(detailsChangesOptions({ path: { recipient_id: pkg.recipient_id } }));
  const pending = (changes.data ?? []).filter((c) => c.status === "pending");
  return (
    <Dialog
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={COPY.details.title}
      description={pkg.recipient_name}
      size="md"
    >
      <div className="flex flex-col gap-[10px] p-[16px] text-paragraph text-ink-2">
        {pending.length === 0 ? (
          <p className="text-ink-3">{COPY.details.none}</p>
        ) : (
          pending.map((c) => (
            <div
              key={c.id}
              className="flex items-center gap-[10px] rounded-nested bg-card px-[12px] py-[8px] shadow-e1"
            >
              <span className="min-w-0 flex-1 text-body text-ink">
                {COPY.details.submitted(
                  c.kind === "address" ? "Address" : c.kind.toUpperCase().replace("W", "W-"),
                  formatDate(c.submitted_at, { now }),
                )}
              </span>
              <Button
                size="sm"
                variant="secondary"
                disabled={busy}
                onClick={() => {
                  onDecide(c.id, false);
                }}
              >
                {COPY.details.reject}
              </Button>
              <Button
                size="sm"
                variant="primary"
                disabled={busy}
                onClick={() => {
                  onDecide(c.id, true);
                }}
              >
                {COPY.details.accept}
              </Button>
            </div>
          ))
        )}
      </div>
    </Dialog>
  );
}

/** The page with its return kept in state: the gallery's and the tests' host. */
export function K1PackagePage({
  returnId,
  opening,
}: {
  returnId: string;
  opening?: Txp12Opening;
}): JSX.Element {
  const [current, setCurrent] = useState(returnId);
  return (
    <TXP12
      key={current}
      returnId={current}
      onReturn={setCurrent}
      {...(opening === undefined || current !== returnId ? {} : { opening })}
    />
  );
}
