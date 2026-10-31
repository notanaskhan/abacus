import type { K1PackageOut, PortalK1ExpectedOut } from "@abacus/api-client";
import { portalK1Attachment, portalK1Download } from "@abacus/api-client";
import {
  portalDetailsChangeMutation,
  portalK1Options,
  portalK1sExpectedOptions,
  portalK1sOptions,
} from "@abacus/api-client/query";
import {
  Button,
  Dialog,
  EmptyState,
  Fieldset,
  Icon,
  type PortalNavItem,
  PortalBrandProvider,
  PortalLayout,
  RegistryStatus,
  Tooltip,
  ValueRow,
  amount,
  date as formatDate,
  einMask,
  ssnMask,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type ReactNode, useId, useState } from "react";
import { useNow } from "../../app-core/clock";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import { brandOf, useBranding, usePortalToolbar } from "../../domain/portal";
import { COPY } from "./copy";

// POR-13 · My K-1s (T-02-T27; docs/screens/POR-13.md) on T7's reduced 720 shell, over T-02-T26's
// portal routes and T-02-T27's `expected` read:
//
//   a  Nora Calloway's released 2025 K-1 (Form 1041)      b  Pell Street: not released yet
//   c  Pell Street's released Ridgeline K-1                d  the Update taxpayer ID sheet
//   e  an amended K-1 over the struck, superseded one      f  Meera Shah's role union (DV-11)
//
// A recipient sees only their own released packages; before release only who issues the K-1 and
// by when (no amounts, no documents). Amounts are the server's; the browser adds nothing up. The
// TIN shows masked, from the detail only. A details change goes to the firm to check (DV-10).
// Not built: the electronic-furnishing consent sheet (DV-12) waits on a counsel-approved
// disclosure in the database (OQ-4; DEC-1576).

const K1_NAV: readonly PortalNavItem[] = [{ label: COPY.active, icon: "file-text" }];

export interface Por13Props {
  mobile?: boolean;
  frame?: boolean;
  onNavigate?: (area: string) => void;
  /** d: the Update taxpayer ID sheet held open. */
  opening?: "tin";
}

async function save(blob: Blob, name: string): Promise<void> {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
  await Promise.resolve();
}

function fileName(response: Response, fallback: string): string {
  return (
    /filename="([^"]+)"/.exec(response.headers.get("Content-Disposition") ?? "")?.[1] ?? fallback
  );
}

function MyK1s({ mobile = false, frame = false, onNavigate, opening }: Por13Props): JSX.Element {
  const bar = usePortalToolbar(null);
  const branding = useBranding();
  const firm = branding.data?.firm_name ?? "";
  const rows = useQuery(portalK1sOptions());
  const expected = useQuery(portalK1sExpectedOptions());
  const roleUnion = bar !== undefined && bar.nav.length > 0;
  const nav = roleUnion ? bar.nav : [...K1_NAV];
  const live = (rows.data ?? []).filter((r) => r.status !== "superseded");
  const superseded = (rows.data ?? []).filter((r) => r.status === "superseded");
  const loading = rows.isPending || expected.isPending;
  const nothing =
    !loading && live.length === 0 && superseded.length === 0 && (expected.data ?? []).length === 0;
  const body = (
    <div data-screen="POR-13" className="flex flex-col gap-[12px] bg-shell p-[12px]">
      {roleUnion && (
        <div
          role="status"
          className="flex min-h-[36px] items-center gap-[8px] rounded-nested bg-amber-tint px-[12px] text-dense text-amber-ink"
        >
          <Icon name="info" size={14} />
          <Tooltip content={COPY.roleUnionTip}>
            <span>{COPY.roleUnion}</span>
          </Tooltip>
        </div>
      )}
      {(expected.data ?? []).map((e) => (
        <ExpectedCard key={`${e.issuer_name}:${String(e.tax_year)}`} expected={e} />
      ))}
      {live.map((r, i) => (
        <PackageCard
          key={r.id}
          row={r}
          firm={firm}
          showDetails={i === 0}
          opening={i === 0 ? opening : undefined}
        />
      ))}
      {superseded.map((r) => (
        <SupersededCard key={r.id} row={r} />
      ))}
      {nothing && (
        <EmptyState title={COPY.empty} icon="file-text">
          {COPY.emptyBody}
        </EmptyState>
      )}
      {live.length > 0 && (
        <p className="py-[8px] text-center text-meta text-ink-3">{COPY.footer(firm)}</p>
      )}
    </div>
  );
  return (
    <PortalLayout
      variant={mobile ? "mobile" : "reduced"}
      user={bar?.user ?? ""}
      nav={nav}
      {...(roleUnion ? {} : { active: COPY.active })}
      frame={frame}
      {...(onNavigate === undefined ? {} : { onNavigate })}
    >
      {mobile ? (
        body
      ) : (
        <section aria-labelledby="por13-title" className="flex min-h-0 flex-1 flex-col">
          <h2
            id="por13-title"
            className="flex h-[46px] shrink-0 items-center justify-center text-[14.5px] font-medium hairline-b"
          >
            {COPY.title}
          </h2>
          <div className="min-h-0 flex-1 overflow-auto">{body}</div>
        </section>
      )}
    </PortalLayout>
  );
}

