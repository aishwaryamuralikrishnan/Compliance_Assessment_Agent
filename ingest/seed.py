"""One-off setup script, run by the developer outside the graph.

    python -m ingest.seed all              # schema + corpus + users + memory
    python -m ingest.seed schema           # create tables (idempotent)
    python -m ingest.seed corpus           # download, chunk, embed, upsert both regulations
    python -m ingest.seed corpus --no-embed --regulation GDPR   # dry run without model calls
    python -m ingest.seed stats            # parse the cached HTML and print counts (no DB, no models)
    python -m ingest.seed urls             # URLs + file names if EUR-Lex blocks the download (manual save)
    python -m ingest.seed users            # create lena.k (product_manager) and m.weber (dpo)
    python -m ingest.seed memory           # org facts + user preference into the LangGraph Store
    python -m ingest.seed reindex          # re-chunk + re-embed after chunker / embedding changes

Every seeded memory item carries source: seed so it is distinguishable from learned items.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone

from compliance_agent import config, db, memory
from ingest import chunker, eurlex

# --------------------------------------------------------------------------------------
# Seed data (demo scenario from the project summary)
# --------------------------------------------------------------------------------------

SEED_USERS = [
    {"username": "lena.k", "display_name": "Lena K.", "role": "product_manager", "password_env": "SEED_PM_PASSWORD"},
    {"username": "m.weber", "display_name": "M. Weber", "role": "dpo", "password_env": "SEED_DPO_PASSWORD"},
]

SEED_ORG_FACTS = [
    {
        "key": "org-profile",
        "text": "Organisation profile: EU-based fintech, about 80 staff, has a named Data Protection Officer, "
                "no AI systems registered yet.",
        "kind": "profile",
    },
    {
        "key": "us-fraud-vendor-dpf",
        "text": "DPO note (Sep 2026): our US fraud-prevention vendor is certified under the EU-US Data Privacy "
                "Framework, so transfers of personal data to that vendor are covered (GDPR Art. 45); record each "
                "transfer in the transfer log.",
        "kind": "vendor_transfer",
    },
    {
        "key": "dpo-named",
        "text": "A Data Protection Officer is appointed (m.weber). All assessments that touch automated "
                "decision-making or special-category data must be reviewed by the DPO before build.",
        "kind": "governance",
    },
]

SEED_USER_PREFS = [
    {
        "user_id": "lena.k",
        "key": "answer-length",
        "text": "Prefers short answers: keep findings brief, no long explanations. "
                "(Rated two earlier answers down for being too long.)",
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------------------
# schema
# --------------------------------------------------------------------------------------

def cmd_schema(args: argparse.Namespace) -> None:
    from compliance_agent.models import embedding_dims

    dims = embedding_dims()
    with db.connect_plain() as conn:
        existing = db.existing_embedding_dims(conn)
        if existing is not None and existing != dims:
            sys.exit(
                f"legal_chunks.embedding has {existing} dims but models.yaml says {dims}. "
                f"Run `python -m ingest.seed reindex` to rebuild the corpus with the new embedding model."
            )
        db.create_schema(conn, dims)
    db.setup_langgraph_tables(dims)
    print(f"schema ok (embedding dims = {dims}; checkpointer + store tables ready)")


# --------------------------------------------------------------------------------------
# corpus
# --------------------------------------------------------------------------------------

def _parse_one(reg_code: str, reg_cfg: dict, *, force_download: bool, offline: bool):
    art_src = reg_cfg["articles_source"]
    rec_src = reg_cfg["recitals_source"]
    if offline:
        art = eurlex.load_cached(art_src["celex"])
        rec = eurlex.load_cached(rec_src["celex"])
        if art is None:
            sys.exit(f"No cached HTML for {art_src['celex']} under data/corpus/raw/. Run `corpus` first.")
    else:
        art = eurlex.fetch(art_src["celex"], art_src["url"], force=force_download)
        rec = eurlex.fetch(rec_src["celex"], rec_src["url"], force=force_download)
    split_over = int(config.corpus_config().get("split_article_over_words", 350))
    chunks = chunker.parse_regulation(
        reg_code, reg_cfg.get("short", reg_code), art.html, rec.html if rec else None,
        split_article_over_words=split_over,
    )
    return art, rec, chunks


def _print_stats(reg_code: str, reg_cfg: dict, chunks: list[chunker.Chunk]) -> dict:
    s = chunker.stats(chunks)
    exp = reg_cfg.get("expected", {})
    flags = []
    for k in ("articles", "recitals", "annexes"):
        if k in exp and exp[k] != s[k]:
            flags.append(f"{k}: got {s[k]}, expected {exp[k]}")
    print(f"[{reg_code}] {s['chunks']} chunks  {s['by_type']}")
    print(f"[{reg_code}] articles={s['articles']} recitals={s['recitals']} annexes={s['annexes']} "
          f"words={s['words_total']} (max {s['words_max']}, mean {s['words_mean']})")
    if s["untitled_articles"]:
        print(f"[{reg_code}] WARNING untitled articles: {s['untitled_articles']}")
    for f in flags:
        print(f"[{reg_code}] WARNING {f}")
    return s


def cmd_urls(args: argparse.Namespace) -> None:
    """Print the source URLs and the file names for a manual browser download."""
    regs = config.corpus_config()["regulations"]
    print("If the automatic download is blocked by EUR-Lex's bot check, save each page with\n"
          "Ctrl+S -> 'Webpage, HTML only' under exactly this name, then re-run `corpus`:\n")
    for reg_code, reg_cfg in regs.items():
        for kind in ("articles_source", "recitals_source"):
            src = reg_cfg[kind]
            html_path, _ = eurlex._paths(src["celex"])
            status = "present" if html_path.exists() else "missing"
            print(f"[{reg_code} {kind.split('_')[0]:<8}] {src['url']}\n"
                  f"{'':>20}-> {html_path}   ({status})\n")


def cmd_stats(args: argparse.Namespace) -> None:
    regs = config.corpus_config()["regulations"]
    for reg_code, reg_cfg in regs.items():
        if args.regulation and reg_code != args.regulation:
            continue
        _, _, chunks = _parse_one(reg_code, reg_cfg, force_download=False, offline=True)
        _print_stats(reg_code, reg_cfg, chunks)
        if args.dump:
            out = config.DATA_DIR / "corpus" / f"{reg_code}.chunks.jsonl"
            with out.open("w", encoding="utf-8") as fh:
                for c in chunks:
                    fh.write(json.dumps(c.as_record(), ensure_ascii=False) + "\n")
            print(f"[{reg_code}] wrote {out}")
        if args.show:
            for c in chunks:
                if c.chunk_key in args.show:
                    print("\n----", c.heading, f"({c.word_count} words; cross_refs={c.cross_refs})")
                    print(c.text[:1500])


def _embed_all(texts: list[str], batch_size: int = 64) -> list[list[float]]:
    from compliance_agent.models import embeddings

    emb = embeddings()
    vectors: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        for attempt in range(1, 4):
            try:
                vectors.extend(emb.embed_documents(batch))
                break
            except Exception as exc:  # rate limits, transient gateway errors
                if attempt == 3:
                    raise
                print(f"  embed batch {i // batch_size} failed ({exc}); retrying in {3 * attempt}s")
                time.sleep(3 * attempt)
        print(f"  embedded {min(i + batch_size, len(texts))}/{len(texts)}", end="\r")
    print()
    return vectors


UPSERT_SQL = """
INSERT INTO legal_chunks (
    chunk_key, regulation, unit_type, chapter, chapter_title, section, section_title,
    article, article_letter, article_title, paragraph, paragraph_letter, recital, annex, annex_title, point,
    heading, text, cross_refs, word_count,
    celex, source_url, retrieved_at, embed_model, chunk_version, embedding
) VALUES (
    %(chunk_key)s, %(regulation)s, %(unit_type)s, %(chapter)s, %(chapter_title)s, %(section)s, %(section_title)s,
    %(article)s, %(article_letter)s, %(article_title)s, %(paragraph)s, %(paragraph_letter)s, %(recital)s,
    %(annex)s, %(annex_title)s, %(point)s,
    %(heading)s, %(text)s, %(cross_refs)s, %(word_count)s,
    %(celex)s, %(source_url)s, %(retrieved_at)s, %(embed_model)s, %(chunk_version)s, %(embedding)s
)
ON CONFLICT (chunk_key) DO UPDATE SET
    regulation = EXCLUDED.regulation, unit_type = EXCLUDED.unit_type,
    chapter = EXCLUDED.chapter, chapter_title = EXCLUDED.chapter_title,
    section = EXCLUDED.section, section_title = EXCLUDED.section_title,
    article = EXCLUDED.article, article_letter = EXCLUDED.article_letter, article_title = EXCLUDED.article_title,
    paragraph = EXCLUDED.paragraph, paragraph_letter = EXCLUDED.paragraph_letter, recital = EXCLUDED.recital,
    annex = EXCLUDED.annex, annex_title = EXCLUDED.annex_title, point = EXCLUDED.point,
    heading = EXCLUDED.heading, text = EXCLUDED.text, cross_refs = EXCLUDED.cross_refs,
    word_count = EXCLUDED.word_count, celex = EXCLUDED.celex, source_url = EXCLUDED.source_url,
    retrieved_at = EXCLUDED.retrieved_at,
    embed_model = COALESCE(EXCLUDED.embed_model, legal_chunks.embed_model),
    chunk_version = EXCLUDED.chunk_version,
    embedding = COALESCE(EXCLUDED.embedding, legal_chunks.embedding)
