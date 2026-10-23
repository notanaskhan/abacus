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
