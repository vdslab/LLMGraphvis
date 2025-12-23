
import pytest
from sqlalchemy.orm import Session
from app import models
from app.logic import subgraph, filter
from app.schemas.filter import AttributeCondition, Range

def create_source_network(db: Session, name="Source Network") -> models.Network:
    network = models.Network(name=name)
    db.add(network)
    db.commit()
    db.refresh(network)
    
    # Create attributes
    attr_group = models.NodeAttribute(network_id=network.id, attribute_name="group", data_type="string")
    attr_val = models.NodeAttribute(network_id=network.id, attribute_name="value", data_type="float")
    attr_x = models.NodeAttribute(network_id=network.id, attribute_name="x", data_type="float")
    attr_y = models.NodeAttribute(network_id=network.id, attribute_name="y", data_type="float")
    db.add_all([attr_group, attr_val, attr_x, attr_y])
    db.commit()
    
    # Create Topology:
    # Component 1: Star/Ego (0 is center, 1-4 connected to 0) => Radius 1 size 5
    # Component 2: Path (5-6-7-8)
    # Component 3: Clique (9, 10, 11, 12 connected to each other) => K-Core 3
    # Component 4: Single Node (13)
    
    nodes = []
    for i in range(14):
        node = models.Node(network_id=network.id, node_id=str(i), label=f"Node {i}")
        db.add(node)
        nodes.append(node)
    db.commit()
    
    edges = []
    # Star (0 center)
    for i in range(1, 5):
        edges.append((0, i))
    
    # Path (5-6-7-8)
    edges.extend([(5, 6), (6, 7), (7, 8)])
    
    # Clique (9-12)
    clique_nodes = [9, 10, 11, 12]
    for i in range(len(clique_nodes)):
        for j in range(i + 1, len(clique_nodes)):
            edges.append((clique_nodes[i], clique_nodes[j]))
            
    for u, v in edges:
        db.add(models.Edge(
            network_id=network.id,
            edge_id=f"{u}-{v}",
            source_node_id=nodes[u].id,
            target_node_id=nodes[v].id
        ))
    db.commit()
    
    # Add Attribute Values
    # Group A: 0-4 (Star)
    # Group B: 5-8 (Path)
    # Group C: 9-13 (Clique + Single)
    for i in range(14):
        group = "A" if i < 5 else ("B" if i < 9 else "C")
        val = float(i) * 10.0
        
        # Add group
        db.add(models.NodeAttributeValue(
            node_id=nodes[i].id, 
            attribute_id=attr_group.id,
            text_value=models.NodeTextAttributeValue(text_value=group)
        ))
        
        # Add value
        db.add(models.NodeAttributeValue(
            node_id=nodes[i].id, 
            attribute_id=attr_val.id,
            float_value=models.NodeFloatAttributeValue(float_value=val)
        ))
        
        # Add x, y (dummy)
        db.add(models.NodeAttributeValue(
            node_id=nodes[i].id, attribute_id=attr_x.id,
            float_value=models.NodeFloatAttributeValue(float_value=float(i))
        ))
        db.add(models.NodeAttributeValue(
            node_id=nodes[i].id, attribute_id=attr_y.id,
            float_value=models.NodeFloatAttributeValue(float_value=float(i))
        ))
        
    db.commit()
    return network

def verify_subgraph(db: Session, result: dict, expected_node_count: int, expected_description: str = None):
    new_net_id = result["new_network_id"]
    new_net = db.query(models.Network).filter(models.Network.id == new_net_id).first()
    assert new_net is not None
    
    # Check node count
    count = db.query(models.Node).filter(models.Node.network_id == new_net_id).count()
    assert count == expected_node_count
    
    # Check description
    if expected_description:
        assert new_net.description == expected_description
    else:
        assert new_net.description is not None # Should assume auto-generated one exists
        
    return new_net

def test_create_ego_network(db: Session):
    net = create_source_network(db)
    
    # Test 1: Radius 1 around 0 (Star center) -> Should be 0,1,2,3,4 (5 nodes)
    custom_desc = "My Ego Network"
    result = subgraph.create_ego_network(
        net.id, "0", radius=1, db=db, description=custom_desc
    )
    verify_subgraph(db, result, 5, custom_desc)
    
    # Test 2: Radius 0 -> Only center (1 node)
    result = subgraph.create_ego_network(
        net.id, "0", radius=0, db=db
    )
    verify_subgraph(db, result, 1)

