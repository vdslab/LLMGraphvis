from sqlalchemy.orm import Session
from app import models
from typing import Dict, List, Any
from app.core.logging import get_logger

logger = get_logger(__name__)

class AttributeCopier:
    """
    Helper class to copy node and edge attributes from one network to another.
    """
    def __init__(self, db: Session):
        self.db = db

    def copy_attributes(self, source_network_id: int, new_network_id: int, node_map: Dict[int, int], edge_map: Dict[int, int]):
        """
        Copies both node and edge attributes definitions and values.
        """
        logger.info(f"Copying attributes from {source_network_id} to {new_network_id}")
        
        # Copy Node Attribute Definitions
        node_attr_id_map = self._copy_attribute_definitions(source_network_id, new_network_id, models.NodeAttribute)
        
        # Copy Edge Attribute Definitions
        edge_attr_id_map = self._copy_attribute_definitions(source_network_id, new_network_id, models.EdgeAttribute)
        
        # Copy Node Attribute Values
        self._copy_values(models.NodeAttributeValue, models.NodeFloatAttributeValue, models.NodeTextAttributeValue, 
                    node_map, node_attr_id_map, "node_id", "node_attribute_value_id")
                    
        # Copy Edge Attribute Values
        self._copy_values(models.EdgeAttributeValue, models.EdgeFloatAttributeValue, models.EdgeTextAttributeValue, 
                    edge_map, edge_attr_id_map, "edge_id", "edge_attribute_value_id")
        
        logger.info("Attribute copying complete.")

    def _copy_attribute_definitions(self, source_network_id: int, new_network_id: int, model_class) -> Dict[int, int]:
        """
        Copies attribute definitions for a given model (NodeAttribute or EdgeAttribute).
        Returns map of old_attr_id -> new_attr_id.
        """
        source_attrs = self.db.query(model_class).filter(model_class.network_id == source_network_id).all()
        attr_id_map = {}
        
        new_attrs_data = []
        for attr in source_attrs:
            new_attrs_data.append({
                "network_id": new_network_id,
                "attribute_name": attr.attribute_name,
                "data_type": attr.data_type
            })
            
        if new_attrs_data:
            self.db.bulk_insert_mappings(model_class, new_attrs_data)
            self.db.commit()
            
            new_attrs = self.db.query(model_class).filter(model_class.network_id == new_network_id).all()
            source_attr_map = {a.attribute_name: a.id for a in source_attrs}
            for new_attr in new_attrs:
                old_id = source_attr_map.get(new_attr.attribute_name)
                if old_id:
                    attr_id_map[old_id] = new_attr.id
                    
        return attr_id_map

    def _copy_values(self, model_val, model_float, model_text, id_map, attr_id_map, parent_col, val_parent_col):
        # Fetch old values
        old_ids = list(id_map.keys())
        old_attr_ids = list(attr_id_map.keys())
        
        if not old_ids or not old_attr_ids: return

        # Chunking might be needed for large datasets, but assuming reasonable size for now
        old_vals = self.db.query(model_val).filter(
            getattr(model_val, parent_col).in_(old_ids),
            model_val.attribute_id.in_(old_attr_ids)
        ).all()
        
        new_vals_data = []
        
        for val in old_vals:
            new_pk = id_map.get(getattr(val, parent_col))
            new_attr_id = attr_id_map.get(val.attribute_id)
            if new_pk and new_attr_id:
                new_vals_data.append({
                    parent_col: new_pk,
                    "attribute_id": new_attr_id
                })
        
        if new_vals_data:
            self.db.bulk_insert_mappings(model_val, new_vals_data)
            self.db.commit()
            
            # Fetch back to get IDs
            new_ids = list(id_map.values())
            new_attr_ids = list(attr_id_map.values())
            
            inserted_vals = self.db.query(model_val).filter(
                getattr(model_val, parent_col).in_(new_ids),
                model_val.attribute_id.in_(new_attr_ids)
            ).all()
            
            # Map (parent_id, attr_id) -> new_val_id
            val_map = {(getattr(v, parent_col), v.attribute_id): v.id for v in inserted_vals}
            
            # Now copy Float/Text values
            new_float_data = []
            new_text_data = []
            
            old_val_ids = [v.id for v in old_vals]
            
            old_floats = self.db.query(model_float).filter(getattr(model_float, val_parent_col).in_(old_val_ids)).all()
            old_texts = self.db.query(model_text).filter(getattr(model_text, val_parent_col).in_(old_val_ids)).all()
            
            float_map = {getattr(f, val_parent_col): f.float_value for f in old_floats}
            text_map = {getattr(t, val_parent_col): t.text_value for t in old_texts}
            
            for val in old_vals:
                new_pk = id_map.get(getattr(val, parent_col))
                new_attr_id = attr_id_map.get(val.attribute_id)
                if new_pk and new_attr_id:
                    new_val_id = val_map.get((new_pk, new_attr_id))
                    if new_val_id:
                        if val.id in float_map:
                            new_float_data.append({val_parent_col: new_val_id, "float_value": float_map[val.id]})
                        if val.id in text_map:
                            new_text_data.append({val_parent_col: new_val_id, "text_value": text_map[val.id]})
            
            if new_float_data:
                self.db.bulk_insert_mappings(model_float, new_float_data)
            if new_text_data:
                self.db.bulk_insert_mappings(model_text, new_text_data)
            self.db.commit()
