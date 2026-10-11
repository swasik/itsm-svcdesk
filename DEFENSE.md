<!-- ai-generated: 50% - Claude Code (Opus 5.5), working as the student, measured every number below and drafted the prose; the positions (chunking, the suite's design, the classification, what not to claim) are the student's and were checked against AI-SPEC.md -->

# Lab 8 defence

## Retrieval

**Corpus.** Eight documents, one or two per lab: `specs/spec.md` and `DECISIONS.md` (Lab 1), `EDGE-CASES.md`
(Lab 2), `slo.md` (Lab 3), `postmortem.md` (Lab 4), `TRIAGE.md` (Lab 5), `EVIDENCE.md` (Lab 7) - my own, each at
the path it had at that lab's submission commit, now in this repository's history (Labs 5 and 7 were done on side
branches and merged in) - and the course's `corpus/checkpoint/lab6/BLAST-RADIUS.md`, because Lab 6 had no accepted
submission when I built this. 63,000 characters, 94 chunks, `/index` in 2.3 s.

**Chunking.** One chunk per `##`/`###` section, packed paragraph by paragraph up to 1,200 characters; a block
longer than that (a table, a cqlsh transcript) is split at line boundaries, never mid-word or mid-row. The YAML front
matter is a chunk of its own (it is the densest set of facts in four of the documents), and HTML comments (the
ai-generated lines) are dropped. Every chunk begins with `<document title> > <section>`, so "## Detection" is found
by "incident" - but never with the document's path: a path in the chunk text would survive `no-names` and let the
model cite without the `[<doc>]` line (AI-SPEC.md section 10, rule 2).

**Ranking.** Reciprocal-rank fusion of two rankings, cosine similarity of all-minilm:22m embeddings and BM25 over the
same text, with BM25 weighted 3 to 1. k is what the caller asks (the answer step asks 6 and uses 1-3, the recall
check asks 3). Ties break by corpus order, so two calls agree byte for byte.

**recall@3 = 0.981** over 26 answerable questions (25 at 1.0; g09 at 0.5: it lists `slo.md` and the Lab 6
document, which restates the SLO's 0.3 s and 99 %, and the first three results were all `slo.md`). The skeleton
scores 0.981 too, and dense-only ranking with my chunks 0.962 - **recall@3 cannot tell these apart**: each lab's
document is so different from the others that almost any retriever finds the right file. What decided my choices
was a stricter measure I added: is the chunk that holds the answer (a needle string per question) among the first
three? Skeleton 21/26, my chunks with dense ranking 18/26 (smaller, heading-bounded chunks dilute all-minilm's
vectors less but lose neighbours), BM25 alone 25/26, fusion 1:1 23/26, fusion 3:1 24/26 at 1,200 characters (25/26
at 1,600, 23/26 at 800). I kept 1,200 at 3:1: it is within one question of the best and keeps three chunks well
under the prompt's budget. The miss, g23 ("how many buckets does events_by_actor use"), retrieves the chunk that
states the bucket rule but not the one that says `B = 24`: a right document, a wrong chunk - exactly what recall@3
counts as a hit. All of this is measured on the same 26 questions I tuned on, so it is optimistic.

## Suite

18 tests (`promptfoo.yaml`): 15 answerable, two or three per lab, each asserting a fact only my corpus holds **and**
the whole bracketed citation of its document; 3 unanswerable, asserting the prompt's own refusal words. Before
writing a test I checked with `/retrieve` (k = 6) that its fact sits in exactly one chunk among results 1-3, none of
results 4-6, and **past the first quarter** of that chunk; facts that failed that check (the three flags, which five
chunks of the postmortem repeat; the CVE id in the first row of the triage table; "eleven" pairs, early in E6) were
dropped. Where two numbers can swap, a `regex` ties each to its name (`p99\D{0,30}236`, `[Pp]recision\D{0,20}0\.8`).

| tests | what fails them under each regression |
|---|---|
| 15 answerable (L1-owner, L1-clock, L1-friday, L2-skew, L3-budget, L3-p99, L3-ladder, L4-rss, L4-mtta, L5-semgrep, L6-375, L6-promote, L7-stress, L7-repo-buckets, L7-bytes) | `no-context`, `skip-top`, `truncated`: the fact is not in what the model reads, it refuses or invents; `no-names`: no `[<doc>]` line to copy, it cites the prompt's dummy `[folder/file.md]` or a title; `default-prompt`: no citation rule, no `[...]` at all |
| 3 unanswerable (U-bill, U-cloud, U-students) | none by design (the floor): every regression leaves a refusal a refusal, except `default-prompt`, whose generic prompt has no refusal sentence |

With 18 tests a regression must fail 9 (A-15): the 3 refusals pass, so at least 9 of the 15 answerable tests must
fail, and my prompt must pass 14 (0.75 x 18 = 13.5).

| regression | tests that should fail | prompt A (run 1) | prompt B (run 2) | final prompt (run 3) |
|---|---|---|---|---|
| none (my prompt) | 0 | 16/18 = 0.89 | **13/18 = 0.72** | 17/18 = 0.94 |
| `no-context` | 15 | 3/18 = 0.17 | 3/18 = 0.17 | 3/18 = 0.17 |
| `skip-top` | 15 | 2/18 = 0.11 | 2/18 = 0.11 | 2/18 = 0.11 |
| `truncated` | 15 | 4/18 = 0.22 | 3/18 = 0.17 | 4/18 = 0.22 |
| `no-names` | 15 | 3/18 = 0.17 | 2/18 = 0.11 | 2/18 = 0.11 |
| `default-prompt` | 18 | 0/18 = 0.00 | 0/18 = 0.00 | 0/18 = 0.00 |

The regressions never came near 0.50: they are caught with a margin of 5 to 9 tests in every run. **The least margin
is my own prompt.** Prompt A asked to "end the answer with the source ... as in Source: [folder/file.md]" and lost
two tests (the owner question answered only `Source: [DECISIONS.md]`; a 128-hours question, since replaced, cited
`slo.md`). Prompt B added "Start with the answer itself" and made it worse: four answers were nothing but
`Source: [...]`, and the pipeline fell to 0.72 - below 0.75, so the sound pipeline failed its own suite. The final
prompt spells out the shape of a reply (`<the answer, in words and numbers> Source: [<the document's name>]`) and
reached 17/18; the one failure is U-cloud, where the model answered "AWS" with a citation of `EVIDENCE.md` (see
below). Run 1 also used a test since dropped: asked how many PlaceOrder calls failed "out of how many", the model
said "4, out of 91" - the corpus says 4 of 50 - with the right citation. Among the regressions `truncated` keeps the
most: the refusals and the 375 s arithmetic, whose sentence survived in the first quarter of one chunk. The prompt
is mine, written with the assistant; no real path appears in it, which is why `no-names` produced the dummy
`[folder/file.md]` or a section title and failed. Each run of all six took about 12 minutes (727 s for run 3).

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
  retriever against; the skeleton scores the same. A stranger's questions, paraphrased, would score lower, and
  document-level recall says nothing about the chunk (24/26 answer chunks in the top three).
- **That the answers are right.** A pass means a substring and a citation appeared. In run 1 the model said "4 out
  of 91" PlaceOrder calls failed (the corpus: 4 of 50) and the citation was correct; that test was dropped, not
  fixed. Asked which Kubernetes version the production cluster runs - nothing in the corpus mentions Kubernetes -
  the model answered "version 1.22" and cited `[EVIDENCE.md]`, twice, with both prompts I tried. I replaced that
  refusal test with "which cloud provider hosts the production database", which then came back as "AWS. Source:
  [EVIDENCE.md]" in run 3 (and "I don't know" in runs 1 and in single tries). The hallucination is still there, and a
  regulator should read it as: this system invents a confident, cited answer to a question with a false premise.
- **That 0.94 is a property of the system.** At temperature 0 the first answer after a model load differs from the
  next; three runs of nearly the same suite gave 0.89, 0.72 and 0.94, and one sentence of the prompt moved it
  across the 0.75 line. It is a property of this model, this prompt and this day.
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
does not know. What is still unclear to me is how stable the suite's verdicts are on a slower runner, where the
grader's single draw of one regression and one sound run is all the evidence there is.