"""


def cmd_corpus(args: argparse.Namespace) -> None:
    from compliance_agent.models import embedding_dims, embedding_model_id

    cfg = config.corpus_config()
    chunk_version = int(cfg.get("chunk_version", 1))
    dims = embedding_dims()
    embed_model = embedding_model_id()

    with db.connect_plain() as conn:
        existing = db.existing_embedding_dims(conn)
        if existing is not None and existing != dims:
            sys.exit(f"legal_chunks.embedding has {existing} dims, models.yaml says {dims}: run `reindex`.")
        db.create_schema(conn, dims)

        for reg_code, reg_cfg in cfg["regulations"].items():
            if args.regulation and reg_code != args.regulation:
                continue
            print(f"[{reg_code}] downloading / loading HTML ...")
            art, rec, chunks = _parse_one(reg_code, reg_cfg, force_download=args.force_download, offline=args.offline)
            print(f"[{reg_code}] articles html: {art.celex} ({'cache' if art.from_cache else 'downloaded'}), "
                  f"recitals html: {rec.celex if rec else '-'}")
            s = _print_stats(reg_code, reg_cfg, chunks)

            vectors: list[list[float] | None]
            if args.no_embed:
                vectors = [None] * len(chunks)
                embed_model_used = None
            else:
                print(f"[{reg_code}] embedding {len(chunks)} chunks with {embed_model} ...")
                vectors = _embed_all([f"{c.heading}\n{c.text}" for c in chunks])  # type: ignore[assignment]
                embed_model_used = embed_model

            if args.replace:
                conn.execute("DELETE FROM legal_chunks WHERE regulation = %s", (reg_code,))

            rows = []
            for c, v in zip(chunks, vectors):
                celex = art.celex if c.unit_type != "recital" else (rec.celex if rec else art.celex)
                src = art if c.unit_type != "recital" else (rec or art)
                rec_dict = c.as_record()
                rec_dict.update(
                    celex=celex,
                    source_url=src.url,
                    retrieved_at=src.retrieved_at,
                    embed_model=embed_model_used,
                    chunk_version=chunk_version,
                    embedding=v,
                )
                rows.append(rec_dict)
            with conn.cursor() as cur:
                cur.executemany(UPSERT_SQL, rows)
            conn.execute(
                """INSERT INTO corpus_versions (regulation, celex, source_url, retrieved_at, embed_model,
                                                embed_dims, chunk_version, n_chunks, stats)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (reg_code, art.celex, art.url, art.retrieved_at, embed_model_used, dims,
                 chunk_version, len(rows), json.dumps(s)),
            )
            print(f"[{reg_code}] upserted {len(rows)} chunks")

        total = conn.execute("SELECT count(*) AS n FROM legal_chunks").fetchone()["n"]
        print(f"legal_chunks now holds {total} rows")


