// Lucide glyphs per column type (F-08-T05; T18 headers).
import {
  AtSign,
  Calendar,
  CircleDot,
  DollarSign,
  FileText,
  Hash,
  Inbox,
  PenLine,
  ShieldAlert,
  Sparkles,
  Type,
  type LucideIcon,
} from "lucide-react";
import type { SheetColumnType } from "./types";

export const COLUMN_GLYPHS: Readonly<Record<SheetColumnType, LucideIcon>> = {
  text: Type,
  number: Hash,
  currency: DollarSign,
  date: Calendar,
  single_select: CircleDot,
  person: AtSign,
  linked_evidence: FileText,
  linked_request: Inbox,
  linked_risk: ShieldAlert,
  sign_off: PenLine,
  agent: Sparkles,
};
