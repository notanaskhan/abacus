import { createRoute } from "@tanstack/react-router";
import type { JSX } from "react";
import { FeatureGate } from "../../app-core/flags";
import { useParam } from "../params";
import { appRoute, lazyScreen } from "../root";

// Clients (P-07 §5): `/clients` → CLI-01 behind `clients.v2`; while the flag is off the area keeps
// SPEC-303's legacy list (TASK-304), so turning the flag on is the only switch. The record stays
// the legacy ClientRecord until CLI-02 (P-07-T19).
const ClientsIndex = lazyScreen(async () => (await import("../../screens/CLI-01")).ClientsIndex);
const Clients = lazyScreen(async () => (await import("../../legacy/Clients")).Clients);
const ClientRecord = lazyScreen(async () => (await import("../../legacy/Clients")).ClientRecord);

export const clientsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/clients",
  component: function ClientsPage(): JSX.Element {
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <FeatureGate flag="clients.v2" fallback={<Clients />}>
          <ClientsIndex />
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
    return <ClientRecord clientId={clientId} />;
  },
});

export const clientRoutes = [clientsRoute, clientRoute] as const;