def cmd_reindex(args: argparse.Namespace) -> None:
    """Drop the chunk table (vector dim may change) and rebuild from cached HTML."""
    from compliance_agent.models import embedding_dims

    with db.connect_plain() as conn:
        conn.execute("DROP TABLE IF EXISTS legal_chunks")
        db.create_schema(conn, embedding_dims())
    print("legal_chunks dropped and recreated")
    args.replace = True
    args.no_embed = False
    args.force_download = False
    args.offline = args.offline if hasattr(args, "offline") else False
    cmd_corpus(args)


# --------------------------------------------------------------------------------------
# users
# --------------------------------------------------------------------------------------

def cmd_users(args: argparse.Namespace) -> None:
    import bcrypt

    with db.connect_plain() as conn:
        for u in SEED_USERS:
            password = config.env(u["password_env"]) or ""
            if not password:
                sys.exit(f"{u['password_env']} is not set (see .env.example).")
            pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            conn.execute(
                """INSERT INTO users (username, display_name, role, password_hash)
                   VALUES (%s, %s, %s, %s)
                   ON CONFLICT (username) DO UPDATE
                   SET display_name = EXCLUDED.display_name, role = EXCLUDED.role,
                       password_hash = EXCLUDED.password_hash""",
                (u["username"], u["display_name"], u["role"], pw_hash),
            )
            print(f"user {u['username']} ({u['role']}) ready")


