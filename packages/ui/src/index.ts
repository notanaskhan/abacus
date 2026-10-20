// The design system (ADR-011): every screen builds from these. Agent text goes through AgentText.
export { AGENT_TEXT_LIMIT, AgentText, type AgentTextProps, sanitiseAgentText } from "./agent-text";
export { cn } from "./cn";
export { Button, type ButtonProps } from "./components/button";
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
export { AiTag, Count, Panel, Rail, RailButton, StatusPill } from "./components/workspace";
export { Table, Td, Th } from "./components/table";
export { Drawer, Fieldset, Sheet } from "./components/overlays";
export { Toaster, UNDO_MS, toast } from "./components/toast";
export { Menu, type MenuItem, Popover, Tooltip, TooltipProvider } from "./components/popover";
export { type Column, DataTable } from "./components/data-table";
export { STATUS, Status, type StatusDomain, type StatusWord, statusWord } from "./status";
// Icons for the shell, so apps use one icon set without depending on it directly.
export {
  Bell,
  BookOpen,
  Building2,
  ChevronDown,
  ChevronLeft,
  FolderOpen,
  LogOut,
} from "lucide-react";
