// The smoke user's hosted sign-in (Q-01-T32). Staging and the production canary sign in through
// WorkOS AuthKit with an email code read from the sink mailbox, which F-04-T22's mailbox reader
// provides; that task registers the sign-in here. Until then the signed-in steps are off
// (SMOKE_SIGN_IN unset) and this says why instead of guessing. Nothing here holds a credential.
import type { Page } from "@playwright/test";

export type SmokeSignIn = (page: Page, environment: "staging" | "production") => Promise<void>;

let registered: SmokeSignIn | null = null;

export function registerSmokeSignIn(signIn: SmokeSignIn): void {
  registered = signIn;
}

export async function signInAsSmokeUser(
  page: Page,
  environment: "staging" | "production",
): Promise<void> {
  if (registered === null) {
    throw new Error(
      "no smoke sign-in registered: it needs the sink mailbox reader (F-04-T22) and the smoke user in WorkOS",
    );
  }
  await registered(page, environment);
}
