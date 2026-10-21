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
export { Dialog } from "./components/dialog";
export { Input, Label } from "./components/field";
export {
  Alert,
  Badge,
  Card,
  EmptyState,
  Skeleton,
  Spinner,
  type Tone,
} from "./components/surfaces";
export { AiTag, Fraction, Panel, Rail, RailButton } from "./components/workspace";
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
export { Drawer, Sheet } from "./components/overlays";
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
export { Toaster, UNDO_MS, toast } from "./components/toast";
export {
  Menu,
  type MenuItem,
  type MenuProps,
  Popover,
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
  since,
  ssnMask,
  time,
  viaAgent,
} from "./format";
export { CommandPalette, type PaletteGroup, type PaletteItem } from "./components/command-palette";
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
