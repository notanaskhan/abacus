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
// Icons for the shell, so apps use one icon set without depending on it directly.
export { Bell, Building2, FolderOpen, LogOut } from "lucide-react";