function Card({
  children,
  struck = false,
}: {
  children: ReactNode;
  struck?: boolean;
}): JSX.Element {
  return (
    <article
      className={`flex flex-col gap-[12px] rounded-pane bg-card p-[16px] shadow-e1 ${struck ? "opacity-70" : ""}`}
    >
      {children}
    </article>
  );
}

/** b: who issues the K-1 and by when; no amounts and no documents before release. */
function ExpectedCard({ expected }: { expected: PortalK1ExpectedOut }): JSX.Element {
  const now = useNow();
  return (
    <>
      <Card>
        <header className="flex items-start justify-between gap-[12px]">
          <h3 className="text-body font-medium text-ink">
            {COPY.heading(expected.issuer_name, expected.tax_year, expected.form)}
          </h3>
          <RegistryStatus object="k1_package" code="draft" client />
        </header>
        <p className="text-dense text-ink-2">
          {expected.expected_on == null
            ? COPY.expectedNoDate
            : COPY.expected(formatDate(expected.expected_on, { now, withYear: true }))}
        </p>
      </Card>
      {expected.k3_status === "included" && (
        <Card>
          <h3 className="text-body font-medium text-ink">{COPY.k3Title}</h3>
          <p className="text-dense leading-[1.5] text-ink-2">
            {COPY.k3Body(expected.issuer_name)}
          </p>
        </Card>
      )}
    </>
  );
}

/** e: the earlier package, struck, under the amended one. */
function SupersededCard({ row }: { row: K1PackageOut }): JSX.Element {
  return (
    <Card>
      <header className="flex items-start justify-between gap-[12px]">
        <h3 className="text-body font-medium text-ink-2 line-through">
          {COPY.heading(row.issuer_name ?? "", row.tax_year, row.form)}
        </h3>
        <RegistryStatus object="k1_package" code="superseded" client />
      </header>
    </Card>
  );
}

