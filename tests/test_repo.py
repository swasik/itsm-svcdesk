# ai-generated: 100% - Claude Code (Fable 5.1) wrote these self-checks from design/LAB1.md sections 2.1, 3 and 5; the lecturer ran them
"""Self-checks of the repository files the Tier A checker reads: DECISIONS.md, the Stretch artifacts,
the compose contract, itsmlab.yaml and the AI-disclosure headers. They mirror the published checks so a
broken artifact is caught here before the checker sees it."""

from __future__ import annotations

import importlib.util
import itertools
import os
import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
LABELS = ("Decision", "Rejected alternative", "Reason", "Service owner", "Customer outcome")
ADMISSIBLE = {"C1": ("wallclock", "business"), "C2": ("reopen", "immutable"), "C3": ("matrix", "vip")}
HEADER = re.compile(r"ai-generated:\s*\d{1,3}\s*%\s*-\s*\S")
DASHES = (chr(0x2014), chr(0x2013))  # em-dash and en-dash, built from code points so this file stays clean
# Course files kept byte for byte (LAB7.md D-02: scylla.yaml is ScyllaDB's own file with five lines changed, and
# ScyllaDB's comments carry an em-dash); they are checked by their SHA-256, not by this repository's style rules.
COURSE_FILES = {"scylla/scylla.yaml": "5806b13274cf2500f400e389d3280996e4797d7a83131a08925d5a6522f92766"}


