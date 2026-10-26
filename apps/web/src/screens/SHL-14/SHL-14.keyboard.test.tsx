// SHL-14 keyboard suite (P-06-T26; P-06 §5.6): the composer drawer takes focus when it opens,
// Tab runs tabs → fields → footer with Save draft and Save & send last, the Segmented controls move
// with the arrow keys, the due-date error is linked to its field, Escape closes a pristine drawer
// and gives focus back to its opener, and a dirty one asks "Discard changes?" first. axe runs in
// e2e/screens/SHL-14.spec.ts (Playwright).
import { client } from "@abacus/api-client/client";
import { toastStore } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { type JSX, useState } from "react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { positions, tabOrder } from "../../testing/keyboard";
import { renderRoutes } from "../../testing/support";
import { RequestComposer } from ".";
import { OPENS, type Shl14State, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
  toastStore.clear();
});

const OPENER = "+ Request";

/** BND-02's "+ Request" (or a row) opening the drawer, as the `?ov=request` overlay does. */
function Host({ state }: { state: Shl14State }): JSX.Element {
  const [open, setOpen] = useState(false);
  const { binderId, requestId } = OPENS[state];
  return (
    <>
      <button
        type="button"
        onClick={() => {
          setOpen(true);
        }}
      >
        {OPENER}
      </button>
      <RequestComposer
        binderId={binderId}
        requestId={requestId}
        open={open}
        onOpenChange={setOpen}
      />
    </>
  );
}

async function open(state: Shl14State): Promise<{ opener: HTMLElement; drawer: HTMLElement }> {
  restore = installFixtureMode(scenarios[state]);
  renderRoutes([{ path: "/", component: () => <Host state={state} /> }]);
  const opener = await screen.findByRole("button", { name: OPENER });
  opener.focus();
  fireEvent.click(opener);
  const drawer = await screen.findByRole("dialog");
  return { opener, drawer };
}

describe("SHL-14 keyboard (P-06 §5.6)", () => {
  it("focus moves into the drawer when it opens", async () => {
    const { drawer } = await open("a");
    await waitFor(() => {
      expect(drawer.contains(document.activeElement)).toBe(true);
    });
  });

  it("Tab runs the tabs, the fields, then Save draft and Save & send last", async () => {
    const { drawer } = await open("a");
    await within(drawer).findByRole("button", { name: "Save & send" });
    // The footer joins the tab order once the request can be saved (disabled buttons never do).
    fireEvent.change(within(drawer).getByLabelText("Request"), {
      target: { value: "ERISA fidelity bond — 2025 declarations page" },
    });
    fireEvent.change(within(drawer).getByLabelText("Description"), {
      target: { value: "ERISA §412 requires a fidelity bond." },
    });
    const category = within(drawer).getByRole("button", { name: /^Category/ });
    category.focus();
    fireEvent.keyDown(category, { key: "ArrowDown" });
    fireEvent.click(within(await screen.findByRole("menu")).getByText("Plan documents"));
    await waitFor(() => {
      expect(
        within(drawer).getByRole<HTMLButtonElement>("button", { name: "Save draft" }).disabled,
      ).toBe(false);
    });
    const at = positions(drawer, [
      /^Details$/,
      "Request",
      "Description",
      "Save draft",
      "Save & send",
    ]);
    expect(at).not.toContain(-1);
    expect([...at].sort((x, y) => x - y)).toEqual(at);
    const order = tabOrder(drawer);
    expect(order[order.length - 1]?.textContent).toBe("Save & send");
  });

  it("the tabs are a tablist the arrow keys move through", async () => {
    const { drawer } = await open("a");
    const details = await within(drawer).findByRole("tab", { name: "Details" });
    expect(details.getAttribute("aria-selected")).toBe("true");
    // Roving tabindex: only the selected tab is in the tab order.
    expect(within(drawer).getByRole("tab", { name: "Comments" }).tabIndex).toBe(-1);
    details.focus();
    fireEvent.keyDown(details, { key: "ArrowRight" });
    await waitFor(() => {
      expect(
        within(drawer).getByRole("tab", { name: "Comments" }).getAttribute("aria-selected"),
      ).toBe("true");
    });
  });

  it("e: the due-date error is linked to its field", async () => {
    const { drawer } = await open("e");
    const message = await within(drawer).findByText("Add a due date to send");
    const due = within(drawer).getByLabelText("Due");
    expect(due.getAttribute("aria-invalid")).toBe("true");
    const described = due.getAttribute("aria-describedby") ?? "";
    expect(described).not.toBe("");
    expect(document.getElementById(described)?.textContent).toBe(message.textContent);
  });

  it("Escape closes a pristine drawer and focus returns to its opener", async () => {
    const { opener, drawer } = await open("b");
    await within(drawer).findByText("Requested Sep 1 · due Sep 25");
    fireEvent.keyDown(drawer, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
    await waitFor(() => {
      expect(document.activeElement).toBe(opener);
    });
  });

  it("Escape on a dirty drawer asks Discard changes? and keeps the drawer until confirmed", async () => {
    const { opener, drawer } = await open("a");
    const field = await within(drawer).findByLabelText("Request");
    fireEvent.change(field, { target: { value: "ERISA fidelity bond — 2025 declarations page" } });
    fireEvent.keyDown(drawer, { key: "Escape" });
    const guard = await screen.findByRole("alertdialog", { name: "Discard changes?" });
    expect(drawer.isConnected).toBe(true);
    fireEvent.click(within(guard).getByRole("button", { name: "Discard" }));
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
    await waitFor(() => {
      expect(document.activeElement).toBe(opener);
    });
  });
});
