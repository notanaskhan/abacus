// The review domain's public entry (P-04 §5): what screens import.
export {
  type Gate,
  type GateBlocked,
  type GatePhase,
  type UseGateOptions,
  conflictOf,
  needsStepUp,
  useGate,
} from "./useGate";
export {
  type ProposalWrites,
  REJECT_REASONS,
  type RejectReason,
  useProposal,
  useProposalWrites,
} from "./proposals";
