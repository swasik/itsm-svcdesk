---
lab8_kappa:
  n: 44
  kappa: -0.12
  judge: deepeval 4.2.7 G-Eval, qwen3:1.7b through Ollama (think off), the course's judge.py rubric
---
<!-- ai-generated: 50% - Claude Code (Opus 5.5), working as the student, ran answers.py, judge.py and kappa.py on the accepted corpus; the 44 labels were given before the judge ran, by eval/RUBRIC.md; the reading of the disagreements is the student's -->

# Judge agreement

**What was judged.** 44 answers of the answer step on the accepted corpus, drawn with a fixed seed (8) from the 102
distinct answers of two runs of `./itsmlab.sh eval 8 --regression all --ollama shared --json` (`eval/runs-1.json`,
`eval/runs-2.json`; the final prompt and suite of DEFENSE.md): 14 of my own pipeline's and 6 of each regression's,
every one judged against the context my sound pipeline retrieves for its question. I labelled all 44 by
`eval/RUBRIC.md` (the fact right and cited with its document's real name, or "I don't know" when the context holds
nothing) before running the judge. Then `stretch/judge/judge.py` (deepeval 4.2.7 G-Eval, qwen3:1.7b with thinking
off, 535 s for 44 answers, about 12 s each) gave its own verdict. (A first version of this file measured -0.07 on
answers over an older copy of my semester; those answers quoted documents that are no longer the corpus, so they were
replaced.)

**The numbers.** I said pass 17 times, the judge 35. Both pass 12, both fail 4: p_o = 16/44 = 0.364; chance with
these frequencies, p_e = 0.386 x 0.795 + 0.614 x 0.205 = 0.433; **kappa = -0.12** - the judge agrees with me less
often than two raters who said pass at our rates without reading anything.

**What drives it.** 23 of the 28 disagreements are the judge passing what I failed, and its own reasons show why. It
passed all five `default-prompt` answers I failed, for "citing the relevant document", when none of them has a
bracketed citation. It passed every `no-names` answer that states the right fact under a section title or an invented
name - `[Lab 7 evidence > Model]`, `[canary set.md]` - writing that it cites `[slo.md]` or calling `[canary set.md]`
"correct according to the context": it reads the citation from the context, not from the answer. It passed wrong
facts and restated them as right: "the Service Desk Manager" while its reason names the Incident Manager; P3 targets
of "P2 and P1"; an MTTA of "15 seconds" (79 s) "explicitly stated" in the context; "0.8" for Semgrep (0.3333 / 0.25);
"2 seconds" and "1 minute" for a 39 s cassandra-stress run. And it passed refusals to questions the context answers
("correctly states that it does not know"). Its five fails against my passes are all refusals of unanswerable
questions, failed with a score of 0.0 or 0.1 and a reason that says the refusal is correct: its score and its reason
disagree, as the course's README warned.

**What a kappa certifies.** Agreement beyond chance between two raters applying one rubric, on these 44 answers:
nothing about correctness by itself, and nothing about answers unlike these. -0.12 certifies that this judge cannot
stand in for me on this rubric: its verdict is close to "pass whatever looks fluent and names a source". A kappa of
0.3 ("fair" on Landis and Koch's scale, whose cut-offs its authors called arbitrary) would certify only that the judge
agrees somewhat beyond chance - with p_e near 0.4 that still allows it to disagree on a third of the answers, too
often to replace the hand-labelled check of a regulated claim, but enough to triage which answers a human reads first.
This is why the suite asserts substrings and citations and uses no model-graded assertion: the same
1.7-billion-parameter model grading its own answers is not an independent instrument.
