import networkx as nx
from sqlalchemy.orm import Session
from app import models
import io
import datetime
from typing import Dict, List, Any
from .attributes import _ensure_attributes

def parse_and_save_graphml(network_id: int, graphml_content: str, db: Session):
    # Parse GraphML
    try:
        # NetworkX expects bytes or file-like object
        if isinstance(graphml_content, str):
            graphml_content = graphml_content.encode('utf-8')
        
        G = nx.read_graphml(io.BytesIO(graphml_content))
    except Exception as e:
        raise ValueError(f"Failed to parse GraphML: {e}")

    # Ensure Network exists in DB
    network = db.query(models.Network).filter(models.Network.id == network_id).first()
    
    final_network_id = network_id
    
    if not network:
        # Should typically exist if called from Backend, but if not, create it
        network = models.Network(id=network_id, name=f"Network {network_id}", graphml_content=graphml_content.decode('utf-8') if isinstance(graphml_content, bytes) else graphml_content)
        db.add(network)
        db.commit()
    else:
        # Check if network already has data (nodes)
        existing_node_count = db.query(models.Node).filter(models.Node.network_id == network_id).count()
        if existing_node_count > 0:
            # COLLISION: Network exists and has data.
            # Create a NEW network instead of overwriting.
            new_network = models.Network(
                name=f"{network.name} (Uploaded {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})",
                graphml_content=graphml_content.decode('utf-8') if isinstance(graphml_content, bytes) else graphml_content
            )
            db.add(new_network)
            db.commit()
            db.refresh(new_network)
            final_network_id = new_network.id
            
            # Note: We do NOT delete the old data. We just switch to a new ID.
        else:
            # Network exists but is empty (e.g. created by Backend chat initialization).
            # Update the content.
            network.graphml_content = graphml_content.decode('utf-8') if isinstance(graphml_content, bytes) else graphml_content
            db.commit()

    network_id = final_network_id # Use the confirmed ID for all subsequent operations

    # --- 1. Bulk Insert Nodes ---
    nodes_data = []
    for node_id, data in G.nodes(data=True):
        nodes_data.append({
            "network_id": network_id,
            "node_id": str(node_id),
            "label": data.get('label', str(node_id))
        })
    
    if nodes_data:
        db.bulk_insert_mappings(models.Node, nodes_data)
        db.commit()

    # Build Node Map (node_id_str -> db_id)
    # We need this for edges and attributes
    db_nodes = db.query(models.Node).filter(models.Node.network_id == network_id).all()
    node_map = {n.node_id: n.id for n in db_nodes}

    # --- 2. Bulk Insert Edges ---
    edges_data = []
    for u, v, data in G.edges(data=True):
        if str(u) in node_map and str(v) in node_map:
            edges_data.append({
                "network_id": network_id,
                "edge_id": f"{u}-{v}",
                "source_node_id": node_map[str(u)],
                "target_node_id": node_map[str(v)],
                "weight": float(data.get('weight', 1.0))
            })
    
    if edges_data:
        db.bulk_insert_mappings(models.Edge, edges_data)
        db.commit()
    
    # Build Edge Map (edge_id_str -> db_id)
    db_edges = db.query(models.Edge).filter(models.Edge.network_id == network_id).all()
    edge_map = {e.edge_id: e.id for e in db_edges}

    # --- 3. Process Attributes ---
    
    # Infer Attribute Types
    node_attr_types = {}
    for _, data in G.nodes(data=True):
        for key, val in data.items():
            if key == 'label': continue
            if key not in node_attr_types:
                node_attr_types[key] = "float" # Assume float initially
            
            if node_attr_types[key] == "float":
                if not isinstance(val, (int, float)) or isinstance(val, bool):
                     node_attr_types[key] = "string"

    edge_attr_types = {}
    for _, _, data in G.edges(data=True):
        for key, val in data.items():
            if key == 'weight': continue
            if key not in edge_attr_types:
                edge_attr_types[key] = "float"
            
            if edge_attr_types[key] == "float":
                if not isinstance(val, (int, float)) or isinstance(val, bool):
                     edge_attr_types[key] = "string"

    # Ensure Attributes Exist
    node_attr_map = _ensure_attributes(network_id, node_attr_types, models.NodeAttribute, db)
    edge_attr_map = _ensure_attributes(network_id, edge_attr_types, models.EdgeAttribute, db)

    # --- 4. Bulk Insert Attribute Values ---
    
    # Prepare Node Attribute Values
    # Prepare data for NodeAttributeValue
    nav_data = []
    for node_id, data in G.nodes(data=True):
        db_node_id = node_map[str(node_id)]
        for key, value in data.items():
            if key == 'label': continue
            if key in node_attr_map:
                nav_data.append({
                    "node_id": db_node_id,
                    "attribute_id": node_attr_map[key]
                })
    
    if nav_data:
        db.bulk_insert_mappings(models.NodeAttributeValue, nav_data)
        db.commit()
        
        # Fetch back to map (node_id, attr_id) -> nav_id
        all_navs = db.query(models.NodeAttributeValue).join(models.Node).filter(models.Node.network_id == network_id).all()
        nav_map = {(nav.node_id, nav.attribute_id): nav.id for nav in all_navs}
        
        # Prepare specific values
        node_float_vals = []
        node_text_vals = []
        for node_id, data in G.nodes(data=True):
            db_node_id = node_map[str(node_id)]
            for key, value in data.items():
                if key == 'label': continue
                if key in node_attr_map:
                    nav_id = nav_map.get((db_node_id, node_attr_map[key]))
                    if nav_id:
                        if isinstance(value, (int, float)):
                            node_float_vals.append({"node_attribute_value_id": nav_id, "float_value": float(value)})
                        else:
                            node_text_vals.append({"node_attribute_value_id": nav_id, "text_value": str(value)})

        if node_float_vals:
            db.bulk_insert_mappings(models.NodeFloatAttributeValue, node_float_vals)
        if node_text_vals:
            db.bulk_insert_mappings(models.NodeTextAttributeValue, node_text_vals)
        db.commit()

    # Prepare Edge Attribute Values
    eav_data = []
    for u, v, data in G.edges(data=True):
        edge_id_str = f"{u}-{v}"
        if edge_id_str in edge_map:
            db_edge_id = edge_map[edge_id_str]
            for key, value in data.items():
                if key == 'weight': continue
                if key in edge_attr_map:
                    eav_data.append({
                        "edge_id": db_edge_id,
                        "attribute_id": edge_attr_map[key]
                    })

    if eav_data:
        db.bulk_insert_mappings(models.EdgeAttributeValue, eav_data)
        db.commit()
        
        all_eavs = db.query(models.EdgeAttributeValue).join(models.Edge).filter(models.Edge.network_id == network_id).all()
        eav_map = {(eav.edge_id, eav.attribute_id): eav.id for eav in all_eavs}
        
        edge_float_vals = []
        edge_text_vals = []
        
        for u, v, data in G.edges(data=True):
            edge_id_str = f"{u}-{v}"
            if edge_id_str in edge_map:
                db_edge_id = edge_map[edge_id_str]
                for key, value in data.items():
                    if key == 'weight': continue
                    if key in edge_attr_map:
                        eav_id = eav_map.get((db_edge_id, edge_attr_map[key]))
                        if eav_id:
                            if isinstance(value, (int, float)):
                                edge_float_vals.append({"edge_attribute_value_id": eav_id, "float_value": float(value)})
                            else:
                                edge_text_vals.append({"edge_attribute_value_id": eav_id, "text_value": str(value)})

        if edge_float_vals:
            db.bulk_insert_mappings(models.EdgeFloatAttributeValue, edge_float_vals)
        if edge_text_vals:
            db.bulk_insert_mappings(models.EdgeTextAttributeValue, edge_text_vals)
        db.commit()
    
    return final_network_id
