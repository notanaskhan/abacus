# The upload reviewer's recorded answers for the scenario (TASK-7816; DEC-4814)

The `pbc_screening` slice runs the reviewer's own path in the loader on the fake route, and the fake model answers from these files only. The format is the evaluation's (`abacus_tools/evals/fake_answers/upload_review/README.md`):

```json
{"document": "<file name>", "prompt_ref": "evidence.upload_review@v3", "content_sha256": "<64 hex>", "response": {"no_concerns": false, "flags": []}}
```

- `content_sha256` is `agents.api.review_sha256` of the reviewer's request: the request's wording and the masked document as the reviewer is shown it. A changed prompt, request title, extraction or masking changes it, and the load then stops with `no recorded review for <prompt> and <sha>`, naming the new hash to record.
- `response` is written by hand from the generated document, never by a model. Every quote is on the page it names, so code verifies it.
- These answer uploads, not `documents.py`'s documents, so they live apart from `responses/` (whose tests tie each file to a scenario document).

| File | Upload | Answer |
|---|---|---|
| `granite_card_statement.json` | "Granite Peak card statement June 2026.pdf" on Granite Peak's "Bank statements (year-end month + subsequent month)" | one `irrelevant` flag quoting the issuer line and "PAYMENTS AND OTHER CREDITS" |
