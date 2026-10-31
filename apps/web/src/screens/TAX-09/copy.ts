// TAX-09 · Tax-engine sync (T-01-T15): copy verbatim from the handoff's spec.md. Accrued never
// transmits or files: the export is a file for CCH Axcess, marked exported by a person.

export const COPY = {
  noChanges: "No changes needed",
  title: "2025 Form 1040",
  client: "Jonah & Claire Feld",
  approved: "Approved",
  syncLabel: "Tax-engine sync",
  actions: "Actions",
  history: "History",
  diagnostics: "Diagnostics",
  exportTitle: "Export to tax engine",
  exportBody: "Send approved return data to CCH Axcess",
  importTitle: "Import from tax engine",
  importBody: "Fetch the latest return data from CCH Axcess",
  uploadTitle: "Upload engine file",
  uploadBody: "An export or diagnostics file from CCH Axcess",
  openK1Package: "Open K-1 package",
  blocked: (approver: string, policy: string, k1: string | null): string =>
    k1 === null
      ? `Final approval required — ${approver} (${policy})`
      : `Final approval required — ${approver} (${policy}) · ${k1} K-1 is a Draft K-1 · pre-release`,
  notExportedTitle: "Not yet exported to tax engine",
  notExportedBody: "No export activity yet",
  importedTitle: "Return imported from tax engine",
  exportedTitle: "Return exported to tax engine",
  uploadedTitle: "Import pending approval",
  changedTitle: "Accrued changed after the last import",
  changedBody: (n: number, fields: string): string => `${String(n)} fields (${fields})`,
  diagnosticsTitle: "Diagnostics returned",
  diagnosticsBody: (errors: number, info: number): string =>
    `${String(errors)} errors · ${String(info)} informational`,
  justNow: "Just now",
  connection: "CCH Axcess Tax · Connected · firm token",
  settings: "Settings",
  /** The footer's link to the binders index (TAX-09 → BND-01). */
  binder: "Binder",
  /** The footer's link to the inbox (TAX-09 → INB-01). */
  inbox: "Inbox",
  settingsTip: "Opens WB-11 · Integration detail",
  markTitle: "Mark exported",
  markBody: (file: string): string =>
    `Download ${file}, import it in CCH Axcess, then mark it exported here.`,
  download: "Download",
  markConfirm: "Mark exported",
  cancel: "Cancel",
  exportFailed: "The export file couldn't be generated.",
  sheetTitle: (version: string): string => `Import from tax engine · ${version}`,
  close: "Close",
  summary: (n: number): string =>
    `${String(n)} fields differ between CCH Axcess and Accrued. 0 conflict with cited workpaper values.`,
  columns: {
    field: "Field",
    accrued: "Accrued",
    engine: "CCH Axcess",
    cause: "Cause",
    accept: "Accept",
  },
  acceptRow: (field: string): string => `Accept ${field}`,
  reject: "Reject import",
  approve: "Approve import",
  helper:
    "Approving creates checkpoint 'Engine import V3' and records 'Return import approved by Samuel Ito'.",
  approvedToast: "Import approved",
  rejectedToast: "Import rejected",
  rejectReason: "Rejected by the reviewer",
} as const;

/** The import diff's field names (the engine file's keys, as the return reads them). */
export const FIELDS: Readonly<Record<string, string>> = {
  "f1040es.2026.vouchers": "Form 1040-ES (2026) vouchers",
  "refund.direct_deposit": "Refund direct deposit",
  "f8879.signature_method": "Form 8879 signature method",
  "il1040.schnr.il_income": "IL-1040 Schedule NR — Illinois-source income",
  "co0104pn.co_income": "CO DR 0104PN — Colorado-source income",
  "f1040.l2a": "Form 1040 line 2a",
  "it201.l20": "IT-201 line 20",
  "it201.l33": "IT-201 line 33",
};

/** The cause line by code, filled from the engine file's figures. */
export const CAUSES: Readonly<Record<string, (f: Readonly<Record<string, string>>) => string>> = {
  entered_in_engine: (f) =>
    `Entered in CCH Axcess by ${f.by ?? ""} · ${f.pct ?? ""}% of 2025 tax ${f.tax ?? ""} = ${f.safe_harbour ?? ""} − withholding ${f.withholding ?? ""} = ${f.balance ?? ""} ÷ ${f.quarters ?? ""}`,
  direct_deposit_authorization: (f) => `From the direct deposit authorization (${f.on ?? ""})`,
  firm_default: () => "Firm default (ADM-08 engine settings)",
  engine_state_allocation: (f) =>
    `Engine state allocation; Accrued holds it only in the TXI-03 sourcing schedule, where it equals ${f.pct ?? ""}% × ${f.total ?? ""}`,
};
