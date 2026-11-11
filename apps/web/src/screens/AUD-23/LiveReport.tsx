import type { AuditReportOut, ReportChoiceOut, ReportParagraphOut } from "@abacus/api-client";
import {
  auditReportChoiceMutation,
  auditReportDocumentMutation,
  auditReportOptions,
  auditReportRequestDecisionMutation,
} from "@abacus/api-client/query";
import { Button, Icon, Picker, Pill, Skeleton, Toggle, toast } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { JSX } from "react";
import { MODS, type Mod } from "./copy";

// AUD-23 · Report builder on live data (S33 partials round, A-07-T34; DEC-3137): the report's
// structured choices and its assembled paper from `GET /v1/audits/{id}/report` (A-07-T27's
// service). A choice is set through `PATCH …/report/choices` with the version the person saw; a
// modification asks the partner's SHL-11 card (`…/request-decision`); Generate .docx… goes through
// `…/documents`. Paragraphs are the server's template blocks: never free text. "Approve report"
// shows only with the server's `sign_off.l4` and is the host's SHL-12 (`onApprove`); release
// lives in AUD-24. A refusal shows the server's code. The canvas version (index's ReportBuilder)
// stays the fixture-mode gallery.

const FORM_LABEL: Readonly<Record<string, string>> = Object.fromEntries(
  MODS.map(([k, l]) => [
    k === "none"
      ? "unmodified"
      : k === "qual"
        ? "qualified"
        : k === "adv"
          ? "adverse"
          : "disclaimer",
    l,
  ]),
);
const MOD_OF: Readonly<Record<string, Mod>> = {
  unmodified: "none",
  qualified: "qual",
  adverse: "adv",
  disclaimer: "dis",
};
const TOGGLE_LABEL: Readonly<Record<string, string>> = {
  going_concern: "Going concern section",
  erisa_supplemental_schedules: "Supplemental schedules required by ERISA (AU-C 703 section)",
  other_information: "Other information (AU-C 720)",
};
const TITLE: Readonly<Record<AuditReportOut["report_kind"], string>> = {
  audit: "Independent Auditor’s Report",
  review: "Independent Accountant’s Review Report",
  compilation: "Accountant’s Compilation Report",
};

export interface LiveReportProps {
  workItemId: string;
  onBack?: () => void;
  /** SHL-12 at Partner level over the version the person read. */
  onApprove?: (versionNo: number, contentHash: string) => void;
  onGoToRelease?: () => void;
}

function refusal(error: unknown): string {
  if (typeof error === "object" && error !== null) {
    const body = error as { code?: unknown; detail?: unknown };
    if (typeof body.code === "string") return body.code.replaceAll("_", " ");
    if (typeof body.detail === "string") return body.detail;
  }
  return "The report did not take that change.";
}

function key(): { "Idempotency-Key": string } {
  return { "Idempotency-Key": crypto.randomUUID() };
}

function Paragraph({ p }: { p: ReportParagraphOut }): JSX.Element {
  return (
    <section data-block={p.block_id}>
      {p.heading !== null && <h4 className="pt-[10px] text-[13.5px] font-medium">{p.heading}</h4>}
      <p>
        {p.text}
        {p.citations.map((c, i) => (
          <span
            key={c.citation_id}
            title={c.label}
            className="ml-[3px] rounded-[4px] bg-nested px-[4px] text-[10.5px] text-ink-2"
          >
            {i + 1}
          </span>
        ))}
      </p>
    </section>
  );
}

