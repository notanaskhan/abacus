// The design system (ADR-011): every screen builds from these. Agent text goes through AgentText.
export { AGENT_TEXT_LIMIT, AgentText, type AgentTextProps, sanitiseAgentText } from "./agent-text";
export { cn } from "./cn";
// The T0 controls and pills (F-05-T14): Button, IconButton, and the Pill family.
export {
  BUTTON_SIZES,
  BUTTON_VARIANTS,
  Button,
  type ButtonForceState,
  type ButtonProps,
  type ButtonSize,
  type ButtonVariant,
  ICON_BUTTON_VARIANTS,
  IconButton,
  type IconButtonProps,
  type IconButtonVariant,
} from "./components/button";
export {
  CheckPill,
  type CheckPillProps,
  Count,
  type CountProps,
  type CountTone,
  DoneCount,
  type DoneCountProps,
  PILL_SIZES,
  PILL_VARIANTS,
  Pill,
  type PillProps,
  Tag,
  type TagProps,
} from "./components/pill";
export { type ForceState } from "./force-state";
export { Input, Label } from "./components/field";
export { Alert, Badge, Card, Spinner, type Tone } from "./components/surfaces";
// View states and feedback (F-05-T19): ViewState and its body, the C-20 States kit and the C-19
// Progress kit. EmptyState and Skeleton are the upgraded ones the app already imports.
export {
  AgentLive,
  type AgentLiveProps,
  AgentRunningRow,
  type AgentRunningRowProps,
  EmptyLink,
  EmptyState,
  type EmptyStateProps,
  type EmptyTone,
  ErrorRow,
  type ErrorRowProps,
  ErrorState,
  type ErrorStateProps,
  FieldsetEmpty,
  OfflineBanner,
  type OfflineBannerProps,
  type RunRowView,
  type RunState,
  SKELETON_COUNT,
  SKELETON_DELAY_MS,
  SKELETON_META_WIDTHS,
  SKELETON_TITLE_WIDTHS,
  STATE_COPY,
  STATE_GEOMETRY,
  Skeleton,
  type SkeletonProps,
  SkeletonRows,
  type SkeletonRowsProps,
  type SkeletonType,
  WaitingBadge,
  type WaitingBadgeProps,
  runRowView,
  skeletonRows,
  useDelayedShow,
  useOnline,
} from "./components/states";
export {
  type FlagKey,
  FlagOffState,
  type FlagOffStateProps,
  READ_ONLY_REASONS,
  RESTRICTED_COPY,
  type EmptyContent,
  type ReadOnlyReason,
  RestrictedState,
  type RestrictedStateProps,
  type StateAction,
  VIEW_STATE_KINDS,
  type ViewState,
  ViewStateBody,
  type ViewStateBodyProps,
  type ViewStateKind,
  flagLabel,
} from "./components/view-state";
export {
  KPI_STAGGER_MS,
  KpiGrid,
  KpiTile,
  type KpiTileProps,
  ProgressBar,
  type ProgressBarProps,
  RatioStat,
  type RatioStatItem,
  type RatioStatProps,
  StatusTile,
  type StatusTileProps,
  StatusTileStrip,
  type StatusTileStripProps,
  type StatusTileVariant,
  StepCounter,
  type StepCounterProps,
  UploadRing,
  type UploadRingProps,
} from "./components/progress";
export {
  type BarTone,
  type BarView,
  INDETERMINATE_LABEL,
  type KpiDelta,
  type KpiTone,
  LONG_PILL_CHARS,
  RING_CIRCUMFERENCE,
  RING_RADIUS,
  type RingView,
  SPARK_HEIGHT,
  SPARK_WIDTH,
  type StepInput,
  type StepState,
  type StepView,
  barView,
  isLongPillLabel,
  kpiDelta,
  percentOf,
  practiceOpen,
  ringView,
  sparkPoints,
  stepViews,
} from "./components/progress-model";
export { AiTag, Fraction, Panel } from "./components/workspace";
export {
  RegistryStatus,
  type RegistryStatusProps,
  Status,
  StatusDisc,
  type StatusDiscProps,
  StatusPill,
  type StatusPillProps,
  SubLine,
  type SubLineProps,
  SyncChip,
  type SyncChipProps,
  TallyPill,
  type TallyPillProps,
  Tick,
  type TickCode,
} from "./components/status";
export { Table, Td, Th } from "./components/table";
// Inputs and tabs (F-05-T15): the C-05 Tabs kit, the pill inputs, switches and boxes, the
// fieldset and its value rows, the menu and the tooltip.
export { Fieldset, FieldsetAdd, type FieldsetProps } from "./components/fieldset";
export {
  FilterChip,
  type FilterChipProps,
  Picker,
  type PickerOption,
  type PickerProps,
  type PickerVariant,
  SearchField,
  type SearchFieldProps,
  ValueRow,
  type ValueRowProps,
} from "./components/inputs";
export {
  Checkbox,
  type CheckboxProps,
  Radio,
  RadioGroup,
  type RadioGroupProps,
  type RadioOption,
  type RadioProps,
  type RadioSize,
  Toggle,
  type ToggleProps,
  type ToggleSize,
} from "./components/toggles";
export {
  DEFAULT_VIEWS,
  MAX_OPTIONS_PER_TRACK,
  type Opt,
  Segmented,
  SegmentedGroup,
  type SegmentedGroupProps,
  type SegmentedProps,
  SheetTabs,
  type SheetTabsProps,
  type TabForceState,
  type TabOption,
  UnderlineTabs,
  type UnderlineTabsProps,
  type ViewOption,
  ViewToggle,
  type ViewToggleProps,
  nextTab,
} from "./components/tabs";
export { HIT, MIN_TARGET } from "./components/hit-area";
export {
  Toast,
  ToastHost,
  Toaster,
  UNDO_MS,
  toast,
  toastStore,
  useToasts,
  type ToastHostProps,
  type ToastItem,
  type ToastKind,
  type ToastViewProps,
} from "./components/toast";
export {
  copyProblems,
  createToast,
  createToastStore,
  type RunningHandle,
  type ToastInput,
  type ToastStore,
  type UndoableHandle,
  type UndoableInput,
} from "./components/toast-store";
export {
  Menu,
  type MenuItem,
  type MenuProps,
  TOOLTIP_DELAY_MS,
  Tooltip,
  type TooltipProps,
  TooltipProvider,
} from "./components/popover";
export { type Column, DataTable } from "./components/data-table";
export { CitationChip } from "./components/citation";
export {
  Amount,
  type AmountProps,
  DateText,
  type DateKind,
  type DateTextProps,
} from "./components/amount";
export {
  type BoundFormat,
  ClockProvider,
  type ClockProviderProps,
  type NowSource,
  useFormat,
  useNow,
  useTimeZone,
  useToday,
} from "./clock";
export {
  type AmountOptions,
  type AmountStyle,
  type AmountTone,
  type Decimal,
  type FormattedAmount,
  type Instant,
  DASH,
  DEFAULT_TZ,
  SEP,
  accountMask,
  amount,
  bytes,
  cellRef,
  count,
  date,
  dateTime,
  einMask,
  isoDate,
  longDate,
  monthYear,
  parseDecimal,
  pct,
  period,
  progress,
  prose,
  ratio,
  relative,
  sameDay,
  since,
  ssnMask,
  time,
  viaAgent,
  weekdayDate,
  zoneName,
} from "./format";
// The shell's L1 (F-05-T18): AppShell, Toolbar and its nav overflow, PortalToolbar, RecordHeader,
// Tabsbar, Pane and PaneHeader, Timeline.
export * from "./layout";
export {
  DISC_LABEL,
  DISC_STATES,
  type DiscSize,
  type DiscState,
  type EnumCovered,
  HANDOFF_OBJECTS,
  type HandoffObject,
  handoffStatus,
  type LineTone,
  type PillSize,
  type PillVariant,
  type RegistryCode,
  type RegistryContext,
  type RegistryDisc,
  type RegistryObject,
  type RegistryVariant,
  registryWord,
  RETIRED,
  RETIRED_CODES,
  type RetiredWord,
  type ResolvedStatus,
  STATUS,
  status,
  type StatusDomain,
  type StatusOptions,
  type StatusWord,
  statusWord,
  type StoredCode,
  type SyncGlyph,
} from "./status";
export { HANDOFF_WORDS, STATUS_REGISTRY } from "./status.gen";
// Motion (F-05-T14): the reduced-motion hook, the word reveal and the animated primitives.
export {
  REDUCED_MOTION_QUERY,
  type WordReveal,
  WORD_REVEAL_MS,
  useMotion,
  useReducedMotion,
  useWordReveal,
  wordsOf,
} from "./motion";
export {
  LiveDot,
  type LiveDotProps,
  PULSE_STAGGER_MS,
  Pulse,
  type PulseProps,
  Reveal,
  type RevealProps,
  SPINNER_SIZES,
  type SpinnerProps,
  type SpinnerSize,
  TypingDots,
  type TypingDotsProps,
} from "./components/motion";
// Identity (F-05-T14): wordmark, monogram, the Agent's avatar, the firm's mark and people.
export * from "./brand";
// The icon registry (F-05-T13): handoff kebab names, the Icon component and the custom glyphs.
export * from "./icons";
// Icons for the shell, so apps use one icon set without depending on it directly.
export {
  Atom,
  Bell,
  BookOpen,
  Building2,
  ChevronDown,
  ChevronLeft,
  FolderOpen,
  LogOut,
  PanelRight,
  Search,
} from "lucide-react";
export * from "./overlays";

// E4 DataTable engine (F-05-T27): the grid on @tanstack/react-table, ledger and statement grammars.
export * from "./data";

// Templates (F-05-T28): T1 IndexList on the list envelope.
export * from "./templates";

// Attribution and human verbs (F-05-T30).
export * from "./attribution";

// C-16 Request kit, portal variant (F-05-T36).
export * from "./requests";

// C-03 Rail kit and C-04 Record kit (F-05-T40).
export * from "./record";
