# Local screening UI bridge

This is the standard-library adapter for the existing TraceSphere UI. The
screening submission still runs with `system/run <input folder> <output file>`;
neither Streamlit nor the UI is required by the screening engine.

The visual workspace lives in the existing TraceSphere project, in
`src/scam_linker/screening_ui.py`. Its `app.py` offers a **Watchlist screening** workspace next to the
original investigation workspace. Start that project with its existing
`.venv/bin/python run.py`, then select the screening workspace. Set the local
repository path in the page, or set `SCREENING_REPO` before starting the UI.
The repository path must point to this checkout, with `ui/bridge.py` present.

## Workflow

```text
Select input folder
  -> ui/bridge.py run -> existing system/run -> official JSONL predictions
  -> filter hits and select one
  -> ui/bridge.py inspect -> existing link/customer/hitfacts -> facts + sources
  -> inspect cited evidence; save separate human-review annotations
  -> download predictions and annotations
  -> explicit evaluation -> local official validate.py + separate labels
```

The bridge calls the existing runner in a subprocess. It does not rewrite
decision rules, modify input tables, train on gold labels, call a model or
overwrite `output/dev.jsonl`. Working predictions are temporary and the user
downloads them from the page. Errors and existing engine warnings are exposed.

Raw customer records, linked accounts/onboarding, KYC checks, notes and supplied
search results remain available for inspection. Producer facts show their
original source IDs. Missing or unresolved evidence is displayed as unresolved,
never invented. Search results are supplied evidence, not a claim of live web
search. An alert is cleared only when all its hits are DIFFERENT_ENTITY.

Input tables and engine files have a SHA-256 fingerprint. Switching a dataset,
changing the code or changing the inputs invalidates displayed predictions.
Human-review status/notes are session-only until downloaded, and never replace
the official automated decisions. The same input produces the same decisions;
elapsed runtime is display metadata only.

## Command-line inspection

From the repository root:

```sh
python3 ui/bridge.py run adversarial/input > /tmp/screening-run.json
python3 ui/bridge.py inspect adversarial/input --hit YOUR_HIT_ID
python3 -m unittest discover -s tests -p test_ui_bridge.py
```

`run` returns a JSON envelope containing predictions and metadata. For the
official seven-field JSONL output, use the UI download or `system/run`.
`evaluate` accepts a JSON array of predictions on stdin and a separate
`--labels` path. Only this explicit evaluation action reads labels; the official
validator remains the sole scoring implementation. A perfect practice or
synthetic score is not an unseen-data accuracy claim.

## Scope and follow-up

This change is a review UI integration, not a replacement of either lane's
resolver or the shared decision rules. The current classifier has unresolved
synthetic cases; the UI exposes them for follow-up rather than changing rules
to match this test set. The existing final `system/README.md` deliverable and
submission/publication are separate team tasks.
