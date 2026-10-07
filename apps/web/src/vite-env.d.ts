/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** The OpenID Connect provider (local: the fake sign-in server; staging: WorkOS, TASK-014). */
  readonly VITE_OIDC_AUTHORITY?: string;
  readonly VITE_OIDC_CLIENT_ID?: string;
}
