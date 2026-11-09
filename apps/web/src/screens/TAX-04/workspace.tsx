import type { JSX, ReactNode } from "react";
import { WorkspaceFrame, type WorkspaceTab } from "./frame";

// The review workspace's sections as a screen module (T-04-T12): the routes load it lazily and hold
// the flags; each section's body is its own screen's (TAX-04 Prepare is index.tsx).

export interface WorkspaceProps {
  returnId: string;
  tab: WorkspaceTab;
  title: string;
  onTab: (tab: WorkspaceTab) => void;
  onAssistant: () => void;
  children?: ReactNode;
}

export function Workspace(props: WorkspaceProps): JSX.Element {
  return (
    <WorkspaceFrame
      returnId={props.returnId}
      tab={props.tab}
      title={props.title}
      onTab={props.onTab}
      onAssistant={props.onAssistant}
    >
      {props.children}
    </WorkspaceFrame>
  );
}

export type { WorkspaceTab } from "./frame";
