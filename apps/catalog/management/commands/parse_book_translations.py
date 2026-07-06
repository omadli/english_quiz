"""Extract Uzbek translations from the source PDFs into data/book{n}.json.

The 6 "4000 Essential English Words" PDFs are the Uzbek-annotated edition. On each
vocabulary page ~10 English headword entries sit in a left column and the matching
Uzbek translations sit in a right column, vertically aligned row-by-row with their
headword (see media/books/). This command reads that layout with PyMuPDF and writes
the full Uzbek string (all comma-separated synonyms) into the ``uz`` field of each
record in data/book{n}.json, aligned to the known English word of each unit.

Pipeline: parse PDFs -> write data/book{n}.json -> `manage.py import_words` to load DB.

Requires PyMuPDF, which is not in the base venv. Run via uv:
    python -m uv run --with pymupdf python manage.py parse_book_translations
Add --dry-run to report coverage without writing.
"""

from __future__ import annotations

import glob
import json
import re
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

# --- layout / OCR constants -------------------------------------------------
ARROW = re.compile(r"^\s*[-—]\s*[»*►■♦→▶]|^\s*-[>»*]", re.M)
IPA = re.compile(r"\[[^\]]{2,}\]")
POS_ONLY = re.compile(r"^[\W_]*(v|n|adj|adv|prep|pron|conj|phr|int|art|aux)\.?[\W_]*$", re.I)
ARROW_START = re.compile(r"^\s*[-—][»*►■♦→▶>]|^\s*[»►■♦→▶]")
STRAY = set("rcfijltn")  # OCR often prefixes a headword with one of these stray letters
X_SPLIT = 150            # rough left/right gate used only for page classification
ROW_TOL = 20             # px: how close a uz block's row must be to its headword's
ANCHOR = 0.7             # head_score above which a headword confidently identifies its word
ENG_STOP = {
    "the", "is", "are", "to", "of", "a", "an", "and", "you", "they", "it", "that", "with",
    "for", "was", "were", "his", "her", "their", "in", "on", "at", "or", "be", "as", "this",
    "when", "if", "not", "from", "means", "something", "someone", "my", "has", "have", "she",
    "he", "can", "because", "i", "we", "but", "so", "do", "does", "your", "its", "them",
    "there", "who", "what", "will", "would", "these", "than",
}


def norm(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


def head_candidates(line: str) -> set[str]:
    """Normalized guesses at the headword on an OCR'd entry line."""
    region = line.split("[")[0].split("]")[0]
    region = re.split(r"[-—][»*►■♦→▶>]", region)[0]
    toks = region.split()
    core = [t for t in toks if norm(t)]
    cands: set[str] = set()
    if not core:
        return cands
    avg = sum(len(norm(t)) for t in core) / len(core)
    if len(core) >= 3 and avg <= 2.0:  # spaced-out OCR word, e.g. 'e x e r c is e'
        cands.add(norm("".join(core)))
    if all(len(norm(t)) == 1 for t in core):
        cands.add(norm("".join(core)))
    tt = toks[:]
    while tt and norm(tt[0]) and len(norm(tt[0])) == 1 and norm(tt[0]) in STRAY:
        tt.pop(0)
    if tt:
        cands.add(norm(tt[0]))
        cands.add(norm("".join(tt[:2])))
    cands.discard("")
    return cands


def head_score(head_line: str, wn: str) -> float:
    cands = head_candidates(head_line)
    if not cands:
        return 0.0
    s = max(SequenceMatcher(None, c, wn).ratio() for c in cands)
    if any(wn and wn in c for c in cands):
        s = max(s, 0.9)
    return s


def english_like(t: str) -> bool:
    # whole-token match only: apostrophes in Uzbek (to'g'ri, o'rin) must not read as English
    toks = [w.strip(".,;:!?") for w in re.split(r"[\s\-]+", t.lower())]
    return sum(1 for w in toks if w in ENG_STOP) >= 2


def looks_junk_uz(t: str) -> bool:
    # real Uzbek translations are lowercase words; OCR junk (e.g. 'LTJ', '[20J') is not
    return sum(1 for c in t if c.islower()) < 2


def clean_uz(t: str) -> str:
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"^\d{1,4}\s+", "", t)  # drop a leading page-number token
    return t.strip(" .;")


