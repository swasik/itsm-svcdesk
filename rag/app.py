# ai-generated: 70% - the course's skeleton (contract, Ollama call, index lifecycle) kept; Claude Code (Opus 5.5) wrote the heading chunker, the front-matter/comment handling and the BM25 + dense fusion as the student, and measured each change on golden-set.jsonl (DEFENSE.md, Retrieval)
"""The Lab 8 retrieval service (AI-SPEC.md A-06 to A-08), grown from the course's skeleton.

    GET  /health                         200 while the process is up
    POST /index                          (re)build the index from rag/corpus.yaml -> {"documents": n, "chunks": m}
    POST /retrieve {"question", "k"}     -> {"results": [{"doc", "chunk", "score"}, ...]}, at most k, best first

Embeddings come from all-minilm:22m through Ollama at OLLAMA_BASE_URL, the only network call the service makes.
It never generates text: the answer step is the course's (A-09).

What changed from the skeleton, and why (numbers in DEFENSE.md, `## Retrieval`):

- Chunks follow the Markdown structure: one chunk per `##`/`###` section, packed paragraph by paragraph up to
  MAX_CHARS, a long block (a table, a transcript) split at line boundaries. A section is never cut mid-word or
  mid-row, and a table stays with its heading.
- The YAML front matter is a chunk of its own (it is the densest facts of most documents); HTML comments (the
  ai-generated headers) are dropped - they are about the file, not about the semester.
- Every chunk starts with a one-line breadcrumb, `<document title> > <section heading>`, so a section whose body
  never names its subject ("## Detection") is still found by it. The document's PATH is never put into the chunk:
  the citation must come from the answer step's `[<doc>]` line, not from the text (AI-SPEC.md section 10, rule 2).
- Ranking fuses two rankings by reciprocal rank (RRF, k0 = 60): cosine similarity of all-minilm embeddings and
  BM25 over the same chunk text. all-minilm alone misses questions whose words are rare identifiers (CVE ids,
  alert names, flag names); BM25 alone misses paraphrases. Ties break by corpus order, so two identical calls give
  identical results (A-07).
"""

import json
import math
import os
import pathlib
import re
import threading
import urllib.error
import urllib.request
from collections import Counter

import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://ollama:11434").rstrip("/")
EMBED_MODEL = "all-minilm:22m"  # A-06: the one model the rag service may call
REPO = pathlib.Path(os.environ.get("RAG_REPO", "/repo")).resolve()  # the repository, copied into the image
CORPUS_FILE = REPO / "rag" / "corpus.yaml"  # A-04
MAX_CHARS = int(os.environ.get("RAG_MAX_CHARS", "1200"))  # a chunk's body at most this long (all-minilm: 512 tokens)
EMBED_BATCH = 16  # chunks per /api/embed call
RRF_K0 = 60  # reciprocal-rank-fusion constant (Cormack et al. 2009)
MODE = os.environ.get("RAG_MODE", "hybrid")  # hybrid | dense | bm25 - for measuring each ranking alone
BM25_K1, BM25_B = 1.2, 0.75
BM25_WEIGHT = float(os.environ.get("RAG_BM25_WEIGHT", "3"))  # the lexical ranking's weight in the fusion

STOPWORDS = set(
    "a an and are as at be by did do does for from had has have how in is it its of on or that the their this to"
    " was were what when where which who why will with".split()
)

app = FastAPI(title="rag")
_lock = threading.Lock()
_index: list[dict] = []  # one entry per chunk: {"doc", "chunk", "vector", "norm", "tf", "len"}
_df: Counter = Counter()
_avglen = 1.0
_documents = 0


def embed(texts: list[str]) -> list[list[float]]:
    """Ollama's /api/embed: one vector of 384 numbers per text."""
    body = json.dumps({"model": EMBED_MODEL, "input": texts}).encode("utf-8")
    request = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/embed", data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.load(response)["embeddings"]
    except urllib.error.HTTPError as err:  # for example 404: the model is not pulled into this Ollama
        raise HTTPException(502, f"Ollama answered {err.code}: {err.read().decode('utf-8', 'replace')}") from err
    except urllib.error.URLError as err:
        raise HTTPException(502, f"Ollama at {OLLAMA_BASE_URL} unreachable: {err.reason}") from err


def load_corpus() -> list[tuple[str, str]]:
    """rag/corpus.yaml -> [(path, text)]; a document is named by its repository path (A-04)."""
    config = yaml.safe_load(CORPUS_FILE.read_text(encoding="utf-8"))
    documents = []
    for entry in config["lab8_corpus"]["documents"]:
        path = entry["path"]
        file = (REPO / path).resolve()
        if REPO not in file.parents:
            raise HTTPException(422, f"{path}: not a file of the repository")
        if not file.is_file():
            raise HTTPException(422, f"{path}: not in the image - rebuild it: docker compose up -d --build rag")
        documents.append((path, file.read_text(encoding="utf-8")))
    return documents


