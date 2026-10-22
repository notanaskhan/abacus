import type { JSX, ReactNode } from "react";
import { type Module, useCapabilities } from "./session";

// Flags and entitlements for the active firm (F-03-T32; ADR-145), from `/v1/me/capabilities`.
// While it loads, or if it fails, a flag reads false and no module is held (fail closed).

/** A flag's value: a boolean, or a variant flag's value. */
export function useFlag(name: string): boolean | string {
  return useCapabilities()?.flags[name] ?? false;
}

/** Whether the active firm holds `module`. */
export function useEntitlement(module: Module): boolean {
  return useCapabilities()?.entitlements.includes(module) ?? false;
}

interface GateProps {
  children: ReactNode;
  /** Rendered instead when the gate is shut, or while capabilities load. */
  fallback?: ReactNode;
}

type FeatureGateProps = GateProps &
  (
    | {
        flag: string;
        /** For a variant flag: open only when the flag holds this value. */
        value?: string;
        entitlement?: never;
      }
    | { entitlement: Module; flag?: never; value?: never }
  );

function FlagGate({
  flag,
  value,
  children,
  fallback,
}: GateProps & { flag: string; value: string | undefined }): JSX.Element {
  const held = useFlag(flag);
  const open = value === undefined ? held === true : held === value;
  return <>{open ? children : fallback}</>;
}

function EntitlementGate({
  entitlement,
  children,
  fallback,
}: GateProps & { entitlement: Module }): JSX.Element {
  return <>{useEntitlement(entitlement) ? children : fallback}</>;
}

/** Renders `children` only when `flag` is on (or holds `value`), or the firm holds the module. */
export function FeatureGate(props: FeatureGateProps): JSX.Element {
  const fallback = props.fallback ?? null;
  return props.entitlement !== undefined ? (
    <EntitlementGate entitlement={props.entitlement} fallback={fallback}>
      {props.children}
    </EntitlementGate>
  ) : (
    <FlagGate flag={props.flag} value={props.value} fallback={fallback}>
      {props.children}
    </FlagGate>
  );
}
