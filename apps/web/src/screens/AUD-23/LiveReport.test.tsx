// S33 partials round (A-07-T34; DEC-3137): AUD-23 on the live report. The paper is the server's
// included template blocks; a choice posts with the version seen; Approve renders only with
// `sign_off.l4` and a host to approve through; a modification asks the partner's card.
import type { AuditReportOut } from "@abacus/api-client";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import type { JSX } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { cleanup } from "@testing-library/react";
import { json, mockApi, renderRoutes } from "../../testing/support";
import { LiveReport } from "./LiveReport";

afterEach(cleanup);

const WI = "00000000-0000-4000-8000-0000000004a1";
const P = `/v1/audits/${WI}/report`;

function report(over: Partial<AuditReportOut> = {}): AuditReportOut {
  return {
    allowed_actions: ["report.draft", "report.request_decision", "report.generate", "sign_off.l4"],
    choices: [
      {
        field: "opinion_form",
        value: "unmodified",
        locked_by: null,
        decision_card_id: null,
        reason_code: null,
      },
      {
        field: "going_concern",
        value: false,
        locked_by: "AUD-19 going concern",
        decision_card_id: null,
        reason_code: null,
      },
      {
        field: "erisa_supplemental_schedules",
        value: true,
        locked_by: null,
        decision_card_id: null,
        reason_code: "ERISA-SUPP",
      },
      {
        field: "other_information",
        value: false,
        locked_by: null,
        decision_card_id: null,
        reason_code: null,
      },
    ],
    current_version: {
      version_no: 2,
      content_hash: "a".repeat(64),
      report_date: null,
      city: null,
      created_by_name: "Hannah Leclerc",
      created_at: "2026-10-02T16:20:00Z",
      approved_by_name: null,
      approved_at: null,
    },
    documents: [],
    eqr_required_not_concurred: false,
    framework: "US GAAP · ASC 962",
    paragraphs: [
      {
        block_id: "opinion",
        heading: "Opinion",
        text: "In our opinion …",
        included: true,
        reason_code: null,
        citations: [],
      },
      {
        block_id: "eom",
        heading: "Emphasis of Matter",
        text: "Hidden",
        included: false,
        reason_code: null,
        citations: [],
      },
    ],
    report_kind: "audit",
    status: "draft",
    version: 2,
    ...over,
  };
}

function show(data: AuditReportOut, approve?: () => void): { bodies: unknown[] } {
  const seen = { bodies: [] as unknown[] };
  mockApi({
    [`GET ${P}`]: () => json(data),
    [`PATCH ${P}/choices`]: (call) => {
      seen.bodies.push(call.body);
      return json({ ...data, version: data.version + 1 });
    },
    [`POST ${P}/request-decision`]: () => json(data),
  });
  const Page = (): JSX.Element => (
    <LiveReport workItemId={WI} {...(approve === undefined ? {} : { onApprove: approve })} />
  );
  renderRoutes([{ path: "/", component: Page }]);
  return seen;
}

describe("AUD-23 live report", () => {
  it("draws only the included blocks under the DRAFT mark", async () => {
    show(report());
    expect(await screen.findByText("In our opinion …")).toBeTruthy();
    expect(screen.queryByText("Hidden")).toBeNull();
    expect(document.querySelector("[data-watermark='draft']")).not.toBeNull();
  });

  it("posts a choice with the version the person saw", async () => {
    const seen = show(report());
    fireEvent.click(await screen.findByRole("switch", { name: "Other information (AU-C 720)" }));
    await waitFor(() => {
      expect(seen.bodies).toEqual([{ field: "other_information", value: true, seen_version: 2 }]);
    });
  });

  it("keeps going concern locked to AUD-19", async () => {
    show(report());
    const toggle = await screen.findByRole<HTMLButtonElement>("switch", {
      name: "Going concern section",
    });
    expect(toggle.disabled).toBe(true);
  });

  it("offers Approve only with sign_off.l4 and a host", async () => {
    show(report());
    await screen.findByText("In our opinion …");
    expect(screen.queryByRole("button", { name: /Approve report/ })).toBeNull();
    cleanup();
    let approved = 0;
    show(report(), () => {
      approved += 1;
    });
    fireEvent.click(await screen.findByRole("button", { name: /Approve report/ }));
    expect(approved).toBe(1);
  });

  it("a modification without the partner's card asks for it and blocks approval", async () => {
    const data = report({
      choices: report().choices.map((c) =>
        c.field === "opinion_form" ? { ...c, value: "qualified" } : c,
      ),
    });
    show(data, () => undefined);
    expect(await screen.findByText("Decision required")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Request partner decision…" })).toBeTruthy();
    expect(
      screen.getByRole<HTMLButtonElement>("button", { name: /Approve report/ }).disabled,
    ).toBe(true);
  });
});

describe("AUD-23 live report: Request EQR… (DV-4; DF-05)", () => {
  it("shows only while an EQR is required and not concurred, and only asks", async () => {
    const asked: string[] = [];
    mockApi({
      [`GET ${P}`]: () => json(report({ eqr_required_not_concurred: true })),
      [`POST /v1/audits/${WI}/eqr/request`]: () => {
        asked.push("request");
        return new Response(null, { status: 204 });
      },
    });
    renderRoutes([{ path: "/", component: () => <LiveReport workItemId={WI} /> }]);
    fireEvent.click(await screen.findByRole("button", { name: "Request EQR…" }));
    await waitFor(() => {
      expect(asked).toHaveLength(1);
    });
  });

  it("is absent once the EQR has concurred, or for an approved report", async () => {
    show(report({ eqr_required_not_concurred: false }));
    await screen.findByText("In our opinion …");
    expect(screen.queryByRole("button", { name: "Request EQR…" })).toBeNull();
    cleanup();
    show(report({ eqr_required_not_concurred: true, status: "approved" }));
    await screen.findByText("In our opinion …");
    expect(screen.queryByRole("button", { name: "Request EQR…" })).toBeNull();
  });
});
