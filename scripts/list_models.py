"""Print the model ids available to your OpenRouter key, to fill in config/models.yaml.

    python scripts/list_models.py                 # all models: id | name
    python scripts/list_models.py luna sonnet     # only ids/names containing these words

Reads OPENROUTER_API_KEY and OPENROUTER_BASE_URL from the environment / .env.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from compliance_agent import config  # noqa: E402


def main() -> None:
    filters = [f.lower() for f in sys.argv[1:]]
    url = f"{config.openrouter_base_url()}/models"
    resp = requests.get(url, headers={"Authorization": f"Bearer {config.openrouter_api_key()}"}, timeout=30)
    resp.raise_for_status()
    models = resp.json().get("data", [])
    rows = []
    for m in models:
        mid = m.get("id", "")
        name = m.get("name", "")
        hay = f"{mid} {name}".lower()
        if filters and not any(f in hay for f in filters):
            continue
        rows.append((mid, name))
    rows.sort()
    width = max((len(r[0]) for r in rows), default=10)
    for mid, name in rows:
        print(f"{mid:<{width}} | {name}")
    print(f"\n{len(rows)} models (of {len(models)} available) from {url}")


if __name__ == "__main__":
    main()
