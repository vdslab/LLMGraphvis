"""Catalog and file access for the bundled sample networks."""

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


SAMPLE_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "samples"


@dataclass(frozen=True)
class SampleNetwork:
    id: str
    name: str
    description: str
    asset_filename: str
    node_count: int
    edge_count: int
    source_url: str

    @property
    def upload_filename(self) -> str:
        return f"{self.name}.graphml"

    def public_data(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("asset_filename")
        return data


SAMPLE_NETWORKS = (
    SampleNetwork(
        id="karate-club",
        name="Zachary's Karate Club",
        description="A weighted friendship network from a university karate club.",
        asset_filename="karate-club.graphml",
        node_count=34,
        edge_count=78,
        source_url=(
            "https://networkx.org/documentation/stable/reference/generated/"
            "networkx.generators.social.karate_club_graph.html"
        ),
    ),
    SampleNetwork(
        id="les-miserables",
        name="Les Misérables",
        description="Character co-appearances in Victor Hugo's novel.",
        asset_filename="les-miserables.graphml",
        node_count=77,
        edge_count=254,
        source_url=(
            "https://networkx.org/documentation/stable/reference/generated/"
            "networkx.generators.social.les_miserables_graph.html"
        ),
    ),
    SampleNetwork(
        id="florentine-families",
        name="Florentine Families",
        description="Marriage ties among prominent Renaissance Florentine families.",
        asset_filename="florentine-families.graphml",
        node_count=15,
        edge_count=20,
        source_url=(
            "https://networkx.org/documentation/stable/reference/generated/"
            "networkx.generators.social.florentine_families_graph.html"
        ),
    ),
    SampleNetwork(
        id="davis-southern-women",
        name="Davis Southern Women",
        description="A bipartite network linking women to social events they attended.",
        asset_filename="davis-southern-women.graphml",
        node_count=32,
        edge_count=89,
        source_url=(
            "https://networkx.org/documentation/stable/reference/generated/"
            "networkx.generators.social.davis_southern_women_graph.html"
        ),
    ),
)

_SAMPLES_BY_ID = {sample.id: sample for sample in SAMPLE_NETWORKS}


def list_samples() -> list[dict[str, Any]]:
    """Return the public catalog in its curated display order."""
    return [sample.public_data() for sample in SAMPLE_NETWORKS]


def get_sample(sample_id: str) -> SampleNetwork | None:
    """Resolve a public sample ID through the fixed allowlist."""
    return _SAMPLES_BY_ID.get(sample_id)


def load_graphml(sample: SampleNetwork) -> str:
    """Read one allowlisted bundled GraphML asset as UTF-8 text."""
    return (SAMPLE_DATA_DIR / sample.asset_filename).read_text(encoding="utf-8")
