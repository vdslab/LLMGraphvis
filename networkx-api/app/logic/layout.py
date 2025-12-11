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
        
        # Improved ForceAtlas2 implementation
        # Constants
        k_gra = 0.5 # Gravity (Reduced from 1.0)
        k_r = 10.0 # Repulsion strength (standard factor)
        
        # Init positions
        # Use existing positions if available? No, random start is safer for now to avoid local minima
        pos = nx.spring_layout(G, iterations=0, seed=42) 
        
        # Convert to numpy
        nodes_list = list(G.nodes())
        n_node = len(nodes_list)
        node_idx = {n: i for i, n in enumerate(nodes_list)}
        
        pos_arr = np.array([pos[n] for n in nodes_list])
        
        # Degrees for repulsion weighting
        # ForceAtlas2 uses (deg + 1)
        deg = np.array([G.degree(n) for n in nodes_list]) + 1
        
        # Edges indices
        edges_idx = []
        for u, v in G.edges():
            if u in node_idx and v in node_idx:
                edges_idx.append((node_idx[u], node_idx[v]))
        
        # Iterations
        iter_count = 300 if n_node < 500 else 100
        
        # Adaptive speed parameters
        speed = 1.0
        speed_efficiency = 1.0
        
        for i in range(iter_count):
            disp = np.zeros((n_node, 2))
            
            # 1. Repulsion (F_r = k_r * (deg_u * deg_v) / dist)
            # Vector = F_r * (delta / dist) = k_r * deg_prod * delta / dist^2
            
            # matrix of diffs
            delta = pos_arr[:, np.newaxis, :] - pos_arr[np.newaxis, :, :] # (N, N, 2)
            dist_sq = np.sum(delta**2, axis=2)
            
            # Avoid self-repulsion and div by zero
            # We add a small epsilon to dist_sq for stability
            np.fill_diagonal(dist_sq, 1.0) 
            dist = np.sqrt(dist_sq)
            
            # Force Magnitude: F = k_r * (deg_i * deg_j) / dist
            # We want Displacement Vector Contribution: F * (delta / dist) = F / dist * delta
            # So coeff = k_r * (deg_i * deg_j) / dist^2
            
            deg_matrix = deg[:, np.newaxis] * deg[np.newaxis, :]
            
            # Limit distance to avoid explosion
            dist_sq[dist_sq < 0.01] = 0.01
            
            # Repulsion coefficient
            coeff = (k_r * deg_matrix) / dist_sq
            
            # Apply Repulsion
            # disp += sum(coeff * delta)
            # We need to manually zero out diagonal contribution just in case
            np.fill_diagonal(coeff, 0)
            
            # Sum over columns (j)
            # shape of coeff: (N, N). shape of delta: (N, N, 2).
            # result (N, 2)
            disp += np.sum(delta * coeff[:, :, np.newaxis], axis=1)

            # 2. Attraction (Edges) (F_a = dist)
            # Vector = F_a * (delta / dist) = dist * delta / dist = delta
            # or F_a = dist (LinLog/Noack) vs F_a = dist^2? 
            # FA2 uses linear attraction: F = dist.
            # So displacement towards neighbor is just vector to neighbor?
            # Wait, classic spring layout is F=dist (Hooke's law).
            # FA2 attraction is F(d) = d. Direction is towards neighbor.
            
            for u_i, v_i in edges_idx:
                # Vector from v to u
                d_vec = pos_arr[u_i] - pos_arr[v_i] 
                # Attract v towards u, u towards v
                # F vector on u: - d_vec
                # F vector on v: d_vec
                
                # Apply weight 1.0
                disp[u_i] -= d_vec
                disp[v_i] += d_vec
            
            # 3. Gravity
            # Pull to center. Stronger for distant nodes.
            # Force = k_g * (deg + 1) * dist_to_center
            # This keeps disconnected components from flying away.
            # Using simple linear gravity without degree for stability for now.
            disp -= k_gra * pos_arr
            
            # 4. Update Positions with Speed
            # Simple global speed (simplified from FA2's local speed)
            length = np.linalg.norm(disp, axis=1)
            
            # Avoid large jumps
            max_disp = 100.0
            too_fast = length > max_disp
            if np.any(too_fast):
                scale = max_disp / length[too_fast]
                disp[too_fast] *= scale[:, np.newaxis]
            
            pos_arr += disp * (0.1 * speed)
            
            # Cooling (optional)
            # speed *= 0.99
            
        # Normalize to [-1, 1]
        if n_node > 0:
            min_vals = np.min(pos_arr, axis=0)
            max_vals = np.max(pos_arr, axis=0)
            range_vals = max_vals - min_vals
            
            # Center
            center = (max_vals + min_vals) / 2.0
            pos_arr = pos_arr - center
            
            # Scale
            max_range = np.max(range_vals)
            if max_range > 0:
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
    from sqlalchemy import text
    try:
        db.execute(
            text("UPDATE networks SET last_layout_name = :algo WHERE id = :nid"),
            {"algo": layout_name, "nid": network_id}
        )
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Warning: Failed to update last_layout_name: {e}")
        # non-critical, proceed
