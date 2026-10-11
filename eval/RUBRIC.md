<!-- ai-generated: 30% - the rubric is the course's judge.py STEPS, restated by the student before labelling; Claude Code (Opus 5.5) worked as the student -->
# Labelling rubric (Stretch 1, written before any label)

An answer is labelled against the context my own (sound) pipeline retrieves for its question, never against the
regressed context it was generated from.

- **pass** when the context holds the answer and the answer states that fact correctly (the number with its unit,
  the name, both numbers of a pair in the right roles) **and** cites, in square brackets, the document the fact
  comes from exactly as the context's `[<doc>]` line names it.
- **pass** when the context does not hold the answer and the answer says it does not know, stating no answer.
- **fail** otherwise: a wrong or missing fact, a refusal where the context holds the answer, no citation, a
  citation of another document or of a name that is not a document (`[folder/file.md]`, `[Blast radius ...]`), or
  an answer invented where the context holds none.
- Wording, length and Markdown do not count.