# --------------------------------------------------------------------------------------
# memory
# --------------------------------------------------------------------------------------

def cmd_memory(args: argparse.Namespace) -> None:
    from langgraph.store.postgres import PostgresStore

    with PostgresStore.from_conn_string(config.database_url(), index=db.store_index_config()) as store:
        store.setup()
        for fact in SEED_ORG_FACTS:
            store.put(
                memory.ORG_FACTS,
                fact["key"],
                {"text": fact["text"], "kind": fact["kind"], "source": "seed", "author": "seed",
                 "run_id": None, "created_at": _now()},
            )
            print(f"org fact '{fact['key']}' stored")
        for pref in SEED_USER_PREFS:
            store.put(
                memory.user_prefs_namespace(pref["user_id"]),
                pref["key"],
                {"text": pref["text"], "user": pref["user_id"], "source": "seed", "author": "seed",
                 "run_id": None, "created_at": _now()},
            )
            print(f"preference '{pref['key']}' for {pref['user_id']} stored")
        n_facts = len(store.search(memory.ORG_FACTS, limit=100))
        print(f"store holds {n_facts} org facts")


# --------------------------------------------------------------------------------------
# all
# --------------------------------------------------------------------------------------

def cmd_all(args: argparse.Namespace) -> None:
    cmd_schema(args)
    cmd_corpus(args)
    cmd_users(args)
    cmd_memory(args)


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def corpus_args(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--regulation", choices=["GDPR", "AI_ACT"], help="only this regulation")
        sp.add_argument("--no-embed", action="store_true", help="skip embeddings (no model calls)")
        sp.add_argument("--replace", action="store_true", help="delete existing rows of the regulation first")
        sp.add_argument("--force-download", action="store_true", help="ignore the HTML cache")
        sp.add_argument("--offline", action="store_true", help="use cached HTML only")

    sub.add_parser("schema").set_defaults(func=cmd_schema)
    sp = sub.add_parser("corpus"); corpus_args(sp); sp.set_defaults(func=cmd_corpus)
    sp = sub.add_parser("reindex"); corpus_args(sp); sp.set_defaults(func=cmd_reindex)
    sp = sub.add_parser("stats")
    sp.add_argument("--regulation", choices=["GDPR", "AI_ACT"])
    sp.add_argument("--dump", action="store_true", help="write data/corpus/<REG>.chunks.jsonl")
    sp.add_argument("--show", nargs="*", default=[], help="print these chunk keys, e.g. GDPR:art22 AI_ACT:anxIII:5")
    sp.set_defaults(func=cmd_stats)
    sub.add_parser("urls", help="print source URLs + target file names for a manual download").set_defaults(func=cmd_urls)
    sub.add_parser("users").set_defaults(func=cmd_users)
    sub.add_parser("memory").set_defaults(func=cmd_memory)
    sp = sub.add_parser("all"); corpus_args(sp); sp.set_defaults(func=cmd_all)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
