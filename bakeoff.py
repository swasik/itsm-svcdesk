# ai-generated: 100% - Claude Code (fresh-solution run) wrote it from CI-SPEC.md section 3 alone, checked on lab5-practice
"""bakeoff.py - scanner SARIF + a labels file -> a per-tool confusion matrix (CI-SPEC.md P-14..P-23).

    python3 -S -E bakeoff.py --labels labels.json a.sarif b.sarif > bakeoff.json

Standard library only. Each function names the rule it implements.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from urllib.parse import unquote

# P-19: the course table of classes and their CWE numbers.
CLASS_CWES: dict[str, frozenset[int]] = {
    "secret": frozenset({259, 260, 321, 798}),
    "injection": frozenset({74, 77, 78, 79, 80, 88, 89, 90, 91, 94, 95, 96, 611, 776, 917, 943, 1336}),
    "deserialization": frozenset({502}),
    "weak-crypto": frozenset({261, 326, 327, 328, 330, 331, 338, 759, 760, 916}),
    "insecure-transport": frozenset({295, 297, 319, 322, 757}),
    "path-traversal": frozenset({22, 23, 35, 36, 73}),
    "ssrf": frozenset({918}),
    "vulnerable-dependency": frozenset({937, 1035, 1104, 1395}),
    "misconfiguration": frozenset({16, 215, 250, 489, 668, 732, 1188}),
    "access-control": frozenset({284, 285, 639, 862, 863}),
}
VULN = "vulnerable-dependency"

SEMGREP_NAMES = {"semgrep", "semgrep oss", "semgrep ce", "semgrep community edition", "semgrep pro"}
FIXED_NAMES = {"trivy": "trivy", "grype": "grype", "osv-scanner": "osv-scanner", "gitleaks": "gitleaks"}

# P-19 (c): "CWE" in any case, not preceded by a letter or digit, then "-" and the whole run of digits.
CWE_RE = re.compile(r"(?<![A-Za-z0-9])[Cc][Ww][Ee]-([0-9]+)")
# P-20: a token is a maximal run of A-Z a-z 0-9 . _ -
TOKEN_RE = re.compile(r"[A-Za-z0-9._-]+")
SEP_RE = re.compile(r"[-_.]+")


def get(obj, *keys):
    """Nested member access where a missing member, a null and a non-object all give None (P-16: null is absent)."""
    for key in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def as_list(value) -> list:
    return value if isinstance(value, list) else []


def is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def tool_id(run: dict) -> str:
    """P-15."""
    name = get(run, "tool", "driver", "name")
    if not isinstance(name, str):
        return "unknown"
    name = name.strip().lower()
    if name in FIXED_NAMES:
        return FIXED_NAMES[name]
    if name in SEMGREP_NAMES:
        return "semgrep"
    slug = re.sub(r"[^a-z0-9]+", "-", name).strip("-")
    return slug or "unknown"


def result_path(uri: str) -> str:
    """P-17: decode %XX, drop file:// (any case), drop one leading ./"""
    path = unquote(uri)
    if path[:7].lower() == "file://":
        path = path[7:]
    if path.startswith("./"):
        path = path[2:]
    return path


def set_file(path: str, root: str) -> str | None:
    """P-17: the path from the last component equal to the set root, or None when outside the set."""
    parts = path.split("/")
    for i in range(len(parts) - 1, -1, -1):
        if parts[i] == root:
            return "/".join(parts[i:])
    return None


def result_lines(region) -> tuple[int, int] | None:
    """P-18."""
    start = get(region, "startLine")
    if not is_int(start) or start < 1:
        return None
    end = get(region, "endLine")
    if not is_int(end) or end < start:
        end = start
    return start, end


def cwe_numbers(tags) -> set[int]:
    found: set[int] = set()
    for tag in as_list(tags):
        if isinstance(tag, str):
            found.update(int(n) for n in CWE_RE.findall(tag))
    return found


def result_classes(tool: str, result: dict, rule: dict | None) -> set[str]:
    """P-19 (a) to (d); "other" is returned as an empty set (it matches nothing)."""
    declared = get(result, "properties", "class")
    if isinstance(declared, str) and declared in CLASS_CWES:  # (a)
        return {declared}
    if tool == "gitleaks":  # (b)
        return {"secret"}
    if tool in ("grype", "osv-scanner"):
        return {VULN}
    if tool == "trivy":
        tags = {t.lower() for t in as_list(get(rule, "properties", "tags")) if isinstance(t, str)}
        by_tag = {"vulnerability": VULN, "secret": "secret", "misconfiguration": "misconfiguration"}
        classes = {cls for tag, cls in by_tag.items() if tag in tags}
        if classes:
            return classes
    numbers = cwe_numbers(get(result, "properties", "tags")) | cwe_numbers(get(rule, "properties", "tags"))  # (c)
    return {cls for cls, cwes in CLASS_CWES.items() if cwes & numbers}  # (d) when empty


