import networkx as nx
from sqlalchemy.orm import Session
from app import models
import io
import datetime
from typing import Dict, List, Any
from .attributes import _ensure_attributes

def parse_and_save_graphml(network_id: int, graphml_content: str, db: Session):
    from sqlalchemy.dialects.postgresql import insert
    
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
            # No content update needed for Network table anymore.
            pass

    network_id = final_network_id # Use the confirmed ID for all subsequent operations

    # --- 1. Bulk Insert Nodes with ID Return ---
    # We use chunks to avoid massive SQL statements
    CHUNK_SIZE = 5000
    node_map = {} # node_id_str -> db_id
    
    nodes_iter = list(G.nodes(data=True))
    total_nodes = len(nodes_iter)
    
    for i in range(0, total_nodes, CHUNK_SIZE):
        chunk = nodes_iter[i:i + CHUNK_SIZE]
        nodes_data = []
        for node_id, data in chunk:
            nodes_data.append({
                "network_id": network_id,
                "node_id": str(node_id),
                "label": data.get('label', str(node_id))
            })
        
        if nodes_data:
            stmt = insert(models.Node).values(nodes_data).returning(models.Node.node_id, models.Node.id)
            # No on_conflict needed as we are inserting into a fresh (or verified empty) network ID space
            result = db.execute(stmt)
            for row in result:
                node_map[row.node_id] = row.id
            db.commit()

    # --- 2. Bulk Insert Edges with ID Return ---
    edge_map = {} # edge_id_str -> db_id
    
    edges_iter = list(G.edges(data=True))
    total_edges = len(edges_iter)
    
    for i in range(0, total_edges, CHUNK_SIZE):
        chunk = edges_iter[i:i + CHUNK_SIZE]
        edges_data = []
        for u, v, data in chunk:
            if str(u) in node_map and str(v) in node_map:
                edges_data.append({
                    "network_id": network_id,
                    "edge_id": f"{u}-{v}",
                    "source_node_id": node_map[str(u)],
                    "target_node_id": node_map[str(v)],
                    "weight": float(data.get('weight', 1.0))
                })
        
        if edges_data:
            stmt = insert(models.Edge).values(edges_data).returning(models.Edge.edge_id, models.Edge.id)
            result = db.execute(stmt)
            for row in result:
                edge_map[row.edge_id] = row.id
            db.commit()

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
    
    # Optimize Attribute Value Insertion
    # We can also use chunks and avoid fetching all NAVs back if we can structure it right.
    # However, NAV insertion is a bit more complex (parent -> child).
    # For now, let's just chunk the standard flow but optimize the parent-child linking if possible.
    # Actually, returning IDs from NAV insert helps avoid re-fetching all NAVs.
    
    # Prepare data for NodeAttributeValue
    # We iterate nodes again.
    
    # Chunks for Attributes
    for i in range(0, total_nodes, CHUNK_SIZE):
        chunk = nodes_iter[i:i + CHUNK_SIZE]
        
        nav_data = [] # (node_id_str, attr_name, value) for processing
        
        # Prepare Batch 1: NodeAttributeValue parents
        batch_nav_inserts = []
        
        for node_id, data in chunk:
            db_node_id = node_map[str(node_id)]
            for key, value in data.items():
                if key == 'label': continue
                if key in node_attr_map:
                    batch_nav_inserts.append({
                        "node_id": db_node_id,
                        "attribute_id": node_attr_map[key]
                    })
                    nav_data.append((db_node_id, key, value))
        
        if batch_nav_inserts:
             # Insert Parents and get IDs
            stmt = insert(models.NodeAttributeValue).values(batch_nav_inserts).returning(models.NodeAttributeValue.id, models.NodeAttributeValue.node_id, models.NodeAttributeValue.attribute_id)
            result = db.execute(stmt)
            
            # Map (node_id, attr_id) -> nav_id
            local_nav_map = {}
            for row in result:
                local_nav_map[(row.node_id, row.attribute_id)] = row.id
            
            # Prepare Batch 2: Children (Float/Text)
            node_float_vals = []
            node_text_vals = []
            
            for db_node_id, key, value in nav_data:
                attr_id = node_attr_map[key]
                nav_id = local_nav_map.get((db_node_id, attr_id))
                
                if nav_id:
                     if isinstance(value, (int, float)):
                         node_float_vals.append({"node_attribute_value_id": nav_id, "float_value": float(value)})
                     else:
                         node_text_vals.append({"node_attribute_value_id": nav_id, "text_value": str(value)})
            
            if node_float_vals:
                db.execute(insert(models.NodeFloatAttributeValue).values(node_float_vals))
            if node_text_vals:
                db.execute(insert(models.NodeTextAttributeValue).values(node_text_vals))
            
            db.commit()

    # Edge Attributes
    for i in range(0, total_edges, CHUNK_SIZE):
        chunk = edges_iter[i:i + CHUNK_SIZE]
        
        eav_data = []
        batch_eav_inserts = []
        
        for u, v, data in chunk:
            edge_id_str = f"{u}-{v}"
            if edge_id_str in edge_map:
                db_edge_id = edge_map[edge_id_str]
                for key, value in data.items():
                    if key == 'weight': continue
                    if key in edge_attr_map:
                        batch_eav_inserts.append({
                            "edge_id": db_edge_id,
                            "attribute_id": edge_attr_map[key]
                        })
                        eav_data.append((db_edge_id, key, value))
        
        if batch_eav_inserts:
            stmt = insert(models.EdgeAttributeValue).values(batch_eav_inserts).returning(models.EdgeAttributeValue.id, models.EdgeAttributeValue.edge_id, models.EdgeAttributeValue.attribute_id)
            result = db.execute(stmt)
            
            local_eav_map = {}
            for row in result:
                local_eav_map[(row.edge_id, row.attribute_id)] = row.id
                
            edge_float_vals = []
            edge_text_vals = []
            
            for db_edge_id, key, value in eav_data:
                 attr_id = edge_attr_map[key]
                 eav_id = local_eav_map.get((db_edge_id, attr_id))
                 
                 if eav_id:
                     if isinstance(value, (int, float)):
                         edge_float_vals.append({"edge_attribute_value_id": eav_id, "float_value": float(value)})
                     else:
                         edge_text_vals.append({"edge_attribute_value_id": eav_id, "text_value": str(value)})

            if edge_float_vals:
                 db.execute(insert(models.EdgeFloatAttributeValue).values(edge_float_vals))
            if edge_text_vals:
                 db.execute(insert(models.EdgeTextAttributeValue).values(edge_text_vals))
            
            db.commit()
    
    return final_network_id
