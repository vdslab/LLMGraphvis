from sqlalchemy.orm import Session
from typing import Dict, Any, List, Set, Tuple, Optional
from app import models
from app.logic.common_utils import calculate_smart_node_size, calculate_smart_edge_width
from app.logic.style_service import StyleService

class VisualizationBuilder:
    def __init__(
        self,
        network_id: int,
        db: Session,
        layout_name: str = "forceatlas2",
        node_size_config: Optional[Dict] = None,
        node_color_config: Optional[Dict] = None,
        edge_width_config: Optional[Dict] = None,
        edge_color_config: Optional[Dict] = None,
        focus_network_id: Optional[int] = None,
        context_config: Optional[Dict] = None,
        focus_config: Optional[Dict] = None,
        custom_node_colors: Optional[List[Dict]] = None,
        node_label_config: Optional[Dict] = None
    ):
        self.network_id = network_id
        self.db = db
        self.layout_name = layout_name
        self.node_size_config = node_size_config
        self.node_color_config = node_color_config
        self.edge_width_config = edge_width_config
        self.edge_color_config = edge_color_config
        self.focus_network_id = focus_network_id
        self.context_config = context_config
        self.focus_config = focus_config
        self.custom_node_colors = custom_node_colors
        self.node_label_config = node_label_config

        # State to be populated
        self.network = None
        self.global_node_attr_map = {}
        self.global_node_values = {}
        self.edge_attr_map = {}
        self.edge_values = {}
        self.focus_node_map = {}
        self.focus_node_attr_map = {}
        self.focus_node_values = {}
        
        # Stats & Maps
        self.node_size_stats = (False, 0, 0)
        self.node_color_stats = (False, 0, 0)
        self.edge_width_stats = (False, 0, 0)
        self.edge_color_stats = (False, 0, 0)
        self.focus_node_size_stats = (None, 0, 0)
        self.focus_node_color_stats = (None, 0, 0)
        
        self.ranking_color_map = {}
        self.categorical_color_map = {}
        self.custom_color_map = {}
        
        self.layout_x_attr = ""
        self.layout_y_attr = ""

    def validate_and_prepare(self):
        # 0. Resolve Network
        self.network = self.db.query(models.Network).filter(models.Network.id == self.network_id).first()
        if not self.network:
            raise ValueError(f"Network {self.network_id} not found.")

        # Resolve Layout Name from DB if not provided
        if self.layout_name is None:
            self.layout_name = self.network.last_layout_name if self.network.last_layout_name else "forceatlas2"
        
        self.layout_x_attr = f"{self.layout_name}_x"
        self.layout_y_attr = f"{self.layout_name}_y"

        # Initialize Color Maps
        if self.custom_node_colors:
            for item in self.custom_node_colors:
                 if "node_id" in item and "color" in item:
                     self.custom_color_map[str(item["node_id"])] = item["color"]

    def fetch_data(self):
        # 1. Identify Attributes
        global_attrs_configs = [self.node_size_config, self.node_color_config, self.node_label_config]
        global_node_attrs = StyleService.collect_required_attributes(global_attrs_configs)
        
        # Layout attributes
        global_node_attrs.add(self.layout_x_attr)
        global_node_attrs.add(self.layout_y_attr)
        
        edge_attrs_configs = [self.edge_width_config, self.edge_color_config]
        required_edge_attrs = StyleService.collect_required_attributes(edge_attrs_configs)
        
        focus_node_attrs = set()
        if self.focus_config:
            focus_node_attrs = StyleService.collect_required_attributes([
                self.focus_config.get("node_size_config"),
                self.focus_config.get("node_color_config")
            ])

        # 2. Fetch Global Data
        self.global_node_attr_map, self.global_node_values = self._fetch_node_data(self.network_id, global_node_attrs)
        self.edge_attr_map, self.edge_values = self._fetch_edge_data(self.network_id, required_edge_attrs)
        
        # 2.5 Auto-Calculate Layout if Missing
        if self.layout_x_attr not in self.global_node_attr_map or self.layout_y_attr not in self.global_node_attr_map:
            from app.logic import layout
            layout.calculate_layout(self.network_id, self.layout_name, self.db)
            # Re-fetch
            self.global_node_attr_map, self.global_node_values = self._fetch_node_data(self.network_id, global_node_attrs)

        # 3. Fetch Focus Data
        if self.focus_network_id:
            self.focus_node_map = self._get_focus_node_map(self.focus_network_id)
            if focus_node_attrs:
                self.focus_node_attr_map, self.focus_node_values = self._fetch_node_data(self.focus_network_id, focus_node_attrs)

        # 4. Validations
        self._validate_attributes(global_node_attrs, required_edge_attrs, focus_node_attrs)

    def calculate_statistics(self):
        self.node_size_stats = StyleService.calculate_stats(self.node_size_config, self.global_node_attr_map, self.global_node_values)
        self.node_color_stats = StyleService.calculate_stats(self.node_color_config, self.global_node_attr_map, self.global_node_values)
        self.edge_width_stats = StyleService.calculate_stats(self.edge_width_config, self.edge_attr_map, self.edge_values)
        self.edge_color_stats = StyleService.calculate_stats(self.edge_color_config, self.edge_attr_map, self.edge_values)
        
        if self.focus_config:
            self.focus_node_size_stats = StyleService.calculate_stats(self.focus_config.get("node_size_config"), self.focus_node_attr_map, self.focus_node_values)
            self.focus_node_color_stats = StyleService.calculate_stats(self.focus_config.get("node_color_config"), self.focus_node_attr_map, self.focus_node_values)

        self.ranking_color_map = StyleService.prepare_ranking_map(self.node_color_config, self.global_node_attr_map, self.global_node_values)
        self.categorical_color_map = StyleService.prepare_categorical_map(self.node_color_config, self.global_node_attr_map, self.global_node_values)

    def build(self) -> Dict[str, List[Dict]]:
        vis_nodes = self._build_vis_nodes()
        vis_edges = self._build_vis_edges(vis_nodes)
        
        self._save_state()
        
        return {"nodes": vis_nodes, "links": vis_edges}

    def _build_vis_nodes(self) -> List[Dict]:
        nodes = self.db.query(models.Node).filter(models.Node.network_id == self.network_id).all()
        smart_defaults = calculate_smart_node_size(len(nodes))
        focus_node_ids_str = set(self.focus_node_map.keys())
        
        vis_nodes = []
        for n in nodes:
            is_focused = n.node_id in focus_node_ids_str
            
            if not is_focused and self.context_config and self.context_config.get("visible") is False:
                continue

            # Resolve Size & Color common logic
            size = StyleService.resolve_node_size(
                n.id, self.node_size_config, self.node_size_stats, 
                self.global_node_attr_map, self.global_node_values, smart_defaults
            )
            color = StyleService.resolve_node_color(
                n.id, str(n.node_id), self.node_color_config, self.node_color_stats,
                self.global_node_attr_map, self.global_node_values,
                self.ranking_color_map, self.categorical_color_map, self.custom_color_map
            )
            opacity = 1.0

            # Focus/Context Overrides
            if self.focus_network_id:
                if is_focused:
                    if self.focus_config:
                        focus_db_id = self.focus_node_map.get(n.node_id)
                        if focus_db_id:
                            f_size_conf = self.focus_config.get("node_size_config")
                            if f_size_conf:
                                size = StyleService.resolve_node_size(
                                    focus_db_id, f_size_conf, self.focus_node_size_stats,
                                    self.focus_node_attr_map, self.focus_node_values, smart_defaults
                                )
                            
                            f_color_conf = self.focus_config.get("node_color_config")
                            if f_color_conf:
                                if f_color_conf.get("static_color"):
                                    color = f_color_conf["static_color"]
                                else:
                                    color = StyleService.resolve_node_color(
                                        focus_db_id, str(n.node_id), f_color_conf, self.focus_node_color_stats,
                                        self.focus_node_attr_map, self.focus_node_values,
                                        {}, {}, {}, default_color=color
                                    )
                else:
                     if self.context_config:
                        opacity = self.context_config.get("opacity", 0.1)
                        if self.context_config.get("color"):
                            color = self.context_config["color"]
                        if self.context_config.get("size"):
                            size = self.context_config["size"]
                        elif not self.node_size_stats[0]:
                             size = smart_defaults["min"]

            # Layout
            x = StyleService.get_val(n.id, self.layout_x_attr, self.global_node_attr_map, self.global_node_values)
            y = StyleService.get_val(n.id, self.layout_y_attr, self.global_node_attr_map, self.global_node_values)
            if x is None: x = 0.5
            if y is None: y = 0.5
            
            # Label
            label = n.label
            if self.node_label_config and self.node_label_config.get("attribute"):
                val = StyleService.get_val(n.id, self.node_label_config["attribute"], self.global_node_attr_map, self.global_node_values)
                if val is not None:
                     label = str(val)
            if not label:
                label = n.node_id

            vis_nodes.append({
                "id": n.node_id,
                "label": label,
                "x": x,
                "y": y,
                "size": size, 
                "color": color,
                "opacity": opacity
            })
        return vis_nodes

    def _build_vis_edges(self, vis_nodes: List[Dict]) -> List[Dict]:
        edges = self.db.query(models.Edge).filter(models.Edge.network_id == self.network_id).all()
        smart_edge_defaults = calculate_smart_edge_width(len(edges))
        vis_edges = []
        
        visible_node_ids = {n["id"] for n in vis_nodes}
        focus_node_ids_str = set(self.focus_node_map.keys())
        
        # Optimize ID lookup
        node_id_map = {n.id: n.node_id for n in self.db.query(models.Node.id, models.Node.node_id).filter(models.Node.network_id == self.network_id).all()}

        for e in edges:
            source_node_id = node_id_map.get(e.source_node_id)
            target_node_id = node_id_map.get(e.target_node_id)
            
            if not source_node_id or not target_node_id:
                continue
            
            if source_node_id not in visible_node_ids or target_node_id not in visible_node_ids:
                continue
            
            is_focused = False
            if self.focus_network_id:
                is_focused = (source_node_id in focus_node_ids_str) and (target_node_id in focus_node_ids_str)

            if not is_focused and self.context_config and self.context_config.get("visible") is False:
                continue

            width = StyleService.resolve_edge_width(
                e.id, self.edge_width_config, self.edge_width_stats,
                self.edge_attr_map, self.edge_values, smart_edge_defaults
            )
            color = StyleService.resolve_edge_color(
                 e.id, self.edge_color_config, self.edge_color_stats,
                 self.edge_attr_map, self.edge_values
            )
            opacity = 1.0

            if self.focus_network_id and not is_focused:
                if self.context_config:
                    opacity = self.context_config.get("opacity", 0.1)
                    if self.context_config.get("color"):
                        color = self.context_config["color"]
            
            vis_edges.append({
                "source": source_node_id,
                "target": target_node_id,
                "width": width,
                "color": color,
                "opacity": opacity
            })

        return vis_edges

    def _save_state(self):
        if self.network:
            if self.layout_name:
                self.network.last_layout_name = self.layout_name
            if self.node_size_config is not None:
                self.network.last_node_size_config = self.node_size_config
            if self.node_color_config is not None:
                self.network.last_node_color_config = self.node_color_config
            if self.edge_width_config is not None:
                self.network.last_edge_width_config = self.edge_width_config
            if self.edge_color_config is not None:
                self.network.last_edge_color_config = self.edge_color_config
            if self.node_label_config is not None:
                self.network.last_node_label_config = self.node_label_config
            self.db.commit()

    # --- Helpers ---

    def _validate_attributes(self, node_attrs, edge_attrs, focus_node_attrs):
        missing_attrs = []
        for attr in node_attrs:
            if attr not in self.global_node_attr_map:
                missing_attrs.append(f"Node '{attr}'")
        for attr in edge_attrs:
            if attr not in self.edge_attr_map:
                missing_attrs.append(f"Edge '{attr}'")
        if self.focus_network_id and focus_node_attrs:
            for attr in focus_node_attrs:
                if attr not in self.focus_node_attr_map:
                    missing_attrs.append(f"Focus Node '{attr}'")
                    
        if missing_attrs:
            raise ValueError(f"Missing required attributes for visualization: {', '.join(missing_attrs)}. Please calculate them first.")

    def _fetch_node_data(self, net_id, attrs):
        if not attrs: return {}, {}
        defs = self.db.query(models.NodeAttribute).filter(
            models.NodeAttribute.network_id == net_id,
            models.NodeAttribute.attribute_name.in_(attrs)
        ).all()
        attr_map = {attr.attribute_name: attr.id for attr in defs}
        values = self._fetch_attribute_values(models.NodeAttributeValue, models.NodeFloatAttributeValue, models.NodeTextAttributeValue, list(attr_map.values()))
        return attr_map, values
        
    def _fetch_edge_data(self, net_id, attrs):
        if not attrs: return {}, {}
        defs = self.db.query(models.EdgeAttribute).filter(
            models.EdgeAttribute.network_id == net_id,
            models.EdgeAttribute.attribute_name.in_(attrs)
        ).all()
        attr_map = {attr.attribute_name: attr.id for attr in defs}
        values = self._fetch_attribute_values(models.EdgeAttributeValue, models.EdgeFloatAttributeValue, models.EdgeTextAttributeValue, list(attr_map.values()))
        return attr_map, values

    def _get_focus_node_map(self, focus_net_id):
        nodes = self.db.query(models.Node).filter(models.Node.network_id == focus_net_id).all()
        return {n.node_id: n.id for n in nodes}

    def _fetch_attribute_values(self, model_val, model_float, model_text, attr_ids):
        # Same logic as original
        if not attr_ids: return {}
        
        q_float = self.db.query(model_val.node_id if model_val == models.NodeAttributeValue else model_val.edge_id, model_val.attribute_id, model_float.float_value)\
            .join(model_float, model_val.id == model_float.node_attribute_value_id if model_val == models.NodeAttributeValue else model_val.id == model_float.edge_attribute_value_id)\
            .filter(model_val.attribute_id.in_(attr_ids)).all()

        q_text = self.db.query(model_val.node_id if model_val == models.NodeAttributeValue else model_val.edge_id, model_val.attribute_id, model_text.text_value)\
            .join(model_text, model_val.id == model_text.node_attribute_value_id if model_val == models.NodeAttributeValue else model_val.id == model_text.edge_attribute_value_id)\
            .filter(model_val.attribute_id.in_(attr_ids)).all()

        result = {}
        for entity_id, attr_id, val in q_float:
            if entity_id not in result: result[entity_id] = {}
            result[entity_id][attr_id] = val
            
        for entity_id, attr_id, val in q_text:
            if entity_id not in result: result[entity_id] = {}
            result[entity_id][attr_id] = val
        return result