/** a, c, e: the released statement, its documents and the recipient's own details. */
function PackageCard({
  row,
  firm,
  showDetails,
  opening,
}: {
  row: K1PackageOut;
  firm: string;
  showDetails: boolean;
  opening: "tin" | undefined;
}): JSX.Element {
  const now = useNow();
  const queryClient = useQueryClient();
  const detail = useQuery(portalK1Options({ path: { package_id: row.id } }));
  const [sheet, setSheet] = useState<"tin" | "address" | null>(opening ?? null);
  const [busy, setBusy] = useState(false);
  const lines = (detail.data?.lines ?? []).filter((l) => l.document_kind === "k1");
  const docs = detail.data?.documents ?? row.documents ?? [];
  const states = docs.filter((d) => d.kind === "state_k1").map((d) => d.jurisdiction ?? "");
  const amended = row.supersedes_package_id != null;
  const refresh = (): void => {
    void queryClient.invalidateQueries();
  };
  const downloadAll = async (): Promise<void> => {
    setBusy(true);
    try {
      const { data, response } = await portalK1Download({
        path: { package_id: row.id },
        parseAs: "blob",
        throwOnError: true,
      });
      await save(data, fileName(response, "k1.zip"));
      refresh();
    } catch {
      toast.show(COPY.downloadFailed);
    } finally {
      setBusy(false);
    }
  };
  const downloadOne = async (documentId: string, fallback: string): Promise<void> => {
    try {
      const { data, response } = await portalK1Attachment({
        path: { package_id: row.id, document_id: documentId },
        parseAs: "blob",
        throwOnError: true,
      });
      await save(data, fileName(response, fallback));
      refresh();
    } catch {
      toast.show(COPY.downloadFailed);
    }
  };
  const chip = (id: string, label: string): JSX.Element => (
    <button
      key={id}
      type="button"
      onClick={() => {
        void downloadOne(id, `${label}.pdf`);
      }}
      className="inline-flex h-[28px] items-center gap-[6px] rounded-pill bg-card px-[10px] text-dense text-ink shadow-e1 hover:shadow-e3"
    >
      <Icon name="file-text" size={13} className="text-ink-3" />
      {label}
    </button>
  );
  const tin = detail.data?.tin;
  return (
    <>
      <Card>
        <header className="flex items-start justify-between gap-[12px]">
          <div className="flex min-w-0 flex-col gap-[4px]">
            <h3 className="text-body font-medium text-ink">
              {amended
                ? `${COPY.amended(row.tax_year)} · ${COPY.heading(row.issuer_name ?? "", row.tax_year, row.form)}`
                : COPY.heading(row.issuer_name ?? "", row.tax_year, row.form)}
            </h3>
            {firm !== "" && <p className="text-dense text-ink-3">{COPY.preparedBy(firm)}</p>}
          </div>
          <RegistryStatus
            object="k1_package"
            code={row.status}
            client
            {...(row.released_at === null
              ? {}
              : { vars: { date: formatDate(row.released_at, { now }) } })}
          />
        </header>
        {lines.length > 0 && (
          <table className="w-full border-collapse overflow-hidden rounded-nested text-dense shadow-e1">
            <caption className="sr-only">{COPY.amounts}</caption>
            <thead>
              <tr className="h-[28px] bg-band-hd text-th text-ink-3">
                <th scope="col" className="w-[72px] px-[14px] text-left font-medium">
                  {COPY.columns.box}
                </th>
                <th scope="col" className="px-[14px] text-left font-medium">
                  {COPY.columns.description}
                </th>
                <th scope="col" className="px-[14px] text-right font-medium">
                  {COPY.columns.amount}
                </th>
              </tr>
            </thead>
            <tbody>
              {lines.map((l) => (
                <tr
                  key={`${l.box_code}:${l.description}`}
                  className={
                    l.is_total
                      ? "border-t-[0.5px] border-stroke font-medium"
                      : "h-[34px] hairline-b"
                  }
                >
                  <td className="px-[14px] text-ink-2">{l.is_total ? "" : l.box_code}</td>
                  <td className="px-[14px] py-[6px]">
                    <span className="flex flex-col">
                      <span>{l.description}</span>
                      {l.is_total && row.form === "1041" && (
                        <span className="text-meta font-normal text-ink-3">
                          {COPY.distributions(row.tax_year)}
                        </span>
                      )}
                    </span>
                  </td>
                  <td className="px-[14px] text-right tabular-nums">
                    {amount(l.amount, "whole").text}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {row.form === "1041" && lines.length > 0 && (
          <p className="text-dense leading-[1.5] text-ink-2">{COPY.help1041(row.tax_year)}</p>
        )}
        {row.k3_status === "included" && (
          <p className="text-dense text-ink-2">{COPY.k3Included}</p>
        )}
        <footer className="flex flex-wrap items-center gap-[8px] border-t-[0.5px] border-hair pt-[12px]">
          {docs.filter((d) => d.kind === "k1").map((d) => chip(d.id, COPY.documents.k1(row.form)))}
          {docs.filter((d) => d.kind === "k3").map((d) => chip(d.id, COPY.documents.k3(row.form)))}
          {states.length > 0 &&
            docs
              .filter((d) => d.kind === "state_k1")
              .slice(0, 1)
              .map((d) => chip(d.id, COPY.documents.state(states)))}
          {docs
            .filter((d) => d.kind === "letter")
            .map((d) => chip(d.id, COPY.documents.letter(row.form)))}
          <Button
            variant="primary"
            icon="download"
            className="ml-auto"
            loading={busy}
            onClick={() => {
              void downloadAll();
            }}
          >
            {COPY.downloadAll}
          </Button>
        </footer>
      </Card>
      {showDetails && (
        <Fieldset title={COPY.details.title}>
          <ValueRow label={COPY.details.name} kind="value">
            {row.recipient_name}
          </ValueRow>
          <ValueRow label={COPY.details.tin} kind="value">
            <span className="inline-flex items-center gap-[12px]">
              {tin?.last4 == null
                ? "—"
                : tin.kind === "ein"
                  ? einMask(tin.last4)
                  : ssnMask(tin.last4)}
              {PLANNED_VISIBLE && (
                <Button
                  variant="ghost"
                  size="sm"
                  aria-haspopup="dialog"
                  onClick={() => {
                    setSheet("tin");
                  }}
                >
                  {COPY.details.update}
                </Button>
              )}
            </span>
          </ValueRow>
          <ValueRow label={COPY.details.address} kind="value" help={COPY.details.help(firm)}>
            <span className="inline-flex items-center gap-[12px]">
              {detail.data?.address_on_file === false
                ? COPY.details.notOnFile
                : COPY.details.onFile}
              <Button
                variant="ghost"
                size="sm"
                aria-haspopup="dialog"
                onClick={() => {
                  setSheet("address");
                }}
              >
                {COPY.details.update}
              </Button>
            </span>
          </ValueRow>
        </Fieldset>
      )}
      {sheet === "tin" && PLANNED_VISIBLE && (
        <TinSheet
          onClose={() => {
            setSheet(null);
          }}
        />
      )}
      {sheet === "address" && (
        <AddressSheet
          recipientId={row.recipient_id}
          firm={firm}
          onClose={() => {
            setSheet(null);
          }}
        />
      )}
    </>
  );
}

/** d: a signed W-9 (or W-8) for the firm to check; never a typed number (DV-10). Planned: no
 * portal upload yet yields an evidence version in a K-1 recipient's scope, so the sheet is drawn
 * in fixture builds with Send held (DEC-1576); production shows the masked TIN alone. */
function TinSheet({ onClose }: { onClose: () => void }): JSX.Element {
  const inputId = useId();
  const [file, setFile] = useState<File | null>(null);
  return (
    <Dialog
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={COPY.tinSheet.title}
      size="md"
      action={
        <Button variant="primary" disabled>
          {COPY.tinSheet.submit}
        </Button>
      }
    >
      <div className="flex flex-col gap-[12px] p-[16px] text-paragraph text-ink-2">
        <label
          htmlFor={inputId}
          className="flex cursor-pointer flex-col items-center gap-[6px] rounded-nested bg-nested px-[16px] py-[20px] text-center"
        >
          <Icon name="upload" size={16} className="text-ink-3" />
          <span className="text-body font-medium text-ink">{COPY.tinSheet.upload}</span>
          <span className="text-meta text-ink-3">{file?.name ?? COPY.tinSheet.choose}</span>
        </label>
        <input
          id={inputId}
          type="file"
          accept="application/pdf,image/*"
          className="sr-only"
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null);
          }}
        />
        <p className="text-meta text-ink-3">{COPY.tinSheet.uploadW8}</p>
        <p className="text-meta text-ink-3">{COPY.tinSheet.helper}</p>
      </div>
    </Dialog>
  );
}

const ADDRESS_FIELDS = ["line1", "line2", "city", "state", "postal_code", "country"] as const;
type AddressField = (typeof ADDRESS_FIELDS)[number];
const ADDRESS_LABEL: Readonly<Record<AddressField, string>> = {
  line1: COPY.addressSheet.line1,
  line2: COPY.addressSheet.line2,
  city: COPY.addressSheet.city,
  state: COPY.addressSheet.state,
  postal_code: COPY.addressSheet.postal,
  country: COPY.addressSheet.country,
};

/** A structured address for the firm to check (DV-10). */
function AddressSheet({
  recipientId,
  firm,
  onClose,
}: {
  recipientId: string;
  firm: string;
  onClose: () => void;
}): JSX.Element {
  const [value, setValue] = useState<Record<AddressField, string>>({
    line1: "",
    line2: "",
    city: "",
    state: "",
    postal_code: "",
    country: "US",
  });
  const change = useMutation(portalDetailsChangeMutation());
  const ready = value.line1 !== "" && value.city !== "" && value.postal_code !== "";
  return (
    <Dialog
      open
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={COPY.addressSheet.title}
      size="md"
      dirty={value.line1 !== ""}
      action={
        <Button
          variant="primary"
          disabled={!ready}
          loading={change.isPending}
          onClick={() => {
            const address = Object.fromEntries(
              ADDRESS_FIELDS.filter((k) => value[k] !== "").map((k) => [k, value[k]]),
            );
            change.mutate(
              { path: { recipient_id: recipientId }, body: { kind: "address", address } },
              {
                onSuccess: () => {
                  toast.show(COPY.tinSheet.sent(firm));
                  onClose();
                },
              },
            );
          }}
        >
          {COPY.addressSheet.submit}
        </Button>
      }
    >
      <Fieldset flush>
        {ADDRESS_FIELDS.map((k) => (
          <ValueRow
            key={k}
            label={ADDRESS_LABEL[k]}
            kind="text"
            value={value[k]}
            onChange={(v) => {
              setValue((prev) => ({ ...prev, [k]: v }));
            }}
          />
        ))}
      </Fieldset>
    </Dialog>
  );
}

/** POR-13 under the firm's portal brand (the T7 shell reads it). */
export function POR13(props: Por13Props): JSX.Element | null {
  const branding = useBranding();
  if (branding.data === undefined) return null;
  return (
    <PortalBrandProvider brand={brandOf(branding.data)}>
      <MyK1s {...props} />
    </PortalBrandProvider>
  );
}
