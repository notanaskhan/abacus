// P-11-T31 (TASK-5128): SHL-08's OCR additions. Row: "The viewer states how each page's text was
// read, low-confidence fields are announced to assistive technology, and no state renders without
// registered copy."
import type { ExtractedFieldsOut, ViewerPageOut } from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { defineScenarios, installFixtureMode, json } from "../../app-core/fixture-mode";
import { newQueryClient } from "../../testing/support";
import { COPY } from "./copy";
import { OcrNotes } from "./OcrNotes";

const VERSION = "0a110000-0000-4000-8000-000000000031";

function page(over: Partial<ViewerPageOut> = {}): ViewerPageOut {
  return {
    n: 1,
    width_pt: 612,
    height_pt: 792,
    rotation: 0,
    image_w: 1224,
    image_h: 1584,
    text_layer: false,
    pii_scan: "done",
    ...over,
  };
}

const FIELDS: ExtractedFieldsOut = {
  form_type: "w2",
  tax_year: 2025,
  corrected: false,
  form_map_version: "1",
  items: [
    {
      field_key: "w2.box1",
      label: "Form W-2 · box 1",
      value_type: "money",
      value_text: "268400.00",
      page: 1,
      bbox: { x: 1, y: 2, w: 3, h: 4 },
      confidence: 0.81,
      low_confidence: true,
      extractor_kind: "ocr_map",
      match_id: `ev:${VERSION}#field:w2.box1`,
    },
    {
      field_key: "w2.ssn",
      label: "Form W-2 · box a",
      value_type: "tin",
      mask_token: "•••-••-6081",
      page: 1,
      bbox: { x: 1, y: 2, w: 3, h: 4 },
      confidence: 0.88,
      low_confidence: true,
      extractor_kind: "ocr_map",
      match_id: `ev:${VERSION}#field:w2.ssn`,
    },
  ],
};

const scenarios = defineScenarios({
  ocr: {
    state: "ocr",
    handlers: {
      "GET /v1/evidence-versions/{version_id}/fields": () => json(FIELDS),
    },
  },
});

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

function show(pages: readonly ViewerPageOut[]): void {
  restore = installFixtureMode(scenarios.ocr);
  render(
    <QueryClientProvider client={newQueryClient()}>
      <OcrNotes versionId={VERSION} pages={pages} page={1} canRetry />
    </QueryClientProvider>,
  );
}

describe("SHL-08 OCR", () => {
  it("states how the page's text was read", () => {
    show([page({ text_source: "text_layer" })]);
    expect(document.querySelector("[data-text-source]")?.textContent).toBe(COPY.ocr.textLayer);
  });

  it("gives the page's confidence for an OCR page", () => {
    show([page({ text_source: "ocr", ocr: { mean_confidence: 0.94, low_confidence_words: 2 } })]);
    expect(document.querySelector("[data-text-source]")?.textContent).toContain("94%");
  });

  it("announces low-confidence fields, with a TIN as its mask only", async () => {
    show([page({ text_source: "ocr", ocr: { mean_confidence: 0.8, low_confidence_words: 9 } })]);
    await waitFor(() => {
      expect(document.querySelector("[data-low-confidence]")).not.toBeNull();
    });
    const list = document.querySelector("[data-low-confidence]");
    expect(list?.getAttribute("aria-live")).toBe("polite");
    expect(list?.textContent).toContain(COPY.ocr.low);
    expect(list?.textContent).toContain("•••-••-6081");
    expect(list?.textContent).not.toContain("000-00");
  });

  it("every refusal has registered words and offers a retry", () => {
    for (const refusal of Object.keys(COPY.ocr.refused) as (keyof typeof COPY.ocr.refused)[]) {
      show([
        page({ text_source: "none", ocr: { low_confidence_words: 0, refused_reason: refusal } }),
      ]);
      expect(document.querySelector("[data-ocr-refused]")?.textContent).toContain(
        COPY.ocr.refused[refusal],
      );
      expect(document.body.textContent).toContain(COPY.ocr.retry);
      cleanup();
      restore?.();
      restore = undefined;
    }
  });

  it("says nothing for a page with no facts", () => {
    show([page()]);
    expect(document.querySelector("[data-ocr-notes]")).toBeNull();
  });
});
