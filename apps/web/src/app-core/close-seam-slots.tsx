// C-01-T57: the in-window closes components the seams lazy-import. Until each lands in the Sep 1
// window (C-01-T36 POR-11, C-01-T37 POR-04 e, C-01-T38 to T40 the close sources), a slot renders
// the screen it sits on unchanged, so turning a flag on early shows nothing broken.
import { type JSX, type ReactNode, Suspense, lazy } from "react";

// POR-11 is portal code: the firm production build (which reaches this file through the close
// sources) drops the import, so portal screens never enter the firm chunk graph (the route
// budgets, F-05-T17). The portal build (`--mode portal`), dev and tests keep it.
const FIRM_PRODUCTION = import.meta.env.MODE === "production";
const POR11 = lazy(async () =>
  FIRM_PRODUCTION
    ? { default: Unchanged }
    : { default: (await import("../screens/POR-11")).POR11 },
);

function Unchanged(props: {
  children?: ReactNode;
  period?: string;
  questionId?: string;
}): JSX.Element {
  return <>{props.children}</>;
}

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
  return (
    <Suspense fallback={props.children}>
      <POR11 period={props.period} {...(question ? { questionId: question } : {})}>
        {props.children}
      </POR11>
    </Suspense>
  );
}

export function QuestionVariantSlot(props: {
  questionId: string;
  children: ReactNode;
}): JSX.Element {
  return <>{props.children}</>;
}