def tokens(text: str) -> list[str]:
    """Lower-case words and numbers; '0.3', 'p99', 'cve-2026-84782' and 'kb/search' parts stay whole."""
    return [t for t in re.findall(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", text.lower()) if t not in STOPWORDS]


def _split_long(block: str) -> list[str]:
    """A block longer than MAX_CHARS (a table, a transcript): pieces at line boundaries, then at spaces."""
    pieces, current = [], ""
    for line in block.split("\n"):
        while len(line) > MAX_CHARS:  # a single huge line: cut at the last space before the limit
            cut = line.rfind(" ", 0, MAX_CHARS)
            cut = cut if cut > 0 else MAX_CHARS
            if current:
                pieces.append(current)
                current = ""
            pieces.append(line[:cut])
            line = line[cut:].lstrip()
        if current and len(current) + 1 + len(line) > MAX_CHARS:
            pieces.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current.strip():
        pieces.append(current)
    return pieces


def chunk(text: str) -> list[str]:
    """Markdown-aware chunks, each prefixed by '<title> > <section>' (see the module docstring)."""
    text = text.replace("\r\n", "\n")
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)  # ai-generated headers and other comments
    chunks: list[str] = []
    title = ""
    match = re.match(r"---\n(.*?)\n---\n", text, flags=re.S)
    front = None
    if match:
        front = match.group(1).strip()
        text = text[match.end() :]
    heading = re.search(r"^# (.+)$", text, flags=re.M)
    title = heading.group(1).strip() if heading else ""
    if front:
        for piece in _split_long(front):
            chunks.append(f"{title} > front matter\n{piece}")
    # sections at ## and ### headings; text before the first one belongs to the title
    parts = re.split(r"^(#{2,3} .+)$", text, flags=re.M)
    sections = [("", parts[0])] + [(parts[i].lstrip("#").strip(), parts[i + 1]) for i in range(1, len(parts), 2)]
    for name, body in sections:
        body = re.sub(r"^# .+$", "", body, flags=re.M).strip()
        if not body:
            continue
        crumb = f"{title} > {name}" if name else title
        blocks = [b for b in re.split(r"\n\s*\n", body) if b.strip()]
        current = ""
        for block in blocks:
            for piece in _split_long(block) if len(block) > MAX_CHARS else [block]:
                if current and len(current) + 2 + len(piece) > MAX_CHARS:
                    chunks.append(f"{crumb}\n{current}")
                    current = piece
                else:
                    current = f"{current}\n\n{piece}" if current else piece
        if current.strip():
            chunks.append(f"{crumb}\n{current}")
    return [c for c in chunks if c.strip()]


def cosine(a: list[float], a_norm: float, b: list[float], b_norm: float) -> float:
    if a_norm == 0.0 or b_norm == 0.0:
        return 0.0
    return sum(x * y for x, y in zip(a, b)) / (a_norm * b_norm)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "documents": _documents, "chunks": len(_index)}


@app.post("/index")
def build_index() -> dict:
    global _index, _documents, _df, _avglen
    documents = load_corpus()
    entries = [{"doc": path, "chunk": piece} for path, text in documents for piece in chunk(text)]
    for start in range(0, len(entries), EMBED_BATCH):
        batch = entries[start : start + EMBED_BATCH]
        for entry, vector in zip(batch, embed([e["chunk"] for e in batch])):
            entry["vector"] = vector
            entry["norm"] = math.sqrt(sum(x * x for x in vector))
    df: Counter = Counter()
    for entry in entries:
        words = tokens(entry["chunk"])
        entry["tf"] = Counter(words)
        entry["len"] = len(words)
        df.update(set(words))
    avglen = sum(e["len"] for e in entries) / len(entries) if entries else 1.0
    with _lock:
        _index, _documents, _df, _avglen = entries, len(documents), df, avglen
    return {"documents": len(documents), "chunks": len(entries)}


class RetrieveRequest(BaseModel):
    question: str = Field(min_length=1)
    k: int = Field(default=3, ge=1, le=100)


def _bm25(query: list[str], entry: dict, n: int, df: Counter, avglen: float) -> float:
    score = 0.0
    for term in set(query):
        tf = entry["tf"].get(term, 0)
        if not tf:
            continue
        idf = math.log(1 + (n - df[term] + 0.5) / (df[term] + 0.5))
        score += idf * tf * (BM25_K1 + 1) / (tf + BM25_K1 * (1 - BM25_B + BM25_B * entry["len"] / avglen))
    return score


@app.post("/retrieve")
def retrieve(request: RetrieveRequest) -> dict:
    with _lock:
        index, df, avglen = _index, _df, _avglen
    if not index:
        raise HTTPException(409, "no index yet: POST /index first")
    query = embed([request.question])[0]
    query_norm = math.sqrt(sum(x * x for x in query))
    dense = [(cosine(query, query_norm, e["vector"], e["norm"]), i) for i, e in enumerate(index)]
    words = tokens(request.question)
    lexical = [(_bm25(words, e, len(index), df, avglen), i) for i, e in enumerate(index)]
    if MODE == "dense":
        scored = dense
    elif MODE == "bm25":
        scored = lexical
    else:
        fused = [0.0] * len(index)
        for ranking, weight in ((dense, 1.0), (lexical, BM25_WEIGHT)):
            for rank, (_, i) in enumerate(sorted(ranking, key=lambda pair: (-pair[0], pair[1]))):
                fused[i] += weight / (RRF_K0 + rank + 1)
        scored = [(score, i) for i, score in enumerate(fused)]
    scored.sort(key=lambda pair: (-pair[0], pair[1]))  # best first; a tie keeps corpus order (A-07: repeatable)
    return {
        "results": [
            {"doc": index[i]["doc"], "chunk": index[i]["chunk"], "score": round(score, 6)}
            for score, i in scored[: request.k]
        ]
    }
