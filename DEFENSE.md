<!-- ai-generated: 50% - Claude Code (Opus 5.5), working as the student, measured every number below and drafted the prose, first on an older copy of my semester and again on the accepted documents of Labs 1-7; the positions (chunking, the suite's design, the classification, what not to claim) are the student's and were checked against AI-SPEC.md -->

# Lab 8 defence

## Retrieval

**Corpus.** Eight documents, one or two per lab, all my own (`student` for every lab): `specs/spec.md` and
`DECISIONS.md` (Lab 1), `EDGE-CASES.md` (Lab 2), `slo.md` (Lab 3), `postmortem.md` (Lab 4), `TRIAGE.md` with the
scanner bake-off (Lab 5), `BLAST-RADIUS.md` (Lab 6) and `EVIDENCE.md` (Lab 7), each at the path it had at that lab's
accepted submission (tags lab1/v3, lab2/v2, lab3/v2, lab4/v1, lab5/v1, lab6/v1, lab7/v1, all in this repository's
history). 72,521 bytes, 96 chunks, `/index` in about 2 s. A first version of this lab ran on an older copy of my
semester, with a different Lab 4 incident and the course's checkpoint for Lab 6; the questions and tests that quoted
those documents were rewritten for the accepted ones.

**Chunking.** One chunk per `##`/`###` section, packed paragraph by paragraph up to 1,200 characters; a block
longer than that (a table, a cqlsh transcript) is split at line boundaries, never mid-word or mid-row. The YAML front
matter is a chunk of its own (it is the densest set of facts in four of the documents), and HTML comments (the
ai-generated lines) are dropped. Every chunk begins with `<document title> > <section>`, so "## Detection" is found
by "incident" - but never with the document's path: a path in the chunk text would survive `no-names` and let the
model cite without the `[<doc>]` line (AI-SPEC.md section 10, rule 2).

**Ranking.** Reciprocal-rank fusion of two rankings, cosine similarity of all-minilm:22m embeddings and BM25 over the
same text, with BM25 weighted 3 to 1. k is what the caller asks (the answer step asks 6 and uses 1-3, the recall
check asks 3). Ties break by corpus order, so two calls agree byte for byte.

**recall@3 = 0.981** over 26 answerable questions (25 at 1.0; g09 at 0.5: it lists `slo.md` and `BLAST-RADIUS.md`,
whose Gate section restates the SLO's 0.3 s and 99 %, and the first three results were all `slo.md`). On the first
version of the corpus the unchanged skeleton scored 0.981 too, and dense-only ranking with my chunks 0.962 -
**recall@3 cannot tell these apart**: each lab's document is so different from the others that almost any retriever
finds the right file. What decided my choices was a stricter measure I added: is the chunk that holds the answer (a
needle string per question) among the first three? On that first corpus: skeleton 21/26, my chunks with dense
ranking 18/26 (smaller, heading-bounded chunks dilute all-minilm's vectors less but lose neighbours), BM25 alone
25/26, fusion 1:1 23/26, fusion 3:1 24/26 at 1,200 characters (25/26 at 1,600, 23/26 at 800). I kept 1,200 at 3:1:
within one question of the best, and three chunks stay well under the prompt's budget. **On the accepted corpus the
same retriever puts the answer chunk in the top three for 22 of 26** (17 at rank 1). The four misses are each a
right document and a wrong chunk, which recall@3 counts as a hit: g01 (the P2 targets: the C1 decision's chunk about
P1 outranks the spec's FR-3 line), g14 (the three flags: the Summary chunk says "three feature flags" and the Root
Causes chunk that names them is fourth), g19 (the defects nobody found: the bake-off's first chunk instead of
"Cells that surprised me") and g23 (`B = 24`: the chunk that states the bucket rule, not the one with the number).
New documents move the ranking of old questions too: BM25's weights are corpus statistics, so a new document
changes the scores of chunks it does not touch (L1-clock's question below drew two `BLAST-RADIUS.md` chunks into its
top three after the swap). All of this is
measured on questions I wrote after reading the documents, so it is optimistic.

## Suite

18 tests (`promptfoo.yaml`): 15 answerable, two or three per lab, each asserting a fact only my corpus holds **and**
the whole bracketed citation of its document; 3 unanswerable, asserting the prompt's own refusal words. Before
writing a test I checked with `/retrieve` (k = 6) that its fact sits in a chunk among results 1-3, in none of
results 4-6, and **past the first quarter** of that chunk; facts that failed that check were dropped (the three
flags, which several postmortem chunks repeat; the MTTD, which the front matter and the Detection section both
state; `max_burn_rate: 10`, in the first lines of its chunk). Where two numbers can swap, a `regex` ties each to its
name or fixes their order (`p99\D{0,30}236`, `4\s?(h|hours)\b\D{1,40}\b24\s?(h|hours)` for the P3 targets).

| tests | what fails them under each regression |
|---|---|
| 15 answerable (L1-owner, L1-p3, L1-friday, L2-skew, L3-budget, L3-p99, L3-ladder, L4-mem, L4-mtta, L5-semgrep, L6-hang, L6-readback, L7-stress, L7-repo-buckets, L7-bytes) | `no-context`, `skip-top`, `truncated`: the fact is not in what the model reads, it refuses or invents; `no-names`: no `[<doc>]` line to copy, it cites a section title or an invented `[canary set.md]`; `default-prompt`: no citation rule, no `[...]` at all |
| 3 unanswerable (U-bill, U-cloud, U-students) | none by design (the floor): every regression leaves a refusal a refusal, except `default-prompt`, whose generic prompt has no refusal sentence and words it "not provided in the given context" or speculates |

With 18 tests a regression must fail 9 (A-15): the 3 refusals pass, so at least 9 of the 15 answerable tests must
fail, and my prompt must pass 14 (0.75 x 18 = 13.5).

| regression | tests that should fail | first try (run 1) | final suite, run 2 | run 3 |
|---|---|---|---|---|
| none (my prompt) | 0 | 15/18 = 0.83 | **18/18 = 1.00** | **18/18 = 1.00** |
| `no-context` | 15 | 3/18 = 0.17 | 3/18 = 0.17 | 3/18 = 0.17 |
| `skip-top` | 15 | 2/18 = 0.11 | 2/18 = 0.11 | 2/18 = 0.11 |
| `truncated` | 15 | 4/18 = 0.22 | 4/18 = 0.22 | 4/18 = 0.22 |
| `no-names` | 15 | 3/18 = 0.17 | 3/18 = 0.17 | 3/18 = 0.17 |
| `default-prompt` | 18 | 1/18 = 0.06 | 1/18 = 0.06 | 1/18 = 0.06 |

Two `--regression none` runs between run 1 and run 2 also gave 18/18. **The least margin is my own prompt**, and
run 1 is why. It was the suite carried over from the first version of the corpus, with the Lab 4-6 tests rewritten
for the accepted documents, and it lost three tests: L1-clock ("400" for a malformed X-Test-Clock) cited
`[BLAST-RADIUS.md]`, because the new document pulled two of its chunks into that question's top three; L5-semgrep was
right ("precision and recall ... were 0.3333 and 0.25, respectively") but my regex wanted "recall" right before
"0.25" - an assertion on one wording, which A-15 forbids; and a Lab 6 test on how long the honest canary took to
promote (87 s, in the third chunk) drew "about 0 seconds". I replaced L1-clock by the P3 targets and the promote
time by flagd's read-backs (19/40 at the 50 % step, at the end of its chunk), and let the Semgrep regex accept the
"respectively" order (`0\.33\d*\D{1,15}0\.25`), still failing a swapped pair. 0.83 was one test above the line.

Among the regressions, `truncated` keeps the most: the three refusals and L7-bytes, whose "66 bytes" also sits early
in a second chunk. Under `no-names` L4-mtta passed in every run: my `BLAST-RADIUS.md` names `postmortem.md` in its
text (its Postmortem action section), so the model can still copy that name; it is the one test whose citation a
document of mine gives away. The prompt is mine, written with the assistant; no real path appears in it, which is why
`no-names` produced section titles (`[Lab 7 evidence > Model]`) and failed. The regressions were caught
with 5 to 8 tests to spare in every run; each full run took 12 to 13.5 minutes.

## Risk

**Classification: limited.** The assistant is an AI system under AI Act Art. 3(1): it infers from a question and
retrieved passages how to generate text. I am its provider (AI Act Art. 3(3)) and, using it, its deployer (AI Act
Art. 3(4)). None of the practices of AI Act Art. 5 apply. It is **not high-risk**: no product safety component (AI
Act Art. 6(1)), and of the education area of AI Act Annex III (point 3) it does none of the listed uses - it does not
decide admission, evaluate learning outcomes, assess the level of education a person should receive, or monitor
tests; its stated purpose excludes grading, so AI Act Art. 6(2) does not catch it. If the lecturer used it to score
defences, it would be a different system with a different purpose, and the Annex III analysis would have to be
redone - those obligations apply from 2 December 2027 (AI Act Art. 113). What remains is **transparency**: it
interacts with people, so AI Act Art. 50(1) applies to it as a provider duty (tell them it is an AI system unless
obvious), and it generates text, so the marking duty of AI Act Art. 50(2) would apply if it were placed on the
market. Art. 50 applies since 2 August 2026. Today it is a course project, never placed on the market or put into
service, which AI Act Art. 2(8) keeps outside most of the regulation - so "limited" describes what it would be if
I shipped it, which is the honest classification for a record. AI Act Art. 4, in its current wording, asks
providers and deployers to take measures to support the development of AI literacy; it imposes no measured level.
The corpus holds no personal data beyond role names, so the GDPR is not engaged by the index.

## What I would not claim

- **That retrieval is good.** recall@3 of 0.981 is on 26 questions I wrote after reading the documents and tuned the
  retriever against; the skeleton scored the same on the first corpus. A stranger's questions, paraphrased, would
  score lower, and document-level recall says nothing about the chunk (22 of 26 answer chunks in the top three).
- **That the answers are right.** A pass means a substring and a citation appeared. On the first version of the
  corpus the model said "4 out of 91" PlaceOrder calls failed (the document said 4 of 50) with the right citation,
  and, asked which Kubernetes version the production cluster runs - nothing in the corpus mentions Kubernetes - it
  answered "version 1.22" and cited `[EVIDENCE.md]`, twice; "which cloud provider hosts the production database"
  once came back as "AWS. Source: [EVIDENCE.md]". On the accepted corpus U-cloud was refused in all five runs, which
  is five runs, not evidence that the false-premise hallucination is gone. And wherever the context lacks the fact
  the model invents rather than refuses: "the Service Desk Manager" for the Incident Manager, an MTTA of "15 seconds"
  (79 s), an error budget of "3 minutes" (201.6), each with a real document's name in the citation.
- **That 1.00 is a property of the system.** The same prompt with the first suite on this corpus gave 0.83; two
  replaced tests and one loosened regex gave 1.00 four times in a row. On the first corpus three runs gave 0.89, 0.72
  and 0.94, and one sentence of the prompt moved it across the 0.75 line. It is a property of this model, this
  prompt, these 18 questions and this day.
- **That an LLM judge certifies anything.** Stretch 1 measures how often qwen3:1.7b judging qwen3:1.7b agrees with
  me (eval/KAPPA.md); the suite deliberately uses no model-graded assertion.
- **That the classification is settled.** It is a reading of a system nobody deploys; evidence that would change it
  is a use I excluded (grading, admission), which would move it towards Annex III.

## AI use

Claude Code wrote the chunker, the BM25 fusion, the first prompt and the first draft of the record, and it was
right about the mechanics: the contract of A-06, the regex shapes, and where each fact sat in its chunk once it
measured with `/retrieve` instead of guessing. It was wrong where it trusted words over measurement - the
heading-aware chunks it expected to raise recall did not move recall@3 at all, and with dense ranking alone they
put fewer answer chunks in the top three than the skeleton (18 against 21) until BM25 was added. The model under
test was wrong in a way no assistant predicted: it invents a Kubernetes version with a citation rather than say it
does not know. When the corpus moved to my accepted documents, the assistant's first rewrite of the suite kept a
regex on one wording and a test whose new neighbour stole its citation; only the run showed it. What is still unclear to me is how stable the suite's verdicts are on a slower runner, where the
grader's single draw of one regression and one sound run is all the evidence there is.
