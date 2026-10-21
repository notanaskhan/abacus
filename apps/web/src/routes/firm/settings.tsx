import { meOptions } from "@abacus/api-client/query";
import { useQuery } from "@tanstack/react-query";
import { createRoute } from "@tanstack/react-router";
import type { JSX } from "react";
import { useParam } from "../params";
import { appRoute, lazyScreen } from "../root";

// Firm settings (SPEC-016, SPEC-019 Q1): one section list, a section per page. The /admin paths
// move to /settings with redirects in G-01-T07 (DEC-113); today's URLs are kept.
const screens = {
  Methodology: lazyScreen(async () => (await import("../../screens/Methodology")).Methodology),
  GroupingSets: lazyScreen(async () => (await import("../../screens/GroupingSets")).GroupingSets),
  MethodologyVersion: lazyScreen(
    async () => (await import("../../screens/MethodologyVersion")).MethodologyVersion,
  ),
  KnowledgeDocuments: lazyScreen(
    async () => (await import("../../screens/KnowledgeDocuments")).KnowledgeDocuments,
  ),
  Budget: lazyScreen(async () => (await import("../../screens/Budget")).Budget),
  AutonomySettings: lazyScreen(async () => {
    const m = await import("../../screens/Autonomy");
    const ai = await import("../../screens/AiClientData");
    return function AutonomySettings({ canSet }: { canSet: boolean }): JSX.Element {
      return (
        <div className="flex flex-col gap-4">
          <m.Autonomy canSet={canSet} />
          <m.LetterPolicy canSet={canSet} />
          <m.DraftedGuidanceSetting canSet={canSet} />
          <m.FirmAgents canSet={canSet} />
          <m.FirmTimeZone canSet={canSet} />
          <ai.AiClientDataSetting canSet={canSet} />
        </div>
      );
    };
  }),
  Onboarding: lazyScreen(async () => (await import("../../screens/Onboarding")).Onboarding),
  FirmPeople: lazyScreen(async () => (await import("../../screens/FirmPeople")).FirmPeople),
  AuditLog: lazyScreen(async () => (await import("../../screens/AuditLog")).AuditLog),
  SupportAccess: lazyScreen(
    async () => (await import("../../screens/SupportAccess")).SupportAccess,
  ),
  Walls: lazyScreen(async () => (await import("../../screens/Walls")).Walls),
};

const AdminLayout = lazyScreen(
  async () => (await import("../../screens/AdminLayout")).AdminLayout,
);
const adminRoute = createRoute({
  getParentRoute: () => appRoute,
  id: "admin",
  component: function AdminPage(): JSX.Element {
    return <AdminLayout />;
  },
});

function section<const P extends string>(path: P, page: () => JSX.Element) {
  return createRoute({ getParentRoute: () => adminRoute, path, component: page });
}

const methodologyVersionRoute = createRoute({
  getParentRoute: () => adminRoute,
  path: "/admin/methodology/$versionId",
  component: function VersionPage(): JSX.Element {
    const versionId = useParam("versionId");
    return <screens.MethodologyVersion versionId={versionId} />;
  },
});

export const settingsRoutes = [
  adminRoute.addChildren([
    section("/admin/methodology", () => <screens.Methodology />),
    methodologyVersionRoute,
    section("/admin/knowledge", () => <screens.KnowledgeDocuments />),
    section("/admin/fs-groupings", () => <screens.GroupingSets />), // SPEC-316 (TASK-345)
    section("/admin/budget", () => <screens.Budget />),
    section("/admin/autonomy", function AutonomyPage(): JSX.Element {
      const me = useQuery(meOptions());
      const tenant = me.data?.active_tenant_id ?? null;
      const role = me.data?.memberships.find((m) => m.tenant_id === tenant)?.firm_role;
      return <screens.AutonomySettings canSet={role === "firm_admin"} />;
    }),
    section("/admin/setup", () => <screens.Onboarding always />),
    section("/admin/people", () => <screens.FirmPeople />),
    section("/admin/support", () => <screens.SupportAccess />),
    section("/admin/audit-log", () => <screens.AuditLog />),
    section("/admin/walls", () => <screens.Walls />),
  ]),
] as const;
