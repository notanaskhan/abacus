import type { JSX, ReactNode } from "react";
import type { Action } from "./actions.gen";
import { type Scope, useCapabilities } from "./session";

// What the person may do (F-03-T32; ADR-145). The server evaluates the permission matrix; this
// only reads the answer. `Action` comes from actions.gen.ts, so a misspelt action is a type
// error. While capabilities load, or if they fail, the answer is false (fail closed).

/** Whether the person may take `action`: on the firm, or on `scope.engagementId`. */
export function useCan(action: Action, scope: Scope = {}): boolean {
  return useCapabilities(scope)?.capabilities.includes(action) ?? false;
}

interface CanProps {
  action: Action;
  engagementId?: string | undefined;
  children: ReactNode;
  /** Rendered instead when the person may not, or while capabilities load. */
  fallback?: ReactNode;
}

/** Renders `children` only when the person may take `action`. */
export function Can({ action, engagementId, children, fallback = null }: CanProps): JSX.Element {
  return <>{useCan(action, { engagementId }) ? children : fallback}</>;
}
