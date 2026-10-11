# ai-generated: 100% - Claude Code (Opus 5.5) wrote this for Lab 8 Stretch 1 from AI-SPEC.md section 8's formula and checked it against the checker's kappa on 1 October 2026; the lecturer reviews it
"""Cohen's kappa between the "student" and "judge" columns of eval/judge.jsonl, as the checker recomputes it (A-24).

    python3 kappa.py eval/judge.jsonl

Prints the 2x2 table, p_o, p_e and kappa, and the front matter for eval/KAPPA.md. Standard library only.
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    pairs = []
    with open(sys.argv[1], encoding="utf-8") as f:
        for line in f:
            if line.strip():
                row = json.loads(line)
                pairs.append((row["student"], row["judge"]))
    n = len(pairs)
    table = {(s, j): sum(1 for p in pairs if p == (s, j)) for s in ("pass", "fail") for j in ("pass", "fail")}
    p_o = (table["pass", "pass"] + table["fail", "fail"]) / n
    s_pass = (table["pass", "pass"] + table["pass", "fail"]) / n
    j_pass = (table["pass", "pass"] + table["fail", "pass"]) / n
    p_e = s_pass * j_pass + (1 - s_pass) * (1 - j_pass)
    print(f"n = {n}")
    print(f"                judge pass  judge fail")
    print(f"student pass    {table['pass', 'pass']:10d}  {table['pass', 'fail']:10d}")
    print(f"student fail    {table['fail', 'pass']:10d}  {table['fail', 'fail']:10d}")
    print(f"p_o = {p_o:.3f}   p_e = {s_pass:.3f} x {j_pass:.3f} + {1 - s_pass:.3f} x {1 - j_pass:.3f} = {p_e:.3f}")
    if p_e >= 1:
        print("kappa is undefined: both of you used one and the same label for everything")
        return 1
    kappa = (p_o - p_e) / (1 - p_e)
    print(f"kappa = (p_o - p_e) / (1 - p_e) = {kappa:.3f}\n")
    print("---\nlab8_kappa:\n  n: %d\n  kappa: %.2f\n  judge: deepeval 4.2.7 G-Eval, qwen3:1.7b through Ollama\n---" % (n, kappa))
    return 0


if __name__ == "__main__":
    sys.exit(main())
