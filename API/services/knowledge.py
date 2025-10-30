"""
This module provides knowledge base information about network visualization.

It includes functions that return detailed information about network layouts,
centrality metrics, and other concepts related to network analysis.
"""

def get_network_visualization_knowledge() -> str:
    """
    Returns a string containing a knowledge base on network visualization.

    Returns:
        A string with detailed information about network visualization concepts.
    """
    return """
# Network Visualization Knowledge

## Network Layouts

Different layout algorithms position nodes in a network visualization to highlight different aspects of the network structure:

1. **Spring Layout (Force-Directed)**
   - Uses a physical simulation of forces to position nodes
   - Nodes repel each other, while edges act as springs
   - Good for general-purpose visualization
   - Tends to place connected nodes closer together
   - Example: `spring_layout` in NetworkX

2. **Circular Layout**
   - Arranges nodes in a circle
   - Simple and clean visualization
   - Good for showing cycles or ring structures
   - Example: `circular_layout` in NetworkX

3. **Random Layout**
   - Places nodes randomly
   - Useful as a starting point for other layouts
   - Example: `random_layout` in NetworkX

4. **Spectral Layout**
   - Uses the eigenvectors of the graph Laplacian
   - Tends to place nodes with similar connections close together
   - Good for revealing community structure
   - Example: `spectral_layout` in NetworkX

5. **Shell Layout**
   - Arranges nodes in concentric circles
   - Good for hierarchical networks
   - Example: `shell_layout` in NetworkX

6. **Kamada-Kawai Layout**
   - Force-directed layout based on energy minimization
   - Often produces aesthetically pleasing layouts
   - Good for medium-sized networks
   - Example: `kamada_kawai_layout` in NetworkX

7. **Fruchterman-Reingold Layout**
   - Another force-directed layout
   - Tends to produce more evenly distributed nodes
   - Good for showing overall structure
   - Example: `fruchterman_reingold_layout` in NetworkX

8. **Bipartite Layout**
   - Specialized layout for bipartite networks
   - Places nodes in two parallel lines
   - Example: Custom implementation based on bipartite sets

9. **Community Layout**
   - Arranges nodes based on community detection
   - Nodes in the same community are placed closer together
   - Good for visualizing group structures
   - Example: Custom implementation using community detection algorithms

## Centrality Metrics

Centrality metrics measure the importance of nodes in a network:

1. **Degree Centrality**
   - Measures the number of connections a node has
   - Simple and intuitive
   - Higher values indicate nodes with many connections
   - Example: `degree_centrality` in NetworkX

2. **Closeness Centrality**
   - Measures how close a node is to all other nodes
   - Based on shortest paths
   - Higher values indicate nodes that can quickly reach others
   - Example: `closeness_centrality` in NetworkX

3. **Betweenness Centrality**
   - Measures how often a node lies on shortest paths between other nodes
   - Identifies bridge nodes or bottlenecks
   - Higher values indicate nodes that control information flow
   - Example: `betweenness_centrality` in NetworkX

4. **Eigenvector Centrality**
   - Measures node importance based on the importance of its neighbors
   - Recursive definition: a node is important if it's connected to other important nodes
   - Higher values indicate nodes connected to other central nodes
   - Example: `eigenvector_centrality` in NetworkX

5. **PageRank**
   - Similar to eigenvector centrality but with random jumps
   - Originally developed for ranking web pages
   - Higher values indicate nodes with many connections to other important nodes
   - Example: `pagerank` in NetworkX

6. **Katz Centrality**
   - Similar to eigenvector centrality but with a baseline value
   - Works well for directed networks
   - Example: `katz_centrality` in NetworkX

## Visual Properties

Visual properties can be used to encode additional information in the network visualization:

1. **Node Size**
   - Can represent node importance, centrality, or other attributes
   - Larger nodes draw more attention
   - Example: Mapping node size to degree centrality

2. **Node Color**
   - Can represent node categories, communities, or attribute values
   - Effective for showing group membership
   - Example: Coloring nodes by community

3. **Edge Width**
   - Can represent edge weight, importance, or frequency
   - Thicker edges draw more attention
   - Example: Mapping edge width to edge weight

4. **Edge Color**
   - Can represent edge types, directions, or attributes
   - Useful for distinguishing different kinds of relationships
   - Example: Coloring edges by type

## Network Analysis

Network analysis techniques help understand the structure and properties of networks:

1. **Community Detection**
   - Identifies groups of nodes that are densely connected internally
   - Methods include Louvain, Girvan-Newman, and modularity optimization
   - Example: `community.best_partition` (Louvain method)

2. **Path Analysis**
   - Finds shortest paths between nodes
   - Useful for understanding information flow
   - Example: `nx.shortest_path` in NetworkX

3. **Connectivity Analysis**
   - Determines if the network is connected
   - Identifies connected components
   - Example: `nx.is_connected` and `nx.connected_components` in NetworkX

4. **Structural Analysis**
   - Identifies structural properties like density, diameter, and clustering coefficient
   - Provides insights into overall network characteristics
   - Example: `nx.density` and `nx.diameter` in NetworkX

## Visualization Recommendations

Recommendations for effective network visualization:

1. **For Small Networks (< 50 nodes)**
   - Force-directed layouts like Fruchterman-Reingold or Kamada-Kawai
   - Show all nodes and edges
   - Use node size and color to encode attributes

2. **For Medium Networks (50-500 nodes)**
   - Force-directed layouts with appropriate parameters
   - Consider filtering less important nodes or edges
   - Use community detection to organize the layout

3. **For Large Networks (> 500 nodes)**
   - Consider specialized layouts or clustering
   - Focus on important subgraphs
   - Use aggregation or summarization techniques

4. **For Hierarchical Networks**
   - Use shell layout or specialized hierarchical layouts
   - Emphasize parent-child relationships

5. **For Bipartite Networks**
   - Use bipartite layout
   - Clearly distinguish the two node sets

6. **For Community Structure**
   - Use community detection and community-based layout
   - Color nodes by community membership
"""

