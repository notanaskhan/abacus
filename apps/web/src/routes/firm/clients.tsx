import { createRoute, useNavigate, useSearch } from "@tanstack/react-router";
import type { JSX } from "react";
import { FeatureGate } from "../../app-core/flags";
import { useParam } from "../params";
import { appRoute, lazyScreen } from "../root";

// Clients (P-07 §5): `/clients` is CLI-01 and the record CLI-02 (P-07-T19) for every firm since
// P-07-T59 retired `clients.v2` with SPEC-303's legacy list and record (DEC-905).
const ClientsIndex = lazyScreen(async () => (await import("../../screens/CLI-01")).ClientsIndex);
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
        <ClientsIndex
          onOpen={(clientId) => {
            void navigate({ to: "/clients/$clientId", params: { clientId } });
          }}
        />
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
      </div>
    );
  },
});

// CLI-04 (P-07-T33): the record on its "Contacts & access" tab; the tab itself is live only with `contacts.v2` (otherwise the record opens on its Overview).
const clientContactsRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/clients/$clientId/contacts",
  component: function ClientContactsPage(): JSX.Element {
    const clientId = useParam("clientId");
    const navigate = useNavigate();
    return (
      <div className="flex min-h-0 flex-1 flex-col">
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
      </div>
    );
  },
});

// CLI-07 (P-07-T46): acceptance and continuance of one engagement. Its links to the client
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
      <div className="flex min-h-0 flex-1 flex-col">
        <Acceptance
          clientId={clientId}
          engagementId={engagementId}
          onNavigate={(target) => {
            void navigate({ to: "/clients/$clientId", params: { clientId: target.clientId } });
          }}
        />
      </div>
    );
  },
});

// CLI-06 (P-07-T49): the single-client intake wizard over CLI-01. "Create &
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
    );
  },
});

// CLI-08 (P-07-T48): independence and conflicts of one engagement (CLI-08 v2). `?check=` names the conflict check its Conflicts tab
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
      <div className="flex min-h-0 flex-1 flex-col">
        <Independence clientId={clientId} engagementId={engagementId} checkId={check} />
      </div>
    );
  },
});

// CLI-05 (T-01-T14): the client's Tax profile behind `clients.tax_profile` (the consents section
// reads `consents.registry`). `?entity=` names the taxpayer entity whose profile opens; the record
// resolves its first entity otherwise.
const TaxProfile = lazyScreen(async () => (await import("../../screens/CLI-05")).TaxProfilePage);
const clientTaxProfileRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/clients/$clientId/tax-profile/$sub",
  component: function ClientTaxProfilePage(): JSX.Element {
    const clientId = useParam("clientId");
    const sub = useParam("sub");
    const navigate = useNavigate();
    const search: Record<string, unknown> = useSearch({ strict: false });
    const entity = typeof search.entity === "string" ? search.entity : undefined;
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <FeatureGate flag="clients.tax_profile" fallback={null}>
          <TaxProfile
            clientId={clientId}
            {...(entity === undefined ? {} : { clientEntityId: entity })}
            section={sub}
            onSection={(next) => {
              void navigate({
                to: "/clients/$clientId/tax-profile/$sub",
                params: { clientId, sub: next },
                search: { ...search },
              });
            }}
            onBack={() => {
              void navigate({ to: "/clients" });
            }}
          />
        </FeatureGate>
      </div>
    );
  },
});

export const clientRoutes = [
  clientTaxProfileRoute,
  clientsRoute,
  clientRoute,
  clientContactsRoute,
  clientAcceptanceRoute,
  clientIndependenceRoute,
  clientIntakeRoute,
] as const;
