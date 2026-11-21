# Track 2: Same Person or Not?

For every screening hit, decide `DIFFERENT_ENTITY`, `SAME_ENTITY` or `REVIEW`, following `dev/POLICY.md`.

Python 3 standard library only: no packages to install. Any language model call goes through OpenRouter with the key in `OPENROUTER_API_KEY`.

## Setup

Download the data room zip from the event's participant access (the link is in the team chat, not here: the data is for participants only). From its `screening/` folder, copy `dev/` and `validate.py` into the repo root. Both are in `.gitignore`.

## Run and check

```sh
system/run dev output/dev.jsonl
python3 validate.py --data dev --output output/dev.jsonl --score dev/practice_labels.jsonl
```

`validate.py` is the organisers' checker: it validates the output the way they do and scores the 50 practice labels. Run it after every change. Unsafe clearances (`DIFFERENT_ENTITY` on a hit that is the customer or needs review) cost 60 each against 2-3 for any other mistake, so they must stay at 0. The decision score is the share of cost saved against sending every hit to review, so all-`REVIEW` scores 0.

Evidence IDs may be record IDs from the data files, URLs, or a hit field written as `H-XXXXXX#field` (for example `H-2C4CE7#dobs`).

## Submission rules

- The repo must be public at the deadline, with `system/` and `output/dev.jsonl`.
- Never commit `dev/` or an API key.
- `system/README.md` must explain the architecture (with a diagram), how both sides are resolved, how evidence is represented, how runs stay deterministic, the model, time and cost of a run, and three cases: a clear mismatch, a match, and one left for review.

## Layout

| Path | What |
|---|---|
| `system/run` | Entry point: `system/run <data folder> <output file>` |
| `output/dev.jsonl` | The system's predictions on the dev set |
| `tests/` | Unit tests (`python3 -m unittest discover tests`) |
| `dev/`, `validate.py` | From the data room (not in git) |
