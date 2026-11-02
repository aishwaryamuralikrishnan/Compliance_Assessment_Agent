"""Chunker tests on a small EUR-Lex-shaped fixture (both HTML flavours)."""
from __future__ import annotations

from ingest import chunker

OJ_HTML = """
<html><body>
<p class="doc-ti">REGULATION (EU) 2016/679 OF THE EUROPEAN PARLIAMENT AND OF THE COUNCIL</p>
<p class="normal">THE EUROPEAN PARLIAMENT AND THE COUNCIL OF THE EUROPEAN UNION,</p>
<p class="normal">Having regard to the Treaty on the Functioning of the European Union, and in particular Article 16 thereof,</p>
<p class="normal">Whereas:</p>
<table><tr><td><p>(1)</p></td><td><p>The protection of natural persons in relation to the processing of personal data is a fundamental right.</p></td></tr></table>
<table><tr><td><p>(2)</p></td><td><p>The principles of, and rules on the protection of natural persons should, whatever their nationality or residence, respect their fundamental rights and freedoms, in particular their right to the protection of personal data. See Article 22 and Articles 12 to 14.</p></td></tr></table>
<p class="normal">HAVE ADOPTED THIS REGULATION:</p>
<p class="ti-section-1">CHAPTER I</p>
<p class="ti-section-2">General provisions</p>
<p class="ti-art">Article 1</p>
<p class="sti-art">Subject-matter and objectives</p>
<p class="normal">1.&nbsp;&nbsp;&nbsp;This Regulation lays down rules relating to the protection of natural persons.</p>
<p class="normal">2.&nbsp;&nbsp;&nbsp;This Regulation protects fundamental rights and freedoms of natural persons.</p>
<p class="ti-art">Article 2</p>
<p class="sti-art">Material scope</p>
<p class="normal">1.&nbsp;&nbsp;&nbsp;This Regulation applies to the processing of personal data wholly or partly by automated means. %s</p>
<table><tr><td><p>(a)</p></td><td><p>in the course of an activity which falls outside the scope of Union law;</p></td></tr></table>
<p class="normal">2.&nbsp;&nbsp;&nbsp;This Regulation does not apply to the processing of personal data by a natural person. %s</p>
<p class="normal">3.&nbsp;&nbsp;&nbsp;Regulation (EC) No 45/2001 applies, see Article 98 and Article 2(1). %s</p>
<p class="normal">Done at Brussels, 27 April 2016.</p>
<p class="normal">For the European Parliament</p>
<p class="normal">The President</p>
<p class="doc-ti">ANNEX III</p>
<p class="doc-ti">High-risk AI systems referred to in Article 6(2)</p>
<p class="normal">High-risk AI systems pursuant to Article 6(2) are the AI systems listed in any of the following areas:</p>
<p class="normal">1.&nbsp;&nbsp;&nbsp;Biometrics, in so far as their use is permitted:</p>
<table><tr><td><p>(a)</p></td><td><p>remote biometric identification systems.</p></td></tr></table>
<p class="normal">2.&nbsp;&nbsp;&nbsp;Critical infrastructure.</p>
<p class="normal">5.&nbsp;&nbsp;&nbsp;Access to essential services:</p>
<table><tr><td><p>(b)</p></td><td><p>AI systems intended to be used to evaluate the creditworthiness of natural persons.</p></td></tr></table>
<p class="note">( 1 ) OJ C 229, 31.7.2012, p. 90.</p>
</body></html>
""" % (" lorem" * 150, " ipsum" * 150, " dolor" * 100)

