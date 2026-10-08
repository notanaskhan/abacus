import {
  addDocumentMutation,
  listDocumentsOptions,
  listDocumentsQueryKey,
  withdrawDocumentMutation,
} from "@abacus/api-client/query";
import {
  Alert,
  Button,
  Dialog,
  EmptyState,
  Input,
  Label,
  Panel,
  Skeleton,
  StatusPill,
  Table,
  Td,
  Th,
  type Tone,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, type SyntheticEvent, useState } from "react";
import { errorMessage } from "../api";
import { ConfirmItsYou, isForbidden } from "../shell/mfa";

const STATUS: Record<string, { label: string; tone: Tone }> = {
  pending: { label: "Processing", tone: "info" },
  ready: { label: "Ready", tone: "success" },
  failed: { label: "Failed", tone: "danger" },
  stale: { label: "Needs reprocessing", tone: "warning" },
  withdrawn: { label: "Withdrawn", tone: "neutral" },
};

// SPEC-019 §12: a failed document's reason in plain words.
const FAILURES: Record<string, string> = {
  budget_exceeded: "The firm's model budget was reached. Raise it, then add the document again.",
  budget_exhausted: "The firm's model budget was used up. Raise it, then add the document again.",
  embed_refused: "The document couldn't be processed. Check the text and add it again.",
};

/** SPEC-019 AC-2: add, watch and withdraw the firm's methodology documents. */
export function KnowledgeDocuments(): JSX.Element {
  const queryClient = useQueryClient();
  const documents = useQuery({
    ...listDocumentsOptions(),
    refetchInterval: (query) =>
      (query.state.data ?? []).some((d) => d.status === "pending") ? 3000 : false,
  });
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: listDocumentsQueryKey() });
  };
  const [confirm, setConfirm] = useState(false);
  const [withdrawing, setWithdrawing] = useState<{ id: string; title: string } | null>(null);
  const withdraw = useMutation({
    ...withdrawDocumentMutation(),
    onSuccess: refresh,
    onError: (error) => {
      if (isForbidden(error)) setConfirm(true);
    },
  });
  return (
    <div className="flex flex-col gap-4">
      <AddDocument
        onAdded={refresh}
        onNeedsMfa={() => {
          setConfirm(true);
        }}
      />
      {withdraw.isError && !isForbidden(withdraw.error) && (
        <Alert title="Couldn't withdraw">{errorMessage(withdraw.error)}</Alert>
      )}
      {documents.isPending ? (
        <Skeleton className="h-32" />
      ) : documents.isError ? (
        <Alert title="Couldn't load documents">{errorMessage(documents.error)}</Alert>
      ) : documents.data.length === 0 ? (
        <EmptyState title="No documents yet">
          Add your methodology so staff can search it.
        </EmptyState>
      ) : (
        <div className="overflow-x-auto rounded-[var(--radius-panel)] border border-line bg-surface">
          <Table className="min-w-[560px]">
            <thead>
              <tr>
                <Th>Document</Th>
                <Th>Status</Th>
                <Th>Passages</Th>
                <Th>
                  <span className="sr-only">Actions</span>
                </Th>
              </tr>
            </thead>
            <tbody>
              {documents.data.map((d) => {
                const status = STATUS[d.status] ?? { label: d.status, tone: "neutral" as Tone };
                return (
                  <tr key={d.id}>
                    <Td className="font-semibold">{d.title}</Td>
                    <Td>
                      <StatusPill tone={status.tone}>{status.label}</StatusPill>
                      {d.status === "failed" && d.failure_code !== null && (
                        <p className="mt-1 text-xs text-muted">
                          {FAILURES[d.failure_code] ?? "Processing failed. Add it again."}
                        </p>
                      )}
                    </Td>
                    <Td className="tabular-nums">{d.chunk_count}</Td>
                    <Td className="text-right">
                      {d.status !== "withdrawn" && (
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => {
                            setWithdrawing({ id: d.id, title: d.title });
                          }}
                        >
                          Withdraw
                        </Button>
                      )}
                    </Td>
                  </tr>
                );
              })}
            </tbody>
          </Table>
        </div>
      )}
      <Dialog
        open={withdrawing !== null}
        onOpenChange={(open) => {
          if (!open) setWithdrawing(null);
        }}
        title={`Withdraw "${withdrawing?.title ?? ""}"?`}
        description="It stops appearing in search straight away."
      >
        <div className="flex justify-end gap-2">
          <Button
            variant="outline"
            onClick={() => {
              setWithdrawing(null);
            }}
          >
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={() => {
              if (withdrawing !== null) withdraw.mutate({ path: { document_id: withdrawing.id } });
              setWithdrawing(null);
            }}
          >
            Withdraw
          </Button>
        </div>
      </Dialog>
      <ConfirmItsYou open={confirm} onOpenChange={setConfirm} />
    </div>
  );
}

function AddDocument({
  onAdded,
  onNeedsMfa,
}: {
  onAdded: () => void;
  onNeedsMfa: () => void;
}): JSX.Element {
  const [title, setTitle] = useState("");
  const [text, setText] = useState("");
  const [kind, setKind] = useState<"firm_own" | "public">("firm_own");
  const [markdown, setMarkdown] = useState(false);
  const add = useMutation({
    ...addDocumentMutation(),
    onSuccess: () => {
      setTitle("");
      setText("");
      onAdded();
    },
    onError: (error) => {
      if (isForbidden(error)) onNeedsMfa();
    },
  });
  const submit = (event: SyntheticEvent): void => {
    event.preventDefault();
    add.mutate({
      body: {
        title: title.trim(),
        text,
        source_kind: kind,
        media_type: markdown ? "text/markdown" : "text/plain",
      },
    });
  };
  return (
    <Panel title="Add a document">
      <form className="flex flex-col gap-3" onSubmit={submit}>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="flex flex-col gap-1">
            <Label htmlFor="doc-title">Title</Label>
            <Input
              id="doc-title"
              required
              maxLength={200}
              value={title}
              onChange={(event) => {
                setTitle(event.target.value);
              }}
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor="doc-kind">Source</Label>
            <select
              id="doc-kind"
              value={kind}
              onChange={(event) => {
                setKind(event.target.value === "public" ? "public" : "firm_own");
              }}
              className="h-9 rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm"
            >
              <option value="firm_own">Our firm&apos;s own</option>
              <option value="public">Publicly available</option>
            </select>
          </div>
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="doc-file">Load a .txt or .md file (optional)</Label>
          <input
            id="doc-file"
            type="file"
            accept=".txt,.md,text/plain,text/markdown"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file === undefined) return;
              setMarkdown(file.name.toLowerCase().endsWith(".md"));
              if (title === "") setTitle(file.name.replace(/\.(txt|md)$/i, ""));
              void file.text().then(setText);
            }}
            className="text-sm"
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="doc-text">Text</Label>
          <textarea
            id="doc-text"
            required
            rows={6}
            value={text}
            onChange={(event) => {
              setText(event.target.value);
            }}
            className="rounded-[var(--radius-control)] border border-line bg-surface p-3 text-sm"
          />
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={markdown}
            onChange={(event) => {
              setMarkdown(event.target.checked);
            }}
          />
          The text is Markdown (headings become sections)
        </label>
        {add.isError && !isForbidden(add.error) && (
          <p role="alert" className="text-sm text-danger">
            {errorMessage(add.error)}
          </p>
        )}
        <div>
          <Button
            type="submit"
            disabled={add.isPending || title.trim() === "" || text.trim() === ""}
          >
            Add document
          </Button>
        </div>
      </form>
    </Panel>
  );
}
