// TAX-11 · Form preview with K-1s (T-06-T53; TASK-9030; DEC-6035) on T17 at
// `/tax-returns/$returnId/preview`, behind `tax.form_preview`. The read-only face of the return
// before export: the server's pages (thumbnails with their blocking counts, placeholders for a
// form without a published face), the page image watermarked "Draft — not for filing" with the
// page's typed values under it (each opens SHL-09's provenance tray, which opens SHL-08), the
// K-1 list with the server's tie to Schedule K line 2, and the diagnostics in code's words, each
// failing one linked to its TXP-10 issue. "Approve return…" opens SHL-12's final approval and
// stays disabled with "n blocking diagnostics" while any blocks; "Export to tax engine…" opens
// TAX-09 once the return is approved. Download draft lives only in the ⋯ menu (fresh MFA, audited
// server-side). Nothing here transmits or files (R-04).
import { downloadDraft } from "@abacus/api-client";
import {
  diagnosticsOptions,
  formFieldsOptions,
  formPagesOptions,
  k1PreviewsOptions,
  returnRecordOptions,
} from "@abacus/api-client/query";
import { client } from "@abacus/api-client/client";
import {
  Button,
  type FormDiagnostic,
  FormRendererLayout,
  type MatchId,
  MatchScope,
  Pill,
  toast,
  type ViewerFile,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { type JSX, useState } from "react";
import { isForbidden, ConfirmItsYou } from "../../app-core/mfa";
import { useOpenOverlay } from "../../app-core/open";
import { ov, to } from "../../routes/to";
import { COPY as C } from "./copy";

export interface TAX11Props {
  returnId: string;
  /** Open on a page (its key), as an artboard opens. */
  initialPage?: string;
  /** Open on a partner's K-1 (its name), as TAX-11 b opens. */
  initialK1?: string;
}

/** Letter size in points: the server renders every face page at 612 × 792. */
const LETTER = { width_pt: 612, height_pt: 792 } as const;

function pageUrl(returnId: string, pageKey: string): string {
  const base = client.getConfig().baseUrl ?? "";
  return `${base}/v1/tax-returns/${encodeURIComponent(returnId)}/form-pages/${encodeURIComponent(pageKey)}/image`;
}

async function download(returnId: string, onMfa: () => void): Promise<void> {
  try {
    const { data, response } = await downloadDraft({
      path: { return_id: returnId },
      parseAs: "blob",
      throwOnError: true,
    });
    const header = response.headers.get("Content-Disposition") ?? "";
    const name = /filename="([^"]+)"/u.exec(header)?.[1] ?? "draft.pdf";
    const url = URL.createObjectURL(data);
    const a = document.createElement("a");
    a.href = url;
    a.download = name;
    a.click();
    URL.revokeObjectURL(url);
  } catch (error) {
    if (isForbidden(error)) onMfa();
    else toast.show({ kind: "error", text: C.downloadFailed });
  }
}

