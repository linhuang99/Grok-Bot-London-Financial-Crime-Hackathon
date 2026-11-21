# Synthetic policy challenges: 4 groups × 13 cases

52 fully synthetic identity-screening cases, with policy-derived expected labels.
No participant records, original workbook, API keys or solver outputs are included.
The V1 inputs and gold files are preserved byte-for-byte from the local test pack;
the SHA256 manifest records those frozen files. Labels need independent human
review: a format check is not proof of correct policy interpretation.

| Group | Focus | Cases |
|---|---|---:|
| 01 | Basic names, DOBs, countries, entity types and deceased profiles | 13 |
| 02 | Age attribution, partial dates, negation and the age-16 boundary | 13 |
| 03 | KYC, notes, joint accounts, record merging and ambiguity | 13 |
| 04 | Search distractors, aliases, invalid facts and policy exceptions | 13 |

Each group contains 5 DIFFERENT_ENTITY, 4 SAME_ENTITY and 4 REVIEW labels.
These proportions are deliberately chosen for policy coverage, not production prevalence.

## Layout

- `group_XX/input/`: synthetic JSONL business tables and name variants; no answers.
- `gold/group_XX.labels.jsonl`: expected labels in the organisers' practice format.
- `gold/group_XX.case_cards.txt`: purpose, policy reasoning and evidence per case.
- `cases.manifest.jsonl`: case index, without expected decisions.
- `FROZEN_INPUT_AND_GOLD_SHA256.json`: frozen source hashes.
- `STRUCTURE_CHECK.json`: original structural-check report, not a solver score.

## Run one group

From the repository root, set the group to 01, 02, 03 or 04:

```sh
CHALLENGE_ROOT=evaluation/synthetic_challenges_v1
CHALLENGE_GROUP=01
mkdir -p "$CHALLENGE_ROOT/results"
python3 system/run "$CHALLENGE_ROOT/group_$CHALLENGE_GROUP/input" "$CHALLENGE_ROOT/results/group_$CHALLENGE_GROUP.predictions.jsonl"
python3 validate.py --data "$CHALLENGE_ROOT/group_$CHALLENGE_GROUP/input" --output "$CHALLENGE_ROOT/results/group_$CHALLENGE_GROUP.predictions.jsonl" --score "$CHALLENGE_ROOT/gold/group_$CHALLENGE_GROUP.labels.jsonl"
```

`validate.py` is supplied separately through participant access and remains ignored.
The `results/` folder is ignored, so local predictions will not be uploaded.
Never read `gold/` from the submitted classification program.

## Evaluation limits / 使用约定

- These are challenge/regression cases, not official hidden data or a statistically independent benchmark. The author knew the existing implementation.
- Groups use disjoint customer/account/contact/document records. One synthetic watchlist name is reused between groups 01 and 04; they are not completely person-disjoint. This is disclosed rather than silently changing frozen V1 data.
- No case was copied from the original 50 labelled cases. Separately verified: no hit ID, alert ID, labelled customer ID or primary hit-name overlap with those 50.
- Labels are policy-derived, not generated from solver predictions. If a case fails, review both the code and gold against the SOP; do not change gold merely to agree with the program.
- If all four groups evaluate one frozen version, run all four before making changes. If groups 01-03 guide development, keep 04 unopened until a final freeze; the opened groups become development/regression data.
- Gold is included here for transparent review, so this repository cannot enforce blind access. Use an independent reviewer for stronger evaluation.
- Existing 50 development cases plus these 52 tests are about 49/51, not an 80/20 split. Do not describe this package as an uncontaminated 80/20 holdout.
- Record the code commit, all group scores, unsafe clearances and mistakes. Do not report only the best group.

中文：四组输入与答案分开放，原50条只作为已有开发集。第一、四组有一个重复合成人名，但没有共享客户或业务记录。本包的标准答案建议由队友独立复核；未公开官方测试成绩仍未知。
