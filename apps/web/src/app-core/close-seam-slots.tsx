// C-01-T57: the in-window closes components the seams lazy-import. Until each lands in the Sep 1
// window (C-01-T36 POR-11, C-01-T37 POR-04 e, C-01-T38 to T40 the close sources), a slot renders
// the screen it sits on unchanged, so turning a flag on early shows nothing broken.
import type { JSX, ReactNode } from "react";

export function CloseSourceSlot(props: {
  overlay: string;
  targetType: string;
  targetId: string;
  children: ReactNode;
}): JSX.Element {
  return <>{props.children}</>;
}

export function PortalCloseIntakeSlot(props: {
  period: string;
  children: ReactNode;
}): JSX.Element {
  return <>{props.children}</>;
}

export function QuestionVariantSlot(props: {
  questionId: string;
  children: ReactNode;
}): JSX.Element {
  return <>{props.children}</>;
}