def normalise(name: str) -> str:
    """PEP 503 as P-20 states it."""
    return SEP_RE.sub("-", name.lower())


def message_tokens(text) -> set[str]:
    """P-20: tokens of message.text, with . _ - stripped from both ends, normalised."""
    if not isinstance(text, str):
        return set()
    tokens = set()
    for raw in TOKEN_RE.findall(text):
        token = raw.strip("._-")
        if token:
            tokens.add(normalise(token))
    return tokens


def collect(labels: dict, documents: list[dict]) -> tuple[list[str], dict[str, list[dict]]]:
    """P-15, P-16, P-17: tool ids in input order, and per tool the results inside the set."""
    root = labels.get("set")
    order: list[str] = []
    per_tool: dict[str, list[dict]] = {}
    for document in documents:
        for run in as_list(get(document, "runs")):
            if not isinstance(run, dict):
                continue
            tool = tool_id(run)
            if tool not in per_tool:
                per_tool[tool] = []
                order.append(tool)
            rules: dict[str, dict] = {}
            for rule in as_list(get(run, "tool", "driver", "rules")):
                rid = get(rule, "id")
                if isinstance(rid, str) and rid not in rules:
                    rules[rid] = rule
            for result in as_list(get(run, "results")):
                if not isinstance(result, dict):
                    continue
                kind = result.get("kind")
                if kind is not None and kind != "fail":
                    continue
                if result.get("suppressions"):  # any suppression drops it; absent, null, [] keep it
                    continue
                locations = as_list(result.get("locations"))
                if not locations:
                    continue
                physical = get(locations[0], "physicalLocation")
                uri = get(physical, "artifactLocation", "uri")
                if not isinstance(uri, str) or uri == "":
                    continue
                file = set_file(result_path(uri), root) if isinstance(root, str) else None
                if file is None:
                    continue  # outside the set: triage material, not the matrix
                rule_id = result.get("ruleId")
                rule = rules.get(rule_id) if isinstance(rule_id, str) else None
                per_tool[tool].append({
                    "rule_id": rule_id if isinstance(rule_id, str) else None,
                    "file": file,
                    "lines": result_lines(get(physical, "region")),
                    "classes": result_classes(tool, result, rule),
                    "tokens": message_tokens(get(result, "message", "text")),
                })
    return order, per_tool


def matches(result: dict, defect: dict) -> bool:
    """P-20."""
    if result["file"] != defect.get("file") or defect.get("class") not in result["classes"]:
        return False
    if defect["class"] == VULN:
        package = defect.get("package")
        return isinstance(package, str) and normalise(package) in result["tokens"]
    lines = result["lines"]
    if lines is None:
        return False
    start, end = lines
    d_start, d_end = defect.get("start_line"), defect.get("end_line")
    if not is_int(d_start) or not is_int(d_end):
        return False
    return start <= d_end and d_start <= end


def ratio(numerator: int, denominator: int):
    return None if denominator == 0 else round(numerator / denominator, 4)


def confusion_matrix(labels: dict, sarif_documents: list[dict]) -> dict:
    """The matrix of P-21 and P-22 for the labels (P-14) and the parsed SARIF documents."""
    defects = [d for d in as_list(labels.get("defects")) if isinstance(d, dict)]
    order, per_tool = collect(labels, sarif_documents)
    tools: dict[str, dict] = {}
    for tool in sorted(order):
        found: set[int] = set()
        unmatched: set[tuple] = set()
        for result in per_tool[tool]:
            hit = False
            for index, defect in enumerate(defects):
                if matches(result, defect):
                    found.add(index)
                    hit = True
            if not hit:
                start, end = result["lines"] if result["lines"] else (None, None)
                unmatched.add((result["rule_id"], result["file"], start, end))
        tp, fp = len(found), len(unmatched)
        fn = len(defects) - tp
        tools[tool] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": ratio(tp, tp + fp),
            "recall": ratio(tp, tp + fn),
            "f1": ratio(2 * tp, 2 * tp + fp + fn),
        }
    return {"set": labels.get("set"), "defects": len(as_list(labels.get("defects"))), "tools": tools}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="per-tool confusion matrix of SARIF against labels (CI-SPEC.md P-23)")
    parser.add_argument("--labels", required=True, help="the labels file (P-14)")
    parser.add_argument("sarif", nargs="+", help="SARIF 2.1.0 files")
    args = parser.parse_args(argv)
    with open(args.labels, encoding="utf-8-sig") as fh:
        labels = json.load(fh)
    documents = []
    for path in args.sarif:
        with open(path, encoding="utf-8-sig") as fh:
            documents.append(json.load(fh))
    json.dump(confusion_matrix(labels, documents), sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
