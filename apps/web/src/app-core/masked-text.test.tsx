// DEC-369 (review M-A): a sheet withheld from the reader is named, never shown; masked text pages
// render as plain text with the unread line where the server says so.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { MaskedTextView, TEXT_VIEW } from "./masked-text";

afterEach(cleanup);

describe("MaskedTextView", () => {
  it("names a withheld sheet and shows none of its cells", () => {
    render(
      <MaskedTextView
        width={296}
        text={{
          items: [{ page: 1, text: "SSN •••-••-6081", unread: true }],
          sheets: [{ name: "Payroll", rows: [], withheld: true }],
          truncated: false,
        }}
      />,
    );
    expect(screen.getByText("Payroll")).toBeTruthy();
    expect(screen.getByText(TEXT_VIEW.sheetWithheld)).toBeTruthy();
    expect(screen.getByText(TEXT_VIEW.unread)).toBeTruthy();
    expect(screen.getByText("SSN •••-••-6081")).toBeTruthy();
  });

  it("shows an onshore sheet's masked cells with no withheld line", () => {
    render(
      <MaskedTextView
        width={296}
        text={{
          items: [],
          sheets: [{ name: "Payroll", rows: [["Claire Feld", "•••-••-1234"]], withheld: false }],
          truncated: false,
        }}
      />,
    );
    expect(screen.getByText("Claire Feld · •••-••-1234")).toBeTruthy();
    expect(screen.queryByText(TEXT_VIEW.sheetWithheld)).toBeNull();
  });
});
