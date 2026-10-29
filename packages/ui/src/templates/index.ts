// Templates (plan 04 §4; F-05 F): T1 Index list first.
export {
  IndexList,
  type IndexChip,
  type IndexColumn,
  type IndexListProps,
  type IndexTile,
  type ListEnvelope,
} from "./index-list";
// T7 PortalLayout (F-05-T35): split, reduced and mobile.
export {
  PORTAL_AREAS,
  PORTAL_VARIANTS,
  type PortalClientKind,
  PortalLayout,
  type PortalLayoutProps,
  type PortalVariant,
  portalNav,
} from "./portal-layout";
// T7-M home cards (F-06-T10; TPL-19 frame 1).
export {
  MobileGreeting,
  type MobileTodo,
  MobileTodoCard,
  MobileTeamCard,
  ReturnProgressCard,
  type ReturnProgressCardProps,
  type TeamMember,
} from "./portal-mobile-home";
// T15 AuthCard (F-05-T37): the 400 card, the 720 single page and the six code boxes.
export {
  AUTH_FIELD,
  AuthBrand,
  AuthButton,
  AuthCard,
  type AuthCardProps,
  type AuthChoice,
  AuthChoices,
  AuthFooter,
  AuthFrame,
  type AuthFrameProps,
  AuthPage,
  type AuthPageProps,
  CodeInput,
  type CodeInputProps,
} from "./auth-card";
// The O6 wizard's kit (F-05-T38, TPL-18): the data-driven type catalogue and the gate cards.
export {
  type CatalogueGroup,
  type CatalogueTone,
  type CatalogueType,
  GateCard,
  type GateCardProps,
  type GateTone,
  TypeCard,
  type TypeCardProps,
  TypeCatalogue,
  type TypeCatalogueProps,
  type TypeAvailability,
  WizardSummary,
  typeAvailability,
} from "./wizard-kit";
// T11 DashboardLayout (F-05-T46): greeting row, tiles, queue, deadlines and client activity.
export {
  ActivityRow,
  type ActivityRowProps,
  DashTile,
  type DashTileProps,
  DashboardLayout,
  type DashboardLayoutProps,
  type DashboardOffice,
  DeadlineRow,
  type DeadlineRowProps,
  QueueEmpty,
  QueueRow,
  type QueueRowProps,
} from "./dashboard-layout";
// T12 SettingsLayout (F-05-T45): section list, form pane, Save and Discard, the step-up slot.
export {
  type SettingsGroup,
  SettingsLayout,
  type SettingsLayoutProps,
  SettingsLock,
  type SettingsSection,
  canSave,
} from "./settings-layout";
// T2 RecordCockpit (F-05-T40): rail, canvas and dock under the audit record bar.
export {
  type CockpitCanvas,
  type CockpitDock,
  DOCK_VIEWS,
  DockComposer,
  type DockComposerProps,
  type DockView,
  RecordCockpit,
  type RecordCockpitProps,
} from "./record-cockpit";
// T3 EvidenceTriad (F-05-T53): tree, viewer and sheet in one MatchScope under three presets.
export {
  EvidenceTriad,
  type EvidenceTriadProps,
  TRIAD_VIEWS,
  type TriadDoc,
  TriadFooter,
  type TriadGroup,
  type TriadPreset,
  type TriadSheet,
  TriadSheetBar,
  TriadTree,
  type TriadTreeProps,
} from "./evidence-triad";
// T9 QueueDetailLayout (F-05-T55): queue, detail and evidence under three presets.
export {
  QUEUE_PRESETS,
  QueueDetailLayout,
  type QueueDetailLayoutProps,
  type QueuePreset,
} from "./queue-detail";
// T8 InboxLayout (F-05-T56): the filter bar, the 392 rail and the reading pane.
export { InboxLayout, type InboxLayoutProps } from "./inbox-layout";
// T5 CatalogLayout (F-05-T59): side pane with About and Categories beside the three-column grid.
export { CatalogLayout, type CatalogLayoutProps } from "./catalog-layout";
// T16 SigningCeremony (F-06-T04): provider mode only; the L2 parts are ../signing.
export { SigningCeremony } from "./signing-ceremony/SigningCeremony";
