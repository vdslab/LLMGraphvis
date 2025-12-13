
import networkx as nx
import io

graphml_content = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"  
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns
     http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <graph id="G" edgedefault="undirected">
    <desc>Network Description</desc>
    <node id="n0">
      <desc>Node n0 Description</desc>
      <data key="d0">green</data>
    </node>
    <node id="n1"/>
    <edge id="e0" source="n0" target="n1">
      <desc>Edge e0 Description</desc>
    </edge>
  </graph>
  <key id="d0" for="node" attr.name="color" attr.type="string">
    <default>yellow</default>
  </key>
</graphml>
"""

# Test with default read_graphml
G = nx.read_graphml(io.BytesIO(graphml_content.encode('utf-8')))

print("--- Network Attributes ---")
print(G.graph)

print("\n--- Node Attributes ---")
for n, d in G.nodes(data=True):
    print(f"Node {n}: {d}")

print("\n--- Edge Attributes ---")
for u, v, d in G.edges(data=True):
    print(f"Edge {u}-{v}: {d}")
