import { createRoute, useNavigate, useSearch } from "@tanstack/react-router";
import type { JSX } from "react";
import { FeatureGate } from "../../app-core/flags";
import { useParam } from "../params";
import { appRoute, lazyScreen } from "../root";

// Clients (P-07 §5): `/clients` → CLI-01 behind `clients.v2`; while the flag is off the area keeps
// SPEC-303's legacy list (TASK-304), so turning the flag on is the only switch. The record is
// CLI-02 (P-07-T19) behind the same flag, and the legacy ClientRecord while it is off.
const ClientsIndex = lazyScreen(async () => (await import("../../screens/CLI-01")).ClientsIndex);
const Clients = lazyScreen(async () => (await import("../../legacy/Clients")).Clients);
const ClientRecord = lazyScreen(async () => (await import("../../legacy/Clients")).ClientRecord);
const ClientRecordV2 = lazyScreen(
  async () => (await import("../../screens/CLI-02")).ClientRecordPage,
);

export const clientsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/clients",
  component: function ClientsPage(): JSX.Element {
    const navigate = useNavigate();
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <FeatureGate flag="clients.v2" fallback={<Clients />}>
          <ClientsIndex
            onOpen={(clientId) => {
              void navigate({ to: "/clients/$clientId", params: { clientId } });
            }}
          />
        </FeatureGate>
      </div>
    );
  },
});
const clientRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/clients/$clientId",
  component: function ClientPage(): JSX.Element {
    const clientId = useParam("clientId");
    const navigate = useNavigate();
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <FeatureGate flag="clients.v2" fallback={<ClientRecord clientId={clientId} />}>
          <ClientRecordV2
            clientId={clientId}
            onNavigate={(target) => {
              if (target.screen === "CLI-01") void navigate({ to: "/clients" });
              else if (target.screen === "ENG-02") {
                void navigate({
                  to: "/engagements/$engagementId",
                  params: { engagementId: target.engagementId },
                });
              } else {
                void navigate({ to: "/binders/$binderId", params: { binderId: target.binderId } });
              }
            }}
          />
        </FeatureGate>
      </div>
    );
  },
});

// CLI-04 (P-07-T33): the record on its "Contacts & access" tab, behind `clients.v2`; the tab
// itself is live only with `contacts.v2` (otherwise the record opens on its Overview).
const clientContactsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/clients/$clientId/contacts",
  component: function ClientContactsPage(): JSX.Element {
    const clientId = useParam("clientId");
    const navigate = useNavigate();
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <FeatureGate flag="clients.v2" fallback={<ClientRecord clientId={clientId} />}>
          <ClientRecordV2
            clientId={clientId}
            initialTab="contacts"
            onNavigate={(target) => {
              if (target.screen === "CLI-01") void navigate({ to: "/clients" });
              else if (target.screen === "ENG-02") {
                void navigate({
                  to: "/engagements/$engagementId",
                  params: { engagementId: target.engagementId },
                });
              } else {
                void navigate({ to: "/binders/$binderId", params: { binderId: target.binderId } });
              }
            }}
          />
        </FeatureGate>
      </div>
    );
  },
});

// CLI-07 (P-07-T46): acceptance and continuance of one engagement, behind
// `engagements.acceptance_v2` (the routes answer 404 while it is off). Its links to the client
// record (the back chip, "Open ‹client›" after a decline) are wired here (DEC-195, DEC-431).
const Acceptance = lazyScreen(async () => (await import("../../screens/CLI-07")).AcceptancePage);

const clientAcceptanceRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/clients/$clientId/acceptance/$engagementId",
  component: function ClientAcceptancePage(): JSX.Element {
    const clientId = useParam("clientId");
    const engagementId = useParam("engagementId");
    const navigate = useNavigate();
    return (
      <FeatureGate flag="engagements.acceptance_v2">
        <div className="flex min-h-0 flex-1 flex-col">
          <Acceptance
            clientId={clientId}
            engagementId={engagementId}
            onNavigate={(target) => {
              void navigate({ to: "/clients/$clientId", params: { clientId: target.clientId } });
            }}
          />
        </div>
      </FeatureGate>
    );
  },
});

// CLI-06 (P-07-T49): the single-client intake wizard over CLI-01, behind `clients.v2`. "Create &
// start acceptance" lands on CLI-07; "Create" on CLI-02; closing returns to CLI-01 (wired here,
// DEC-195). `?mode=import` opens the bulk import (g, P-07-T54).
const Intake = lazyScreen(async () => (await import("../../screens/CLI-06")).IntakePage);

const clientIntakeRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/clients/new",
  validateSearch: (search: Record<string, unknown>): { mode?: "import" } =>
    search.mode === "import" ? { mode: "import" } : {},
  component: function ClientIntakePage(): JSX.Element {
    const navigate = useNavigate();
    const search: { mode?: "import" } = useSearch({ strict: false });
    return (
      <FeatureGate flag="clients.v2">
        <Intake
          mode={search.mode === "import" ? "bulk" : "single"}
          onClose={() => {
            void navigate({ to: "/clients" });
          }}
          onNavigate={(target) => {
            if (target.screen === "CLI-07") {
              void navigate({
                to: "/clients/$clientId/acceptance/$engagementId",
                params: { clientId: target.clientId, engagementId: target.engagementId },
              });
            } else {
              void navigate({ to: "/clients/$clientId", params: { clientId: target.clientId } });
            }
          }}
        />
      </FeatureGate>
    );
  },
});

// CLI-08 (P-07-T48): independence and conflicts of one engagement, behind
// `engagements.acceptance_v2` (CLI-08 v2). `?check=` names the conflict check its Conflicts tab
// reads (the intake's, P-07-T42).
const Independence = lazyScreen(
  async () => (await import("../../screens/CLI-08")).IndependencePage,
);

const clientIndependenceRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/clients/$clientId/independence/$engagementId",
  validateSearch: (search: Record<string, unknown>): { check?: string } =>
    typeof search.check === "string" ? { check: search.check } : {},
  component: function ClientIndependencePage(): JSX.Element {
    const clientId = useParam("clientId");
    const engagementId = useParam("engagementId");
    const search: { check?: string } = useSearch({ strict: false });
    const check = search.check ?? null;
    return (
      <FeatureGate flag="engagements.acceptance_v2">
        <div className="flex min-h-0 flex-1 flex-col">
          <Independence clientId={clientId} engagementId={engagementId} checkId={check} />
        </div>
      </FeatureGate>
    );
  },
});

export const clientRoutes = [
  clientsRoute,
  clientRoute,
  clientContactsRoute,
  clientAcceptanceRoute,
  clientIndependenceRoute,
  clientIntakeRoute,
] as const;
