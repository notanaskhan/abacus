// The clients domain's public entry (P-07 §5): what screens import.
export {
  CLIENT_KINDS,
  CLIENT_PAGE_SIZE,
  CLIENT_STATUSES,
  type ClientFilters,
  type ClientKind,
  DEFAULT_CLIENT_FILTERS,
  SERVICE_LINES,
  type ServiceLine,
  isClientKind,
  isClientStatus,
  isNarrowed,
  isServiceLine,
  useClients,
} from "./queries";
export { ACTIVITY_WORDS, KIND_WORDS, activityWords } from "./messages";
export {
  REVEAL_REASONS,
  type RevealReason,
  type StatItem,
  daysUntil,
  givenName,
  itemOf,
  maskTin,
  patchOf,
  sectionOf,
  statItems,
  sumFigures,
  tinEntity,
  useClientOverview,
  useClientRecord,
  useRevealTin,
  useStaff,
  useUpdateClient,
} from "./record";
export { MaskedTin, TIN_COPY } from "./MaskedTin";
export {
  type ContactRoleCode,
  type GrantRole,
  grantsFor,
  isThirdParty,
  useClientRequestItems,
  useContact,
  useContactWrites,
  useContacts,
} from "./contacts";
export {
  INTAKE_STEPS,
  type IntakeStep,
  stepOfField,
  useConflictResults,
  useIntakeWrites,
} from "./intake";
