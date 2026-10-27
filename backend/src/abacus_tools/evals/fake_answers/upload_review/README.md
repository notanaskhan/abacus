# The upload reviewer's recorded fake answers (P-06-T21; F-04.26)

One JSON file per case of `evals/upload_review/suite.yaml`, read by `abacus_tools.evals.upload_review.fake_answers` (the scenario loader's format):

```json
{"case": "<suite case id>", "prompt_ref": "evidence.upload_review@v3", "content_sha256": "<64 hex>", "response": {"no_concerns": false, "flags": []}}
```

- `content_sha256` is `agents.api.review_sha256` of the reviewer's request: the SHA-256 of the request's wording and the untrusted document block, as the reviewer is shown it (extracted and masked). It doesn't change with the upload's bytes (each attempt is made unique) and it tells apart one document uploaded to two requests (`clean_statement`, `statement_for_aging`). The throwaway stack's engagement ends 2025-12-31, so the documents and their hashes are fixed.
- `response` is the reviewer's output (`UploadReviewOutput`), written by hand from the generated documents (`_documents`), never by a model. Every quote is in the masked page it names, so code verifies it.
- The two `code_catches_*` answers raise an `altered` flag that code keeps hidden: its own balance checks already found the problem.
- A changed prompt, request wording, extraction or masking changes the hash: the fast run then fails (no recorded answer) until the answers are written again for it.

`make evals-review-fast` runs every case once on these answers; the run fails unless every attempt is reviewed and shows exactly its case's flags, at the protected thresholds.