def test_create_path_subgraph(db: Session):
    net = create_source_network(db)
    
    # Path from 5 to 8 (5-6-7-8) -> 4 nodes
    custom_desc = "My Path"
    result = subgraph.create_path_subgraph(
        net.id, "5", "8", db=db, description=custom_desc
    )
    verify_subgraph(db, result, 4, custom_desc)
    
    # No search path (disconnected) -> Should raise ValueError
    with pytest.raises(ValueError):
        subgraph.create_path_subgraph(net.id, "0", "5", db=db)

def test_create_k_core_subgraph(db: Session):
    net = create_source_network(db)
    
    # Clique (9,10,11,12) has degree 3 within itself.
    # Star (0-4): Center deg 4, loose ends deg 1.
    # Path (5-8): Interior deg 2, ends deg 1.
    
    # k=3 -> Should only get clique (4 nodes)
    custom_desc = "My 3-Core"
    result = subgraph.create_k_core_subgraph(
        net.id, k=3, db=db, description=custom_desc
    )
    verify_subgraph(db, result, 4, custom_desc)
    
    # k=2 -> Clique (4) + (0 and neighbors?) No, leaves are deg 1. Center is deg 4. 
    # K-core recursively removes nodes < k.
    # Star leaves (1,2,3,4) removed -> 0 becomes deg 0 -> 0 removed.
    # Path ends (5,8) removed -> 6,7 become deg 1 -> 6,7 removed.
    # Clique remains.
    # So k=2 result should also be clique (4 nodes).
    result = subgraph.create_k_core_subgraph(net.id, k=2, db=db)
    verify_subgraph(db, result, 4)
    
    # k=5 -> Empty -> ValueError
    with pytest.raises(ValueError):
        subgraph.create_k_core_subgraph(net.id, k=5, db=db)

def test_create_largest_component_subgraph(db: Session):
    net = create_source_network(db)
    
    # Star (5 nodes) is largest. 
    # Path (4 nodes). Clique (4 nodes). Single (1 node).
    
    custom_desc = "Largest Comp"
    result = subgraph.create_largest_component_subgraph(
        net.id, db=db, description=custom_desc
    )
    verify_subgraph(db, result, 5, custom_desc)

def test_create_component_containing_node(db: Session):
    net = create_source_network(db)
    
    # Node 6 is in Path component (5,6,7,8) -> 4 nodes
    custom_desc = "Component for 6"
    result = subgraph.create_component_containing_node(
        net.id, "6", db=db, description=custom_desc
    )
    verify_subgraph(db, result, 4, custom_desc)
    
    # Node 13 is single -> 1 node
    result = subgraph.create_component_containing_node(
        net.id, "13", db=db
    )
    verify_subgraph(db, result, 1)

def test_create_subgraph_by_filter(db: Session):
    net = create_source_network(db)
    
    # Group A (0-4) -> 5 nodes
    cond = AttributeCondition(
        attribute_name="group",
        categories=["A"]
    )
    custom_desc = "Filtered Group A"
    result = filter.create_subgraph_by_filter(
        net.id, [cond], suffix="FilterTest", db=db, description=custom_desc
    )
    verify_subgraph(db, result, 5, custom_desc)
    
    # Value > 85.0 (Nodes 9,10,11,12,13) -> 5 nodes
    cond_range = AttributeCondition(
        attribute_name="value",
        ranges=[Range(min=85.0)]
    )
    result = filter.create_subgraph_by_filter(
        net.id, [cond_range], suffix="FilterTest2", db=db
    )
    verify_subgraph(db, result, 5)
    
    # AND Condition: Group C AND Value > 125.0 (Node 13 only, val=130)
    cond_c = AttributeCondition(attribute_name="group", categories=["C"])
    cond_val = AttributeCondition(attribute_name="value", ranges=[Range(min=125.0)])
    
    result = filter.create_subgraph_by_filter(
        net.id, [cond_c, cond_val], suffix="FilterTest3", db=db
    )
    verify_subgraph(db, result, 1)
