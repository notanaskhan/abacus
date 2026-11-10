// SHL-18 Comments and @mentions (P-05-T10): C-29 CommentThread v2 in its three hosts, one artboard
// at a time. The popover and drawer variants read the server through the generated client; in the
// gallery, fixture mode answers with the seed.
import { type JSX } from "react";
import { LiveCommentThread } from "../../domain/collaboration";
import { FRAMES, type State } from "./scenarios";

export interface CommentsAndMentionsProps {
  state: State;
  onConvertToTodo?: () => void;
  onClose?: () => void;
}

export function CommentsAndMentions({
  state,
  onConvertToTodo,
  onClose,
}: CommentsAndMentionsProps): JSX.Element {
  const frame = FRAMES[state];
  return (
    <div data-screen="SHL-18" data-state={state} data-live={frame.live}>
      <LiveCommentThread
        variant={frame.variant}
        anchor={frame.anchor}
        anchorLabel={frame.anchorLabel}
        engagementId={frame.engagementId}
        engagementLabel={frame.engagementLabel}
        viewerId={frame.viewerId}
        {...(frame.context ? { context: frame.context } : {})}
        {...(frame.sharedWith ? { sharedWith: frame.sharedWith } : {})}
        {...(frame.draft === undefined ? {} : { initialDraft: frame.draft })}
        {...(state === "d" ? { expandResolved: true } : {})}
        onCopyLink={() => undefined}
        {...(onConvertToTodo ? { onConvertToTodo } : {})}
        {...(onClose ? { onClose } : {})}
      />
    </div>
  );
}

export { FRAMES, STATES, scenarios } from "./scenarios";
