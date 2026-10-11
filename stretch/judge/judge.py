# ai-generated: 100% - Claude Code (Opus 5.5) wrote this judge for Lab 8 Stretch 1 and ran it with deepeval 4.2.7 on qwen3:1.7b on 1 October 2026; the lecturer reviews it
"""A deepeval judge over answers you have already labelled (AI-SPEC.md A-24).

    deepeval set-ollama --model=qwen3:1.7b --save=dotenv    # once; .deepeval/.deepeval and .env.local, here
    python judge.py eval/answers.jsonl > eval/judge.jsonl   # the venv's python, where deepeval 4.2.7 is installed
    python3 kappa.py eval/judge.jsonl

Reads the lines of `answers.py`, each with your own "student": "pass"|"fail" (it refuses to run while one is
missing: label first, judge second, or the judge's verdicts leak into yours). Asks deepeval's G-Eval metric, with
the model `deepeval set-ollama` configured (thinking off, see THINK) and the rubric in STEPS below, for a score
between 0 and 1 on each answer; at THRESHOLD or above the judge says "pass". Writes {"id", "question", "answer",
"student", "judge", "score", "reason"} per line on stdout, the progress on stderr. STEPS is a starting point: make it the rubric you labelled
with - kappa measures agreement on a rubric, and two different rubrics disagree by construction.
"""

from __future__ import annotations

import functools
import json
import os
import sys
import time

# deepeval's default per-call timeouts abort a judgement of a 1.7B model on a busy CPU (measured): off, before deepeval
# reads its settings. Telemetry off too, whatever the shell exported.
os.environ.setdefault("DEEPEVAL_DISABLE_TIMEOUTS", "1")
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "1")

from deepeval.metrics import GEval  # noqa: E402
from deepeval.models import OllamaModel
from deepeval.test_case import LLMTestCase, SingleTurnParams

THINK = False           # qwen3 is a thinking model; deepeval 4.2.7 has no switch for it, so this file adds one
THRESHOLD = 0.5
STEPS = [
    "Decide first whether the retrieval context contains the answer to the input question.",
    "If it does: the actual output must state that answer correctly, as the retrieval context states it. An output "
    "that says it does not know, or that states a different fact, gets a low score.",
    "If it does: the actual output must also cite, in square brackets, the name of the document the fact comes "
    "from, as the retrieval context names it in its [document] lines. No citation, or a citation of another "
    "document, lowers the score.",
    "If the retrieval context does not contain the answer: the actual output must say that it does not know and "
    "must not state any answer. An output that states an answer anyway gets a low score.",
    "Do not reward or penalise wording, length or politeness.",
]


class OllamaJudge(OllamaModel):
    """deepeval's Ollama model with the model and URL `deepeval set-ollama` saved, and `think` passed to Ollama.

    Without it qwen3 thinks before every verdict: measured on 1 October 2026, about 30 s per answer, and one answer
    ran past 1,000 generated tokens without finishing (deepeval sets no length limit)."""

    def load_model(self, async_mode: bool = False):
        client = super().load_model(async_mode)
        client.chat = functools.partial(client.chat, think=THINK)
        return client


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    with open(sys.argv[1], encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    unlabelled = [r.get("id") for r in rows if r.get("student") not in ("pass", "fail")]
    if unlabelled:
        print(f"label these first (\"student\": \"pass\" or \"fail\"): {', '.join(map(str, unlabelled))}",
              file=sys.stderr)
        return 1
    metric = GEval(name="Grounded answer", evaluation_steps=STEPS, threshold=THRESHOLD, async_mode=False,
                   model=OllamaJudge(),
                   evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT,
                                      SingleTurnParams.RETRIEVAL_CONTEXT])
    started = time.monotonic()
    for number, row in enumerate(rows, start=1):
        case = LLMTestCase(input=row["question"], actual_output=row["answer"],
                           retrieval_context=[row.get("context") or "(nothing was retrieved)"])
        metric.measure(case)
        judge = "pass" if metric.score is not None and metric.score >= THRESHOLD else "fail"
        print(json.dumps({"id": row["id"], "question": row["question"], "answer": row["answer"],
                          "student": row["student"], "judge": judge, "score": metric.score,
                          "reason": metric.reason}, ensure_ascii=False), flush=True)
        print(f"{number}/{len(rows)} {row['id']}: student {row['student']}, judge {judge} ({metric.score}), "
              f"{time.monotonic() - started:.0f} s", file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
