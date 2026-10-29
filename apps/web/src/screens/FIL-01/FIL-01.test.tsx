// FIL-01 (N-01-T16; docs/screens/FIL-01.md): "Ten scenarios render, no write control appears, and
// the virtual statements foot to 512,400." Each artboard's scenario through the generated client
// in fixture mode; axe and parity are e2e (N-01-T25 to T28).
import { client } from "@abacus/api-client/client";
import { cleanup, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import {
  FIL01_STATES,
  type Fil01State,
  OPENS,
  REVEALED_TIN,
  scenarios,
} from "../../fixtures/scenarios/FIL-01";
import { renderRoutes } from "../../testing/support";
import { FilesPage } from ".";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

const WRITES = /Upload|Move…|Void|Delete|Sign off…|Lock$|Upload new version|\+ New/;

async function show(state: Fil01State): Promise<void> {
  restore = installFixtureMode(scenarios[state]);
  renderRoutes([
    {
      path: "/",
      component: () => (
        <FilesPage
          node={OPENS[state].node}
          doc={OPENS[state].doc}
          viewer="Olivia Brandt"
          reveal={() => Promise.resolve(REVEALED_TIN)}
          revealedValue={state === "f" ? REVEALED_TIN : null}
          frame
        />
      ),
    },
  ]);
  await waitFor(() => {
    expect(document.querySelector('[data-files="tree"]')).toBeTruthy();
  });
}

describe("FIL-01: every artboard renders read-only", () => {
  it.each(FIL01_STATES)("%s renders and offers no write control", async (state) => {
    await show(state);
    const labels = [...document.querySelectorAll("button")].map((b) => b.textContent);
    expect(labels.filter((l) => WRITES.test(l))).toEqual([]);
  });
});

describe("FIL-01a: Ridgeline's source documents", () => {
  it("12 documents, 7 virtual, and the statements foot to 512,400 tied to 5500", async () => {
    await show("a");
    await waitFor(() => {
      expect(document.querySelector('[data-files="count"]')?.textContent).toBe(
        "12 documents · 7 virtual",
      );
    });
    await waitFor(() => {
      expect(document.querySelector('[data-files="tie"]')?.textContent).toContain("512,400");
    });
    expect(document.querySelector('[data-files="tie"]')?.textContent).toContain("ties to 5500");
    expect(screen.getByText("XX-XXX0287")).toBeTruthy();
  });
});

describe("FIL-01c, d, f, g", () => {
  it("c: the March 1099-DIV is struck with its replacement", async () => {
    await show("c");
    await waitFor(() => {
      expect(
        screen.getByText(/Replaced by Iyer_2025_1099DIV_Halvard_Corrected\.pdf/),
      ).toBeTruthy();
    });
  });

  it("d: the hold banner, and no reveal for a metadata-only reader", async () => {
    await show("d");
    await waitFor(() => {
      expect(document.querySelector('[data-files="hold"]')?.textContent).toContain(
        "placed by Victor Hammond",
      );
    });
    expect(screen.queryByText("Reveal (logged)")).toBeNull();
  });

  it("f: the revealed TIN with the logged note", async () => {
    await show("f");
    await waitFor(() => {
      expect(document.querySelector('[data-files="tin"]')?.textContent).toBe(REVEALED_TIN);
    });
    expect(screen.getByText("Logged to the audit log as Olivia Brandt")).toBeTruthy();
  });

  it("g: Signed authorizations is empty", async () => {
    await show("g");
    await waitFor(() => {
      expect(screen.getByText("No signed authorizations yet.")).toBeTruthy();
    });
  });
});
