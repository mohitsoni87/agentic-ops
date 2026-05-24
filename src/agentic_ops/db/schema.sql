-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Known error patterns with embeddings
CREATE TABLE IF NOT EXISTS known_errors (
    id SERIAL PRIMARY KEY,
    error_type VARCHAR(100),
    pattern TEXT NOT NULL,
    log_keywords TEXT[],
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Root causes linked to known errors
CREATE TABLE IF NOT EXISTS root_causes (
    id SERIAL PRIMARY KEY,
    known_error_id INTEGER REFERENCES known_errors(id),
    description TEXT NOT NULL,
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Solutions linked to root causes
CREATE TABLE IF NOT EXISTS solutions (
    id SERIAL PRIMARY KEY,
    root_cause_id INTEGER REFERENCES root_causes(id),
    title VARCHAR(255),
    description TEXT NOT NULL,
    steps JSONB,
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Incident log
CREATE TABLE IF NOT EXISTS incidents (
    id SERIAL PRIMARY KEY,
    pod_name VARCHAR(255),
    namespace VARCHAR(255),
    pod_logs TEXT,
    error_pattern TEXT,
    rca_summary TEXT,
    solution_summary TEXT,
    full_report TEXT,
    notification_sent BOOLEAN DEFAULT FALSE,
    slack_sent BOOLEAN DEFAULT FALSE,
    email_sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for vector similarity search
CREATE INDEX IF NOT EXISTS known_errors_embedding_idx ON known_errors USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS root_causes_embedding_idx ON root_causes USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS solutions_embedding_idx ON solutions USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
