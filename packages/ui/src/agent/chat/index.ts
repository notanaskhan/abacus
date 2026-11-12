// T4 Workbench chat kit (F-07): the session list and the chat header (F-07-T02); the thread and
// composer land with F-07-T03, the question card with F-07-T06.
export { ChatHeader, type ChatHeaderProps } from "./chat-header";
export {
  SESSION_LIST_GEOMETRY,
  SessionList,
  type SessionListProps,
  type SessionRow,
  sessionMeta,
  type WorkbenchSessionStatus,
} from "./session-list";
// F-07-T03: the thread, its rows and the composer (SPEC-652 AC-4).
export {
  type ArtifactIntent,
  ChatThread,
  type ChatThreadProps,
  type SlotKind,
  type ThreadItem,
  type ThreadItemKind,
} from "./thread";
// F-07-T06: the chat-ask DecisionCard variant above the composer (SPEC-652 AC-5).
export {
  QUESTION_CARD_GEOMETRY,
  type QuestionAnswer,
  QuestionCard,
  type QuestionCardProps,
  type QuestionOption,
  type QuestionPayload,
  type QuestionStep,
} from "./question-card";
// F-07-T07: the empty session, the context row and picker, and WB-06's agent detail.
export {
  AGENT_DETAIL_GEOMETRY,
  AgentDetail,
  type AgentDetailProps,
  type AgentFact,
  type AgentRecentRun,
  type AgentRunState,
} from "./agent-detail";
export { CONTEXT_PICKER_WIDTH, ContextPicker, type ContextPickerProps } from "./context-picker";
export {
  CONTEXT_KINDS,
  ContextChips,
  type ContextChipsProps,
  type ContextItem,
  type ContextKind,
  EMPTY_SESSION_COPY,
  EMPTY_SESSION_GEOMETRY,
  EmptySession,
  type EmptySessionProps,
  type SuggestedPrompt,
} from "./empty-session";
