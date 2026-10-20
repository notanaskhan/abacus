/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** The OpenID Connect provider (local: the fake sign-in server; staging: WorkOS, TASK-014). */
  readonly VITE_OIDC_AUTHORITY?: string;
  readonly VITE_OIDC_CLIENT_ID?: string;
  /** "1" compiles the /components gallery (F-05-T09). Dev servers default it on; production never has it. */
  readonly VITE_UI_GALLERY?: string;
}
