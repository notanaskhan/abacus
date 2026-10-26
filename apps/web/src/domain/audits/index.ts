// The audits domain's public entry (A-01 §5.2, L3): the shared audit cockpit parts every AUD
// screen, EBP-* and ATT-01 compose, and the reads they need.
export { AuditBar, type AuditBarOptions, auditBarProps } from "./AuditBar";
export {
  AUTO_MODE_CAPABILITY,
  AUTO_MODE_PATH,
  type AutoModeControl,
  type AutoModeIn,
  type AutoModeResult,
  type AutoModeStep,
  putAutoMode,
  useAutoMode,
} from "./mutations";
export { AuditCockpit, type AuditCockpitProps } from "./AuditCockpit";
export { BlockedSectionCard, type BlockedSectionCardProps } from "./BlockedSectionCard";
export { type DockHostOptions, dockHost } from "./DockHost";
export { AUDIT_MESSAGES, type BandKey } from "./messages";
export { isNotFound, useAuditCockpit, useSourceDocuments } from "./queries";
export { AgentActivityTab, AgentDockMenu, aiRefused, useAgentTab } from "./AgentActivityTab";
export { DockViewer } from "./DockViewer";
export {
  BEGIN_ACTION,
  type RailModel,
  discOf,
  idlePillOf,
  linkOf,
  phaseOf,
  railModel,
  subLineOf,
} from "./rail";
export { SectionRail, type SectionRailProps } from "./SectionRail";
export {
  AUDIT_DUE_WINDOWS,
  AUDIT_SEGMENTS,
  AUDIT_TILES,
  type AuditDueWindow,
  type AuditFilters,
  type AuditSegment,
  type AuditTile,
  type AuditType,
  AUDIT_SEARCH_KEYS,
  type AuditSearch,
  DEFAULT_AUDIT_FILTERS,
  auditFiltersOf,
  auditQueryOf,
  auditSearchOf,
  auditTypeLabel,
  auditTypeWord,
  isAuditDue,
  isAuditSegment,
  isAuditTile,
  isNarrowedAudits,
  useAuditIndex,
} from "./list";
