import networkx as nx
import math
from sqlalchemy.orm import Session
from app import models
from .attributes import _get_or_create_attribute, _delete_attribute_values

def calculate_layout(network_id: int, layout_name: str, db: Session):
    # Reconstruct graph from DB
    G = nx.Graph()
    nodes = db.query(models.Node).filter(models.Node.network_id == network_id).all()
    
    id_map = {n.id: n.node_id for n in nodes} # db_id -> str_id
    node_map = {n.node_id: n.id for n in nodes} # str_id -> db_id
    
    for n in nodes:
        G.add_node(n.node_id)
        
    edges = db.query(models.Edge).filter(models.Edge.network_id == network_id).all()
    for e in edges:
        u = id_map.get(e.source_node_id)
        v = id_map.get(e.target_node_id)
        if u and v:
            G.add_edge(u, v)
    
    # Calculate Layout
    # Dynamic parameter adjustment based on network size
    num_nodes = len(G.nodes)
    
    if layout_name == "spring" or layout_name == "fruchterman_reingold":
        # Heuristic for k: 1/sqrt(N) is default. 
        # Increasing it to 2.5/sqrt(N) helps spread nodes out more significantly.
        k = 2.5 / math.sqrt(num_nodes) if num_nodes > 0 else None
        
        # Dynamic iterations: increased for smaller graphs for better convergence
        iterations = 100 if num_nodes < 500 else 50
        
        pos = nx.spring_layout(G, k=k, iterations=iterations, seed=42)
        
    elif layout_name == "forceatlas2":
        # Check for numeric libraries
        import numpy as np
        
        # Simple ForceAtlas2 implementation
        # Constants
        k_gra = 1.0 # Gravity
        # Repulsion
        k_r = 0.5 # Repulsion strength (scaling)
        
        # Scaling
        # To match FA2 typical spread, we need significant repulsion
        
        # Init positions
        pos = nx.spring_layout(G, iterations=0, seed=42) # Random start
        # Convert to numpy
        pos_arr = np.array([pos[n] for n in G.nodes()])
        nodes_list = list(G.nodes())
        node_idx = {n: i for i, n in enumerate(nodes_list)}
        
        # Edges indices
        edges_idx = []
        for u, v in G.edges():
            if u in node_idx and v in node_idx:
                edges_idx.append((node_idx[u], node_idx[v]))
        
        # Iterations
        n_node = len(nodes_list)
        iter_count = 100 if n_node < 500 else 50
        
        # Degrees for simplified logic (optional, standard FA2 uses degrees in repulsion)
        # Repulsion: F = kr * (deg+1)(deg+1)/dist
        deg = np.array([G.degree(n) for n in nodes_list]) + 1
        
        # Scaling adjustment based on size
        speed = 1.0
        
        for _ in range(iter_count):
            disp = np.zeros((n_node, 2))
            
            # Repulsion (N^2) - vectorized
            # matrix of diffs
            # x_diff[i, j] = x[i] - x[j]
            # using broadcasting
            delta = pos_arr[:, np.newaxis, :] - pos_arr[np.newaxis, :, :] # (N, N, 2)
            dist_sq = np.sum(delta**2, axis=2)
            dist_sq[dist_sq == 0] = 0.1 # Avoid div zero
            dist = np.sqrt(dist_sq)
            
            # Repulsion force magnitude: kr * (deg_i * deg_j) / dist
            # Direction: delta / dist
            # Force vector: (kr * deg_product / dist^2) * delta
            
            deg_matrix = deg[:, np.newaxis] * deg[np.newaxis, :]
            rep_force = (k_r * deg_matrix) / (dist_sq + 0.1) # Soften
            
            # Apply only rep (i != j is handled by delta being 0? No, dist=0.1)
            # if dist is small, rep is large.
            # Avoid self:
            np.fill_diagonal(rep_force, 0)
            
            # Compute displacement contribution
            # disp[i] += sum(rep_force[i,j] * delta[i,j] / dist[i,j])??
            # actually delta is vec from j to i implies pos[i]-pos[j].
            # Force on i from j is Repulsing, so direction is pos[i]-pos[j]. Correct.
            
            # We need to project rep_force along delta. 
            # delta is vector. rep_force is magnitude/dist??
            # Standard: Force = C / dist. Vector = Force * (delta/dist) = C * delta / dist^2.
            # My rep_force calculation above is roughly C/dist^2.
            
            # Sum over j
            disp += np.sum(delta * rep_force[:, :, np.newaxis], axis=1)

            # Attraction (Edges)
            # F = dist
            # Vector = - dist * (delta/dist) = - delta
            # or F = dist (linear attraction)
            # FA2 standard: F = dist.
            for u_i, v_i in edges_idx:
                d_vec = pos_arr[u_i] - pos_arr[v_i] # u -> v
                d_len = np.linalg.norm(d_vec)
                if d_len == 0: continue
                
                # Force on u towards v: - d_vec
                # But typically F = d implies simple spring.
                # Displacement = Force * speed?
                
                # Attraction strength 1.0
                attr_vec = -1.0 * d_vec 
                
                disp[u_i] += attr_vec
                disp[v_i] -= attr_vec # Action/Reaction
            
            # Gravity
            # Pull to center (0,0)
            # F = k_g * dist(u, 0)
            # Vector = - pos_arr
            disp -= k_gra * pos_arr
            
            # Apply
            # Limit max displacement for stability
            max_disp = 100.0
            length = np.linalg.norm(disp, axis=1)
            # If length > max_disp, scale down
            too_fast = length > max_disp
            if np.any(too_fast):
                disp[too_fast] = disp[too_fast] * (max_disp / length[too_fast][:, np.newaxis])
            
            pos_arr += disp * (0.1 * speed)
            
        # Normalize to [-1, 1]
        if n_node > 0:
            min_vals = np.min(pos_arr, axis=0)
            max_vals = np.max(pos_arr, axis=0)
            range_vals = max_vals - min_vals
            range_vals[range_vals == 0] = 1.0 # Avoid div zero
            
            # Center
            pos_arr = pos_arr - min_vals - (range_vals / 2.0)
            # Scale to [-1, 1] (so range becomes 2)
            max_range = np.max(range_vals)
            pos_arr = pos_arr * (2.0 / max_range)
        
        # update dict
        pos = {nodes_list[i]: pos_arr[i] for i in range(n_node)}

    elif layout_name == "circular" or layout_name == "circle":
        pos = nx.circular_layout(G)
        
    elif layout_name == "kamada_kawai":
        pos = nx.kamada_kawai_layout(G)
        
    elif layout_name == "shell":
        pos = nx.shell_layout(G)
        
    elif layout_name == "spectral":
        pos = nx.spectral_layout(G)
        
    elif layout_name == "spiral":
        pos = nx.spiral_layout(G)
        
    else:
        # Default fallback
        pos = nx.spring_layout(G, seed=42)
    
    # Save to DB - Bulk Update Strategy
    # 1. Ensure attributes exist
    attr_x = _get_or_create_attribute(network_id, f"{layout_name}_x", models.NodeAttribute, db, data_type="float")
    attr_y = _get_or_create_attribute(network_id, f"{layout_name}_y", models.NodeAttribute, db, data_type="float")
    
    # 2. Delete existing values for these attributes (Clean slate)
    _delete_attribute_values(network_id, attr_x.id, models.NodeAttributeValue, db)
    _delete_attribute_values(network_id, attr_y.id, models.NodeAttributeValue, db)
    
    # 3. Bulk Insert New Values
    nav_data = []
    for node_id in pos:
        db_node_id = node_map[node_id]
        nav_data.append({"node_id": db_node_id, "attribute_id": attr_x.id})
        nav_data.append({"node_id": db_node_id, "attribute_id": attr_y.id})
    
    if nav_data:
        db.bulk_insert_mappings(models.NodeAttributeValue, nav_data)
        db.commit()
        
        # Fetch back IDs
        all_navs = db.query(models.NodeAttributeValue).filter(
            models.NodeAttributeValue.attribute_id.in_([attr_x.id, attr_y.id]),
            models.NodeAttributeValue.node_id.in_(node_map.values())
        ).all()
        
        nav_map = {(nav.node_id, nav.attribute_id): nav.id for nav in all_navs}
        
        float_vals = []
        for node_id, (x, y) in pos.items():
            db_node_id = node_map[node_id]
            
            nav_x_id = nav_map.get((db_node_id, attr_x.id))
            if nav_x_id:
                float_vals.append({"node_attribute_value_id": nav_x_id, "float_value": float(x)})
                
            nav_y_id = nav_map.get((db_node_id, attr_y.id))
            if nav_y_id:
                float_vals.append({"node_attribute_value_id": nav_y_id, "float_value": float(y)})
        
        if float_vals:
            db.bulk_insert_mappings(models.NodeFloatAttributeValue, float_vals)
        db.commit()

    # 4. Update Network Record with last layout name
    network = db.query(models.Network).filter(models.Network.id == network_id).first()
    if network:
        network.last_layout_name = layout_name
        db.commit()
