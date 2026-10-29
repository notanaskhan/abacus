import { EmptyState } from "@abacus/ui";
import { Navigate, createRoute, useNavigate, useRouter, useSearch } from "@tanstack/react-router";
import type { JSX } from "react";
import { useCan } from "../../app-core/can";
import { FeatureGate, useFlag } from "../../app-core/flags";
import { useParam } from "../params";
import { appRoute, lazyScreen } from "../root";

// Firm settings (SPEC-016, SPEC-019 Q1): one section list, a section per page. The /admin paths
// move to /settings (DEC-113): a legacy path whose new page is built redirects to it while that
// page's flag is on (G-01-T07), and keeps its legacy page otherwise.
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

// R-01-T25: POR-20 at /settings/portal/email-templates/$templateKey, lazy (the firm entry is at its
// budget); the width (`w`) and the preview's sample contact (`sample`) live in the URL. Writes are
// the server's to allow (`allowed_actions`, `portal.settings_editor`); reads are never gated.
const EmailTemplates = lazyScreen(async () => (await import("../../screens/POR-20")).POR20);
// R-01-T28: ADM-10 at /settings/portal; the preview's contact and device and the open template
// drawer live in the URL. "Preview as" lists the sample client only until a visible-contact read
// lands (DEC-20, DEC-956); the preview opens in a new tab at /settings/portal/preview.
const PortalSettings = lazyScreen(async () => (await import("../../screens/ADM-10")).ADM10);
const PortalSettingsPreview = lazyScreen(
  async () => (await import("../../screens/ADM-10")).ADM10Preview,
);
const PORTAL_SEARCH = ["as", "device", "ov"] as const;
const TEMPLATE_SEARCH = ["w", "sample"] as const;
const WIDTHS = new Set(["600", "390", "phone"]);

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
const settingsEmailTemplatesRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/settings/portal/email-templates/$templateKey",
  validateSearch: (search: Record<string, unknown>) => pick(TEMPLATE_SEARCH, search),
  component: function SettingsEmailTemplatesPage(): JSX.Element {
    const navigate = useNavigate();
    const router = useRouter();
    const templateKey = useParam("templateKey");
    const search = pick(TEMPLATE_SEARCH, useSearch({ strict: false }));
    const width = WIDTHS.has(search.w ?? "") ? (search.w as "600" | "390" | "phone") : "600";
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <EmailTemplates
          templateKey={templateKey}
          width={width}
          sample={search.sample ?? ""}
          onWidth={(w) => {
            void navigate({ to: ".", search: { ...search, w }, replace: true });
          }}
          onOpenTemplate={(key) => {
            void navigate({
              to: "/settings/portal/email-templates/$templateKey",
              params: { templateKey: key },
              search: search.w === undefined ? {} : { w: search.w },
            });
          }}
          onBack={() => {
            router.history.back();
          }}
        />
      </div>
    );
  },
});
const settingsPortalRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/settings/portal",
  validateSearch: (search: Record<string, unknown>) => pick(PORTAL_SEARCH, search),
  component: function SettingsPortalPage(): JSX.Element {
    const navigate = useNavigate();
    const router = useRouter();
    const search = pick(PORTAL_SEARCH, useSearch({ strict: false }));
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <PortalSettings
          search={search}
          onSearch={(next) => {
            void navigate({ to: ".", search: pick(PORTAL_SEARCH, { ...next }), replace: true });
          }}
          onNavigate={(section) => {
            void navigate({ to: "/settings/$section", params: { section } });
          }}
          onOpenTemplate={(key) => {
            void navigate({
              to: "/settings/portal/email-templates/$templateKey",
              params: { templateKey: key },
            });
          }}
          onOpenPreview={(as, device) => {
            const query = new URLSearchParams({ as, device }).toString();
            window.open(`/settings/portal/preview?${query}`, "_blank", "noopener");
          }}
          onBack={() => {
            router.history.back();
          }}
        />
      </div>
    );
  },
});
const settingsPortalPreviewRoute = createRoute({
  getParentRoute: () => appRoute,
  path: "/settings/portal/preview",
  validateSearch: (search: Record<string, unknown>) => pick(["as", "device"] as const, search),
  component: function SettingsPortalPreviewPage(): JSX.Element {
    const search = pick(["as", "device"] as const, useSearch({ strict: false }));
    return (
      <div className="flex min-h-0 flex-1 flex-col">
        <PortalSettingsPreview
          as={search.as ?? "sample"}
          device={search.device === "phone" ? "phone" : "desktop"}
        />
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

/** G-01-T07 (DEC-113): the legacy page, or a redirect to its /settings page once `flag` is on. */
export function Moved({
  flag,
  to,
  hash,
  children,
}: {
  flag: string;
  to: "/settings/audit-log";
  hash?: string;
  children: JSX.Element;
}): JSX.Element {
  if (useFlag(flag) !== true) return children;
  return <Navigate to={to} replace {...(hash === undefined ? {} : { hash })} />;
}

export const settingsRoutes = [
  settingsGeneralRoute,
  settingsPeopleRoute,
  settingsOfficesRoute,
  settingsAuditLogRoute,
  settingsSecurityRoute,
  settingsPortalRoute,
  settingsPortalPreviewRoute,
  settingsEmailTemplatesRoute,
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
    // G-01-T07 (DEC-113): the legacy URLs land on their settings pages. People and walls redirect
    // for every firm now that `firm_settings.v2` is retired (G-01-T17, DEC-594); the audit log
    // follows `audit_log.explorer`.
    section("/admin/people", () => <Navigate to="/settings/people" replace />),
    section("/admin/support", () => <screens.SupportAccess />),
    section("/admin/audit-log", () => (
      <Moved flag="audit_log.explorer" to="/settings/audit-log">
        <screens.AuditLog />
      </Moved>
    )),
    // ADM-03 holds the walls in its own section, scrolled to by `#walls`.
    section("/admin/walls", () => <Navigate to="/settings/offices" hash="walls" replace />),
  ]),
] as const;