export function TAX11({ returnId, initialPage, initialK1 }: TAX11Props): JSX.Element {
  const navigate = useNavigate();
  const openOverlay = useOpenOverlay();
  const path = { return_id: returnId };
  const record = useQuery(returnRecordOptions({ path }));
  const pages = useQuery(formPagesOptions({ path }));
  const diagnostics = useQuery(diagnosticsOptions({ path }));
  const k1s = useQuery(k1PreviewsOptions({ path }));
  const [pageKey, setPageKey] = useState<string | null>(initialPage ?? null);
  const [k1, setK1] = useState<string | null>(null);
  const [mfa, setMfa] = useState(false);
  const items = pages.data?.pages ?? [];
  const current = items.find((p) => p.page_key === pageKey) ?? items[0];
  const fields = useQuery({
    ...formFieldsOptions({ path: { return_id: returnId, page_key: current?.page_key ?? "" } }),
    enabled: current !== undefined && !current.placeholder,
  });
  const partners = k1s.data?.items ?? [];
  const chosenK1 =
    k1 ??
    (initialK1 === undefined
      ? null
      : (partners.find((p) => p.name === initialK1)?.partner_id ?? null));

  if (pages.isError || record.isError) {
    return (
      <div
        data-screen="TAX-11"
        role="alert"
        className="flex flex-col items-start gap-[8px] p-[24px]"
      >
        <p className="text-[13px]">{C.failed}</p>
        <Button variant="secondary" size="sm" onClick={() => void pages.refetch()}>
          {C.retry}
        </Button>
      </div>
    );
  }
  const row = record.data?.row;
  const loading = pages.isPending || record.isPending;
  const n = (key: string): number => items.findIndex((p) => p.page_key === key) + 1;
  const file: ViewerFile | null =
    current === undefined || current.placeholder
      ? null
      : {
          name: current.caption,
          pages: [{ n: 1, ...LETTER, rotation: 0, src: pageUrl(returnId, current.page_key) }],
          regions: [],
        };
  const blocking = diagnostics.data?.blocking ?? 0;
  const approved = row?.status === "approved";
  const shown: FormDiagnostic[] = (diagnostics.data?.items ?? []).map((d) => ({
    id: d.rule_key,
    severity: d.severity === "blocking" ? "error" : d.severity === "warning" ? "warning" : "clear",
    text: d.title ?? d.rule_key,
    page: d.page_key ? Math.max(n(d.page_key), 1) : 1,
    match: null as MatchId | null,
    issue: d.issue_id !== null && d.issue_id !== undefined && d.severity !== "clear",
  }));
  const partner = partners.find((p) => p.partner_id === chosenK1);
  const values = fields.data?.items ?? [];
  const face =
    partner !== undefined ? (
      <div
        data-tax11="k1-face"
        className="flex flex-1 flex-col items-center justify-center gap-[10px] rounded-pane bg-nested p-[24px] text-center"
      >
        <p className="text-[14.5px] font-medium">{C.k1Face(partner.name)}</p>
        <Pill variant="amber">{C.draftK1}</Pill>
        <p className="max-w-[420px] text-[12.5px] text-ink-2">{C.k1FaceNote}</p>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => {
            void navigate(to.TXP12({ returnId }));
          }}
        >
          {C.openK1Package}
        </Button>
      </div>
    ) : current?.placeholder === true ? (
      <div
        data-tax11="placeholder"
        className="flex flex-1 items-center justify-center rounded-pane bg-nested p-[24px] text-[12.5px] text-ink-3"
      >
        {C.placeholder}
      </div>
    ) : undefined;
  const afterPages = (
    <section
      aria-label={C.values}
      data-tax11="values"
      className="mx-auto mt-[12px] w-[612px] rounded-pane bg-card"
    >
      <p className="px-[12px] py-[8px] text-[12px] font-medium text-ink-3">
        {C.values} · {C.watermark}
      </p>
      {values.length === 0 ? (
        <p className="px-[12px] pb-[10px] text-[12px] text-ink-3">{C.noValues}</p>
      ) : (
        <ul>
          {values.map((f) => (
            <li
              key={f.field_key}
              className="flex min-h-[30px] items-center justify-between gap-[12px] px-[12px] hairline-b last:shadow-none"
            >
              <span className="text-[12.5px] text-ink-2">{f.label}</span>
              <button
                type="button"
                data-field={f.field_key}
                className="text-[12.5px] font-medium tabular-nums hover:underline"
                onClick={() => {
                  // A typed value traces to its workbook cell and TB line (SHL-09 → SHL-08).
                  openOverlay(ov.SHL09("tax_return", returnId, f.field_key));
                }}
              >
                {f.value ?? "—"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
  const footer = (
    <>
      <Button
        variant="primary"
        disabled={blocking > 0 || approved || diagnostics.isPending}
        title={blocking > 0 ? C.blocking(blocking) : undefined}
        onClick={() => {
          openOverlay(ov.SHL12("tax_return", returnId, "L4_partner"));
        }}
      >
        {C.approve}
      </Button>
      {blocking > 0 ? (
        <p className="text-center text-[11.5px] text-ink-3" data-tax11="blocking">
          {C.blocking(blocking)}
        </p>
      ) : null}
      <Button
        variant="secondary"
        disabled={!approved}
        title={approved ? undefined : C.exportClosed}
        onClick={() => {
          openOverlay(ov.TAX09(returnId));
        }}
      >
        {C.export}
      </Button>
    </>
  );
  return (
    <div data-screen="TAX-11" aria-busy={loading} className="flex min-h-0 flex-1 flex-col">
      <MatchScope>
        <FormRendererLayout
          subbar={
            row === undefined ? null : (
              <div className="flex h-[42px] items-center gap-[10px] px-[12px] text-[13px]">
                <span className="font-medium">
                  {C.title(row.tax_year, row.form.toUpperCase())}
                </span>
                <span className="text-ink-2">{row.client_name}</span>
              </div>
            )
          }
          mode="form"
          thumbs={items.map((p, i) => ({
            n: i + 1,
            src: p.placeholder ? null : pageUrl(returnId, p.page_key),
            diagnostics: p.blocking,
            caption: p.caption,
          }))}
          page={current === undefined ? 1 : n(current.page_key)}
          onPage={(i) => {
            const next = items[i - 1];
            if (next !== undefined) {
              setPageKey(next.page_key);
              setK1(null);
            }
          }}
          file={file}
          menu={[
            {
              label: C.download,
              onSelect: () =>
                void download(returnId, () => {
                  setMfa(true);
                }),
            },
          ]}
          k1s={partners.map((p) => ({
            id: p.partner_id,
            name: p.name,
            amount: p.box_2,
            status: C.draftK1,
          }))}
          total={{
            state: k1s.data === undefined ? "pending" : k1s.data.tally === "tie" ? "tie" : "off",
            difference: null,
          }}
          diagnostics={shown}
          loading={loading}
          onK1={(id) => {
            setK1(id);
          }}
          selectedK1={chosenK1}
          onIssue={() => {
            void navigate(to.TXP10({ returnId }));
          }}
          footer={footer}
          {...(face === undefined ? {} : { face })}
          afterPages={afterPages}
        />
      </MatchScope>
      <ConfirmItsYou open={mfa} onOpenChange={setMfa} />
    </div>
  );
}
