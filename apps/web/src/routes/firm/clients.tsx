import { createRoute } from "@tanstack/react-router";
import type { JSX } from "react";
import { useParam } from "../params";
import { appRoute, lazyScreen } from "../root";

// SPEC-303 (TASK-304): clients, joined from the engagements the person can see.
const Clients = lazyScreen(async () => (await import("../../legacy/Clients")).Clients);
const ClientRecord = lazyScreen(async () => (await import("../../legacy/Clients")).ClientRecord);

const clientsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/clients",
  component: function ClientsPage(): JSX.Element {
    return <Clients />;
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