def get_layout_descriptions() -> dict:
    """
    Returns a dictionary of network layout algorithm descriptions.

    Returns:
        A dictionary where keys are layout names and values are their descriptions.
    """
    return {
        "spring": "Spring layout uses a physical simulation of forces to position nodes. Nodes repel each other, while edges act as springs. Good for general-purpose visualization and tends to place connected nodes closer together.",
        "circular": "Circular layout arranges nodes in a circle. It provides a simple and clean visualization, good for showing cycles or ring structures.",
        "random": "Random layout places nodes randomly. It's useful as a starting point for other layouts or for testing purposes.",
        "spectral": "Spectral layout uses the eigenvectors of the graph Laplacian. It tends to place nodes with similar connections close together and is good for revealing community structure.",
        "shell": "Shell layout arranges nodes in concentric circles. It's good for hierarchical networks or showing layers of connectivity.",
        "kamada_kawai": "Kamada-Kawai layout is a force-directed layout based on energy minimization. It often produces aesthetically pleasing layouts and is good for medium-sized networks.",
        "fruchterman_reingold": "Fruchterman-Reingold layout is a force-directed layout that tends to produce more evenly distributed nodes. It's good for showing overall structure.",
        "bipartite": "Bipartite layout is specialized for bipartite networks. It places nodes in two parallel lines, clearly showing the two distinct sets of nodes.",
        "multipartite": "Multipartite layout arranges nodes in multiple parallel lines based on their partition. It's useful for networks with multiple distinct groups.",
        "planar": "Planar layout arranges nodes to minimize edge crossings. It's useful for networks that can be drawn on a plane without edge crossings.",
        "spiral": "Spiral layout arranges nodes in a spiral pattern. It can be useful for certain types of hierarchical or sequential data."
    }

def get_centrality_descriptions() -> dict:
    """
    Returns a dictionary of centrality metric descriptions.

    Returns:
        A dictionary where keys are centrality metric names and values are their
        descriptions.
    """
    return {
        "degree": "Degree centrality measures the number of connections a node has. It's simple and intuitive, with higher values indicating nodes with many connections.",
        "closeness": "Closeness centrality measures how close a node is to all other nodes. It's based on shortest paths, with higher values indicating nodes that can quickly reach others.",
        "betweenness": "Betweenness centrality measures how often a node lies on shortest paths between other nodes. It identifies bridge nodes or bottlenecks, with higher values indicating nodes that control information flow.",
        "eigenvector": "Eigenvector centrality measures node importance based on the importance of its neighbors. It's a recursive definition: a node is important if it's connected to other important nodes.",
        "pagerank": "PageRank is similar to eigenvector centrality but with random jumps. It was originally developed for ranking web pages, with higher values indicating nodes with many connections to other important nodes.",
        "katz": "Katz centrality is similar to eigenvector centrality but with a baseline value. It works well for directed networks.",
        "load": "Load centrality is similar to betweenness but counts all possible paths, not just shortest paths. It measures the load placed on nodes in the network.",
        "harmonic": "Harmonic centrality is a variant of closeness centrality that works well for disconnected graphs. It measures the average of the inverse shortest path lengths.",
        "subgraph": "Subgraph centrality measures the participation of a node in all subgraphs of the network. It counts closed walks starting and ending at the node.",
        "clustering": "Clustering coefficient measures the degree to which nodes in a graph tend to cluster together. It quantifies how close a node's neighbors are to being a complete graph."
    }
