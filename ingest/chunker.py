"""Chunk EUR-Lex HTML along the legal structure, not by token count.

Units produced (one chunk each):
    article            short articles as a whole
    article_paragraph  one per numbered paragraph for long articles (Art. 6, Art. 13, ...)
    recital            one per recital
    annex_point        one per numbered point of an annex ("Annex III point 5")
    annex              an annex that has no numbered points

Every chunk carries: regulation, chapter, section, article number, paragraph, article
title, annex / point, a human-readable heading for citation, the verbatim text and the
list of cross-referenced article numbers (regex on "Article N" mentions).

The parser works on the *text blocks* of the document (one block per <p> / table row),
which makes it robust to both the Official Journal HTML and the consolidated-text HTML,
whose CSS classes differ. Both formats print "Article 22" and the article title as two
separate blocks, numbered paragraphs as "1.   ...", recitals as "(71) ..." and annexes
as "ANNEX III" followed by the title.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Iterable

import warnings

from bs4 import BeautifulSoup, NavigableString, Tag, XMLParsedAsHTMLWarning

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# --------------------------------------------------------------------------------------
# Block extraction
# --------------------------------------------------------------------------------------

_MARKERS = re.compile(r"[►▼][BMC]\d*|◄")          # consolidated-text amendment markers
_WS = re.compile(r"[\s\u00a0\u2002\u2003\u2009]+")
_SKIP_CLASS = re.compile(r"(footnote|oj-note|note|toc|modref|hd-modifiers|signatory|doc-end)", re.I)


def _clean(text: str) -> str:
    text = _MARKERS.sub(" ", text)
    text = _WS.sub(" ", text)
    return text.strip()


def _row_text(tr: Tag) -> str:
    cells = [_clean(td.get_text(" ")) for td in tr.find_all(["td", "th"], recursive=False)]
    cells = [c for c in cells if c]
    return " ".join(cells)


def _grid_row_text(row: Tag) -> str:
    """EUR-Lex 'grid-container grid-list': column-1 holds the label '(a)', column-2 the text."""
    label, text = "", ""
    for c in row.children:
        if not isinstance(c, Tag):
            continue
        cls = c.get("class", []) or []
        if "grid-list-column-1" in cls:
            label = _clean(c.get_text(" "))
        elif "grid-list-column-2" in cls:
            text = _clean(c.get_text(" "))
    if not (label or text):
        text = _clean(row.get_text(" "))
    return f"{label} {text}".strip()


def html_to_blocks(html: str) -> list[str]:
    """Document text as an ordered list of blocks.

    One block per paragraph (<p>), per table row, per grid-list row ("(a) ...") and per
    loose text run. A paragraph number that EUR-Lex renders as its own
    <span class="no-parag">1.</span> is prepended to the block that follows it, so a
    numbered paragraph always starts "1. ...".
    """
    soup = BeautifulSoup(html, "lxml")
    for t in soup.find_all(["script", "style", "noscript", "head"]):
        t.decompose()
    body = soup.body or soup
    blocks: list[str] = []
    pending: list[str] = []   # paragraph number waiting for its text

    def emit(text: str) -> None:
        s = _clean(text)
        if not s:
            return
        if pending:
            s = f"{pending.pop()} {s}"
        blocks.append(s)

    def skip(tag: Tag) -> bool:
        cls = " ".join(tag.get("class", []) or [])
        tid = tag.get("id", "") or ""
        return bool(_SKIP_CLASS.search(cls)) or tid.startswith(("ntr", "ntc", "footnote"))

    def walk(el: Tag) -> None:
        for child in el.children:
            if isinstance(child, NavigableString):
                emit(str(child))
                continue
            if not isinstance(child, Tag):
                continue
            if skip(child):
                continue
            name = child.name
            cls = child.get("class", []) or []
            if name == "table":
                for tr in child.find_all("tr"):
                    emit(_row_text(tr))
                continue
            if "grid-container" in cls:
                emit(_grid_row_text(child))
                continue
            if name == "span" and "no-parag" in cls:
                num = _clean(child.get_text(" "))
                if num:
                    pending.clear()
                    pending.append(num)
                continue
            if name in ("p", "h1", "h2", "h3", "h4", "h5", "li", "dt", "dd"):
                emit(child.get_text(" "))
                continue
            walk(child)

    walk(body)
    return blocks


# --------------------------------------------------------------------------------------
# Structural regexes
# --------------------------------------------------------------------------------------

RE_ARTICLE = re.compile(r"^Article\s+(\d+)([a-z]?)\s*$")
RE_CHAPTER = re.compile(r"^CHAPTER\s+([IVXLC]+)\s*$")
RE_SECTION = re.compile(r"^S(?:ECTION|ection)\s+(\d+)\s*$")
RE_ANNEX = re.compile(r"^ANNEX\s+([IVXLC]+)?\s*$")
RE_ANNEX_SECTION = re.compile(r"^Section\s+([A-Z])\.?\s*[–—-]?\s*(.*)$")
RE_RECITAL = re.compile(r"^\((\d+)\)\s+(.+)$", re.S)
RE_NUMBERED = re.compile(r"^(\d+)([a-z]?)\.\s+(.+)$", re.S)
RE_WHEREAS = re.compile(r"^Whereas\s*:?\s*$", re.I)
RE_ADOPTED = re.compile(r"^HAVE ADOPTED THIS REGULATION", re.I)
RE_DONE_AT = re.compile(r"^Done at\s+\w+", re.I)
# Closing formula after the last article (consolidated texts have no "Done at ...")
RE_BINDING = re.compile(r"^This Regulation shall be binding in its entirety", re.I)
# End-of-document footnotes: "( 1 ) OJ C 229, 31.7.2012, p. 90." etc.
RE_FOOTNOTE = re.compile(
    r"^\(\s*\d+\s*\)\s+(?:OJ\s+[CL]\b|Position of the European Parliament|Opinion of the|"
    r"Not yet published|Regulation \((?:EU|EC)\)|Directive (?:\d|\(EU\))|"
    r"(?:Council|Commission) (?:Regulation|Directive|Decision|Recommendation|Implementing|Delegated))"
)
RE_XREF = re.compile(
    r"\bArticles?\s+((?:\d+(?:\s*\(\d+\))?(?:\s*\([a-z]\))?)(?:\s*(?:,|and|or|to)\s*\d+(?:\s*\(\d+\))?(?:\s*\([a-z]\))?)*)"
)


def extract_cross_refs(text: str, self_article: int | None = None) -> list[int]:
    found: set[int] = set()
    for m in RE_XREF.finditer(text):
        group = m.group(1)
        nums = [int(n) for n in re.findall(r"(\d+)(?:\s*\(\d+\))?(?:\s*\([a-z]\))?", group)]
        # expand "Articles 12 to 22"
        for rm in re.finditer(r"(\d+)(?:\s*\(\d+\))?\s+to\s+(\d+)", group):
            a, b = int(rm.group(1)), int(rm.group(2))
            if 0 < b - a <= 30:
                nums.extend(range(a, b + 1))
        found.update(n for n in nums if 0 < n < 500)
    if self_article is not None:
        found.discard(self_article)
    return sorted(found)


# --------------------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------------------

@dataclass
class Chunk:
    chunk_key: str
    regulation: str
    unit_type: str
    heading: str
    text: str
    chapter: str | None = None
    chapter_title: str | None = None
    section: str | None = None
    section_title: str | None = None
    article: int | None = None
    article_letter: str | None = None       # "a" for inserted articles such as "Article 75a"
    article_title: str | None = None
    paragraph: int | None = None
    paragraph_letter: str | None = None     # "a" for inserted paragraphs such as "Article 5(1a)"
    recital: int | None = None
    annex: str | None = None
    annex_title: str | None = None
    point: str | None = None
    cross_refs: list[int] = field(default_factory=list)

    @property
    def word_count(self) -> int:
        return len(self.text.split())

    def as_record(self) -> dict:
        d = asdict(self)
        d["word_count"] = self.word_count
        return d


@dataclass
class _Article:
    number: int
    title: str
    chapter: str | None
    chapter_title: str | None
    section: str | None
    section_title: str | None
    letter: str = ""                                        # "a" for "Article 4a"
    intro: list[str] = field(default_factory=list)          # text before the first numbered paragraph
    paragraphs: list[tuple[str, list[str]]] = field(default_factory=list)  # (label "1" / "1a", blocks)

    @property
    def label(self) -> str:
        return f"{self.number}{self.letter}"

    @property
    def text(self) -> str:
        parts = [" ".join(self.intro).strip()] + [" ".join(p).strip() for _, p in self.paragraphs]
        return "\n".join(p for p in parts if p)


def _next_label_ok(last: str | None, num: int, letter: str) -> bool:
    """Is (num, letter) the legal successor of label `last`? '1' -> '2' or '1a'; '1a' -> '1b' or '2'."""
    if last is None:
        return num == 1 and letter == ""
    m = re.match(r"^(\d+)([a-z]?)$", last)
    last_num, last_letter = int(m.group(1)), m.group(2)
    if letter == "":
        return num == last_num + 1
    if num != last_num:
        return False
    return letter == ("a" if not last_letter else chr(ord(last_letter) + 1))


@dataclass
class _Annex:
    number: str
    title: str
    intro: list[str] = field(default_factory=list)
    points: list[tuple[str, list[str]]] = field(default_factory=list)   # (point key, blocks)
    section: str | None = None
    section_title: str | None = None


# --------------------------------------------------------------------------------------
# Parsers
# --------------------------------------------------------------------------------------

def parse_recitals(blocks: Iterable[str]) -> list[tuple[int, str]]:
    """Recitals between 'Whereas:' and 'HAVE ADOPTED THIS REGULATION'."""
    recitals: list[tuple[int, list[str]]] = []
    in_region = False
    for b in blocks:
        if not in_region:
            if RE_WHEREAS.match(b):
                in_region = True
            continue
        if RE_ADOPTED.match(b):
            break
        m = RE_RECITAL.match(b)
        expected = (recitals[-1][0] + 1) if recitals else 1
        if m and int(m.group(1)) == expected:
            recitals.append((expected, [b]))
        elif recitals:
            recitals[-1][1].append(b)
    return [(n, " ".join(parts)) for n, parts in recitals]


def parse_articles_and_annexes(blocks: list[str]) -> tuple[list[_Article], list[_Annex]]:
    articles: list[_Article] = []
    annexes: list[_Annex] = []
    chapter = chapter_title = section = section_title = None
    state = "preamble"          # preamble | body | signature | annex
    pending_title_for: str | None = None   # "article" | "chapter" | "section" | "annex"
    i = 0
    n = len(blocks)
    # The body starts at the first CHAPTER / Article 1 heading that follows the preamble
    # (for consolidated texts there is no preamble: the first heading is the start).
    while i < n:
        b = blocks[i]
        i += 1

        if state in ("body", "annex", "signature") and RE_FOOTNOTE.match(b):
            state = "footnotes"
        if state == "footnotes":
            continue

        if pending_title_for:
            target = pending_title_for
            pending_title_for = None
            if target == "article":
                if not RE_NUMBERED.match(b) and not RE_ARTICLE.match(b):
                    articles[-1].title = b
                    continue
                # article without a title line: fall through to treat b as content
            elif target == "chapter":
                chapter_title = b
                continue
            elif target == "section":
                section_title = b
                continue
            elif target == "annex":
                annexes[-1].title = b
                continue

        if state in ("preamble", "body"):
            if RE_ANNEX.match(b):
                state = "annex"
                num = RE_ANNEX.match(b).group(1) or "I"
                annexes.append(_Annex(number=num, title=""))
                pending_title_for = "annex"
                continue
            m = RE_CHAPTER.match(b)
            if m:
                state = "body"
                chapter, chapter_title, section, section_title = m.group(1), None, None, None
                pending_title_for = "chapter"
                continue
            m = RE_SECTION.match(b)
            if m and state == "body":
                section, section_title = m.group(1), None
                pending_title_for = "section"
                continue
            m = RE_ARTICLE.match(b)
            if m:
                num, letter = int(m.group(1)), m.group(2)
                last = articles[-1].label if articles else None
                if _next_label_ok(last, num, letter):
                    state = "body"
                    articles.append(_Article(num, "", chapter, chapter_title, section, section_title, letter=letter))
                    pending_title_for = "article"
                    continue
                # "Article N" mentioned alone but out of sequence: treat as text
            if state == "body" and articles:
                if RE_DONE_AT.match(b) or RE_BINDING.match(b):
                    state = "signature"
                    continue
                art = articles[-1]
                m = RE_NUMBERED.match(b)
                last = art.paragraphs[-1][0] if art.paragraphs else None
                if m and _next_label_ok(last, int(m.group(1)), m.group(2)):
                    art.paragraphs.append((f"{m.group(1)}{m.group(2)}", [b]))
                elif art.paragraphs:
                    art.paragraphs[-1][1].append(b)
                else:
                    art.intro.append(b)
            continue

        if state == "signature":
            if RE_ANNEX.match(b):
                state = "annex"
                num = RE_ANNEX.match(b).group(1) or "I"
                annexes.append(_Annex(number=num, title=""))
                pending_title_for = "annex"
            continue

        if state == "annex":
            m = RE_ANNEX.match(b)
            if m:
                num = m.group(1) or str(len(annexes) + 1)
                annexes.append(_Annex(number=num, title=""))
                pending_title_for = "annex"
                continue
            anx = annexes[-1]
            m = RE_ANNEX_SECTION.match(b)
            if m and len(m.group(1)) == 1:
                anx.section, anx.section_title = m.group(1), m.group(2).strip() or None
                anx.points.append((f"{anx.section}", [b]))   # section heading becomes its own unit
                continue
            m = RE_NUMBERED.match(b)
            if m:
                num = int(m.group(1))
                last_num = _last_point_number(anx)
                # points are increasing (usually consecutive); numbering restarts per section
                if num > last_num or (num == 1 and anx.section):
                    key = f"{anx.section}.{num}" if anx.section else str(num)
                    anx.points.append((key, [b]))
                    continue
            if anx.points:
                anx.points[-1][1].append(b)
            else:
                anx.intro.append(b)
            continue

    return articles, annexes


RE_ITEM = re.compile(r"^\((\d+)\)\s+(.+)$", re.S)


def _split_numbered_items(blocks: list[str]) -> tuple[list[str], list[tuple[str, list[str]]]] | None:
    """Split blocks into (intro, [("1", blocks), ("2", blocks), ...]) on sequential '(N)' items."""
    intro: list[str] = []
    items: list[tuple[str, list[str]]] = []
    for b in blocks:
        m = RE_ITEM.match(b)
        if m and int(m.group(1)) == len(items) + 1:
            items.append((m.group(1), [b]))
        elif items:
            items[-1][1].append(b)
        else:
            intro.append(b)
    return (intro, items) if len(items) >= 2 else None


def _last_point_number(anx: _Annex) -> int:
    for key, _ in reversed(anx.points):
        tail = key.split(".")[-1]
        if tail.isdigit():
            return int(tail)
    return 0


# --------------------------------------------------------------------------------------
# Chunk assembly
# --------------------------------------------------------------------------------------

def build_chunks(
    regulation: str,
    short_name: str,
    articles: list[_Article],
    annexes: list[_Annex],
    recitals: list[tuple[int, str]],
    *,
    split_article_over_words: int = 350,
) -> list[Chunk]:
    chunks: list[Chunk] = []

    for art in articles:
        base = dict(
            regulation=regulation,
            chapter=art.chapter,
            chapter_title=art.chapter_title,
            section=art.section,
            section_title=art.section_title,
            article=art.number,
            article_letter=art.letter or None,
            article_title=art.title or None,
        )
        title_suffix = f" — {art.title}" if art.title else ""
        long_enough = len(art.text.split()) > split_article_over_words
        if long_enough and not art.paragraphs:
            # Long article made of "(1) ... (2) ..." items (e.g. Art. 4 Definitions): treat the
            # items as paragraphs so "Article 4(4)" is its own chunk.
            items = _split_numbered_items(art.intro)
            if items:
                art.intro, art.paragraphs = items[0], items[1]
        if long_enough and len(art.paragraphs) >= 2:
            intro = " ".join(art.intro).strip()
            for idx, (label, para) in enumerate(art.paragraphs):
                text = " ".join(para).strip()
                if idx == 0 and intro:
                    text = intro + "\n" + text
                pm = re.match(r"^(\d+)([a-z]?)$", label)
                chunks.append(
                    Chunk(
                        chunk_key=f"{regulation}:art{art.label}:p{label}",
                        unit_type="article_paragraph",
                        heading=f"{short_name} Article {art.label}({label}){title_suffix}",
                        text=text,
                        paragraph=int(pm.group(1)),
                        paragraph_letter=pm.group(2) or None,
                        cross_refs=extract_cross_refs(text, art.number),
                        **base,
                    )
                )
        else:
            chunks.append(
                Chunk(
                    chunk_key=f"{regulation}:art{art.label}",
                    unit_type="article",
                    heading=f"{short_name} Article {art.label}{title_suffix}",
                    text=art.text,
                    cross_refs=extract_cross_refs(art.text, art.number),
                    **base,
                )
            )

    for num, text in recitals:
        chunks.append(
            Chunk(
                chunk_key=f"{regulation}:rec{num}",
                regulation=regulation,
                unit_type="recital",
                heading=f"{short_name} Recital {num}",
                text=text,
                recital=num,
                cross_refs=extract_cross_refs(text),
            )
        )

    for anx in annexes:
        title_suffix = f" — {anx.title}" if anx.title else ""
        intro = " ".join(anx.intro).strip()
        if anx.points:
            if intro:
                chunks.append(
                    Chunk(
                        chunk_key=f"{regulation}:anx{anx.number}:intro",
                        regulation=regulation,
                        unit_type="annex",
                        heading=f"{short_name} Annex {anx.number}{title_suffix}",
                        text=intro,
                        annex=anx.number,
                        annex_title=anx.title or None,
                        cross_refs=extract_cross_refs(intro),
                    )
                )
            for key, parts in anx.points:
                text = " ".join(parts).strip()
                label = f"point {key}" if key.split(".")[-1].isdigit() else f"Section {key}"
                chunks.append(
                    Chunk(
                        chunk_key=f"{regulation}:anx{anx.number}:{key}",
                        regulation=regulation,
                        unit_type="annex_point",
                        heading=f"{short_name} Annex {anx.number}, {label}{title_suffix}",
                        text=text,
                        annex=anx.number,
                        annex_title=anx.title or None,
                        point=key,
                        cross_refs=extract_cross_refs(text),
                    )
                )
        else:
            chunks.append(
                Chunk(
                    chunk_key=f"{regulation}:anx{anx.number}",
                    regulation=regulation,
                    unit_type="annex",
                    heading=f"{short_name} Annex {anx.number}{title_suffix}",
                    text=intro,
                    annex=anx.number,
                    annex_title=anx.title or None,
                    cross_refs=extract_cross_refs(intro),
                )
            )

    return [c for c in chunks if c.text.strip()]


def parse_regulation(
    regulation: str,
    short_name: str,
    articles_html: str,
    recitals_html: str | None,
    *,
    split_article_over_words: int = 350,
) -> list[Chunk]:
    """Full pipeline: HTML -> blocks -> structure -> chunks."""
    art_blocks = html_to_blocks(articles_html)
    articles, annexes = parse_articles_and_annexes(art_blocks)
    recitals: list[tuple[int, str]] = []
    if recitals_html is not None:
        rec_blocks = art_blocks if recitals_html is articles_html else html_to_blocks(recitals_html)
        recitals = parse_recitals(rec_blocks)
    if not recitals:
        recitals = parse_recitals(art_blocks)
    return build_chunks(
        regulation, short_name, articles, annexes, recitals,
        split_article_over_words=split_article_over_words,
    )


def stats(chunks: list[Chunk]) -> dict:
    by_type: dict[str, int] = {}
    for c in chunks:
        by_type[c.unit_type] = by_type.get(c.unit_type, 0) + 1
    articles = {c.article for c in chunks if c.article is not None and not c.article_letter}
    inserted = sorted({f"{c.article}{c.article_letter}" for c in chunks if c.article_letter})
    recitals = {c.recital for c in chunks if c.recital is not None}
    annexes = {c.annex for c in chunks if c.annex is not None}
    words = [c.word_count for c in chunks]
    return {
        "chunks": len(chunks),
        "by_type": by_type,
        "articles": len(articles),
        "inserted_articles": inserted,
        "recitals": len(recitals),
        "annexes": len(annexes),
        "words_total": sum(words),
        "words_max": max(words) if words else 0,
        "words_mean": round(sum(words) / len(words), 1) if words else 0,
        "untitled_articles": sorted(
            {c.article for c in chunks if c.article is not None and not c.article_title}
        ),
    }
