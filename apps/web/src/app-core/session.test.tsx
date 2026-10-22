// F-03-T32 (SPEC-024 AC-5; ADR-145): the session hooks against a mocked `/v1/me` and
// `/v1/me/capabilities`. Checks fail closed while loading and after an error; an engagement-scoped
// check sends `engagement_id`; a misspelt action or module does not compile.
import type { CapabilitiesOut, MeOut } from "@abacus/api-client";
import { cleanup, screen, waitFor } from "@testing-library/react";
import type { JSX } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { json, mockApi, never, withQueries } from "../testing/support";
import { Can, useCan } from "./can";
import { FeatureGate, useEntitlement, useFlag } from "./flags";
import { useSession } from "./session";

afterEach(cleanup);

const TENANT = "00000000-0000-0000-0000-0000000000f1";
const ENGAGEMENT = "00000000-0000-0000-0000-0000000000e1";

const ME: MeOut = {
  user_id: "00000000-0000-0000-0000-0000000000a1",
  email: "hannah@example.test",
  display_name: "Hannah Leclerc",
  active_tenant_id: TENANT,
  memberships: [
    { tenant_id: TENANT, firm_name: "Brightwater Hale", firm_role: null, kind: "staff" },
  ],
  server_now: "2026-10-22T15:00:00Z",
  clock_mode: "real",
};

function caps(over: Partial<CapabilitiesOut> = {}): CapabilitiesOut {
  return {
    engagement_id: null,
    capabilities: ["client.read"],
    roles: [],
    flags: { "ledger.import": true, "prompt.evidence.screener": "evidence.screen@v0" },
    entitlements: ["attest"],
    office_id: null,
    tz: "America/Chicago",
    mfa_recent_until: null,
    server_now: "2026-10-22T15:00:00Z",
    clock_mode: "real",
    portal: null,
    ...over,
  };
}

/** Firm-wide answers `firm`; with `engagement_id` answers `engagement`. */
function api(
  firm: CapabilitiesOut,
  engagement: CapabilitiesOut = firm,
): ReturnType<typeof mockApi> {
  return mockApi({
    "GET /v1/me": () => json(ME),
    "GET /v1/me/capabilities": (call) =>
      json(call.query.get("engagement_id") === null ? firm : engagement),
  });
}

function CanProbe({ engagementId }: { engagementId?: string }): JSX.Element {
  const read = useCan("client.read", { engagementId });
  const sign = useCan("workpaper.sign_reviewed", { engagementId });
  return <p data-testid="can">{`${String(read)} ${String(sign)}`}</p>;
}

describe("useCan", () => {
  it("is true for a held capability and false for one not held", async () => {
    api(caps());
    withQueries(<CanProbe />);
    await waitFor(() => {
      expect(screen.getByTestId("can").textContent).toBe("true false");
    });
  });

  it("is false while capabilities load (fail closed)", () => {
    mockApi({ "GET /v1/me/capabilities": () => never() });
    withQueries(<CanProbe />);
    expect(screen.getByTestId("can").textContent).toBe("false false");
  });

  it("is false when capabilities fail", async () => {
    const { calls } = mockApi({
      "GET /v1/me/capabilities": () => json({ detail: "boom" }, 500),
    });
    withQueries(<CanProbe />);
    await waitFor(() => {
      expect(calls.length).toBeGreaterThan(0);
    });
    expect(screen.getByTestId("can").textContent).toBe("false false");
  });

  it("asks about one engagement with engagement_id", async () => {
    const { calls } = api(
      caps(),
      caps({ engagement_id: ENGAGEMENT, capabilities: ["workpaper.sign_reviewed"] }),
    );
    withQueries(<CanProbe engagementId={ENGAGEMENT} />);
    await waitFor(() => {
      expect(screen.getByTestId("can").textContent).toBe("false true");
    });
    const asked = calls.filter((c) => c.path === "/v1/me/capabilities");
    expect(asked.map((c) => c.query.get("engagement_id"))).toEqual([ENGAGEMENT]);
  });

  it("asks about the firm without engagement_id", async () => {
    const { calls } = api(caps());
    withQueries(<CanProbe />);
    await waitFor(() => {
      expect(screen.getByTestId("can").textContent).toBe("true false");
    });
    const asked = calls.filter((c) => c.path === "/v1/me/capabilities");
    expect(asked.every((c) => !c.query.has("engagement_id"))).toBe(true);
  });
});