export function LiveReport(props: LiveReportProps): JSX.Element {
  const queryClient = useQueryClient();
  const options = auditReportOptions({ path: { work_item_id: props.workItemId } });
  const report = useQuery({ ...options, retry: false });
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: options.queryKey });
  };
  const choose = useMutation({
    ...auditReportChoiceMutation(),
    onSuccess: (next) => {
      queryClient.setQueryData(options.queryKey, next);
    },
    onError: (e) => {
      toast.show(refusal(e));
      refresh();
    },
  });
  const ask = useMutation({
    ...auditReportRequestDecisionMutation(),
    onSuccess: refresh,
    onError: (e) => {
      toast.show(refusal(e));
    },
  });
  const generate = useMutation({
    ...auditReportDocumentMutation(),
    onSuccess: refresh,
    onError: (e) => {
      toast.show(refusal(e));
    },
  });

  const data = report.data;
  if (data === undefined) {
    return (
      <div data-screen="AUD-23" data-live className="p-[12px]">
        {report.isError ? (
          <p className="text-dense text-ink-3">{refusal(report.error)}</p>
        ) : (
          <Skeleton className="h-[320px]" />
        )}
      </div>
    );
  }
  const choice = (field: string): ReportChoiceOut | undefined =>
    data.choices.find((c) => c.field === field);
  const can = (action: AuditReportOut["allowed_actions"][number]): boolean =>
    data.allowed_actions.includes(action);
  const locked = data.status !== "draft";
  const form = String(choice("opinion_form")?.value ?? "unmodified");
  const decisionNeeded = form !== "unmodified" && choice("opinion_form")?.decision_card_id == null;
  const set = (field: string, value: string | boolean | null): void => {
    choose.mutate({
      path: { work_item_id: props.workItemId },
      body: { field, value, seen_version: data.version },
    });
  };
  const current = data.current_version;
  const docx = data.documents.find((d) => d.format === "docx");

  return (
    <div data-screen="AUD-23" data-live className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-[50px] items-center px-[12px]">
        <Button size="sm" variant="ghost" onClick={props.onBack}>
          ‹ Cockpit
        </Button>
      </div>
      <div className="flex min-h-0 flex-1 gap-[10px] px-[12px] pb-[12px]">
        <section
          aria-label="Structure"
          className="w-[470px] shrink-0 overflow-y-auto rounded-pane bg-card shadow-e1"
        >
          <h2 className="flex h-[32px] items-center px-[14px] text-[12.5px] font-medium text-ink-2">
            Report › {TITLE[data.report_kind]}
          </h2>
          <h3 className="flex h-[31px] items-center bg-band-hd px-[14px] text-dense font-medium">
            Engagement
          </h3>
          <div className="flex min-h-[34px] items-center justify-between px-[14px] text-[13px]">
            <span className="text-ink-2">Framework</span>
            <span className="font-medium">{data.framework}</span>
          </div>
          <h3 className="flex h-[31px] items-center bg-band-hd px-[14px] text-dense font-medium">
            {data.report_kind === "audit" ? "Opinion" : "Conclusion"}
          </h3>
          <div className="flex min-h-[34px] items-center justify-between gap-2 px-[14px] text-[13px]">
            <span className="text-ink-2">Modification</span>
            <span className="flex items-center gap-2">
              {decisionNeeded && <Pill variant="amber">Decision required</Pill>}
              <Picker
                label="Modification"
                options={Object.keys(MOD_OF).map((k) => ({ value: k, label: FORM_LABEL[k] ?? k }))}
                value={form}
                disabled={locked || !can("report.draft") || choose.isPending}
                onChange={(next) => {
                  set("opinion_form", next);
                }}
              />
            </span>
          </div>
          {decisionNeeded && can("report.request_decision") && (
            <div className="px-[14px] pb-[6px] text-right text-[11.5px] text-ink-3">
              Requires a partner decision card{" "}
              <button
                type="button"
                className="text-ink underline"
                disabled={ask.isPending}
                onClick={() => {
                  ask.mutate({
                    path: { work_item_id: props.workItemId },
                    body: { field: "opinion" },
                  });
                }}
              >
                Request partner decision…
              </button>
            </div>
          )}
          <h3 className="flex h-[31px] items-center bg-band-hd px-[14px] text-dense font-medium">
            Paragraphs
          </h3>
          {Object.entries(TOGGLE_LABEL).map(([field, label]) => {
            const c = choice(field);
            if (c === undefined) return null;
            return (
              <div
                key={field}
                className="flex min-h-[34px] items-center gap-2 px-[14px] text-[13px]"
              >
                <span className="flex-1 text-ink-2">{label}</span>
                {c.reason_code !== null && (
                  <span className="text-[11.5px] text-ink-3">{c.reason_code}</span>
                )}
                <Toggle
                  size="small"
                  label={label}
                  checked={c.value === true}
                  disabled={
                    locked || c.locked_by !== null || !can("report.draft") || choose.isPending
                  }
                  onChange={(on) => {
                    set(field, on);
                  }}
                />
              </div>
            );
          })}
          <h3 className="flex h-[31px] items-center bg-band-hd px-[14px] text-dense font-medium">
            Approvals
          </h3>
          <ul>
            <li className="flex min-h-[34px] items-center gap-2 px-[14px] text-[13px]">
              <Icon name={current?.approved_at != null ? "circle-check" : "circle"} size={15} />
              {current?.approved_by_name != null
                ? `Engagement partner approval · ${current.approved_by_name}`
                : "Engagement partner approval"}
            </li>
            <li className="flex min-h-[34px] items-center justify-between gap-2 px-[14px] text-[13px]">
              <span>Generated documents</span>
              <span className="flex items-center gap-2 text-ink-2">
                {docx === undefined ? "None yet" : `1 · v${String(docx.version_no)}`}
                {docx?.out_of_date === true && (
                  <Pill variant="amber">Out of date · Update from data</Pill>
                )}
              </span>
            </li>
          </ul>
        </section>
        <section aria-label="Paper" className="flex min-w-0 flex-1 flex-col rounded-pane bg-shell">
          <header className="relative flex h-[46px] items-center justify-center">
            <h2 className="text-[14.5px] font-medium">
              {TITLE[data.report_kind]}
              {current === null ? "" : ` · v${String(current.version_no)}`}
            </h2>
            <div className="absolute right-[10px] flex gap-2">
              {can("report.generate") && current !== null && (
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={generate.isPending}
                  onClick={() => {
                    generate.mutate({
                      path: { work_item_id: props.workItemId },
                      body: { format: "docx", report_version: current.version_no },
                      headers: key(),
                    });
                  }}
                >
                  <Icon name="file-down" size={14} />
                  {generate.isPending ? "Generating…" : "Generate .docx…"}
                </Button>
              )}
              {data.status === "approved" ? (
                <Button size="sm" onClick={props.onGoToRelease}>
                  <Icon name="arrow-right" size={14} />
                  Go to issuance & release
                </Button>
              ) : (
                can("sign_off.l4") &&
                current !== null &&
                props.onApprove !== undefined && (
                  <Button
                    size="sm"
                    disabled={decisionNeeded}
                    title={decisionNeeded ? "Decision required first" : undefined}
                    onClick={() => props.onApprove?.(current.version_no, current.content_hash)}
                  >
                    <Icon name="check" size={14} />
                    Approve report
                  </Button>
                )
              )}
            </div>
          </header>
          <div
            // A scrolling region is reachable by keyboard (axe scrollable-region-focusable).
            tabIndex={0}
            role="region"
            aria-label="Paper content"
            className="min-h-0 flex-1 overflow-y-auto p-[14px]"
          >
            <article className="relative mx-auto w-[600px] overflow-hidden rounded-pane bg-card px-[26px] pb-[26px] pt-[22px] text-[12px] leading-[1.55] shadow-e2">
              {data.status === "draft" && (
                <span
                  aria-hidden="true"
                  data-watermark="draft"
                  className="pointer-events-none absolute inset-0 flex -rotate-[30deg] items-center justify-center text-[72px] font-medium text-ink/[.06] before:content-['DRAFT']"
                />
              )}
              <h3 className="text-[16px] font-medium">{TITLE[data.report_kind]}</h3>
              {data.paragraphs
                .filter((p) => p.included)
                .map((p) => (
                  <Paragraph key={p.block_id} p={p} />
                ))}
              <div className="pt-[14px]">
                <div
                  data-signature="placeholder"
                  className="rounded-[6px] border border-dashed border-hair px-[10px] py-[8px]"
                >
                  <p className="text-[11px] text-ink-3">Firm signature applied at release</p>
                </div>
                {current?.city != null && <p>{current.city}</p>}
                {current?.report_date != null && <p>{current.report_date}</p>}
              </div>
            </article>
          </div>
        </section>
      </div>
    </div>
  );
}
