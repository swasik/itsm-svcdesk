# ai-generated: 100% - Claude Code (Opus 5.5) wrote this helper for Lab 8 Stretch 1 and ran it on `itsmlab eval 8 --json` outputs on 1 October 2026; the lecturer reviews it
"""Turn `itsmlab eval 8 --json` outputs into answers for you to label.

    python3 answers.py eval/runs-1.json [eval/runs-2.json ...] > eval/answers.jsonl

One line per distinct answer the answer step gave, in the run of your own pipeline (`"student"` in the JSON) and in
the regressed runs, as {"id", "run", "question", "answer", "context", "student": ""}. The regressed answers are there
on purpose: a set of right answers gives a judge nothing to disagree about. Every answer carries the context YOUR
pipeline retrieved for its question, never the regressed one it was generated from (A-24): a judge reading an answer
against a broken context measures its faithfulness to that context, not whether it is the right answer from the
corpus. Several files - the same suite run more than once, or a wider suite - add answers: generation is not
repeatable to the byte, and the same answer twice is kept once. Fill "student" with "pass" or "fail" yourself, by your
own rubric, BEFORE you run the judge. Standard library only.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    runs = []
    for path in sys.argv[1:]:
        with open(path, encoding="utf-8") as f:
            runs.append(json.load(f).get("answers", {}))
    # the context your own pipeline retrieved, per question (the answer step retrieves each question once, A-09)
    sound = {a["question"]: a.get("context", "") for answers in runs for a in answers.get("student", [])
             if a.get("context")}
    seen = set()
    for index, answers in enumerate(runs, start=1):
        for run, items in answers.items():
            for number, a in enumerate(items, start=1):
                if a.get("error") or not a.get("answer", "").strip():
                    continue
                if a["question"] not in sound:
                    print(f"skipped ({run}): no run of your own pipeline retrieved for {a['question']!r}", file=sys.stderr)
                    continue
                key = (a["question"], a["answer"].strip())
                if key in seen:                      # the same answer twice says nothing new
                    continue
                seen.add(key)
                print(json.dumps({"id": f"r{index}-{run}-{number:02d}", "run": run, "question": a["question"],
                                  "answer": a["answer"].strip(), "context": sound[a["question"]], "student": ""},
                                 ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
