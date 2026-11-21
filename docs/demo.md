# Demo: slides and video script

**Team ucl compsci newbies:** Lin Huang, Gary Yeh.

**Slide deck:** https://claude.ai/artifact/CXxBeVy43Q7brboKVysnba (4 slides with speaker notes; Share it from its page, or export it as PDF or PowerPoint, before sending the link).

The video is 2 minutes: four slides plus live screen recordings of the system.

| Time | On screen | Say |
|---|---|---|
| 0:00-0:15 | Slide 1, title | Banks screen every customer against sanctions and politically exposed person lists. Most matches are just people with similar names, but each one still needs an analyst, and clearing a real match is the worst mistake a bank can make. We built a system that clears the false matches safely, and shows its evidence every time. |
| 0:15-0:40 | Slide 2, how it decides | First, who is the customer really? It follows account and email links, picks the right joint holder, merges duplicate records, and trusts the latest approved identity check. Then, who is the listed person? Birth dates and countries from the profile and from news, but only news about the same role in the same country. Then the bank's policy decides: clear only on a hard contradiction, confirm only on agreement, everything else goes to a person. |
| 0:40-1:00 | Terminal: run and validate | 819 hits in about three seconds, no AI model, no cost, the same answer every run. The organisers' checker: every practice label right, zero unsafe clearances. |
| 1:00-1:25 | `H-622EDD` (UI or terminal) | The customer's verified date of birth, from an approved identity note, is 1979. A news report about the listed person, a politically exposed person in Serbia, says he was 29 in 2002, so born in 1972 or 1973. That contradicts every date, so the hit is cleared, citing the customer record, the note and the news result. When the facts don't settle it, the system says why and a person decides. |
| 1:25-1:50 | Witness one-liner, then slide 3 | The real danger is a fact about the wrong person: a 25-year-old witness must never become the suspect's age. A separate agent built adversarial cases from the policy alone, never our code. Across 190 labelled hits, zero unsafe clearances. |
| 1:50-2:00 | Slide 4, close | Clear the noise, never clear a real match, and show the evidence every time. |

## Commands to record

```sh
time system/run dev output/dev.jsonl
python3 validate.py --data dev --output output/dev.jsonl --score dev/practice_labels.jsonl
grep H-622EDD output/dev.jsonl | python3 -m json.tool
grep H-00E181 output/dev.jsonl | python3 -m json.tool
python3 -c "import sys; sys.path.insert(0,'system'); from common import ages_at_dates as a; print('witness:', a('In March 2019, a UK PEP appeared with a 25-year-old witness.', ['Tom Hale'])); print('own age:', a('In January 2023, Tom Hale was 46.', ['Tom Hale']))"
```

## Slide text

1. **Same Person or Not?** Watchlist screening that clears false matches safely, never clears a real one, and shows its evidence every time. ucl compsci newbies · Lin Huang, Gary Yeh.
2. **It resolves both sides before it compares them.** Who is the customer? Who is the listed person? The bank's policy decides: clear only on a hard contradiction backed by complete facts, confirm only on agreement, send everything else to a person.
3. **Tested to fail safe, not just to score well.** 0 unsafe clearances · 190 labelled test hits (88 adversarial, built from the policy alone) · 262 automated tests. Same output every run, about 3 seconds for 819 hits, no AI model, no cost.
4. **Clear the noise. Never clear a real match. Show the evidence every time.** ucl compsci newbies · Lin Huang, Gary Yeh · Track 2: Is my customer sanctioned?
