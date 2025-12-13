
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, List, Any
import networkx as nx
import io

@dataclass
class ParsedGraphData:
    graph: nx.Graph
    network_message: Optional[str] = None
    node_messages: Dict[str, str] = field(default_factory=dict)
    edge_messages: Dict[Tuple[str, str], str] = field(default_factory=dict)
    node_attr_descriptions: Dict[str, str] = field(default_factory=dict)
    edge_attr_descriptions: Dict[str, str] = field(default_factory=dict)

class GraphMLParser:
    """
    Handles parsing of GraphML content to extract:
    1. NetworkX Graph object
    2. Description metadata (<desc> tags) for network, nodes, edges, and keys.
    """
    
    NS_MAP = {'g': 'http://graphml.graphdrawing.org/xmlns'}

    def parse(self, content: str) -> ParsedGraphData:
        """
        Parses raw GraphML string content.
        """
        if isinstance(content, str):
            content_bytes = content.encode('utf-8')
        else:
            content_bytes = content

        # 1. Parse into NetworkX Graph
        try:
            G = nx.read_graphml(io.BytesIO(content_bytes))
        except Exception as e:
            raise ValueError(f"Failed to parse GraphML structure: {e}")

        # 2. Extract Descriptions via XML
        try:
            root = ET.fromstring(content)
            return self._extract_metadata(root, G)
        except Exception as e:
            print(f"Warning: Failed to extract descriptions from GraphML XML: {e}")
            # Return graph without extra metadata if XML parsing fails but NX succeeded
            return ParsedGraphData(graph=G)

    def _extract_metadata(self, root: ET.Element, G: nx.Graph) -> ParsedGraphData:
        data = ParsedGraphData(graph=G)
        
        # Helper to find desc
        def find_desc(element):
            d = element.find('g:desc', self.NS_MAP)
            if d is not None: return d.text
            d = element.find('desc')
            if d is not None: return d.text
            return None

        # Parse Keys (Attribute Definitions)
        for key_elem in root.findall('g:key', self.NS_MAP) + root.findall('key'):
             attr_name = key_elem.get('attr.name')
             for_type = key_elem.get('for', 'all')
             desc = find_desc(key_elem)
             
             if attr_name and desc:
                 if for_type == 'node':
                     data.node_attr_descriptions[attr_name] = desc
                 elif for_type == 'edge':
                     data.edge_attr_descriptions[attr_name] = desc
                 elif for_type == 'all':
                     data.node_attr_descriptions[attr_name] = desc
                     data.edge_attr_descriptions[attr_name] = desc

        # Find Graph Element
        graph_elem = root.find('g:graph', self.NS_MAP)
        if graph_elem is None:
             graph_elem = root.find('graph')
        
        if graph_elem is not None:
            # Network Description
            data.network_message = find_desc(graph_elem)
            
            # Node Descriptions
            for node in graph_elem.findall('g:node', self.NS_MAP) + graph_elem.findall('node'):
                nid = node.get('id')
                d = find_desc(node)
                if nid and d:
                    data.node_messages[nid] = d
            
            # Edge Descriptions
            for edge in graph_elem.findall('g:edge', self.NS_MAP) + graph_elem.findall('edge'):
                u = edge.get('source')
                v = edge.get('target')
                d = find_desc(edge)
                if u and v and d:
                    data.edge_messages[(u, v)] = d
        
        return data
