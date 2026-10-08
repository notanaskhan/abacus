import type { KnowledgeHitOut } from "@abacus/api-client";
import { searchMutation } from "@abacus/api-client/query";
import { Button, EmptyState, Input, Label, Panel } from "@abacus/ui";
import { useMutation } from "@tanstack/react-query";
import { type JSX, type SyntheticEvent, useState } from "react";
import { errorMessage } from "../api";

/** SPEC-019 AC-1: search the firm's methodology documents (plain text, not model output). */
export function Knowledge(): JSX.Element {
  const [query, setQuery] = useState("");
  const search = useMutation(searchMutation());
  const submit = (event: SyntheticEvent): void => {
    event.preventDefault();
    if (query.trim() !== "") search.mutate({ body: { query: query.trim(), k: 10 } });
  };
  const hits: KnowledgeHitOut[] = search.data ?? [];
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-3xl">Knowledge</h1>
        <p className="text-sm text-muted">Search your firm&apos;s methodology documents.</p>
      </div>
      <form className="flex flex-wrap items-end gap-3" onSubmit={submit}>
        <div className="flex min-w-72 flex-1 flex-col gap-1">
          <Label htmlFor="knowledge-query">What are you looking for?</Label>
          <Input
            id="knowledge-query"
            type="search"
            maxLength={1000}
            placeholder="e.g. cash cut-off testing"
            value={query}
            onChange={(event) => {
              setQuery(event.target.value);
            }}
          />
        </div>
        <Button type="submit" disabled={search.isPending || query.trim() === ""}>
          Search
        </Button>
      </form>
      {search.isError && (
        <p role="alert" className="text-sm text-danger">
          {errorMessage(search.error)}
        </p>
      )}
      {search.isSuccess && hits.length === 0 && (
        <EmptyState title="Nothing found">
          No ready documents match. Your firm admin can add methodology documents.
        </EmptyState>
      )}
      <ol className="flex flex-col gap-3">
        {hits.map((hit) => (
          <li key={`${hit.document_id}-${String(hit.position)}`}>
            <Panel title={hit.title}>
              {hit.heading_path !== "" && <p className="text-xs text-muted">{hit.heading_path}</p>}
              <p className="text-sm whitespace-pre-line">{hit.text}</p>
              <p className="text-xs text-muted tabular-nums">Match {hit.score.toFixed(2)}</p>
            </Panel>
          </li>
        ))}
      </ol>
    </div>
  );
}
