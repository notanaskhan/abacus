// The shell's L1 (C-00 Shell Kit, F-05-T18): AppShell, the firm Toolbar with its measured nav
// overflow, the PortalToolbar and footer, the RecordHeader, the Tabsbar, Pane and PaneHeader, and
// the Timeline. Exported from the package root.
export {
  AppShell,
  type AppShellProps,
  type FirmShellProps,
  type PortalShellProps,
} from "./app-shell";
export {
  FALLBACK_STAGES,
  type FallbackStage,
  type FitInput,
  type FitOptions,
  type ToolbarFit,
  type ToolbarMeasure,
  fitNav,
  fitToolbar,
  navSpace,
} from "./nav-overflow";
export {
  FooterAction,
  type FooterActionKind,
  type FooterActionProps,
  FooterSpacer,
  Pane,
  PaneAction,
  type PaneActionKind,
  type PaneActionProps,
  PaneHeader,
  type PaneHeaderProps,
  type PaneProps,
} from "./pane";
export {
  MOBILE_TABS,
  MobileHeader,
  type MobileHeaderProps,
  MobileTabBar,
  type MobileTabBarProps,
  splitMobileNav,
} from "./mobile-tab-bar";
export {
  PortalFooter,
  type PortalNavItem,
  PortalToolbar,
  type PortalToolbarProps,
} from "./portal-toolbar";
export {
  type AuditRecordHeaderProps,
  type CloseRecordHeaderProps,
  type DefaultRecordHeaderProps,
  RecordHeader,
  type RecordHeaderProps,
  type RecordHeaderVariant,
  type SettingsRecordHeaderProps,
  type SyncCode,
} from "./record-header";
export { Tabsbar, type TabsbarProps, type TabsbarSize } from "./tabsbar";
export { Timeline, type TimelineEvent, type TimelineProps } from "./timeline";
export {
  Toolbar,
  type ToolbarForceState,
  type ToolbarNavItem,
  type ToolbarProps,
} from "./toolbar";
export {
  NestedSplit,
  type NestedSplitProps,
  ResizeGutter,
  type ResizeGutterProps,
  SplitLayout,
  type SplitLayoutProps,
  useNarrowLayout,
} from "./split-layout";
export {
  SPLIT,
  SPLIT_PRESETS,
  type PresetPane,
  type SplitPreset,
  type SplitPresetName,
  clampWidth,
  dragTarget,
  roomFor,
  splitStorageKey,
} from "./split-presets";
