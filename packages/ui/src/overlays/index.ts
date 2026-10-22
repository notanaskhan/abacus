// The overlay stack E3 (F-05-T20): the OverlayStack store, the layers of the O1 to O6 grammar and
// the C-22 dialogs. Exported from the package root; the ?ov= codec and OverlayHost are the app's
// (apps/web/src/app-core/overlays.ts).
export { ConfirmDialog, type ConfirmDialogProps, DiscardGuard } from "./confirm";
export { DIALOG_WIDTH, Dialog, type DialogProps, type DialogSize } from "./dialog";
export { Drawer, DrawerCard, type DrawerProps, type DrawerSize } from "./drawer";
export {
  CommandPalette,
  type CommandPaletteProps,
  type PaletteGroup,
  type PaletteItem,
} from "./palette";
export { Popover, type PopoverProps, PopoverSection, type PopoverVariant } from "./popover";
export {
  FullSheet,
  type FullSheetProps,
  Sheet,
  SheetColumn,
  SheetColumns,
  SheetModal,
  type SheetModalProps,
  SheetRow,
} from "./sheet";
export {
  type CloseReason,
  type LayerInit,
  type OverlayKind,
  type OverlayLayer,
  type OverlayStack,
  appOverlayStack,
  createOverlayStack,
} from "./stack";
export {
  type LayerHandle,
  type LayerOptions,
  OverlayStackProvider,
  layerZ,
  panelZ,
  useAnchoredZ,
  useOverlayLayer,
  useOverlayLayers,
  useOverlayStack,
} from "./stack-react";
export { Wizard, type WizardProps, type WizardStep, type WizardStepState } from "./wizard";