CONSOLIDATED_HTML = """
<html><body>
<div class="eli-container">
<p>02016R0679 — EN — 04.05.2016 — 000.001</p>
<table><tr><td>►B</td><td>REGULATION (EU) 2016/679 OF THE EUROPEAN PARLIAMENT AND OF THE COUNCIL</td></tr></table>
<p>▼B</p>
<div id="cpt_I" class="eli-subdivision"><p class="oj-ti-section-1">CHAPTER I</p><div class="eli-title"><p class="oj-ti-section-2">General provisions</p></div>
<div id="art_1" class="eli-subdivision"><p class="oj-ti-art">Article 1</p><p class="oj-sti-art">Subject-matter and objectives</p>
<div id="art_1.001"><p class="oj-normal">1.&nbsp;&nbsp;&nbsp;This Regulation lays down rules ►M1 as amended ◄ relating to the protection of natural persons.</p></div>
</div>
<div id="art_2" class="eli-subdivision"><p class="oj-ti-art">Article 2</p><p class="oj-sti-art">Material scope</p>
<div id="art_2.001"><p class="oj-normal">1.&nbsp;&nbsp;&nbsp;Short article referencing Article 22(1) and Article 35.</p></div>
</div>
</div>
<div class="oj-footnote"><p class="oj-note">( 1 ) OJ C 229, 31.7.2012, p. 90.</p></div>
</div>
</body></html>
"""


def test_oj_format_full_pipeline():
    chunks = chunker.parse_regulation("GDPR", "GDPR", OJ_HTML, OJ_HTML, split_article_over_words=350)
    keys = [c.chunk_key for c in chunks]
    # recitals
    assert "GDPR:rec1" in keys and "GDPR:rec2" in keys
    rec2 = next(c for c in chunks if c.chunk_key == "GDPR:rec2")
    assert rec2.cross_refs == [12, 13, 14, 22]
    # short article -> one chunk with both paragraphs
    art1 = next(c for c in chunks if c.chunk_key == "GDPR:art1")
    assert art1.unit_type == "article"
    assert art1.article_title == "Subject-matter and objectives"
    assert art1.chapter == "I" and art1.chapter_title == "General provisions"
    assert "1. This Regulation lays down rules" in art1.text and "2. This Regulation protects" in art1.text
    # long article -> one chunk per numbered paragraph; point (a) attaches to paragraph 1
    p1 = next(c for c in chunks if c.chunk_key == "GDPR:art2:p1")
    p3 = next(c for c in chunks if c.chunk_key == "GDPR:art2:p3")
    assert p1.unit_type == "article_paragraph" and p1.paragraph == 1
    assert "(a) in the course of an activity" in p1.text
    assert p1.heading == "GDPR Article 2(1) — Material scope"
    assert p3.cross_refs == [98]            # self-reference Article 2(1) dropped
    # signature block is not in Article 2
    assert "Done at Brussels" not in p3.text and "The President" not in p3.text
    # annex points
    a5 = next(c for c in chunks if c.chunk_key == "GDPR:anxIII:5")
    assert a5.unit_type == "annex_point" and a5.point == "5" and a5.annex == "III"
    assert "(b) AI systems intended to be used to evaluate the creditworthiness" in a5.text
    assert a5.heading.startswith("GDPR Annex III, point 5 — High-risk AI systems")
    intro = next(c for c in chunks if c.chunk_key == "GDPR:anxIII:intro")
    assert intro.cross_refs == [6]
    # footnote dropped
    assert all("OJ C 229" not in c.text for c in chunks)
    s = chunker.stats(chunks)
    assert s["articles"] == 2 and s["recitals"] == 2 and s["annexes"] == 1


def test_consolidated_format_markers_stripped():
    chunks = chunker.parse_regulation("GDPR", "GDPR", CONSOLIDATED_HTML, None)
    keys = {c.chunk_key for c in chunks}
    assert keys == {"GDPR:art1", "GDPR:art2"}
    art1 = next(c for c in chunks if c.chunk_key == "GDPR:art1")
    assert "►" not in art1.text and "◄" not in art1.text and "▼" not in art1.text
    assert "as amended" in art1.text
    art2 = next(c for c in chunks if c.chunk_key == "GDPR:art2")
    assert art2.cross_refs == [22, 35]
    assert all("OJ C 229" not in c.text for c in chunks)


def test_cross_refs_ranges_and_lists():
    assert chunker.extract_cross_refs("see Articles 12 to 14 and Article 22(1)(a), Article 35(3)") == [12, 13, 14, 22, 35]
    assert chunker.extract_cross_refs("Articles 13, 14 and 15 apply", self_article=14) == [13, 15]
