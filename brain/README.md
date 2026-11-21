# brain/: the team's shared knowledge

Everything we have learned that isn't obvious from the code. Pull before you start, update as you go, push often.

| File | What it holds | Update it when |
|---|---|---|
| `status.md` | Who is doing what, current score, next tasks, open questions | You claim or finish a task, the score changes, a question appears or is answered |
| `brief.md` | The challenge: deliverable, output format, scoring, submission rules | The organisers clarify something |
| `data-model.md` | The files, how they link, value formats and quirks | You find a new fact about the data |
| `roadmap.md` | Plan to 17:00: two lanes, phases, sync points, what to cut if behind | The plan changes at a sync point |
| [Lane B contract](../system/LANE_B_README.md) | V1 quality/issue handoff and integration obligations | The interface or unresolved-information behaviour changes |
| `approach.md` | The pipeline and the interfaces between the two lanes | The design or an interface changes |
| `decisions.md` | Choices we made and why | You choose between options |

Rules for editing:

- Facts you checked, not guesses. Mark anything unverified.
- Rewrite or delete stale entries; don't leave contradictions.
- No real records from `dev/` (names, dates of birth, notes). The repo goes public and the data is for participants only. IDs and counts are fine.
