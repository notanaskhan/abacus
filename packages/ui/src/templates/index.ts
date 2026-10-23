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
