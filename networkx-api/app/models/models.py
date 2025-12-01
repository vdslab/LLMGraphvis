from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base

# Network model is needed here to establish relationships, even if Backend creates the record.
class Network(Base):
    __tablename__ = "networks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    nodes = relationship("Node", back_populates="network")
    edges = relationship("Edge", back_populates="network")
    node_attributes = relationship("NodeAttribute", back_populates="network")
    edge_attributes = relationship("EdgeAttribute", back_populates="network")

class Node(Base):
    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, index=True)
    network_id = Column(Integer, ForeignKey("networks.id"), nullable=False)
    node_id = Column(String, nullable=False)
    label = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    network = relationship("Network", back_populates="nodes")
    attribute_values = relationship("NodeAttributeValue", back_populates="node")
    
    __table_args__ = (UniqueConstraint('network_id', 'node_id', name='unique_network_node'),)

class Edge(Base):
    __tablename__ = "edges"

    id = Column(Integer, primary_key=True, index=True)
    network_id = Column(Integer, ForeignKey("networks.id"), nullable=False)
    edge_id = Column(String, nullable=False)
    source_node_id = Column(Integer, ForeignKey("nodes.id"), nullable=False)
    target_node_id = Column(Integer, ForeignKey("nodes.id"), nullable=False)
    weight = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    network = relationship("Network", back_populates="edges")
    attribute_values = relationship("EdgeAttributeValue", back_populates="edge")

    __table_args__ = (UniqueConstraint('network_id', 'edge_id', name='unique_network_edge'),)

class NodeAttribute(Base):
    __tablename__ = "node_attributes"

    id = Column(Integer, primary_key=True, index=True)
    network_id = Column(Integer, ForeignKey("networks.id"), nullable=False)
    attribute_name = Column(String, nullable=False)
    data_type = Column(String) # Expected type: "boolean", "int", "long", "float", "double", "string"
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    network = relationship("Network", back_populates="node_attributes")
    values = relationship("NodeAttributeValue", back_populates="attribute")

    __table_args__ = (UniqueConstraint('network_id', 'attribute_name', name='unique_network_node_attr'),)

class NodeAttributeValue(Base):
    __tablename__ = "node_attribute_values"

    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(Integer, ForeignKey("nodes.id"), nullable=False)
    attribute_id = Column(Integer, ForeignKey("node_attributes.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    node = relationship("Node", back_populates="attribute_values")
    attribute = relationship("NodeAttribute", back_populates="values")
    
    text_value = relationship("NodeTextAttributeValue", uselist=False, back_populates="parent")
    float_value = relationship("NodeFloatAttributeValue", uselist=False, back_populates="parent")

    __table_args__ = (UniqueConstraint('node_id', 'attribute_id', name='unique_node_attr_val'),)

class NodeTextAttributeValue(Base):
    __tablename__ = "node_text_attribute_values"
    
    node_attribute_value_id = Column(Integer, ForeignKey("node_attribute_values.id"), primary_key=True)
    text_value = Column(Text)
    
    parent = relationship("NodeAttributeValue", back_populates="text_value")

class NodeFloatAttributeValue(Base):
    __tablename__ = "node_float_attribute_values"
    
    node_attribute_value_id = Column(Integer, ForeignKey("node_attribute_values.id"), primary_key=True)
    float_value = Column(Float)
    
    parent = relationship("NodeAttributeValue", back_populates="float_value")

class EdgeAttribute(Base):
    __tablename__ = "edge_attributes"

    id = Column(Integer, primary_key=True, index=True)
    network_id = Column(Integer, ForeignKey("networks.id"), nullable=False)
    attribute_name = Column(String, nullable=False)
    data_type = Column(String) # Expected type: "boolean", "int", "long", "float", "double", "string"
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    network = relationship("Network", back_populates="edge_attributes")
    values = relationship("EdgeAttributeValue", back_populates="attribute")

    __table_args__ = (UniqueConstraint('network_id', 'attribute_name', name='unique_network_edge_attr'),)

class EdgeAttributeValue(Base):
    __tablename__ = "edge_attribute_values"

    id = Column(Integer, primary_key=True, index=True)
    edge_id = Column(Integer, ForeignKey("edges.id"), nullable=False)
    attribute_id = Column(Integer, ForeignKey("edge_attributes.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    edge = relationship("Edge", back_populates="attribute_values")
    attribute = relationship("EdgeAttribute", back_populates="values")

    text_value = relationship("EdgeTextAttributeValue", uselist=False, back_populates="parent")
    float_value = relationship("EdgeFloatAttributeValue", uselist=False, back_populates="parent")

    __table_args__ = (UniqueConstraint('edge_id', 'attribute_id', name='unique_edge_attr_val'),)

class EdgeTextAttributeValue(Base):
    __tablename__ = "edge_text_attribute_values"
    
    edge_attribute_value_id = Column(Integer, ForeignKey("edge_attribute_values.id"), primary_key=True)
    text_value = Column(Text)
    
    parent = relationship("EdgeAttributeValue", back_populates="text_value")

class EdgeFloatAttributeValue(Base):
    __tablename__ = "edge_float_attribute_values"
    
    edge_attribute_value_id = Column(Integer, ForeignKey("edge_attribute_values.id"), primary_key=True)
    float_value = Column(Float)
    
    parent = relationship("EdgeAttributeValue", back_populates="float_value")
