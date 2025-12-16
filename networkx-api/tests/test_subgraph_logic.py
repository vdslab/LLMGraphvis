
import pytest
from app import models
from app.logic import subgraph, layout, centrality
from sqlalchemy.orm import Session

def test_subgraph_fresh_view(db: Session):
    """
    Test 'Fresh View' (preserve_layout=False):
    - Should exclude 'x', 'y' from source.
    - Should exclude topological metrics (e.g. 'degree').
    - Should calculate new layout.
    """
    # 1. Setup Source Network
    network = models.Network(name="Source Network")
    db.add(network)
    db.commit()
    db.refresh(network)
    
    # Add Nodes with Layout and Metrics
    nodes = []
    for i in range(5):
        n = models.Node(network_id=network.id, node_id=str(i), label=str(i))
        db.add(n)
        nodes.append(n)
    db.commit()
    
    # Add Edges (Cycle)
    for i in range(5):
        e = models.Edge(network_id=network.id, edge_id=f"e{i}", source_node_id=nodes[i].id, target_node_id=nodes[(i+1)%5].id)
        db.add(e)
    db.commit()
    
    # Add Attributes (x, y, degree)
    # Define Attributes
    attr_x = models.NodeAttribute(network_id=network.id, attribute_name="x", data_type="float")
    attr_y = models.NodeAttribute(network_id=network.id, attribute_name="y", data_type="float")
    attr_deg = models.NodeAttribute(network_id=network.id, attribute_name="degree", data_type="float")
    attr_custom = models.NodeAttribute(network_id=network.id, attribute_name="custom_score", data_type="float")
    db.add_all([attr_x, attr_y, attr_deg, attr_custom])
    db.commit()
    
    # Add Values
    for n in nodes:
        # Layout values
        db.add(models.NodeAttributeValue(node_id=n.id, attribute_id=attr_x.id, float_value=models.NodeFloatAttributeValue(float_value=10.0)))
        db.add(models.NodeAttributeValue(node_id=n.id, attribute_id=attr_y.id, float_value=models.NodeFloatAttributeValue(float_value=10.0)))
        # Metric values
        db.add(models.NodeAttributeValue(node_id=n.id, attribute_id=attr_deg.id, float_value=models.NodeFloatAttributeValue(float_value=2.0)))
        # Custom values (should be preserved)
        db.add(models.NodeAttributeValue(node_id=n.id, attribute_id=attr_custom.id, float_value=models.NodeFloatAttributeValue(float_value=99.0)))
    db.commit()
    
    # 2. Create Subgraph (Fresh View)
    node_ids = ["0", "1", "2"]
    result = subgraph.create_subgraph_from_nodes(network.id, node_ids, db, suffix="Fresh", preserve_layout=False)
    new_net_id = result["new_network_id"]
    
    # 3. Verify
    # Check attributes existence in new network
    new_attrs = db.query(models.NodeAttribute).filter(models.NodeAttribute.network_id == new_net_id).all()
    attr_names = [a.attribute_name for a in new_attrs]
    
    # 'degree' should be GONE
    assert "degree" not in attr_names
    
    # 'x', 'y' should be GONE (excluded)
    assert "x" not in attr_names
    assert "y" not in attr_names
    
    # 'spring_x', 'spring_y' should be PRESENT because calculating new layout adds them!
    assert "spring_x" in attr_names
    assert "spring_y" in attr_names
    assert "custom_score" in attr_names
    
    # Check values
    new_nodes = db.query(models.Node).filter(models.Node.network_id == new_net_id).all()
    
    # Get custom score - should be 99.0
    custom_attr = next(a for a in new_attrs if a.attribute_name == "custom_score")
    val_custom = db.query(models.NodeFloatAttributeValue).join(models.NodeAttributeValue).filter(
        models.NodeAttributeValue.node_id == new_nodes[0].id,
        models.NodeAttributeValue.attribute_id == custom_attr.id
    ).first()
    assert val_custom.float_value == 99.0
    
    # Get spring_x - should verify it created values
    spring_x_attr = next(a for a in new_attrs if a.attribute_name == "spring_x")
    val_sx = db.query(models.NodeFloatAttributeValue).join(models.NodeAttributeValue).filter(
        models.NodeAttributeValue.node_id == new_nodes[0].id,
        models.NodeAttributeValue.attribute_id == spring_x_attr.id
    ).first()
    
    assert val_sx is not None
    assert isinstance(val_sx.float_value, float)

def test_subgraph_cutout_view(db: Session):
    """
    Test 'Cutout View' (preserve_layout=True):
    - Should KEEP 'x', 'y' from source.
    - Should exclude topological metrics (e.g. 'degree').
    """
    # 1. Setup Source Network
    network = models.Network(name="Source Cutout")
    db.add(network)
    db.commit()
    db.refresh(network)
    
    nodes = []
    for i in range(3):
        n = models.Node(network_id=network.id, node_id=str(i), label=str(i))
        db.add(n)
        nodes.append(n)
    db.commit()
    
    attr_x = models.NodeAttribute(network_id=network.id, attribute_name="x", data_type="float")
    attr_y = models.NodeAttribute(network_id=network.id, attribute_name="y", data_type="float")
    attr_deg = models.NodeAttribute(network_id=network.id, attribute_name="degree", data_type="float")
    db.add_all([attr_x, attr_y, attr_deg])
    db.commit()
    
    # Set explicit source positions
    source_pos = {
        "0": (1.0, 1.0),
        "1": (2.0, 2.0),
        "2": (3.0, 3.0)
    }
    
    for n in nodes:
        px, py = source_pos[n.node_id]
        db.add(models.NodeAttributeValue(node_id=n.id, attribute_id=attr_x.id, float_value=models.NodeFloatAttributeValue(float_value=px)))
        db.add(models.NodeAttributeValue(node_id=n.id, attribute_id=attr_y.id, float_value=models.NodeFloatAttributeValue(float_value=py)))
        db.add(models.NodeAttributeValue(node_id=n.id, attribute_id=attr_deg.id, float_value=models.NodeFloatAttributeValue(float_value=5.0)))
    db.commit()
    
    # 2. Create Subgraph (Cutout View)
    result = subgraph.create_subgraph_from_nodes(network.id, ["0", "1"], db, suffix="Cutout", preserve_layout=True)
    new_net_id = result["new_network_id"]
    
    # 3. Verify
    new_attrs = db.query(models.NodeAttribute).filter(models.NodeAttribute.network_id == new_net_id).all()
    attr_names = [a.attribute_name for a in new_attrs]
    
    # 'degree' should be GONE
    assert "degree" not in attr_names
    
    # 'x', 'y' should be PRESENT
    assert "x" in attr_names
    assert "y" in attr_names
    
    new_nodes = db.query(models.Node).filter(models.Node.network_id == new_net_id).all()
    node_map = {n.node_id: n for n in new_nodes}
    
    x_attr = next(a for a in new_attrs if a.attribute_name == "x")
    
    # Verify values match source exactly
    n0 = node_map["0"]
    val_x0 = db.query(models.NodeFloatAttributeValue).join(models.NodeAttributeValue).filter(
        models.NodeAttributeValue.node_id == n0.id,
        models.NodeAttributeValue.attribute_id == x_attr.id
    ).first()
    assert val_x0.float_value == 1.0 
    
