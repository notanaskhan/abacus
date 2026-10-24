// The audits domain's public entry (A-01 §5.2, L3): the shared audit cockpit parts every AUD
// screen, EBP-* and ATT-01 compose, and the reads they need.
export { AuditBar, type AuditBarOptions, auditBarProps } from "./AuditBar";
export { AuditCockpit, type AuditCockpitProps } from "./AuditCockpit";
export { BlockedSectionCard, type BlockedSectionCardProps } from "./BlockedSectionCard";
export { type DockHostOptions, dockHost } from "./DockHost";
export { AUDIT_MESSAGES, type BandKey } from "./messages";
export { useAuditCockpit, useSourceDocuments } from "./queries";
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
