import sqlalchemy
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    # Bumped on password change; tokens carrying an older value are rejected,
    # which signs the user out everywhere else.
    token_version = Column(Integer, nullable=False, default=0, server_default="0")
    # The provider/model a chat uses when it has not pinned its own. Null falls
    # back to the LLM_PROVIDER / *_MODEL environment defaults.
    default_provider = Column(String, nullable=True)
    default_model = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    chats = relationship("Chat", back_populates="user")


class Network(Base):
    __tablename__ = "networks"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    description = Column(Text, nullable=True)
    is_directed = Column(Boolean, nullable=False, default=False, server_default="false")

    # Visual State Tracking
    last_layout_name = Column(String, nullable=True)
    last_node_size_config = Column(JSON, nullable=True)
    last_node_color_config = Column(JSON, nullable=True)
    last_edge_width_config = Column(JSON, nullable=True)
    last_edge_color_config = Column(JSON, nullable=True)
    last_node_label_config = Column(JSON, nullable=True)
    last_highlight_config = Column(JSON, nullable=True)


    parent_network_id = Column(Integer, ForeignKey("networks.id"), nullable=True, index=True)

    subgraphs = relationship("Network", back_populates="parent_network", cascade="all, delete-orphan")
    parent_network = relationship(
        "Network", remote_side=[id], back_populates="subgraphs"
    )

    chat = relationship("Chat", back_populates="network", uselist=False)
    
    # Graph Relationships
    nodes = relationship("Node", back_populates="network", cascade="all, delete-orphan")
    edges = relationship("Edge", back_populates="network", cascade="all, delete-orphan")
    node_attributes = relationship("NodeAttribute", back_populates="network", cascade="all, delete-orphan")
    edge_attributes = relationship("EdgeAttribute", back_populates="network", cascade="all, delete-orphan")


class Chat(Base):
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    network_id = Column(Integer, ForeignKey("networks.id"), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    visualization_state = Column(JSON, nullable=True)
    provider = Column(String, nullable=True)
    model = Column(String, nullable=True)
    # True once the user has renamed the chat themselves. Auto-naming (upload
    # filename, then the LLM-generated title) never touches a chat with this set.
    name_is_custom = Column(
        Boolean, nullable=False, server_default=sqlalchemy.text("false"), default=False
    )

    user = relationship("User", back_populates="chats")
    network = relationship("Network", back_populates="chat")
    messages = relationship("ChatMessage", back_populates="chat")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False, index=True)
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    meta_data = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    chat = relationship("Chat", back_populates="messages")
    tool_executions = relationship("ToolExecution", back_populates="message", cascade="all, delete-orphan")
    usage = relationship("LlmUsage", back_populates="message", uselist=False, cascade="all, delete-orphan")


class ToolExecution(Base):
    __tablename__ = "tool_executions"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=False, index=True)
    tool_name = Column(String, nullable=False)
    arguments = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    thought = Column(Text, nullable=True)
    status = Column(String, nullable=False)
    error = Column(Text, nullable=True)
    call_id = Column(String, nullable=True)
    thought_signature = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    message = relationship("ChatMessage", back_populates="tool_executions")


class Node(Base):
    __tablename__ = "nodes"

    id = Column(Integer, primary_key=True, index=True)
    network_id = Column(Integer, ForeignKey("networks.id"), nullable=False)
    node_id = Column(String, nullable=False)
    label = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    network = relationship("Network", back_populates="nodes")
    attribute_values = relationship("NodeAttributeValue", back_populates="node", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("network_id", "node_id", name="unique_network_node"),
    )


class Edge(Base):
    __tablename__ = "edges"

    id = Column(Integer, primary_key=True, index=True)
    network_id = Column(Integer, ForeignKey("networks.id"), nullable=False)
    edge_id = Column(String, nullable=False)
    source_node_id = Column(Integer, ForeignKey("nodes.id"), nullable=False, index=True)
    target_node_id = Column(Integer, ForeignKey("nodes.id"), nullable=False, index=True)
    weight = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    network = relationship("Network", back_populates="edges")
    attribute_values = relationship("EdgeAttributeValue", back_populates="edge", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("network_id", "edge_id", name="unique_network_edge"),
    )


