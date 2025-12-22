import pytest
from app import models
from app.logic import filter, subgraph
from app.schemas.filter import AttributeCondition, Range
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Use in-memory SQLite for verification of logic independent of current broken Postgres schema
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create tables
models.Base.metadata.create_all(bind=engine)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def setup_dummy_network(db: Session) -> int:
    network = models.Network(name="Test Network", description="Source description")
    db.add(network)
    db.commit()
    db.refresh(network)

    # Add nodes
    nodes = []
    for i in range(5):
        nodes.append(
            models.Node(network_id=network.id, node_id=str(i), label=f"Node {i}")
        )
    db.add_all(nodes)
    db.commit()

    # Add Edges (0-1, 1-2, 2-3, 3-4)
    edges = []
    for i in range(4):
        node_u = (
            db.query(models.Node)
            .filter(models.Node.network_id == network.id, models.Node.node_id == str(i))
            .first()
        )
        node_v = (
            db.query(models.Node)
            .filter(
                models.Node.network_id == network.id, models.Node.node_id == str(i + 1)
            )
            .first()
        )
        edges.append(
            models.Edge(
                network_id=network.id,
                edge_id=f"e{i}",
                source_node_id=node_u.id,
                target_node_id=node_v.id,
            )
        )
    db.add_all(edges)

    # Add Attributes
    attr = models.NodeAttribute(
        network_id=network.id, attribute_name="age", data_type="float"
    )
    db.add(attr)
    db.commit()
    db.refresh(attr)

    # Values: Node 0=10, 1=20, 2=30, 3=40, 4=50
    vals = []
    for i in range(5):
        node = (
            db.query(models.Node)
            .filter(models.Node.network_id == network.id, models.Node.node_id == str(i))
            .first()
        )
        nav = models.NodeAttributeValue(node_id=node.id, attribute_id=attr.id)
        db.add(nav)
        db.commit()
        db.refresh(nav)

        val = models.NodeFloatAttributeValue(
            node_attribute_value_id=nav.id, float_value=float((i + 1) * 10)
        )
        db.add(val)
    db.commit()

    return network.id


def test_filter_subgraph_description(db_session):
    net_id = setup_dummy_network(db_session)

    # Filter: age >= 30
    cond = AttributeCondition(attribute_name="age", ranges=[Range(min=30.0)])

    result = filter.create_subgraph_by_filter(net_id, [cond], "Filtered", db_session)
    sub_id = result["new_network_id"]

    subgraph_net = (
        db_session.query(models.Network).filter(models.Network.id == sub_id).first()
    )

    print(f"DEBUG: Description = {subgraph_net.description}")

    assert subgraph_net is not None
    assert "Filtered by:" in subgraph_net.description
    assert "attribute 'age'" in subgraph_net.description
    assert "x >= 30.0" in subgraph_net.description


def test_ego_network_description(db_session):
    net_id = setup_dummy_network(db_session)

    result = subgraph.create_ego_network(net_id, "2", 1, db_session)
    sub_id = result["new_network_id"]  # Adjust key if needed based on wrapper result

    subgraph_net = (
        db_session.query(models.Network).filter(models.Network.id == sub_id).first()
    )

    print(f"DEBUG: Description = {subgraph_net.description}")

    assert subgraph_net is not None
    assert "Ego Network of node '2'" in subgraph_net.description
    assert "radius 1" in subgraph_net.description
