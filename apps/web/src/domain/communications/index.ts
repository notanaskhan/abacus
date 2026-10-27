// The communications domain's public entry (R-01-T25): the interim EmailPreview and the template
// editor's helpers, for POR-20 (and ADM-10 with R-01-T28).
export {
  EmailPreview,
  type EmailPreviewProps,
  type PreviewWidth,
  guardedDocument,
} from "./EmailPreview";
export { type Segment, insertAt, segments } from "./templateBlocks";
export { token, variableLabel, variableWords } from "./variables";
