// C-29 (P-05-T10): CommentThread v2, its Composer and MentionPicker; shared later with the portal.
export { CommentChip, type CommentChipProps } from "./CommentChip";
export { CommentComposer, type ComposerSubmit } from "./CommentComposer";
export {
  type CommentAnchor,
  CommentThreadView,
  type CommentThreadViewProps,
  LiveCommentThread,
  type LiveCommentThreadProps,
  type ThreadVariant,
  VARIANT_WIDTH,
} from "./CommentThread";
export { COPY as COMMENT_COPY } from "./copy";
export { activeMention, insertMention, segments } from "./mentions";
export { MentionPicker, pickerEntries } from "./MentionPicker";
