// The identity primitives (F-05-T14): the Accrued wordmark and monogram, the Agent's avatar, the
// firm's own mark and people. Exported from the package root.
export { FIRM_MARK_SIZES, FirmMark, type FirmMarkProps, type FirmMarkSize } from "./firm-mark";
export { firmInitials, personInitials } from "./initials";
export {
  AgentAvatar,
  type AgentAvatarProps,
  MONOGRAM_MIN,
  MONOGRAM_SIZES,
  Monogram,
  type MonogramProps,
  type MonogramSize,
} from "./monogram";
export {
  PERSON_SIZES,
  PERSON_TINTS,
  Person,
  PersonAvatar,
  type PersonAvatarProps,
  type PersonProps,
  type PersonSize,
  PersonStack,
  type PersonStackProps,
  type PersonTint,
  tintForJoin,
} from "./person";
export {
  PORTAL_BRAND_SLOTS,
  type PortalBrand,
  PortalBrandProvider,
  type PortalBrandProviderProps,
  SIGN_IN_METHODS,
  type SignInMethod,
  usePortalBrand,
} from "./portal-brand";
export { WORDMARK_MIN, Wordmark, type WordmarkProps } from "./wordmark";
