import type { AuditSectionStatus, EngagementStatus, RequestStatus } from "@abacus/api-client";
import type { EnumCovered } from "@abacus/ui";

// F-05-T12 (C2, DEC-08): an OpenAPI status enum and the status registry never drift apart. Each
// line below is `true` only while every literal of the enum has an entry in
// docs/product/status-vocabulary.yaml (through the generated registry), and every stored code of
// the registry object is in the enum. Add a literal to an enum without a YAML entry, or a stored
// code to the YAML that the API cannot return, and `tsc --noEmit` fails here, naming the
// difference. Derived codes (`overdue`) are the registry's and are never in an enum.
//
// The registry's objects join this list as their API fields adopt the generated enums (C2 §3);
// the other status fields in the generated client are inline unions and join with them.
export const OPENAPI_STATUS_ENUMS = {
  engagement: true satisfies EnumCovered<"engagement", EngagementStatus>,
  request: true satisfies EnumCovered<"request", RequestStatus>,
  audit_section: true satisfies EnumCovered<"audit_section", AuditSectionStatus>,
} as const;
