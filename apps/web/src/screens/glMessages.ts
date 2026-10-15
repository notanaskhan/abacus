// SPEC-034 (TASK-070): what became of a general ledger upload, in plain words. Fixed templates
// (ADR-111); the only values are code-computed amounts, account codes, months and counts.
import type { GlImportOut } from "@abacus/api-client";
import { usd } from "./importMessages";

const SYSTEMS: Record<string, string> = { qbo: "QuickBooks Online", xero: "Xero" };

function month(value: string): string {
  const [y, m] = value.split("-").map(Number);
  return new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, 1)).toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}

function accounts(gl: GlImportOut): string {
  return (gl.accounts ?? []).map((a) => `${a.code} (off by ${usd(a.difference)})`).join(", ");
}

export function glFailureMessage(gl: GlImportOut, system: string): string {
  const code = gl.failure_code ?? "";
  const looksLike = /^looks_like_(.+)$/.exec(code);
  if (looksLike !== null) {
    const other = SYSTEMS[looksLike[1] ?? ""] ?? "another system";
    return `This looks like a ${other} export, but you chose ${system}. Choose ${other} and upload it again.`;
  }
  switch (code) {
    case "period_mismatch":
      return (gl.months ?? []).length > 0
        ? `Your export doesn't cover the whole year: ${(gl.months ?? []).map(month).join(", ")} ${(gl.months ?? []).length === 1 ? "has" : "have"} no transactions. Export the full fiscal year and upload it again.`
        : "Your export has transactions outside the fiscal year. Set the report to the fiscal year exactly and export it again.";
    case "unbalanced": {
      const off = gl.accounts?.[0]?.difference;
      return off != null
        ? `Debits and credits in your export differ by ${usd(off)}. Export the report again without changes.`
        : "Debits and credits in your export don't balance. Export the report again without changes.";
    }
    case "roll_forward":
      return `These accounts don't agree with your trial balance: ${accounts(gl)}. Check both exports are for the same year end, then upload the general ledger again.`;
    case "missing_account":
      return `These accounts are in your trial balance but not in the general ledger: ${(gl.accounts ?? []).map((a) => a.code).join(", ")}. Export every account and upload it again.`;
    case "extra_account":
      return `These accounts are in the general ledger but not in your trial balance: ${(gl.accounts ?? []).map((a) => a.code).join(", ")}. Check both exports come from the same company.`;
    case "payload_too_large":
      return "The file is over 50 MB. Your auditor can help with a ledger this large.";
    case "unreadable":
    case "malformed_payload":
    case "invalid_amount":
      return "Some of the file couldn't be read. Export the report again without editing it.";
    case "unrecognised_format":
      return `This doesn't look like a ${system} general ledger export. Follow the steps above and upload the file it gives you.`;
    case "empty":
      return "This export has no transactions in it. Check the report period and export it again.";
    default:
      return "We couldn't check this file. Export it again following the steps above.";
  }
}

export function glStatusMessage(
  gl: GlImportOut,
  system: string,
): { tone: "info" | "ok" | "danger"; text: string } {
  switch (gl.status) {
    case "processing":
      return { tone: "info", text: "Checking your general ledger…" };
    case "waiting_for_tb":
      return {
        tone: "info",
        text: "Waiting for your trial balance: upload it above and we'll check the general ledger against it.",
      };
    case "reconciled":
      return {
        tone: "ok",
        text: `Received: ${(gl.line_count ?? 0).toLocaleString("en-US")} transactions, reconciled to your trial balance.`,
      };
    default:
      return { tone: "danger", text: glFailureMessage(gl, system) };
  }
}
