# Decisions

Newest first. One line for the choice, one for why.

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
