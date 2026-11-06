// A-06-T30 (TASK-5126): AUD-20 in fixture mode. Row: "Every AUD-20 artboard renders from its
// scenario, hovering 16,500,000 fans its two sources, and the client preview shows no checklist, no
// source link and no studio link."
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode } from "../../app-core/fixture-mode";
import { AUD20_ENGAGEMENT } from "../../fixtures/seed/aud20";
import { newQueryClient } from "../../testing/support";
import { COPY } from "./copy";
import { type Aud20State, scenarios } from "./scenarios";
import { FsDisclosurePane, type FsDisclosureProps } from "./Statements";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(state: Aud20State, props: Partial<FsDisclosureProps> = {}): void {
  restore = installFixtureMode(scenarios[state]);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <FsDisclosurePane engagementId={AUD20_ENGAGEMENT} {...props} />
    </QueryClientProvider>,
  );
}

describe("AUD-20", () => {
  it("a: all tie, and hovering 16,500,000 fans its two sources", async () => {
    show("a");
    await waitFor(() => {
      expect(document.querySelector("[data-tie]")?.textContent).toBe("63 of 63 tie");
    });
    const figure = document.querySelector('[data-figure="total_investments:2025"]');
    expect(figure?.textContent).toBe("16,500,000");
    fireEvent.mouseEnter(figure as Element);
    const sources = document.querySelector("[data-sources]");
    expect(sources?.textContent).toContain("Final TB · TB!E14");
    expect(sources?.textContent).toContain("Harborline Net Trust Assets 12-31-2025.pdf");
  });

  it("a: the checklist counts 97 + 45 + 0 = 142", async () => {
    show("a");
    await waitFor(() => {
      expect(document.querySelector("[data-summary]")?.textContent).toContain("142 items");
    });
    const summary = document.querySelector("[data-summary]")?.textContent;
    expect(summary).toContain("Yes 97");
    expect(summary).toContain("N/A 45");
    expect(summary).toContain("No 0");
  });

  it("a2: the send sheet names Dana, and sending stays off until C10", async () => {
    show("a2", { sending: true });
    await waitFor(() => {
      expect(document.querySelector('[data-sheet="send-draft"]')).not.toBeNull();
    });
    const sheet = document.querySelector('[data-sheet="send-draft"]');
    expect(sheet?.textContent).toContain("Dana Kowalski");
    expect(sheet?.querySelector("button:disabled")?.textContent).toBe(COPY.send.send);
  });

  it("b: 62 of 63, benefits off 14,850, and the card opens RJE-1", async () => {
    const opened: string[] = [];
    show("b", {
      onMismatch: (focus) => {
        opened.push(focus);
      },
    });
    await waitFor(() => {
      expect(document.querySelector("[data-tie]")?.textContent).toBe("62 of 63 tie");
    });
    expect(document.querySelector("[data-off]")?.textContent).toBe("off 14,850");
    const open = [...document.querySelectorAll("button")].find(
      (b) => b.textContent === COPY.mismatch.open,
    );
    fireEvent.click(open as Element);
    expect(opened).toEqual(["RJE-1"]);
  });

  it("c: drafting shows the skeleton and the agent's line", async () => {
    show("c");
    await waitFor(() => {
      expect(document.querySelector("[data-drafting]")?.textContent).toContain(COPY.drafting);
    });
  });

  it("d: the client preview has a watermark, no checklist and no source link", async () => {
    show("d", { preview: true });
    await waitFor(() => {
      expect(document.querySelector("[data-watermark]")).not.toBeNull();
    });
    expect(document.querySelector('[data-pane="checklist"]')).toBeNull();
    expect(document.querySelector("button[data-figure]")).toBeNull();
    expect(document.body.textContent).not.toContain("statements studio");
    expect(document.querySelector("[data-tie]")).toBeNull();
  });

  it("e: approved by management", async () => {
    show("e");
    await waitFor(() => {
      expect(document.body.textContent).toContain(COPY.approved);
    });
  });

  it("f: Note 3's hierarchy reads 16,500,000", async () => {
    show("f", { segment: "notes" });
    await waitFor(() => {
      expect(document.querySelector('[data-note="3"]')?.textContent).toContain("16,500,000");
    });
  });

  it("off: the flag's designed state", async () => {
    show("off");
    await waitFor(() => {
      expect(document.querySelector("[data-off]")).not.toBeNull();
    });
  });
});
