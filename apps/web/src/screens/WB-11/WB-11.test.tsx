import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { DISCONNECT_NAME, IntegrationDrawer, WB11_SCENARIOS } from ".";

// W-01-T16/T17 (WB-11 a to f): each state renders from the seed; Disconnect stays disabled until
// the integration's name is typed exactly; the client-ledger view offers no firm-side connect.

afterEach(cleanup);

describe("WB-11 integration drawer", () => {
  it.each(WB11_SCENARIOS)("renders state %s", (st) => {
    const { container } = render(<IntegrationDrawer st={st} />);
    expect(container.querySelector("[data-screen='WB-11']")?.getAttribute("data-scenario")).toBe(
      st,
    );
  });

  it("keeps Disconnect disabled until CCH Axcess Tax is typed exactly", () => {
    render(<IntegrationDrawer st="e" />);
    const button = screen.getByRole("button", { name: "Disconnect" });
    expect(button).toHaveProperty("disabled", true);
    const field = screen.getByLabelText(`Type ${DISCONNECT_NAME}`);
    fireEvent.change(field, { target: { value: "CCH Axcess tax" } });
    expect(button).toHaveProperty("disabled", true);
    fireEvent.change(field, { target: { value: DISCONNECT_NAME } });
    expect(button).toHaveProperty("disabled", false);
  });

  it("lists Copperleaf and Ridgeline as client-connected with no connect control", () => {
    render(<IntegrationDrawer st="d" />);
    expect(screen.getByText("Copperleaf Coffee Roasters, Inc.")).toBeTruthy();
    expect(screen.getByText("Ridgeline Property Partners, LP")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /connect a client/i })).toBeNull();
  });
});
