// SPEC-033 (TASK-064): why a file was suggested for a request, as fixed labels. The only values
// in them are a date, account digits or file-name words, all computed by code (ADR-111).
import type { ReasonOut } from "@abacus/api-client";
import { longDate } from "./importMessages";

export function reasonLabel(reason: ReasonOut): string {
  const value = reason.value ?? "";
  switch (reason.code) {
    case "kind":
      return value === "bank_statement" ? "Bank statement" : "Aging report";
    case "date":
      return value === "" ? "Year end" : `Covers ${longDate(value)}`;
    case "account":
      return `Account ending ${value}`;
    case "holder":
      return "In the company's name";
    case "file_name":
      return `File name: ${value}`;
  }
}
