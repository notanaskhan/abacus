// T10 DocumentOnWell (F-06-T14): the template, its panes and its view model.
export {
  DocumentOnWell,
  type DocumentOnWellProps,
  DraftWatermark,
  PaperCard,
  agentDrafting,
} from "./DocumentOnWell";
export { ClauseToggles, KvSheet, StructurePane, VariablesFieldset } from "./StructurePane";
export type {
  ApproveVM,
  ClauseVM,
  DocumentOnWellCopy,
  DocumentStatus,
  DocumentVM,
  DocumentVariant,
  KvRowVM,
  KvSectionVM,
  KvSheetVM,
  StructureVM,
  VariableVM,
} from "./types";
// F-06-T15: the paper's body over P-24 segments, and the email variant's frame.
export {
  type DocBlock,
  DocBlocks,
  type DocBlocksProps,
  type DocSegment,
  EmailFrame,
  type Provenance,
  agentAllowed,
} from "./DocBlocks";
