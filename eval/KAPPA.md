---
lab8_kappa:
  n: 44
  kappa: -0.07
  judge: deepeval 4.2.7 G-Eval, qwen3:1.7b through Ollama (think off), the course's judge.py rubric
---
<!-- ai-generated: 50% - Claude Code (Opus 5.5), working as the student, ran answers.py, judge.py and kappa.py; the 44 labels were given before the judge ran, by eval/RUBRIC.md; the reading of the disagreements is the student's -->

# Judge agreement

**What was judged.** 44 answers of the answer step, drawn with a fixed seed from the 152 distinct answers of two
runs of `./itsmlab.sh eval 8 --regression all` (prompts A and B of DEFENSE.md): 14 of my own pipeline's and 6 of
each regression's, every one judged against the context my sound pipeline retrieves for its question. I labelled
all 44 by `eval/RUBRIC.md` (the fact right and cited with its document's real name, or "I don't know" when the
context holds nothing) before running the judge. Then `stretch/judge/judge.py` (deepeval 4.2.7 G-Eval, qwen3:1.7b
with thinking off, 536 s for 44 answers, about 12 s each) gave its own verdict.

**The numbers.** I said pass 15 times, the judge 35. Both pass 11, both fail 5: p_o = 16/44 = 0.364; chance with
these frequencies, p_e = 0.341 x 0.795 + 0.659 x 0.205 = 0.406; **kappa = -0.07** - the judge agrees with me
slightly less often than two raters who said pass at our rates without reading anything.

**What drives it.** 24 of the 28 disagreements are the judge passing what I failed, and its own reasons show why.
It passed every `default-prompt` answer I sampled (6 of 6) for "citing the relevant document" when none of them has
a single bracket. It passed `no-names` answers that cite invented names - `[lab7_ai_draft.md]`, a section title -
writing that they cite `[DECISIONS.md]` or `[slo.md]`: it reads the citation from the context, not from the answer.
It passed wrong facts: "5 seconds" for an MTTA of 17 s while writing "correctly identifies the MTTA as 17 seconds";
"0.3 seconds" for 375 s; "Service Desk Manager" for the Incident Manager while its reason names the Incident
Manager. And it passed three answers that were nothing but `Source: [<doc>]`, describing an answer that is not
there. Its four fails against my passes are refusals of unanswerable questions, failed with a reason that says the
refusal is correct (score 0.0, reason "correctly states that it does not know"): its score and its reason disagree.

**What a kappa certifies.** Agreement beyond chance between two raters applying one rubric, on these 44 answers:
nothing about correctness by itself, and nothing about answers unlike these. -0.07 certifies that this judge cannot
stand in for me on this rubric: its verdict is close to "pass whatever looks fluent". A kappa of 0.3 ("fair" on
Landis and Koch's scale, whose cut-offs its authors called arbitrary) would certify only that the judge agrees
somewhat beyond chance - with p_e near 0.4 that still allows it to disagree on a third of the answers, too often to
replace the hand-labelled check of a regulated claim, but enough to triage which answers a human reads first. This
is why the suite asserts substrings and citations and uses no model-graded assertion: the same 1.7-billion-parameter
model grading its own answers is not an independent instrument.
