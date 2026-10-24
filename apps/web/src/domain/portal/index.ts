// The portal domain's public entry (P-08 §5.2): what portal screens and the portal entry import.
// Nothing here reaches the firm's shell or domains (INV-4).
export type {
  InvitationPreviewOut,
  PortalBrandingOut,
  PortalSignInStartIn,
  PortalSignInVerifyIn,
  PortalLanding,
  PortalSignInStartOut,
  PortalSignInVerifyOut,
  SignInOpening,
} from "../../app-core/portal-contracts";
export { useDismissWelcome, usePortalHome } from "./home";
export {
  type BinderView,
  binderView,
  ignoreCodeOf,
  useBinder,
  useBinderActions,
  useBinders,
} from "./documents";
export { DOCUMENT_WORDS, SIGN_IN_WORDS, failureWords } from "./messages";
export { type PortalToolbarData, portalToolbarData, usePortalToolbar } from "./shell";
export {
  LANDING_PATH,
  portalAccessToken,
  setPortalAccessToken,
  setPortalSession,
} from "../../app-core/portal-session";
export {
  type SignInFailure,
  brandOf,
  failureOf,
  getBranding,
  signIn,
  useBranding,
} from "./sign-in";