class NodeAttribute(Base):
    __tablename__ = "node_attributes"

    id = Column(Integer, primary_key=True, index=True)
    network_id = Column(Integer, ForeignKey("networks.id"), nullable=False)
    attribute_name = Column(String, nullable=False)
    data_type = Column(
        String
    )  # Expected type: "boolean", "int", "long", "float", "double", "string"
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Derived-attribute / cache provenance metadata (populated by later stages)
    is_derived = Column(Boolean, nullable=False, server_default=sqlalchemy.sql.false())
    derived_from = Column(String, nullable=True)
    computation_params = Column(JSON, nullable=True)
    graph_state_hash = Column(String, nullable=True)
    computed_at = Column(DateTime(timezone=True), nullable=True)

    network = relationship("Network", back_populates="node_attributes")
    values = relationship("NodeAttributeValue", back_populates="attribute", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint(
            "network_id", "attribute_name", name="unique_network_node_attr"
        ),
    )


class NodeAttributeValue(Base):
    __tablename__ = "node_attribute_values"

    id = Column(Integer, primary_key=True, index=True)
    node_id = Column(Integer, ForeignKey("nodes.id"), nullable=False)
    attribute_id = Column(Integer, ForeignKey("node_attributes.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    node = relationship("Node", back_populates="attribute_values")
    attribute = relationship("NodeAttribute", back_populates="values")

    text_value = relationship(
        "NodeTextAttributeValue", uselist=False, back_populates="parent", cascade="all, delete-orphan"
    )
    float_value = relationship(
        "NodeFloatAttributeValue", uselist=False, back_populates="parent", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("node_id", "attribute_id", name="unique_node_attr_val"),
    )


class NodeTextAttributeValue(Base):
    __tablename__ = "node_text_attribute_values"

    node_attribute_value_id = Column(
        Integer, ForeignKey("node_attribute_values.id"), primary_key=True
    )
    text_value = Column(Text)

    parent = relationship("NodeAttributeValue", back_populates="text_value")


class NodeFloatAttributeValue(Base):
    __tablename__ = "node_float_attribute_values"

    node_attribute_value_id = Column(
        Integer, ForeignKey("node_attribute_values.id"), primary_key=True
    )
    float_value = Column(Float)

    parent = relationship("NodeAttributeValue", back_populates="float_value")


class EdgeAttribute(Base):
    __tablename__ = "edge_attributes"

    id = Column(Integer, primary_key=True, index=True)
    network_id = Column(Integer, ForeignKey("networks.id"), nullable=False)
    attribute_name = Column(String, nullable=False)
    data_type = Column(
        String
    )  # Expected type: "boolean", "int", "long", "float", "double", "string"
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Derived-attribute / cache provenance metadata (populated by later stages)
    is_derived = Column(Boolean, nullable=False, server_default=sqlalchemy.sql.false())
    derived_from = Column(String, nullable=True)
    computation_params = Column(JSON, nullable=True)
    graph_state_hash = Column(String, nullable=True)
    computed_at = Column(DateTime(timezone=True), nullable=True)

    network = relationship("Network", back_populates="edge_attributes")
    values = relationship("EdgeAttributeValue", back_populates="attribute", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint(
            "network_id", "attribute_name", name="unique_network_edge_attr"
        ),
    )


class EdgeAttributeValue(Base):
    __tablename__ = "edge_attribute_values"

    id = Column(Integer, primary_key=True, index=True)
    edge_id = Column(Integer, ForeignKey("edges.id"), nullable=False)
    attribute_id = Column(Integer, ForeignKey("edge_attributes.id"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    edge = relationship("Edge", back_populates="attribute_values")
    attribute = relationship("EdgeAttribute", back_populates="values")

    text_value = relationship(
        "EdgeTextAttributeValue", uselist=False, back_populates="parent", cascade="all, delete-orphan"
    )
    float_value = relationship(
        "EdgeFloatAttributeValue", uselist=False, back_populates="parent", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("edge_id", "attribute_id", name="unique_edge_attr_val"),
    )


class EdgeTextAttributeValue(Base):
    __tablename__ = "edge_text_attribute_values"

    edge_attribute_value_id = Column(
        Integer, ForeignKey("edge_attribute_values.id"), primary_key=True
    )
    text_value = Column(Text)

    parent = relationship("EdgeAttributeValue", back_populates="text_value")


class EdgeFloatAttributeValue(Base):
    __tablename__ = "edge_float_attribute_values"

    edge_attribute_value_id = Column(
        Integer, ForeignKey("edge_attribute_values.id"), primary_key=True
    )
    float_value = Column(Float)

    parent = relationship("EdgeAttributeValue", back_populates="float_value")


class LlmUsage(Base):
    """Tokens and estimated cost of one LLM task: an agent turn or a chat title.

    Counts follow `UsageData`'s normalized meaning (ADR 0025): input includes
    cache reads/writes, output includes reasoning. `calls` holds the same
    counts per generate() call, in order. `message_id` is null when the turn
    produced no stored message; `chat_id`/`user_id` keep such rows attributable.
    """

    __tablename__ = "llm_usages"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(Integer, ForeignKey("chat_messages.id"), nullable=True, unique=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    purpose = Column(String, nullable=False, default="agent_turn", server_default="agent_turn")
    provider = Column(String, nullable=False)  # "google" | "anthropic" | "openai" | "lmstudio"
    model = Column(String, nullable=False)               # e.g. "gemini-3.8-flash", "claude-opus-4-8"
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    cached_input_tokens = Column(Integer, nullable=False, default=0)
    cache_write_tokens = Column(Integer, nullable=False, default=0, server_default="0")
    reasoning_tokens = Column(Integer, nullable=False, default=0, server_default="0")
    iteration_count = Column(Integer, nullable=False, default=1)
    calls = Column(JSON, nullable=True)
    estimated_cost_usd = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    message = relationship("ChatMessage", back_populates="usage")


class AnalysisInput(Base):
    """One conversational input request with a durable submission state."""

    __tablename__ = "analysis_inputs"
    id = Column(String(36), primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    network_id = Column(Integer, ForeignKey("networks.id", ondelete="CASCADE"), nullable=False)
    specification = Column(JSON, nullable=False)
    status = Column(String, nullable=False, default="pending")
    answer = Column(JSON, nullable=True)
    # Tool names exposed to the model when it asked. Answering resumes the same
    # task in a new turn, so the turn's progressive-disclosure state is restored
    # from here rather than re-earned with another skill_load. See ADR 0014.
    activated_tools = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ParameterTuning(Base):
    """A re-runnable tool pipeline whose parameters are adjusted by words or a panel.

    The agent (`apply_parameter_tuning`) and the panel (`POST .../apply`) update
    the same row, so each sees what the other changed. See ADR 0016.
    """

    __tablename__ = "parameter_tunings"
    id = Column(String(36), primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    network_id = Column(Integer, ForeignKey("networks.id", ondelete="CASCADE"), nullable=False)
    # question and fields (with the schema description copied in).
    specification = Column(JSON, nullable=False)
    # [{tool, arguments}] in execution order: the effective arguments that ran.
    steps = Column(JSON, nullable=False)
    # field id ("tool.argument") -> value currently drawn on the canvas.
    values = Column(JSON, nullable=False)
    initial_values = Column(JSON, nullable=False)
    suggested_values = Column(JSON, nullable=False)
    history = Column(JSON, nullable=False, default=list)
    last_result = Column(JSON, nullable=True)
    status = Column(String, nullable=False, default="active")
    activated_tools = Column(JSON, nullable=True)
    last_applied_at = Column(DateTime(timezone=True), nullable=True)
    # The last time the agent was told about panel changes (TURN_START).
    reported_at = Column(DateTime(timezone=True), nullable=True)
    confirmed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
