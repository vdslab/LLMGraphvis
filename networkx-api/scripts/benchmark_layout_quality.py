"""Compare layout parameter strategies by drawn readability (ADR 0017).

For each graph and force layout, four parameter sets are drawn and scored with
`layout_quality` exactly as the app would show them:

    nx_default  networkx's own defaults
    legacy      the size-only rules used before ADR 0017, with raw weights
    profile     the current profile-driven rules, median-normalized weights
    optimized   the best candidate `layout_optimizer.search` finds from `profile`

plus `legacy_x10` / `profile_x10`, the same rules with every weight multiplied
by ten, to show whether a result depends on the weight's unit.

No database is needed. Run inside the networkx-api container:

    docker compose cp sample_data networkx-api:/tmp/sample_data
    docker compose exec networkx-api python scripts/benchmark_layout_quality.py \\
        --data-dir /tmp/sample_data --out /tmp/layout_quality.csv
"""

import argparse
import csv
import json
import math
import sys
import time
from pathlib import Path

import networkx as nx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.logic import layout_optimizer  # noqa: E402
from app.logic.common_utils import calculate_smart_node_size  # noqa: E402
from app.logic.layout_quality import evaluate  # noqa: E402
from app.logic.layouts import WeightRole, get_spec  # noqa: E402
from app.logic.layouts.profile import profile_graph  # noqa: E402
from app.logic.layouts.weights import normalize_strength  # noqa: E402

LAYOUTS = ("forceatlas2", "spring", "arf")


def legacy_params(name: str, G) -> dict:
    """The size-only tuning as it was before ADR 0017, frozen for comparison."""
    n = G.number_of_nodes()
    if name == "spring":
        iterations, threshold = (
            (1000, 1e-6) if n < 500 else (500, 1e-5) if n < 2000 else (200, 1e-4)
        )
        return {"k": 2.0 / math.sqrt(n), "iterations": iterations,
                "threshold": threshold, "seed": 42}
    if name == "forceatlas2":
        avg_degree = 2 * G.number_of_edges() / n if n else 0
        return {"max_iter": max(200, min(2000, n)),
                "scaling_ratio": max(2.0, min(10.0, avg_degree * 0.5)),
                "gravity": 1.0, "jitter_tolerance": 1.0, "seed": 42}
    if name == "arf":
        return {"max_iter": 1000 if n < 500 else (500 if n < 2000 else 200)}
    return {}


def load_graphs(data_dir: Path, max_nodes: int):
    graphs = {}
    for path in sorted(data_dir.rglob("*.graphml")):
        G = nx.read_graphml(path)
        G = nx.Graph(G)  # layouts here are undirected; keep weights
        if 3 <= G.number_of_nodes() <= max_nodes:
            graphs[path.stem] = G

    # Synthetic graphs covering what the samples lack: fragmentation, trees,
    # hub-dominated degree, and a few hundred nodes.
    parts = [nx.barabasi_albert_graph(k, 2, seed=k) for k in (120, 60, 30, 15, 8)]
    fragmented = nx.disjoint_union_all(parts)
    fragmented.add_nodes_from(f"iso{i}" for i in range(20))
    graphs["synthetic_fragmented"] = fragmented
    graphs["synthetic_tree300"] = nx.random_labeled_tree(300, seed=1)
    graphs["synthetic_ba500"] = nx.barabasi_albert_graph(500, 2, seed=1)
    graphs["synthetic_grid"] = nx.convert_node_labels_to_integers(nx.grid_2d_graph(15, 15))
    return {k: v for k, v in graphs.items() if v.number_of_nodes() <= max_nodes}


def with_weights(G, factor: float, normalize: bool):
    """A copy weighted by `weight` times `factor`, or None if it has no weights."""
    if not any("weight" in d for *_, d in G.edges(data=True)):
        return None
    H = G.copy()
    for *_, data in H.edges(data=True):
        data["weight"] = float(data.get("weight", 1.0)) * factor
    if normalize:
        normalize_strength(H, "weight")
    return H


def draw(spec, G, params, size):
    start = time.perf_counter()
    pos = spec.compute(G, dict(params))
    seconds = time.perf_counter() - start
    return evaluate(pos, G.edges, size), seconds


def rows_for(graph_name, G, layout_name):
    spec = get_spec(layout_name)
    size = calculate_smart_node_size(G.number_of_nodes())["default"]
    weighted_role = spec.weight_role is WeightRole.STRENGTH
    rows = []

    def record(variant, graph, params, report=None, seconds=None):
        if report is None:
            report, seconds = draw(spec, graph, params, size)
        rows.append({
            "graph": graph_name, "nodes": graph.number_of_nodes(),
            "edges": graph.number_of_edges(), "layout": layout_name,
            "variant": variant, "seconds": round(seconds, 3),
            **{k: v for k, v in report.as_dict().items() if k != "issues"},
            "issues": " ".join(report.issues),
            "params": json.dumps(
                {k: v for k, v in params.items() if not isinstance(v, dict)},
                sort_keys=True, default=str,
            ),
        })

    record("nx_default", G, {"seed": 42} if "seed" in spec.params else {})

    raw = with_weights(G, 1.0, normalize=False) if weighted_role else None
    legacy = legacy_params(layout_name, G)
    if raw is not None:
        record("legacy", raw, {**legacy, "weight": "weight"})
        record("legacy_x10", with_weights(G, 10.0, False), {**legacy, "weight": "weight"})
    else:
        record("legacy", G, legacy)

    normalized = with_weights(G, 1.0, normalize=True) if weighted_role else None
    graph = normalized if normalized is not None else G
    weight = "weight" if normalized is not None else None
    profile_params, _notes = spec.tuned(graph, profile_graph(graph, weight))
    if weight:
        profile_params["weight"] = weight
    record("profile", graph, profile_params)
    if normalized is not None:
        record("profile_x10", with_weights(G, 10.0, True), profile_params)

    result = layout_optimizer.search(graph, spec, profile_params, size)
    best = min([result.baseline, *result.candidates], key=lambda c: c.report.score)
    record("optimized", graph, best.params, best.report, best.seconds)
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("layout_quality.csv"))
    parser.add_argument("--layouts", nargs="+", default=list(LAYOUTS))
    parser.add_argument(
        "--max-nodes", type=int, default=800,
        help="Skip larger graphs; ForceAtlas2 is O(n^2) per iteration.",
    )
    args = parser.parse_args()

    graphs = load_graphs(args.data_dir, args.max_nodes)
    rows = []
    for graph_name, G in graphs.items():
        for layout_name in args.layouts:
            print(f"{graph_name} ({G.number_of_nodes()} nodes) / {layout_name}", flush=True)
            rows.extend(rows_for(graph_name, G, layout_name))

    with args.out.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {args.out}")


if __name__ == "__main__":
    main()
