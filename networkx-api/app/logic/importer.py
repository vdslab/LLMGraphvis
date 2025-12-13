import networkx as nx
from sqlalchemy.orm import Session
from app import models
import io
import datetime
import itertools
from typing import Dict, List, Any, Generator
import xml.etree.ElementTree as ET
from .attributes import _ensure_attributes

def chunked_iterable(iterable, size):
    """Yield chunks of size from iterable."""
    it = iter(iterable)
    while True:
        chunk = tuple(itertools.islice(it, size))
        if not chunk:
            break
        yield chunk

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

    # Extract descriptions manually using XML parsing
    network_desc = None
    node_descs = {} # node_id -> desc
    edge_descs = {} # (source, target) -> desc
    
    # Key descriptions: attr_name -> desc
    node_attr_descs = {}
    edge_attr_descs = {}

    try:
        root = ET.fromstring(graphml_content)
        
        # GraphML namespace handling
        ns_map = {'g': 'http://graphml.graphdrawing.org/xmlns'}
        
        # Helper to find with flexible namespace
        def find_desc(element):
            # Try with namespace
            d = element.find('g:desc', ns_map)
            if d is not None: return d.text
            # Try without namespace
            d = element.find('desc')
            if d is not None: return d.text
            return None

        # Parse Keys (Attribute Definitions)
        # Look for <key> at root level
        for key_elem in root.findall('g:key', ns_map) + root.findall('key'):
             attr_name = key_elem.get('attr.name')
             for_type = key_elem.get('for', 'all')
             desc = find_desc(key_elem)
             
             if attr_name and desc:
                 if for_type == 'node':
                     node_attr_descs[attr_name] = desc
                 elif for_type == 'edge':
                     edge_attr_descs[attr_name] = desc
                 elif for_type == 'all':
                     node_attr_descs[attr_name] = desc
                     edge_attr_descs[attr_name] = desc

        # Find Graph
        graph_elem = root.find('g:graph', ns_map)
        if graph_elem is None:
             graph_elem = root.find('graph')
        
        if graph_elem is not None:
            # Network Description
            network_desc = find_desc(graph_elem)
            
            # Node Descriptions
            for node in graph_elem.findall('g:node', ns_map) + graph_elem.findall('node'):
                nid = node.get('id')
                d = find_desc(node)
                if nid and d:
                    node_descs[nid] = d
            
            # Edge Descriptions
            for edge in graph_elem.findall('g:edge', ns_map) + graph_elem.findall('edge'):
                u = edge.get('source')
                v = edge.get('target')
                d = find_desc(edge)
                if u and v and d:
                    edge_descs[(u, v)] = d
                    
    except Exception as e:
        print(f"Warning: Failed to extract descriptions from GraphML: {e}")
        # Continue without descriptions

    # Use iterators directly to save memory
    nodes_iter = G.nodes(data=True)
    edges_iter = G.edges(data=True)

    # Note: G.number_of_nodes() is O(1) for NetworkX graphs
    total_nodes = G.number_of_nodes()
    total_edges = G.number_of_edges()

    node_attr_types = {}
    edge_attr_types = {}
    
    # Pre-register description attribute as string if we found any
    if node_descs:
        node_attr_types['description'] = 'string'
    if edge_descs:
        edge_attr_types['description'] = 'string'

    # Wrap writes in a single transaction to reduce commit overhead
    with db.begin():
        # Ensure Network exists in DB
        network = db.query(models.Network).filter(models.Network.id == network_id).first()
        
        final_network_id = network_id
        
        if not network:
            # Should typically exist if called from Backend, but if not, create it
            network = models.Network(id=network_id, name=f"Network {network_id}")
            db.add(network)
            db.flush()
        else:
            # Check if network already has data (nodes)
            existing_node_count = db.query(models.Node).filter(models.Node.network_id == network_id).count()
            if existing_node_count > 0:
                # COLLISION: Network exists and has data.
                # Create a NEW network instead of overwriting.
                new_network = models.Network(
                    name=f"{network.name} (Uploaded {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
                )
                db.add(new_network)
                db.flush()
                final_network_id = new_network.id
                
                # Note: We do NOT delete the old data. We just switch to a new ID.
            else:
                # Network exists but is empty (e.g. created by Backend chat initialization).
                # No content update needed for Network table anymore.
                pass
                
        # Update Network Description if found
        network_for_update = db.query(models.Network).filter(models.Network.id == final_network_id).first()
        if network_desc and network_for_update:
            network_for_update.description = network_desc

        network_id = final_network_id # Use the confirmed ID for all subsequent operations

        # --- 1. Bulk Insert Nodes with ID Return ---
        # We use chunks to avoid massive SQL statements
        CHUNK_SIZE = 5000
        node_map = {} # node_id_str -> db_id
        
        # Must restart iterator if we want to iterate twice? 
        # Actually, we need to iterate twice: once for nodes table, once for attributes.
        # But `nodes_iter` is an iterator from NetworkX view. It might be consumable or lightweight view.
        # G.nodes(data=True) returns a NodeDataView which is iterable multiple times.
        # However, to be safe and consistent with memory optimization, we should try to do single pass if possible?
        # No, we need db_ids for attributes. So we must insert nodes first.
        # NetworkX views are re-iterable.
        
        # 1st Pass: Nodes
        for chunk in chunked_iterable(G.nodes(data=True), CHUNK_SIZE):
            nodes_data = []
            for node_id, data in chunk:
                # Inject Description
                n_id_str = str(node_id)
                if n_id_str in node_descs:
                    data['description'] = node_descs[n_id_str]
                
                nodes_data.append({
                    "network_id": network_id,
                    "node_id": n_id_str,
                    "label": data.get('label', n_id_str)
                })

                # Track attribute type inference during the first pass to avoid extra scans
                for key, val in data.items():
                    if key == 'label':
                        continue
                    if key not in node_attr_types:
                        node_attr_types[key] = "float"
                    if node_attr_types[key] == "float":
                        if not isinstance(val, (int, float)) or isinstance(val, bool):
                            node_attr_types[key] = "string"
            
            if nodes_data:
                stmt = insert(models.Node).values(nodes_data).returning(models.Node.node_id, models.Node.id)
                # No on_conflict needed as we are inserting into a fresh (or verified empty) network ID space
                result = db.execute(stmt)
                for row in result:
                    node_map[row.node_id] = row.id

        # --- 2. Bulk Insert Edges with ID Return ---
        edge_map = {} # edge_id_str -> db_id
        
        for chunk in chunked_iterable(G.edges(data=True), CHUNK_SIZE):
            edges_data = []
            for u, v, data in chunk:
                u_str, v_str = str(u), str(v)
                
                # Inject Description
                # Try (u, v) and also (v, u) if undirected? 
                # NX read_graphml preserves direction if graph is directed.
                # If undirected, the XML source/target might match u/v or v/u.
                desc = edge_descs.get((u_str, v_str))
                if not desc and not G.is_directed():
                     desc = edge_descs.get((v_str, u_str))
                
                if desc:
                    data['description'] = desc

                if u_str in node_map and v_str in node_map:
                    edges_data.append({
                        "network_id": network_id,
                        "edge_id": f"{u}-{v}",
                        "source_node_id": node_map[u_str],
                        "target_node_id": node_map[v_str],
                        "weight": float(data.get('weight', 1.0))
                    })

                    for key, val in data.items():
                        if key == 'weight':
                            continue
                        if key not in edge_attr_types:
                            edge_attr_types[key] = "float"
                        if edge_attr_types[key] == "float":
                            if not isinstance(val, (int, float)) or isinstance(val, bool):
                                edge_attr_types[key] = "string"
            
            if edges_data:
                stmt = insert(models.Edge).values(edges_data).returning(models.Edge.edge_id, models.Edge.id)
                result = db.execute(stmt)
                for row in result:
                    edge_map[row.edge_id] = row.id

        # --- 3. Process Attributes ---
        node_attr_map = _ensure_attributes(
            network_id, node_attr_types, models.NodeAttribute, db, commit=False,
            descriptions=node_attr_descs
        )
        edge_attr_map = _ensure_attributes(
            network_id, edge_attr_types, models.EdgeAttribute, db, commit=False,
            descriptions=edge_attr_descs
        )

        # --- 3b. Bulk Insert Attribute Values ---
        
        # Prepare data for NodeAttributeValue
        # We iterate nodes again.
        
        # Chunks for Attributes
        for chunk in chunked_iterable(G.nodes(data=True), CHUNK_SIZE):
            
            nav_data = [] # (node_id_str, attr_name, value) for processing
            
            # Prepare Batch 1: NodeAttributeValue parents
            batch_nav_inserts = []
            
            for node_id, data in chunk:
                db_node_id = node_map.get(str(node_id))
                if not db_node_id: continue # Should not happen

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
                         if isinstance(value, (int, float)) and not isinstance(value, bool):
                             node_float_vals.append({"node_attribute_value_id": nav_id, "float_value": float(value)})
                         else:
                             node_text_vals.append({"node_attribute_value_id": nav_id, "text_value": str(value)})
                
                if node_float_vals:
                    db.execute(insert(models.NodeFloatAttributeValue).values(node_float_vals))
                if node_text_vals:
                    db.execute(insert(models.NodeTextAttributeValue).values(node_text_vals))

        # Edge Attributes
        for chunk in chunked_iterable(G.edges(data=True), CHUNK_SIZE):
            
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
                         if isinstance(value, (int, float)) and not isinstance(value, bool):
                             edge_float_vals.append({"edge_attribute_value_id": eav_id, "float_value": float(value)})
                         else:
                             edge_text_vals.append({"edge_attribute_value_id": eav_id, "text_value": str(value)})

                if edge_float_vals:
                     db.execute(insert(models.EdgeFloatAttributeValue).values(edge_float_vals))
                if edge_text_vals:
                     db.execute(insert(models.EdgeTextAttributeValue).values(edge_text_vals))
    
    return final_network_id
