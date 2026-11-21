# Decisions

Newest first. One line for the choice, one for why.

**21 Nov: Lanes: garyyehhh owns Lane A (customer side: `data.py`, `link.py`, `notes.py`, `profile.py`), linhuang owns Lane B (hit side: `common.py`, `names.py`, `hitfacts.py`).**
Both lanes wrote date and country helpers in parallel; Lane B's `common.py` was merged first and its modules depend on it, so it stays and Lane A's duplicate was dropped. Lane A proposes fixes to it through `brain/status.md` instead of editing it.

**21 Nov: An unrecognised or ambiguous country value never supports a location clear.**
A wrong guess ("Korea" as South Korea, "NA" as Namibia) can invent a location mismatch and clear a real match, costing 60; leaving it unknown only costs a `REVIEW`.

**21 Nov: Missing hit type stays unknown; output ordering and English month parsing are explicit.**
Avoid unsupported assumptions and environment-dependent extraction. Add standard-library-only regression guardrails; keep final identity decisions pending shared pipeline integration.

**21 Nov: The official data room replaces the version rebuilt from the browse workbook.**
The content was the same, but the shapes differ (nested alert `customer`, extra hit name fields, joint accounts), and the unseen set uses the official shapes.

**21 Nov: The organisers' `validate.py` is our only checker.**
It scores exactly as they do; a second scorer would drift.

**21 Nov: Rules decide, a language model is at most a fallback for extracting facts.**
The policy is precise enough to code; rules are deterministic (10% of the score is reproducibility) and explainable to the judges. The unseen set has differently worded free text, which is where a model may help.

**21 Nov: Track 2 over Track 1.**
We are a pair. Track 2 has 50 labelled hits to measure against and a near-algorithmic policy; Track 1 has no labels and needs heavy LLM judgement under a tight budget.

## Lane B first implementation

Use deterministic policy code first; no LLM fallback in this change. Bundle country code/name data so the submitted program does not depend on host locale files or installed packages. Preserve fact provenance and all possible birth years instead of collapsing uncertainty. Leave shared runner/decision integration to the next coordinated change, so Lane A work is not overwritten.
