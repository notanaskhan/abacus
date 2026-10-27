// The knowledge domain (K-01 §5.1): the catalog's category registry and reads. The portal bundle
// imports nothing from here (INV-4).
export {
  CATEGORIES,
  type CategoryDef,
  type KnowledgeCategory,
  TONE_FILL,
  type Tone,
  type UsageKind,
  categoryDef,
  usageWords,
} from "./categories";
export { type CatalogFilters, useChangeLog, useKnowledgeItems, useReviewQueue } from "./queries";