def is_vocab(page) -> bool:
    txt = page.get_text("text")
    n_arrow = len(ARROW.findall(txt))
    n_ipa = len(IPA.findall(txt))
    blocks = [b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
    n_right = sum(1 for b in blocks if b[0] >= X_SPLIT)
    # a vocab page has a right-hand uz column plus either arrow example-lines or IPA headwords
    return n_right >= 4 and (n_arrow >= 5 or n_ipa >= 6)


def page_lines_blocks(page):
    blocks = [
        (b[0], b[1], b[2], b[3], b[4].strip())
        for b in page.get_text("blocks")
        if b[6] == 0 and b[4].strip()
    ]
    lines = []
    for blk in page.get_text("dict")["blocks"]:
        if blk.get("type") != 0:
            continue
        for ln in blk["lines"]:
            t = "".join(sp["text"] for sp in ln["spans"]).strip()
            if t:
                x0, y0, x1, y1 = ln["bbox"]
                lines.append((x0, y0, x1, y1, t))
    return lines, blocks


def uz_threshold(blocks) -> float:
    """Adaptive left/right split: text body sits at the left margin; uz column is right of it."""
    xs = sorted(b[0] for b in blocks)
    return xs[len(xs) // 5] + 38  # ~20th percentile x0 (= left margin) + gap


def extract_pairs(doc, grp):
    """Ordered (headword_line, uz_text, page) tuples across a unit's pages, in reading order."""
    pairs = []
    for p in grp:
        lines, blocks = page_lines_blocks(doc[p])
        if not blocks:
            continue
        thr = uz_threshold(blocks)
        left = sorted([L for L in lines if L[0] < thr], key=lambda L: L[1])
        uz_blocks = sorted([b for b in blocks if b[0] >= thr], key=lambda b: b[1])
        for _bx0, by0, _bx1, by1, t in uz_blocks:
            if "[" in t or POS_ONLY.match(t) or ARROW_START.match(t):
                continue
            uz = clean_uz(t)
            if len(uz.split()) > 12:
                continue  # backstop: far longer than any real translation = English sentence
            if english_like(uz):
                # collocation entries e.g. "on the verge of - arafasida": keep the Uzbek tail
                tail = re.split(r"\s[-—]\s*", uz)[-1].strip()
                if tail and tail != uz and not english_like(tail) and not looks_junk_uz(tail):
                    uz = tail
                else:
                    continue
            if looks_junk_uz(uz):
                continue
            bcy = (by0 + by1) / 2
            head = ""
            if left:
                L = min(left, key=lambda L: abs((L[1] + L[3]) / 2 - bcy))
                if abs((L[1] + L[3]) / 2 - bcy) <= ROW_TOL:
                    head = L[4]
            pairs.append((head, uz, p))
    return pairs


def align(pairs, words):
    """Map each known word to the (headword, uz) pair for it.

    Stage 1 locks confident headword-identity matches as anchors -- robust to
    JSON-vs-page order transpositions. Stage 2 fills the remaining words positionally
    between anchors -- robust to garbled headwords where only reading order survives.
    """
    n, m = len(pairs), len(words)
    wn = [norm(w) for w in words]
    S = [[head_score(pairs[i][0], wn[j]) for j in range(m)] for i in range(n)]
    p2w = [None] * n
    w2p = [None] * m
    cand = sorted(
        ((S[i][j], i, j) for i in range(n) for j in range(m) if S[i][j] >= ANCHOR), reverse=True
    )
    for _s, i, j in cand:
        if p2w[i] is None and w2p[j] is None:
            p2w[i], w2p[j] = j, i
    anchors = sorted((j, i) for j, i in enumerate(w2p) if i is not None)
    bounds = [(-1, -1)] + anchors + [(m, n)]
    for (j0, i0), (j1, i1) in zip(bounds, bounds[1:], strict=False):
        free_words = list(range(j0 + 1, j1))
        free_pairs = [i for i in range(i0 + 1, i1) if p2w[i] is None]
        for wj, pi in zip(free_words, free_pairs, strict=False):
            w2p[wj], p2w[pi] = pi, wj
    return w2p, S


def build_groups(doc):
    """Consecutive runs of vocab pages -> one run per unit (verified 30 per book)."""
    vpages = [i for i, p in enumerate(doc) if is_vocab(p)]
    groups, cur = [], [vpages[0]]
    for p in vpages[1:]:
        if p == cur[-1] + 1:
            cur.append(p)
        else:
            groups.append(cur)
            cur = [p]
    groups.append(cur)
    return groups


def extract_book(pdf_path, records):
    import fitz

    doc = fitz.open(pdf_path)
    groups = build_groups(doc)
    by_unit = defaultdict(list)
    for r in records:
        by_unit[r["fields"]["unit"]].append(r)
    units = sorted(by_unit)
    if len(groups) != len(units):
        raise RuntimeError(
            f"{Path(pdf_path).name}: found {len(groups)} vocab-page groups, expected {len(units)} "
            f"units -- page detection needs review"
        )
    result = {}   # en -> uz
    gaps = []     # (unit, en) with no translation found
    for grp, unit_no in zip(groups, units, strict=True):
        words = [r["fields"]["en"] for r in by_unit[unit_no]]
        pairs = extract_pairs(doc, grp)
        w2p, _ = align(pairs, words)
        for j, w in enumerate(words):
            pi = w2p[j]
            if pi is None:
                result[w] = None
                gaps.append((unit_no, w))
            else:
                result[w] = pairs[pi][1]
    return result, gaps


class Command(BaseCommand):
    help = "Extract Uzbek translations from the source PDFs into data/book{n}.json."

    def add_arguments(self, parser):
        parser.add_argument("--book", type=int, default=None, help="Only this book number (1-6)")
        parser.add_argument("--dry-run", action="store_true", help="Report coverage, write nothing")
        parser.add_argument("--data-dir", type=str, default=str(settings.BASE_DIR / "data"))
        parser.add_argument("--books-dir", type=str, default=str(settings.MEDIA_ROOT / "books"))

    def handle(self, *args, **opts):
        try:
            import fitz  # noqa: F401
        except ImportError as exc:
            raise SystemExit(
                "PyMuPDF is required. Run: "
                "python -m uv run --with pymupdf python manage.py parse_book_translations"
            ) from exc

        data_dir = Path(opts["data_dir"])
        books_dir = Path(opts["books_dir"])
        numbers = [opts["book"]] if opts["book"] else range(1, 7)
        grand_total = grand_assigned = 0
        for n in numbers:
            path = data_dir / f"book{n}.json"
            matches = glob.glob(str(books_dir / f"*  {n}*.pdf")) or glob.glob(
                str(books_dir / f"* {n}*.pdf")
            )
            if not path.exists() or not matches:
                self.stderr.write(self.style.WARNING(f"skip book {n}: missing json or pdf"))
                continue
            records = json.loads(path.read_text(encoding="utf-8"))
            result, gaps = extract_book(matches[0], records)

            changed = 0
            for r in records:
                uz = result.get(r["fields"]["en"])
                if uz and uz != r["fields"]["uz"]:
                    r["fields"]["uz"] = uz
                    changed += 1
            assigned = sum(1 for v in result.values() if v)
            grand_total += len(result)
            grand_assigned += assigned
            self.stdout.write(
                f"book {n}: {assigned}/{len(result)} translated, {changed} changed, "
                f"{len(gaps)} gap(s){': ' + ', '.join(w for _, w in gaps) if gaps else ''}"
            )
            if not opts["dry_run"]:
                path.write_text(
                    json.dumps(records, ensure_ascii=True, indent=4), encoding="utf-8"
                )
        note = " (dry-run, nothing written)" if opts["dry_run"] else ""
        self.stdout.write(
            self.style.SUCCESS(f"total {grand_assigned}/{grand_total} translated{note}")
        )
