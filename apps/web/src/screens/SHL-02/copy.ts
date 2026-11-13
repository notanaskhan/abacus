// SHL-02 "Go…" copy, verbatim from the handoff (spec.md, revision.md R2) and docs/screens/SHL-02.md.
// The palette is "Go…" in copy, never "Search…" or "Command palette" (DEC-4502); "To-do", never
// "task"; "saved prompt", never a bare "prompt"; "Session" is a Workbench session.
export const COPY = {
  placeholder: "Go…",
  title: "Go…",
  groups: {
    clients: "Clients",
    returns: "Returns",
    audits: "Audits",
    closes: "Closes",
    binders: "Binders",
    files: "Files",
    inbox: "Inbox",
    sessions: "Sessions",
    todos: "To-dos",
    saved_prompts: "Saved prompts",
    agents: "Run an agent",
    actions: "Actions",
    recent: "Recent",
    create: "Create",
  },
  empty: (q: string) => `No matches for '${q}'.`,
  emptyHint: "Try a client, form, period or file name.",
  suggestion: (title: string, context: string | null) =>
    context === null ? `Did you mean ${title}?` : `Did you mean ${title} · ${context}?`,
  results: (n: number) => `${String(n)} results`,
  error: "Search isn't available right now. Try again.",
  hints: {
    mac: {
      navigate: "Navigate",
      open: "Open",
      newTab: "Open in new tab",
      newTabKey: "⌘↵",
      close: "Close",
    },
    other: {
      navigate: "Navigate",
      open: "Open",
      newTab: "Open in new tab",
      newTabKey: "Ctrl+↵",
      close: "Close",
    },
  },
  /** P-02-T10 rest (DEC-4631; P-02 AC "Actions … bound to the top Clients result"): the
   * context-bound actions, verbatim from SHL-02a and f. "Run an agent on ‹client›…" (W-02's
   * WB-01 target), "Message ‹contact›…" (N-03) and "Open board · ‹audit›" (K-04) join with their
   * epics' targets. */
  contextActions: [
    {
      id: "new-engagement-for",
      label: (client: string) => `New engagement for ${client}…`,
      screen: "ENG-03",
      href: (clientId: string) => `/engagements/new?client=${encodeURIComponent(clientId)}`,
    },
    {
      id: "new-todo-on",
      label: (client: string) => `New to-do on ${client}…`,
      screen: "SHL-17",
      href: (clientId: string) => `?ov=todos:new:client:${encodeURIComponent(clientId)}`,
    },
  ],
  create: [
    { id: "new-client", label: "New client…", screen: "CLI-01", href: "/clients?ov=new-client" },
    {
      id: "new-engagement",
      label: "New engagement…",
      screen: "ENG-01",
      href: "/engagements?ov=new-engagement",
    },
    {
      id: "new-session",
      label: "New Workbench session…",
      screen: "WB-02",
      href: "/workbench/sessions/new",
    },
    { id: "upload-inbox", label: "Upload to Inbox…", screen: "INB-01", href: "/inbox?ov=upload" },
    { id: "new-todo", label: "New to-do…", screen: "SHL-17", href: "?ov=todos:new" },
    {
      id: "load-prompt",
      label: "Load saved prompt…",
      screen: "WB-12",
      href: "/workbench/agents/prompts",
    },
    { id: "open-board", label: "Open board", screen: "AUD-03", href: "/audits" },
  ],
} as const;
