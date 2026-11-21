# Instructions for AI agents and teammates

This repo is a two-person hackathon entry for Track 2, "Same Person or Not?". Two people and their AI tools edit it in parallel, so shared knowledge lives in `brain/` and travels with `git pull`.

## Before you change anything

1. Read `brain/README.md`, then `brain/status.md` (who is doing what right now).
2. Read the other `brain/` files your task touches. `dev/POLICY.md` is the spec; `brain/` explains how we apply it.
3. Do not start a task someone else has claimed in `brain/status.md`.

## While you work

Keep `brain/` current, in the same commit as the code change:

- A new fact about the data (a format, a quirk, a join that surprised you) goes in `brain/data-model.md`.
- A choice between options, and why, goes in `brain/decisions.md`.
- A change to the pipeline or a module's job goes in `brain/approach.md`.
- Claiming or finishing a task, a new score, or a new open question goes in `brain/status.md`.

Rewrite or delete stale entries instead of appending contradictions. Write facts you checked, not guesses; mark anything unverified as such.

## Hard rules

- **Python 3 standard library only.** No packages that need installing.
- **Language models only through OpenRouter** (`https://openrouter.ai/api/v1/chat/completions`, key from `OPENROUTER_API_KEY`), temperature 0, pinned model. A model may extract facts from free text; the decision itself comes from the rules in code.
- **Never commit `dev/`, `validate.py` or any API key.** The data is for event participants only and the repo goes public.
- **Build for the policy, not for these files.** No dev IDs, names or values in `system/`. The unseen set has new people and differently worded free text.
- **When in doubt, `REVIEW`.** `DIFFERENT_ENTITY` only on a contradiction listed in `dev/POLICY.md`. An unsafe clearance costs 60; any other mistake costs 2-3.
- **Deterministic.** Same input, same output, every run: sorted iteration, no randomness, no wall-clock time (use the alert's `screened_at`).
- **`output/dev.jsonl` is written only by `system/run`**, never by hand.

## After every change to `system/`

```sh
system/run dev output/dev.jsonl
python3 validate.py --data dev --output output/dev.jsonl --score dev/practice_labels.jsonl
python3 -m unittest discover tests
```

There must be 0 problems and 0 unsafe clearances. Record the new decision score in `brain/status.md`.
