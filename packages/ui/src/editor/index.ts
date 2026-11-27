// F-08-T28 (DEC-6026): the T20 document editor kit (L2 `editor/`). Its own entry
// (`@abacus/ui/editor`), never the barrel, so TipTap lands only in the engine-editor chunk.
export { DocumentEditor, type DocumentEditorProps } from "./DocumentEditor";
export { PAPER, Paper, PaperWell } from "./PaperWell";
export { plainDrop, plainPaste } from "./paste";
export { PROTECTED_NODES, protectPlugin, touchesLocked } from "./protect";
export { documentExtensions } from "./schema";
export { paperAmount } from "./format";
export type { SectionLock, StatementRow, StatementTableAttrs } from "./types";
export {
  LINKED_UNDERLINE,
  LineagePopover,
  LinkedValueProvider,
  OverrideForm,
  type Lineage,
  type LineageGroup,
  type LinkedSource,
  type LinkedValueAttrs,
  type LinkedValueHandlers,
} from "./linked";
