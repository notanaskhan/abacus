import { createRoute } from "@tanstack/react-router";
import type { JSX } from "react";
import { useCan } from "../../app-core/can";
import { useParam } from "../params";
import { appRoute, lazyScreen } from "../root";

// Firm settings (SPEC-016, SPEC-019 Q1): one section list, a section per page. The /admin paths
// move to /settings with redirects in G-01-T07 (DEC-113); today's URLs are kept.
const screens = {
  Methodology: lazyScreen(async () => (await import("../../legacy/Methodology")).Methodology),
  GroupingSets: lazyScreen(async () => (await import("../../legacy/GroupingSets")).GroupingSets),
  MethodologyVersion: lazyScreen(
    async () => (await import("../../legacy/MethodologyVersion")).MethodologyVersion,
  ),
  KnowledgeDocuments: lazyScreen(
    async () => (await import("../../legacy/KnowledgeDocuments")).KnowledgeDocuments,
  ),
  Budget: lazyScreen(async () => (await import("../../legacy/Budget")).Budget),
  AutonomySettings: lazyScreen(async () => {
    const m = await import("../../legacy/Autonomy");
    const ai = await import("../../legacy/AiClientData");
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
  Onboarding: lazyScreen(async () => (await import("../../legacy/Onboarding")).Onboarding),
  FirmPeople: lazyScreen(async () => (await import("../../legacy/FirmPeople")).FirmPeople),
  AuditLog: lazyScreen(async () => (await import("../../legacy/AuditLog")).AuditLog),
  SupportAccess: lazyScreen(
    async () => (await import("../../legacy/SupportAccess")).SupportAccess,
  ),
  Walls: lazyScreen(async () => (await import("../../legacy/Walls")).Walls),
};

const AdminLayout = lazyScreen(async () => (await import("../../legacy/AdminLayout")).AdminLayout);
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
      // F-03-T32: the matrix decides (identity.yaml: firm admin), not a role comparison.
      const canSet = useCan("autonomy_policy.update");
      return <screens.AutonomySettings canSet={canSet} />;
    }),
    section("/admin/setup", () => <screens.Onboarding always />),
    section("/admin/people", () => <screens.FirmPeople />),
    section("/admin/support", () => <screens.SupportAccess />),
    section("/admin/audit-log", () => <screens.AuditLog />),
    section("/admin/walls", () => <screens.Walls />),
  ]),
] as const;
