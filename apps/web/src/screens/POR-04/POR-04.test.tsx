// POR-04 · Request detail / ignore reason sheet (R-01-T12). One test per artboard on its fixture
// scenario (a–g), the contract's acceptance and AVOID lines, and the task's acceptance: "States
// a, b, c, d and g pass full stack, e and f render from fixtures with one primary button each,
// and Esc returns focus to the invoking row." Full stack and axe run in
// e2e/screens/por-04-request-sheet.spec.ts (Playwright, R-01-T21).
import { client } from "@abacus/api-client/client";
import { Toaster } from "@abacus/ui";
import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import {
  type FixtureHandler,
  type Scenario,
  installFixtureMode,
  json,
} from "../../app-core/fixture-mode";
import { SHEET_UPLOADED, freshScenario } from "../../fixtures/scenarios/POR-04";
import { FELD } from "../../fixtures/seed/portal-documents";
import { renderRoutes } from "../../testing/support";
import { type POR04Hold, PortalRequest } from ".";
import { ARTBOARD, type Por04State, STATES, scenarios } from "./scenarios";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

interface Seen {
  calls: { method: string; path: string; body: unknown }[];
}

function holdOf(state: Por04State): POR04Hold {
  const board = ARTBOARD[state];
  return {
    ...(board.ignoreOpen === true ? { ignoreOpen: true } : {}),
    ...(board.uploading === undefined ? {} : { uploading: board.uploading }),
    ...(board.question === undefined ? {} : { question: board.question }),
    ...(board.decision === undefined ? {} : { decision: board.decision }),
  };
}

function install(state: Por04State, over: Record<string, FixtureHandler> = {}): Seen {
  const seen: Seen = { calls: [] };
  const base = freshScenario(state);
  const scenario: Scenario = { ...base, handlers: { ...base.handlers, ...over } };
  const handlers = Object.fromEntries(
    Object.entries(scenario.handlers).map(([key, handler]) => [
      key,
      ((request) => {
        seen.calls.push({ method: request.method, path: request.path, body: request.body });
        return handler(request);
      }) satisfies FixtureHandler,
    ]),
  );
  restore = installFixtureMode({ ...scenario, handlers });
  return seen;
}

function show(
  state: Por04State,
  options: { over?: Record<string, FixtureHandler>; requestId?: string; mobile?: boolean } = {},
): Seen {
  const seen = install(state, options.over);
  renderRoutes([
    {
      path: "/",
      component: () => (
        <>
          <PortalRequest
            requestId={options.requestId ?? ARTBOARD[state].requestId}
            mobile={options.mobile === true}
            hold={holdOf(state)}
          />
          <Toaster />
        </>
      ),
    },
  ]);
  return seen;
}

async function sheet(): Promise<HTMLElement> {
  return screen.findByRole("dialog");
}

function primaries(root: HTMLElement): HTMLElement[] {
  return [...root.querySelectorAll<HTMLElement>("[data-variant='primary']")];
}

const BANNED = [
  /Accrued/,
  /\bAgent\b/,
  /\bissue\b/i,
  /TXP-10/,
  /review point/i,
  /Action required/,
  /confidence/i,
  /Uploaded – needs review/,
  /Received ✓/,
];

function avoid(root: HTMLElement): void {
  const text = root.textContent;
  for (const word of BANNED) expect(text).not.toMatch(word);
  expect(primaries(root).length).toBeLessThanOrEqual(1);
}