def load_make_decisions():
    spec = importlib.util.spec_from_file_location("make_decisions", ROOT / "make_decisions.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_decisions(text: str) -> dict[str, str]:
    """Front matter values, checked the way L1-CORE-3 checks them."""
    assert text.startswith("---\n"), "DECISIONS.md must start with YAML front matter"
    end = text.index("\n---", 4)
    front = yaml.safe_load(text[4:end])
    values = front["svcdesk_decisions"]
    for key, admissible in ADMISSIBLE.items():
        assert values[key] in admissible, (key, values[key])
    return values


def check_sections(text: str) -> None:
    for key in ("C1", "C2", "C3"):
        match = re.search(rf"^## {key}\b.*?$(.*?)(?=^## |\Z)", text, re.M | re.S)
        assert match, f"section ## {key} missing"
        section = match.group(1)
        for label in LABELS:
            found = re.search(rf"\*\*{label}(?::\*\*|\*\*:)(.*?)(?=\*\*(?:{'|'.join(LABELS)})(?::\*\*|\*\*:)|^#|\Z)",
                              section, re.S | re.M)
            assert found, f"{key}: label {label} missing"
            assert len(found.group(1).strip()) >= 20, f"{key}: {label} has fewer than 20 characters"


def test_decisions_md_structure():
    text = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
    parse_decisions(text)
    check_sections(text)


def test_decisions_md_carries_disclosure_header():
    head = (ROOT / "DECISIONS.md").read_text(encoding="utf-8").splitlines()[:10]
    assert any(HEADER.search(line) for line in head)


def test_shipped_decisions_declare_the_defaults():
    if any(os.environ.get(f"SVCDESK_C{i}") for i in (1, 2, 3)):
        pytest.skip("SVCDESK_C1/C2/C3 are set; the shipped file may have been regenerated for that combination")
    values = parse_decisions((ROOT / "DECISIONS.md").read_text(encoding="utf-8"))
    assert values == {"C1": "wallclock", "C2": "immutable", "C3": "vip"}


def test_decisions_md_is_the_output_of_make_decisions():
    text = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
    values = parse_decisions(text)
    module = load_make_decisions()
    assert module.render(values["C1"], values["C2"], values["C3"]) == text


@pytest.mark.parametrize("combination", list(itertools.product(*ADMISSIBLE.values())), ids="-".join)
def test_make_decisions_renders_every_combination(combination, tmp_path):
    module = load_make_decisions()
    output = tmp_path / "DECISIONS.md"
    assert module.main([*combination, "--output", str(output)]) == 0
    text = output.read_text(encoding="utf-8")
    assert parse_decisions(text) == dict(zip(("C1", "C2", "C3"), combination))
    check_sections(text)
    assert HEADER.search("\n".join(text.splitlines()[:10]))
    assert not any(dash in text for dash in DASHES)


def test_make_decisions_rejects_bad_values(tmp_path):
    module = load_make_decisions()
    assert module.main(["wallclock", "sometimes", "vip", "--output", str(tmp_path / "x.md")]) != 0
    assert not (tmp_path / "x.md").exists()


def test_converge_report():
    path = ROOT / "specs" / "converge.md"
    text = path.read_text(encoding="utf-8")
    assert len(text) >= 400
    ids = set(re.findall(r"R-\d\d", text))
    assert len(ids) >= 3
    assert all(1 <= int(i[2:]) <= 25 for i in ids), sorted(ids)


def test_agent_config():
    assert (ROOT / "CLAUDE.md").is_file()
    agent = (ROOT / ".claude" / "agents" / "reviewer.md").read_text(encoding="utf-8")
    assert agent.startswith("---\n")
    front = yaml.safe_load(agent[4:agent.index("\n---", 4)])
    assert front["name"] and front["description"]
    denied = front["disallowedTools"]
    assert isinstance(denied, list) and len(denied) >= 3
    policy = (ROOT / "AGENT-POLICY.md").read_text(encoding="utf-8")
    for entry in denied:
        assert re.search(rf"^- {re.escape(entry)}: .{{20,}}", policy, re.M), f"no policy line for {entry}"


def test_compose_contract():
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    svc = services["svcdesk"]
    assert "build" in svc
    assert str(svc["environment"]["SVCDESK_TEST_CLOCK"]) == "1"
    assert any(str(p).endswith(":8080") for p in svc["ports"])
    tests = services["tests"]
    assert tests["profiles"] == ["tests"]
    assert "SVCDESK_URL" in tests["environment"]
    for name, service in services.items():
        for volume in service.get("volumes", []) or []:
            if isinstance(volume, dict):
                assert volume.get("type") != "bind", name
            else:
                source = str(volume).split(":")[0]
                assert not (source.startswith(("./", "/", "~")) or source == "."), f"bind mount in {name}: {volume}"


def test_itsmlab_yaml():
    """This file travels with the checkpoint into every student's repository, where `repository:` is the
    student's own (restored from their main during adoption, README "How it becomes checkpoint/lab-1") and
    `baselines` records the adopted checkpoints; so the shape is checked, not the reference's own values."""
    config = yaml.safe_load((ROOT / "itsmlab.yaml").read_text(encoding="utf-8"))
    assert isinstance(config["lab"], int) and 1 <= config["lab"] <= 8
    assert isinstance(config["baselines"], dict)
    for lab, value in config["baselines"].items():
        assert re.fullmatch(r"lab[1-8]", str(lab)) and value in ("checkpoint", "student"), (lab, value)  # template/itsmlab.yaml
    repository = config["repository"]
    assert isinstance(repository, str) and re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9._-]+", repository), repository
    assert "<" not in repository, "the template placeholder <owner>/<repo> is not a repository"
    assert config["submissions_repo"] == "swasik/itsm-2026-submissions"
    assert config["checker_image"].startswith("ghcr.io/swasik/itsmlab")


def _disclosure_files() -> list[Path]:
    files = [ROOT / "DECISIONS.md"]
    for folder in ("src", "specs"):
        files.extend(p for p in (ROOT / folder).rglob("*") if p.suffix in {".py", ".md"} and p.is_file())
    return files


@pytest.mark.parametrize("path", _disclosure_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_ai_disclosure_header(path):
    head = path.read_text(encoding="utf-8").splitlines()[:10]
    assert any(HEADER.search(line) for line in head), f"{path.relative_to(ROOT)} lacks the ai-generated header"


def test_no_em_dashes_anywhere():
    offenders = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in {".venv", ".git", "data", "__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        if path.relative_to(ROOT).as_posix() in COURSE_FILES:
            continue
        if path.suffix in {".py", ".md", ".yml", ".yaml", ".toml", ".sh", ".txt", ".cfg", ".ini", ""} or path.name == "Dockerfile":
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            if any(dash in text for dash in DASHES):
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_course_files_are_the_course_bytes():
    import hashlib
    for relative, digest in COURSE_FILES.items():
        path = ROOT / relative
        if path.exists():
            assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, f"{relative} is not the course's file"
