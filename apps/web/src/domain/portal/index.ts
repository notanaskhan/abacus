// The portal domain's public entry (P-08 §5.2): what portal screens and the portal entry import.
// Nothing here reaches the firm's shell or domains (INV-4).
export type {
  AcceptedInvitationOut,
  InvitationPreviewOut,
  PortalMfaSetupOut,
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
  type RefusedFile,
  type SendResult,
  binderView,
  ignoreCodeOf,
  useBinder,
  useBinderActions,
  useBinders,
} from "./documents";
export { DOCUMENT_WORDS, ROOM_WORDS, SHEET_WORDS, SIGN_IN_WORDS, failureWords } from "./messages";
export {
  type QuestionAnswer,
  type SheetDecision,
  type SheetQuestion,
  noteRecipient,
  postComment,
  uploadFiles,
  useRequestSheet,
  useSheetActions,
  useThread,
  withdrawFile,
  withdrawableFile,
} from "./sheet";
export { DROP_POLL_MS, type DropOutcome, dropOutcome, useDropBatch } from "./drops";
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
  invitation,
  signIn,
  useBranding,
} from "./sign-in";
export {
  type DecisionSlot,
  type QuestionSlot,
  RequestSheet,
  type RequestSheetProps,
  type RequestSlot,
  type SheetSlot,
} from "./RequestSheet";
export { openRows, roomRows, suggestFor, useRoom, useRoomActions } from "./room";
export { ScopedRequestRoom, type ScopedRequestRoomProps } from "./ScopedRequestRoom";