describe("POR-04 artboards", () => {
  it("defines a to g, Claire Feld's except e (Ben Ashby) and f (Owen Calder)", () => {
    expect(STATES).toEqual(["a", "b", "c", "d", "e", "f", "g"]);
    for (const s of ["a", "b", "c", "d", "g"] as const) {
      expect(scenarios[s].persona).toBe("claire-feld");
    }
    expect(scenarios.e.persona).toBe("ben-ashby");
    expect(scenarios.f.persona).toBe("owen-calder");
  });

  it("POR-04a to do: the 1095-C, why we need it, last year's file and Kevin's comment", async () => {
    show("a");
    const box = await sheet();
    expect(
      await within(box).findByRole("heading", { name: "Form 1095-C From Mercer Hill Health" }),
    ).toBeTruthy();
    expect(within(box).getByText("Request")).toBeTruthy();
    expect(within(box).getByText("To do · requested Feb 3")).toBeTruthy();
    expect(within(box).getByText("Why we need it")).toBeTruthy();
    expect(within(box).getByText(/You don't attach it to your return/)).toBeTruthy();
    expect(within(box).getByText("Drop the file here")).toBeTruthy();
    expect(within(box).getByText("PDF, JPG, PNG, HEIC, XLSX · up to 50 MB")).toBeTruthy();
    expect(
      within(box).getByText(
        "Last year you sent Claire_Feld_2024_1095C_MercerHill.pdf on Mar 3, 2025.",
      ),
    ).toBeTruthy();
    expect(await within(box).findByText("Kevin Osei · Brightwater Hale")).toBeTruthy();
    expect(within(box).getByText(/Mercer Hill usually posts these/)).toBeTruthy();
    expect(within(box).getByText("Visible to you and Brightwater Hale")).toBeTruthy();
    expect(within(box).getByPlaceholderText("Write a comment…")).toBeTruthy();
    expect(within(box).getByRole("button", { name: "This doesn't apply to me…" })).toBeTruthy();
    const [primary] = primaries(box);
    expect(primary?.textContent).toBe("Upload…");
    avoid(box);
  });

  it("POR-04b ignore reason: three reasons, a note for Kevin, and Mark not applicable", async () => {
    const seen = show("b");
    const box = await sheet();
    const group = await within(box).findByRole("radiogroup", { name: "Why doesn't this apply?" });
    const options = within(group).getAllByRole("radio");
    expect(options.map((o) => o.getAttribute("aria-label"))).toEqual([
      "Not applicable this year",
      "Already sent another way",
      "I don’t have this",
    ]);
    const save = within(box).getByRole("button", { name: "Mark not applicable" });
    expect((save as HTMLButtonElement).disabled).toBe(true); // a reason is required
    const note = await within(box).findByLabelText("Add a note for Kevin (optional)");
    fireEvent.click(options[0] as HTMLElement);
    fireEvent.change(note, { target: { value: "We had no employer coverage in 2025." } });
    fireEvent.click(save);
    await waitFor(() => {
      const ignore = seen.calls.find((c) => c.path.endsWith("/ignore"));
      expect(ignore?.body).toEqual({
        reason: "not_this_year",
        note: "We had no employer coverage in 2025.",
      });
    });
    avoid(box);
  });

  it("POR-04c received by email: the seeded day's receipt, the file and size, no Withdraw", async () => {
    show("c");
    const box = await sheet();
    expect(await within(box).findByText("✓ Received by email Sep 14")).toBeTruthy();
    expect(within(box).getByText("Feld_1095C_2025.pdf")).toBeTruthy();
    expect(within(box).getByText("412 KB")).toBeTruthy();
    expect(within(box).queryByRole("button", { name: "Withdraw" })).toBeNull();
    expect(
      within(box).getByText(
        "Brightwater Hale will check it and let you know if anything is missing.",
      ),
    ).toBeTruthy();
    avoid(box);
  });

  it("POR-04c portal-upload variant: You uploaded, and Withdraw asks with the DF-15 words", async () => {
    const seen = show("c", {
      over: {
        "GET /v1/portal/request-items/{item_id}": () => json(SHEET_UPLOADED),
        "POST /v1/engagements/{engagement_id}/evidence-versions/{version_id}/withdraw": () =>
          json({}),
      },
    });
    const box = await sheet();
    expect(await within(box).findByText("✓ You uploaded Sep 14")).toBeTruthy();
    fireEvent.click(within(box).getByRole("button", { name: "Withdraw" }));
    const confirm = await screen.findByRole("alertdialog");
    expect(
      within(confirm).getByText(
        "Withdraw this file? Brightwater Hale's team won't use it. It's kept securely for 30 days, then erased.",
      ),
    ).toBeTruthy();
    fireEvent.click(within(confirm).getByRole("button", { name: "Withdraw" }));
    await waitFor(() => {
      expect(seen.calls.some((c) => c.path.endsWith("/withdraw"))).toBe(true);
    });
  });

  it("POR-04d returned: red-tint Returned · wrong year, Kevin's note and the struck file", async () => {
    show("d");
    const box = await sheet();
    expect(await within(box).findByText("Returned · wrong year")).toBeTruthy();
    expect(
      within(box).getByText(/This is the 2024 form\. We need the 2025 Form 1095-C\./),
    ).toBeTruthy();
    expect(within(box).getByText(/— Kevin Osei, Sep 14/)).toBeTruthy();
    const struck = within(box).getByText("Feld_1095C_2024.pdf");
    expect(struck.className).toMatch(/line-through/);
    expect(primaries(box)[0]?.textContent).toBe("Upload…");
    avoid(box);
  });

  it("POR-04e question: Sound Electric's context, the answer and one primary Send answer", async () => {
    show("e");
    const box = await sheet();
    expect(within(box).getByText("Question")).toBeTruthy();
    expect(
      within(box).getByRole("heading", { name: "What was the $3,200 payment to Sound Electric?" }),
    ).toBeTruthy();
    expect(within(box).getByText("Aug 18, 2026 · check #2285")).toBeTruthy();
    expect(within(box).getByText("Front Range Bank ••4410")).toBeTruthy();
    expect(within(box).getByText(/Repairs were \$640 in July/)).toBeTruthy();
    expect(within(box).getByText(/SoundElectric_INV-SE-1187\.pdf/)).toBeTruthy();
    const send = primaries(box);
    expect(send.map((b) => b.textContent)).toEqual(["Send answer"]);
    fireEvent.click(send[0] as HTMLElement);
    expect(await screen.findByText("Sent to Brightwater Hale")).toBeTruthy();
    avoid(box);
  });

  it("POR-04f decision: the §754 figures, due today, one primary Send decision", async () => {
    show("f");
    const box = await sheet();
    expect(within(box).getByText("Decision")).toBeTruthy();
    expect(within(box).getByText("Answer by 5:00 PM CT today")).toBeTruthy();
    // 5/35 × 2,319,835 = 331,405 and 360,000 − 331,405 = 28,595, computed by the fixture's code.
    expect(within(box).getByText(/\$331,405/)).toBeTruthy();
    expect(within(box).getByText(/\$28,595 difference/)).toBeTruthy();
    const send = primaries(box);
    expect(send.map((b) => b.textContent)).toEqual(["Send decision"]);
    expect((send[0] as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(within(box).getByRole("radio", { name: "Yes — make the election" }));
    expect((send[0] as HTMLButtonElement).disabled).toBe(false);
    avoid(box);
  });

  it("POR-04g uploading: the 1095-C's row at 46%, held for review", async () => {
    show("g");
    const box = await sheet();
    const bar = await within(box).findByRole("progressbar", { name: "Feld_1095C_2025.pdf" });
    expect(bar.getAttribute("aria-valuenow")).toBe("46");
    avoid(box);
  });
});

describe("POR-04 behaviour", () => {
  it("a comment goes to the shared thread and shows at once", async () => {
    const seen = show("a");
    const box = await sheet();
    const composer = await within(box).findByPlaceholderText("Write a comment…");
    fireEvent.change(composer, { target: { value: "I'll download it tonight." } });
    fireEvent.keyDown(composer, { key: "Enter" });
    await waitFor(() => {
      const post = seen.calls.find((c) => c.method === "POST" && c.path.endsWith("/comments"));
      expect(post?.body).toEqual({ text: "I'll download it tonight." });
    });
    expect(await within(box).findByText("I'll download it tonight.")).toBeTruthy();
  });

  it("Upload… sends the file through the request's own upload with an intent", async () => {
    const seen = show("a");
    const box = await sheet();
    await within(box).findByRole("heading", { name: "Form 1095-C From Mercer Hill Health" });
    const input = box.querySelector<HTMLInputElement>("input[type='file']");
    expect(input).not.toBeNull();
    const file = new File(["%PDF-1.4"], "Feld_1095C_2025.pdf", { type: "application/pdf" });
    fireEvent.change(input as HTMLInputElement, { target: { files: [file] } });
    await waitFor(() => {
      expect(seen.calls.some((c) => c.path.endsWith("/upload-intents"))).toBe(true);
      expect(
        seen.calls.some((c) => c.path.endsWith(`/request-items/${FELD.form1095c}/uploads`)),
      ).toBe(true);
    });
  });

  it("R-01-T12 acceptance: Esc closes the sheet and returns focus to the invoking row", async () => {
    install("a");
    function Host() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <button
            type="button"
            onClick={() => {
              setOpen(true);
            }}
          >
            Form 1095-C From Mercer Hill Health
          </button>
          {open && (
            <PortalRequest
              requestId={FELD.form1095c}
              onClose={() => {
                setOpen(false);
              }}
            />
          )}
        </>
      );
    }
    renderRoutes([{ path: "/", component: Host }]);
    const row = await screen.findByRole("button", { name: "Form 1095-C From Mercer Hill Health" });
    row.focus();
    fireEvent.click(row);
    const box = await sheet();
    await within(box).findByText("To do · requested Feb 3");
    fireEvent.keyDown(box, { key: "Escape" });
    await waitFor(() => {
      expect(screen.queryByRole("dialog")).toBeNull();
    });
    await waitFor(() => {
      expect(document.activeElement).toBe(row);
    });
  });

  it("INV-4: a request outside the grant reads as not available, nothing more", async () => {
    show("a", { requestId: "00000000-0000-4000-8000-00000000dead" });
    const box = await sheet();
    expect(await within(box).findByText("This request isn't available.")).toBeTruthy();
    avoid(box);
  });

  it("390: the sheet takes the phone's width with Take a photo under the drop area", async () => {
    show("a", { mobile: true });
    const box = await sheet();
    expect(await within(box).findByRole("button", { name: "Take a photo" })).toBeTruthy();
    expect(box.className).toMatch(/w-full/);
  });
});
