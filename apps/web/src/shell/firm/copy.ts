// The firm shell's interim frames (P-01-T02). The shortcut list is SHL-03's ("Keyboard shortcuts
// → shortcuts dialog (560w) listing ⌘K Go…, G H Home, G T Tax Returns, G A Audits, G C Closes,
// G W Workbench, ? Help"); "Support" and "System status" are SHL-05's words. The rest is the
// undesigned interim copy of P-01 §2.2, reviewed by AY (DEC-32 pattern, recorded in TASK-396).

export const INTERIM_GO = {
  placeholder: "Go to an area",
  areas: "Areas",
  shortcutsTitle: "Shortcuts",
  shortcuts: [
    { keys: "⌘K", label: "Go…" },
    { keys: "G H", label: "Home" },
    { keys: "G T", label: "Tax Returns" },
    { keys: "G A", label: "Audits" },
    { keys: "G C", label: "Closes" },
    { keys: "G W", label: "Workbench" },
    { keys: "?", label: "Help" },
  ],
} as const;

export const INTERIM_SUPPORT = {
  title: "Support",
  contact: "Accrued Support",
  contactLine: (email: string) => `Write to ${email}`,
  status: "System status",
} as const;
