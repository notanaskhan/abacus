// C-01-T57: the in-window closes components the seams lazy-import. Until each lands in the Sep 1
// window (C-01-T36 POR-11, C-01-T37 POR-04 e, C-01-T38 to T40 the close sources), a slot renders
// the screen it sits on unchanged, so turning a flag on early shows nothing broken.
import type { JSX, ReactNode } from "react";
import { POR11 } from "../screens/POR-11";

export function CloseSourceSlot(props: {
  overlay: string;
  targetType: string;
  targetId: string;
  children: ReactNode;
}): JSX.Element {
  return <>{props.children}</>;
}

/** C-01-T41 (DEC-5638): POR-11 on the close of `?period=` (the seam already checked the flag). */
export function PortalCloseIntakeSlot(props: {
  period: string;
  children: ReactNode;
}): JSX.Element {
  const question = new URLSearchParams(window.location.search).get("question") ?? undefined;
  return <POR11 period={props.period} {...(question ? { questionId: question } : {})} />;
}

export function QuestionVariantSlot(props: {
  questionId: string;
  children: ReactNode;
}): JSX.Element {
  return <>{props.children}</>;
}
