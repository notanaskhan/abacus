import { listTemplatesOptions, listTemplatesQueryKey } from "@abacus/api-client/query";
import {
  Alert,
  Button,
  EmptyState,
  Input,
  Label,
  Panel,
  Skeleton,
  Table,
  Td,
  Th,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { type JSX, type SyntheticEvent, useState } from "react";
import { errorMessage } from "../api";
import { ConfirmItsYou, isForbidden } from "../shell/mfa";
import { type Problem, XLSX, uploadWorkbook, workbookProblems } from "./methodologyUpload";

/** SPEC-016 AC-6: templates and versions; upload with row-level problems and fresh MFA. */
export function Methodology(): JSX.Element {
  const templates = useQuery(listTemplatesOptions());
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-3xl">Methodology</h1>
        <p className="text-sm text-muted">
          Your firm&apos;s audit areas, standard requests and account rules. Each upload becomes a
          new version; engagements keep the version they started with.
        </p>
      </div>
      <UploadPanel />
      {templates.isPending ? (
        <Skeleton className="h-40" />
      ) : templates.isError ? (
        <Alert
          title="Couldn't load templates"
          action={
            <Button size="sm" variant="outline" onClick={() => void templates.refetch()}>
              Retry
            </Button>
          }
        >
          {errorMessage(templates.error)}
        </Alert>
      ) : templates.data.length === 0 ? (
        <EmptyState title="No methodology yet">
          Upload your first template workbook with the Areas, Requests and Account rules sheets.
        </EmptyState>
      ) : (
        <div className="overflow-x-auto rounded-[var(--radius-panel)] border border-line bg-surface">
          <Table className="min-w-[560px]">
            <thead>
              <tr>
                <Th>Template</Th>
                <Th>Version</Th>
                <Th>Uploaded</Th>
              </tr>
            </thead>
            <tbody>
              {templates.data.map((t) => (
                <tr key={t.version_id}>
                  <Td>
                    <Link
                      to="/admin/methodology/$versionId"
                      params={{ versionId: t.version_id }}
                      className="font-semibold text-accent hover:underline"
                    >
                      {t.template_name}
                    </Link>
                  </Td>
                  <Td className="tabular-nums">v{t.version}</Td>
                  <Td className="text-muted">{new Date(t.created_at).toLocaleDateString()}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      )}
    </div>
  );
}

function UploadPanel(): JSX.Element {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [problems, setProblems] = useState<Problem[] | null>(null);
  const [confirm, setConfirm] = useState(false);
  const upload = useMutation({
    mutationFn: async ({ n, f }: { n: string; f: File }) => {
      await uploadWorkbook(n, f);
    },
    onMutate: () => {
      setProblems(null);
    },
    onSuccess: () => {
      setFile(null);
      void queryClient.invalidateQueries({ queryKey: listTemplatesQueryKey() });
    },
    onError: (error) => {
      if (isForbidden(error)) setConfirm(true);
      else setProblems(workbookProblems(error));
    },
  });
  const submit = (event: SyntheticEvent): void => {
    event.preventDefault();
    if (file !== null && name.trim() !== "") upload.mutate({ n: name.trim(), f: file });
  };
  return (
    <Panel title="Upload a version">
      <form className="flex flex-wrap items-end gap-3" onSubmit={submit}>
        <div className="flex flex-col gap-1">
          <Label htmlFor="template-name">Template name</Label>
          <Input
            id="template-name"
            required
            maxLength={100}
            value={name}
            onChange={(event) => {
              setName(event.target.value);
            }}
          />
        </div>
        <div className="flex flex-col gap-1">
          <Label htmlFor="template-file">Workbook (.xlsx)</Label>
          <input
            id="template-file"
            type="file"
            accept={`.xlsx,${XLSX}`}
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
            }}
            className="text-sm file:mr-3 file:rounded-[var(--radius-control)] file:border file:border-line file:bg-surface file:px-3 file:py-1.5 file:text-sm"
          />
        </div>
        <Button type="submit" disabled={upload.isPending || file === null}>
          {upload.isPending ? "Uploading…" : "Upload"}
        </Button>
      </form>
      {upload.isSuccess && <p className="text-sm text-ok">New version uploaded.</p>}
      {problems !== null && problems.length > 0 && (
        <div role="alert" className="flex flex-col gap-2">
          <p className="text-sm font-semibold text-danger">
            Nothing was saved. Fix{" "}
            {problems.length === 1 ? "this problem" : `these ${String(problems.length)} problems`}{" "}
            and upload again.
          </p>
          <Table>
            <thead>
              <tr>
                <Th>Where</Th>
                <Th>Problem</Th>
              </tr>
            </thead>
            <tbody>
              {problems.map((p, index) => (
                <tr key={`${p.where}-${String(index)}`}>
                  <Td className="whitespace-nowrap tabular-nums">{p.where}</Td>
                  <Td>{p.message}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      )}
      {upload.isError && problems === null && !confirm && (
        <p role="alert" className="text-sm text-danger">
          {errorMessage(upload.error)}
        </p>
      )}
      <ConfirmItsYou open={confirm} onOpenChange={setConfirm} />
    </Panel>
  );
}
