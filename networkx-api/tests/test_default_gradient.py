from app.logic.layout import calculate_layout
from app.logic.visualization_builder import build_visualization
from app.schemas.visualization import NodeColorConfig
from test_layout_parameters import setup_graph


def test_unspecified_gradient_matches_legend_and_survives_reload(db):
    setup_graph(db, attrs={"score": {f"n{i}": i for i in range(6)}})
    calculate_layout(1, "circular", db)
    result = build_visualization(
        db,
        1,
        node_color_config=NodeColorConfig(
            attribute="score", scale_type="LINEAR", gradient=None
        ),
    )
    gradient = result["legend"]["node_color"]["gradient"]
    colors = {node["id"]: node["color"] for node in result["nodes"]}
    assert colors["n0"].lower() == gradient[0].lower()
    assert colors["n5"].lower() == gradient[-1].lower()
    assert len(set(colors.values())) == 6
    reloaded = build_visualization(db, 1)
    assert reloaded["nodes"] == result["nodes"]
    assert reloaded["legend"] == result["legend"]