describe("<Can>", () => {
  it("renders children when allowed and the fallback when not", async () => {
    api(caps());
    withQueries(
      <>
        <Can action="client.read" fallback={<p>no read</p>}>
          <p>may read</p>
        </Can>
        <Can action="workpaper.sign_reviewed" fallback={<p>no sign</p>}>
          <p>may sign</p>
        </Can>
      </>,
    );
    expect(await screen.findByText("may read")).toBeTruthy();
    expect(screen.getByText("no sign")).toBeTruthy();
    expect(screen.queryByText("may sign")).toBeNull();
  });

  it("renders the fallback while loading", () => {
    mockApi({ "GET /v1/me/capabilities": () => never() });
    withQueries(
      <Can action="client.read" fallback={<p>wait</p>}>
        <p>may read</p>
      </Can>,
    );
    expect(screen.getByText("wait")).toBeTruthy();
    expect(screen.queryByText("may read")).toBeNull();
  });
});

function FlagProbe(): JSX.Element {
  const on = useFlag("ledger.import");
  const variant = useFlag("prompt.evidence.screener");
  const missing = useFlag("no.such.flag");
  const attest = useEntitlement("attest");
  const insights = useEntitlement("insights");
  return (
    <p data-testid="flags">
      {[on, variant, missing, attest, insights].map((v) => String(v)).join(" ")}
    </p>
  );
}

describe("useFlag and useEntitlement", () => {
  it("read flags and entitlements from capabilities", async () => {
    api(caps());
    withQueries(<FlagProbe />);
    await waitFor(() => {
      expect(screen.getByTestId("flags").textContent).toBe(
        "true evidence.screen@v0 false true false",
      );
    });
  });

  it("are false while loading", () => {
    mockApi({ "GET /v1/me/capabilities": () => never() });
    withQueries(<FlagProbe />);
    expect(screen.getByTestId("flags").textContent).toBe("false false false false false");
  });
});

describe("<FeatureGate>", () => {
  it("opens on a flag, a variant value or an entitlement, else shows the fallback", async () => {
    api(
      caps({
        flags: { "ledger.import": false, "prompt.evidence.screener": "evidence.screen@v0" },
      }),
    );
    withQueries(
      <>
        <FeatureGate flag="ledger.import" fallback={<p>import off</p>}>
          <p>import on</p>
        </FeatureGate>
        <FeatureGate flag="prompt.evidence.screener" value="evidence.screen@v0">
          <p>screener v0</p>
        </FeatureGate>
        <FeatureGate entitlement="attest">
          <p>attest held</p>
        </FeatureGate>
        <FeatureGate entitlement="group_audit" fallback={<p>no group audit</p>}>
          <p>group audit held</p>
        </FeatureGate>
      </>,
    );
    expect(await screen.findByText("attest held")).toBeTruthy();
    expect(screen.getByText("import off")).toBeTruthy();
    expect(screen.getByText("screener v0")).toBeTruthy();
    expect(screen.getByText("no group audit")).toBeTruthy();
    expect(screen.queryByText("import on")).toBeNull();
    expect(screen.queryByText("group audit held")).toBeNull();
  });
});

function SessionProbe(): JSX.Element {
  const s = useSession();
  return (
    <p data-testid="session">
      {[
        s.status,
        s.user?.displayName ?? "-",
        s.tenant?.firm_name ?? "-",
        s.roles.map((r) => r.label).join("+"),
        s.entitlements.join("+"),
        s.tz ?? "-",
        s.mfaRecentUntil ?? "-",
        s.portal?.shell ?? "-",
      ].join("|")}
    </p>
  );
}

describe("useSession", () => {
  it("joins /v1/me and capabilities", async () => {
    api(
      caps({
        roles: [{ code: "firm_admin", label: "Firm admin" }],
        entitlements: ["attest", "insights"],
        mfa_recent_until: "2026-10-22T15:15:00Z",
      }),
    );
    withQueries(<SessionProbe />);
    await waitFor(() => {
      expect(screen.getByTestId("session").textContent).toBe(
        "ready|Hannah Leclerc|Brightwater Hale|Firm admin|attest+insights|America/Chicago|2026-10-22T15:15:00Z|-",
      );
    });
  });

  it("is loading until both answer", () => {
    mockApi({ "GET /v1/me": () => json(ME), "GET /v1/me/capabilities": () => never() });
    withQueries(<SessionProbe />);
    expect(screen.getByTestId("session").textContent.startsWith("loading|")).toBe(true);
  });
});

// Type-level (SPEC-024 AC-5): `tsc --noEmit` fails if any of these stops being an error.
export function TypeChecks(): JSX.Element {
  // @ts-expect-error a misspelt action is a type error
  useCan("workpaper.sign_revieved");
  // @ts-expect-error a module outside the licensable set is a type error
  useEntitlement("audit");
  return (
    <>
      {/* @ts-expect-error a misspelt action on <Can> is a type error */}
      <Can action="client.raed">x</Can>
      {/* @ts-expect-error a gate takes a flag or an entitlement, not both */}
      <FeatureGate flag="ledger.import" entitlement="attest">
        x
      </FeatureGate>
    </>
  );
}
