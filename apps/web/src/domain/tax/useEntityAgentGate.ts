// T-05-T66 (TASK-8073; SPEC-651 AC-13.1): an entity return's agent gate, read for its engagement
// (`GET /v1/agents/capabilities?engagement_id=`), so a §7216 refusal is this client's, not the
// firm's. The return record supplies the engagement (cached by the entity layout); until both
// answer, nothing is offered (fail closed).
import { listCapabilitiesOptions, returnRecordOptions } from "@abacus/api-client/query";
import { useQuery } from "@tanstack/react-query";
import { type AgentGate, type EntityCapability, entityAgentGate } from "./agents";

export function useEntityAgentGate(returnId: string, capability: EntityCapability): AgentGate {
  const record = useQuery(returnRecordOptions({ path: { return_id: returnId } }));
  const engagement = record.data?.engagement_id;
  const caps = useQuery({
    ...listCapabilitiesOptions({ query: { engagement_id: engagement ?? null } }),
    enabled: engagement !== undefined,
    retry: false,
  });
  return entityAgentGate(engagement === undefined ? undefined : caps.data, capability);
}
