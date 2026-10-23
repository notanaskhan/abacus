import { createRoute, useNavigate } from "@tanstack/react-router";
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

export const clientRoutes = [clientsRoute, clientRoute] as const;
