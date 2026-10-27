import { EmptyState } from "@abacus/ui";
import { createRoute, useNavigate, useRouter, useSearch } from "@tanstack/react-router";
import type { JSX } from "react";
import { useCan } from "../../app-core/can";
import { FeatureGate } from "../../app-core/flags";
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
  AuditLog: lazyScreen(async () => (await import("../../legacy/AuditLog")).AuditLog),
  SupportAccess: lazyScreen(
    async () => (await import("../../legacy/SupportAccess")).SupportAccess,
  ),
};

// G-01-T07: ADM-01 at /settings/general; the other sections are planned (G-01 §5.1) and answer
// "not built yet" until their screens land. G-01-T17 retired `firm_settings.v2` and removed the
// legacy /admin/people and /admin/walls pages: ADM-02 and ADM-03 are the only people and walls
// screens (DEC-594).
const FirmSettingsGeneral = lazyScreen(async () => (await import("../../screens/ADM-01")).ADM01);
// G-01-T10: ADM-02 at /settings/people; its segment, filters, highlighted
// template and open overlay live in the URL (G-01 §5.1), never a name or an email.
const FirmSettingsPeople = lazyScreen(async () => (await import("../../screens/ADM-02")).ADM02);
interface PeopleSearch {
  segment?: string;
  role?: string;
  office?: string;
  team?: string;
  status?: string;
  q?: string;
  template?: string;
  ov?: string;
}
const PEOPLE_SEARCH = [
  "segment",
  "role",
  "office",
  "team",
  "status",
  "q",
  "template",
  "ov",
] as const;

// G-01-T14: ADM-03 at /settings/offices behind the same flag; the expanded office (by code) and the
// open overlay live in the URL, `#walls` and `#offshore` scroll to their fieldsets.
const FirmSettingsOffices = lazyScreen(async () => (await import("../../screens/ADM-03")).ADM03);
interface OfficesSearch {
  expand?: string;
  ov?: string;
}
const OFFICES_SEARCH = ["expand", "ov"] as const;

// G-02-T13: ADM-07 at /settings/audit-log behind `audit_log.explorer`; filters, search and the
// open event live in the URL. G-02-T16: ADM-06 at /settings/security behind
// `security_center.v1`; the open incident, the sessions drawer and the history tray live in the
// URL. The route never passes ADM-06's R2 rows (fixture only until G-03-T29).
const FirmSettingsAuditLog = lazyScreen(async () => (await import("../../screens/ADM-07")).ADM07);
const AUDIT_SEARCH = ["actor", "object", "action", "date", "office", "ip", "q", "event"] as const;
const FirmSettingsSecurity = lazyScreen(async () => (await import("../../screens/ADM-06")).ADM06);
const SECURITY_SEARCH = ["incident", "sessions", "export"] as const;

function pick<const K extends string>(
  keys: readonly K[],
  search: Record<string, unknown>,
): Partial<Record<K, string>> {
  return Object.fromEntries(
    keys.flatMap((key) => {
      const value = search[key];
      return typeof value === "string" && value !== "" ? [[key, value]] : [];
    }),
  ) as Partial<Record<K, string>>;
}

function NotBuilt(): JSX.Element {
  return (
    <div className="flex flex-1 items-center justify-center p-8">
      <EmptyState title="This settings section isn't built yet." />
    </div>
  );
}

const settingsGeneralRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/settings/general",
  component: function SettingsGeneralPage(): JSX.Element {
    const navigate = useNavigate();
    const router = useRouter();
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <FirmSettingsGeneral
          onNavigate={(section) => {
            void navigate({ to: "/settings/$section", params: { section } });
          }}
          onBack={() => {
            router.history.back();
          }}
        />
      </div>
    );
  },
});
const settingsPeopleRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/settings/people",
  validateSearch: (search: Record<string, unknown>): PeopleSearch =>
    Object.fromEntries(
      PEOPLE_SEARCH.flatMap((key) => {
        const value = search[key];
        return typeof value === "string" && value !== "" ? [[key, value]] : [];
      }),
    ),
  component: function SettingsPeoplePage(): JSX.Element {
    // Loose hooks: the page also mounts in tests' routers (the same path, any tree).
    const navigate = useNavigate();
    const router = useRouter();
    const search: Record<string, unknown> = useSearch({ strict: false });
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <FirmSettingsPeople
          search={search}
          onSearch={(next) => {
            void navigate({ to: ".", search: { ...next }, replace: true });
          }}
          onNavigate={(section) => {
            void navigate({ to: "/settings/$section", params: { section } });
          }}
          onBack={() => {
            router.history.back();
          }}
        />
      </div>
    );
  },
});
const settingsOfficesRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/settings/offices",
  validateSearch: (search: Record<string, unknown>): OfficesSearch =>
    Object.fromEntries(
      OFFICES_SEARCH.flatMap((key) => {
        const value = search[key];
        return typeof value === "string" && value !== "" ? [[key, value]] : [];
      }),
    ),
  component: function SettingsOfficesPage(): JSX.Element {
    const navigate = useNavigate();
    const router = useRouter();
    const search: Record<string, unknown> = useSearch({ strict: false });
    const hash = router.state.location.hash;
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <FirmSettingsOffices
          search={search}
          {...(hash === "" ? {} : { anchor: hash })}
          onSearch={(next) => {
            void navigate({ to: ".", search: { ...next }, replace: true });
          }}
          onNavigate={(section) => {
            void navigate({ to: "/settings/$section", params: { section } });
          }}
          onOpenPeople={(filter) => {
            void navigate({ to: "/settings/people", search: { ...filter } });
          }}
          onBack={() => {
            router.history.back();
          }}
        />
      </div>
    );
  },
});
const settingsAuditLogRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/settings/audit-log",
  validateSearch: (search: Record<string, unknown>) => pick(AUDIT_SEARCH, search),
  component: function SettingsAuditLogPage(): JSX.Element {
    const navigate = useNavigate();
    const router = useRouter();
    const search: Record<string, unknown> = useSearch({ strict: false });
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <FeatureGate flag="audit_log.explorer" fallback={<NotBuilt />}>
          <FirmSettingsAuditLog
            search={pick(AUDIT_SEARCH, search)}
            onSearch={(next) => {
              void navigate({ to: ".", search: { ...next }, replace: true });
            }}
            onNavigate={(section) => {
              void navigate({ to: "/settings/$section", params: { section } });
            }}
            onBack={() => {
              router.history.back();
            }}
          />
        </FeatureGate>
      </div>
    );
  },
});
const settingsSecurityRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/settings/security",
  validateSearch: (search: Record<string, unknown>) => pick(SECURITY_SEARCH, search),
  component: function SettingsSecurityPage(): JSX.Element {
    const navigate = useNavigate();
    const router = useRouter();
    const search: Record<string, unknown> = useSearch({ strict: false });
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <FeatureGate flag="security_center.v1" fallback={<NotBuilt />}>
          <FirmSettingsSecurity
            search={pick(SECURITY_SEARCH, search)}
            onSearch={(next) => {
              void navigate({ to: ".", search: { ...next }, replace: true });
            }}
            onNavigate={(section) => {
              void navigate({ to: "/settings/$section", params: { section } });
            }}
            onBack={() => {
              router.history.back();
            }}
          />
        </FeatureGate>
      </div>
    );
  },
});
const settingsSectionRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/settings/$section",
  component: NotBuilt,
});

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
  settingsGeneralRoute,
  settingsPeopleRoute,
  settingsOfficesRoute,
  settingsAuditLogRoute,
  settingsSecurityRoute,
  settingsSectionRoute,
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
    section("/admin/support", () => <screens.SupportAccess />),
    section("/admin/audit-log", () => <screens.AuditLog />),
  ]),
] as const;
