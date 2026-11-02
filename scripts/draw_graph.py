"""Draw the compiled orchestrator graph, as LangGraph sees it, next to the hand-drawn live graph of the UI.

    python scripts/draw_graph.py            # writes docs/images/compiled_graph.mmd and compiled_graph_xray.mmd (Mermaid text)
    python scripts/draw_graph.py --png      # also renders PNGs through mermaid.ink (needs internet), or paste the .mmd into mermaid.live

The outer drawing has exactly the nodes and edges the UI's live graph is pinned to (tests/test_graph.py, layout test); the
x-ray drawing opens the two create_agent subgraphs (model, tools and the middleware hooks). The tool gate and the two
interrupt() boxes of the UI are not nodes: the gate is middleware around every tool call inside the agents' `tools` node,
the DPO's interrupt() is raised inside that gate, and the product manager's interrupt() inside pm_revision.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("OPENROUTER_API_KEY", "not-needed-to-draw")

from compliance_agent.graph import build_graph  # noqa: E402


def _mermaid(graph, xray: bool) -> str:
    text = graph.get_graph(xray=xray).draw_mermaid()
    for a, b in [("\\3a", "__"), ("\\5b", "_"), ("\\5d", "_"), ("\\2e", "_")]:       # ids LangGraph escapes, which Mermaid rejects
        text = text.replace(a, b)
    return re.sub(r'\(([^()<>"]*?)\)(?=\n|;|$)', lambda m: '("' + m.group(1) + '")', text)   # quote labels with [ ] .


def main() -> None:
    out = ROOT / "docs" / "images"
    g = build_graph()
    for name, xray in (("compiled_graph", False), ("compiled_graph_xray", True)):
        (out / f"{name}.mmd").write_text(_mermaid(g, xray), encoding="utf-8")
        print("wrote", out / f"{name}.mmd")
        if "--png" in sys.argv:
            try:
                (out / f"{name}.png").write_bytes(g.get_graph(xray=xray).draw_mermaid_png())
                print("wrote", out / f"{name}.png")
            except Exception as exc:  # mermaid.ink unreachable: the .mmd can be pasted into https://mermaid.live
                print(f"png skipped ({type(exc).__name__}); paste the .mmd into mermaid.live instead")


if __name__ == "__main__":
    main()
