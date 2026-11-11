// C-29 (P-05-T10): CommentThread v2, its Composer and MentionPicker; shared later with the portal.
// The row chip is `domain/comment-chip` (kept apart so its hosts' route chunks stay small).
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
export { DueChip, dueWords, Ring, ToDoGroup, ToDoRow, type DueWords } from "./todos"; // P-05-T13
