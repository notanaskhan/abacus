// SPEC-028 §4.8 (TASK-053): what went wrong with an uploaded export, in plain words. Every
// message is a fixed template (ADR-111); the only values in them are computed by code on the
// server (the difference, the period end found) or come from the format list.

export type ImportFailure = {
  code: string;
  system: string; // the system chosen
  difference?: string | null; // debits minus credits, a decimal string
  foundPeriodEnd?: string | null; // ISO date
  periodEnd?: string | null; // the engagement's year end, ISO date
};

const SYSTEMS: Record<string, string> = { qbo: "QuickBooks Online", xero: "Xero" };

export function longDate(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1)).toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
    timeZone: "UTC",
  });
}

export function usd(decimal: string): string {
  const value = Math.abs(Number(decimal));
  return value.toLocaleString("en-US", { style: "currency", currency: "USD" });
}

export function importFailureMessage(f: ImportFailure): string {
  const looksLike = /^looks_like_(.+)$/.exec(f.code);
  if (looksLike !== null) {
    const other = SYSTEMS[looksLike[1] ?? ""] ?? "another system";
    return `This looks like a ${other} export, but you chose ${f.system}. Choose ${other} and upload it again.`;
  }
  switch (f.code) {
    case "unbalanced":
      return f.difference != null
        ? `Debits and credits differ by ${usd(f.difference)}. Check the export covers every account, then upload it again.`
        : "Debits and credits don't balance. Check the export covers every account, then upload it again.";
    case "period_mismatch":
      return f.foundPeriodEnd != null && f.periodEnd != null
        ? `This export is as of ${longDate(f.foundPeriodEnd)}; we need ${longDate(f.periodEnd)}. Run the report for the year end and export it again.`
        : "This export is for a different date than the year end. Run the report for the year end and export it again.";
    case "control_totals_mismatch":
      return "The export's total row doesn't match its lines. Export the report again without changes.";
    case "unsupported_currency":
      return "This export isn't in US dollars. Only US dollar trial balances can be used.";
    case "duplicate_account":
      return "The same account appears more than once. Export the report again without changes.";
    case "empty":
    case "zero_total":
      return "This export has no balances in it. Check the report period and export it again.";
    case "unrecognised_format":
      return `This doesn't look like a ${f.system} trial balance export. Follow the steps above and upload the file it gives you.`;
    case "invalid_amount":
    case "malformed_payload":
      return "Some amounts or account names couldn't be read. Export the report again without editing it.";
    case "payload_too_large":
      return "The file is over 20 MB.";
    case "empty_file":
      return "The file is empty.";
    case "file_refused":
      return `We couldn't accept this file. Please export it again from ${f.system}.`;
    case "already_connected":
      return "Your accounting system is connected, so an export isn't needed.";
    case "unknown_format":
      return "Choose your accounting system first.";
    default:
      return "We couldn't read this file. Export it again following the steps above.";
  }
}
