-- Create the users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR UNIQUE NOT NULL,
    hashed_password VARCHAR NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Create the conversations table
CREATE TABLE IF NOT EXISTS conversations (
    id SERIAL PRIMARY KEY,
    title VARCHAR DEFAULT 'New Conversation',
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Create the chat_messages table
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    role VARCHAR NOT NULL,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
    meta_data TEXT DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_chat_messages_conversation_id ON chat_messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id ON chat_messages(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);

-- Create the networks table
CREATE TABLE IF NOT EXISTS networks (
    id SERIAL PRIMARY KEY,
    name VARCHAR DEFAULT 'Untitled Network',
    conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE UNIQUE,
    graphml_content TEXT NOT NULL,
    layout_cache TEXT DEFAULT '{}',
    centrality_cache TEXT DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_networks_conversation_id ON networks(conversation_id);
