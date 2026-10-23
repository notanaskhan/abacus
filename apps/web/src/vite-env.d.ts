/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** "1" compiles the /components gallery (F-05-T09). Dev servers default it on; production never has it. */
  readonly VITE_UI_GALLERY?: string;
  /** "1" answers the generated client from the Brightwater Hale seed (F-04-T04, T05): `make dev-fixtures`. Production never has it. */
  readonly VITE_FIXTURES?: string;
  /** The Accrued Support address the interim Support frame shows (P-01-T02, until SHL-05). */
  readonly VITE_SUPPORT_EMAIL?: string;
  /** The System status page (Q-01-T41), linked from the interim Support frame. */
  readonly VITE_STATUS_PAGE_URL?: string;
  /** The release the firm menu's footer names ("Version 2026.9", SHL-03; P-01-T08). Unset hides it. */
  readonly VITE_APP_VERSION?: string;
}
