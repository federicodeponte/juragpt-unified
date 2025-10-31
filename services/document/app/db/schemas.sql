-- JuraGPT Database Schema
-- PostgreSQL with pgvector extension for Supabase

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Documents table (metadata storage)
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    filename TEXT NOT NULL,
    doc_hash TEXT UNIQUE NOT NULL,
    file_size_bytes BIGINT,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    version INT DEFAULT 1,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted'))
);

CREATE INDEX idx_documents_user_id ON documents(user_id);
CREATE INDEX idx_documents_doc_hash ON documents(doc_hash);
CREATE INDEX idx_documents_uploaded_at ON documents(uploaded_at DESC);

-- Chunks table (hierarchical document sections)
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    section_id TEXT NOT NULL,  -- e.g., "§5.2", "Absatz 3"
    parent_id UUID REFERENCES chunks(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    chunk_type TEXT CHECK (chunk_type IN ('section', 'clause', 'paragraph', 'subsection')),
    position INT NOT NULL,  -- Order in document
    metadata JSONB DEFAULT '{}',
    -- Embedding dimension MUST match app/core/retriever.py::Embedder.EXPECTED_DIMENSION
    -- Current: paraphrase-multilingual-mpnet-base-v2 (768 dimensions)
    -- If changing model, update with: ALTER TABLE chunks ALTER COLUMN embedding TYPE vector(NEW_DIM);
    embedding vector(768),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_chunks_document_id ON chunks(document_id);
CREATE INDEX idx_chunks_section_id ON chunks(section_id);
CREATE INDEX idx_chunks_parent_id ON chunks(parent_id);
CREATE INDEX idx_chunks_position ON chunks(document_id, position);

-- Vector similarity index (IVFFlat for fast approximate search)
CREATE INDEX idx_chunks_embedding ON chunks
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- Query logs (audit trail without PII)
CREATE TABLE query_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    query_hash TEXT NOT NULL,  -- SHA256 of original query
    response_hash TEXT,         -- SHA256 of response
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    latency_ms INT,
    tokens_used INT,
    model_version TEXT,
    citations_count INT,
    confidence_score FLOAT,
    error_message TEXT
);

CREATE INDEX idx_query_logs_document_id ON query_logs(document_id);
CREATE INDEX idx_query_logs_created_at ON query_logs(created_at DESC);

-- Function for vector similarity search with metadata filtering
CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding vector(768),
    doc_id UUID,
    match_threshold FLOAT DEFAULT 0.7,
    match_count INT DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    document_id UUID,
    section_id TEXT,
    parent_id UUID,
    content TEXT,
    chunk_type TEXT,
    position INT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        chunks.id,
        chunks.document_id,
        chunks.section_id,
        chunks.parent_id,
        chunks.content,
        chunks.chunk_type,
        chunks.position,
        chunks.metadata,
        1 - (chunks.embedding <=> query_embedding) AS similarity
    FROM chunks
    WHERE chunks.document_id = doc_id
        AND 1 - (chunks.embedding <=> query_embedding) > match_threshold
    ORDER BY chunks.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Function to get parent and sibling chunks
CREATE OR REPLACE FUNCTION get_context_chunks(
    chunk_id UUID
)
RETURNS TABLE (
    id UUID,
    section_id TEXT,
    content TEXT,
    chunk_type TEXT,
    relation TEXT  -- 'target', 'parent', 'sibling'
)
LANGUAGE plpgsql
AS $$
DECLARE
    target_parent_id UUID;
BEGIN
    -- Get parent_id of target chunk
    SELECT parent_id INTO target_parent_id
    FROM chunks
    WHERE chunks.id = chunk_id;

    RETURN QUERY
    -- Target chunk
    SELECT chunks.id, chunks.section_id, chunks.content, chunks.chunk_type, 'target'::TEXT
    FROM chunks
    WHERE chunks.id = chunk_id

    UNION ALL

    -- Parent chunk
    SELECT chunks.id, chunks.section_id, chunks.content, chunks.chunk_type, 'parent'::TEXT
    FROM chunks
    WHERE chunks.id = target_parent_id AND target_parent_id IS NOT NULL

    UNION ALL

    -- Sibling chunks
    SELECT chunks.id, chunks.section_id, chunks.content, chunks.chunk_type, 'sibling'::TEXT
    FROM chunks
    WHERE chunks.parent_id = target_parent_id
        AND chunks.id != chunk_id
        AND target_parent_id IS NOT NULL
    ORDER BY position;
END;
$$;

-- Comments for documentation
COMMENT ON TABLE documents IS 'Metadata for uploaded legal documents';
COMMENT ON TABLE chunks IS 'Hierarchical sections of documents with vector embeddings';
COMMENT ON TABLE query_logs IS 'Audit trail of queries (PII-free, hashed)';
COMMENT ON FUNCTION match_chunks IS 'Vector similarity search with document filtering';
COMMENT ON FUNCTION get_context_chunks IS 'Retrieve target chunk with parent and siblings for hierarchical RAG';

-- ============================================================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================================================
-- Ensures users can only access their own data
-- Critical for multi-tenant security and GDPR compliance

-- Enable RLS on all tables
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE query_logs ENABLE ROW LEVEL SECURITY;

-- Documents policies
CREATE POLICY "Users can view their own documents"
    ON documents FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert their own documents"
    ON documents FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update their own documents"
    ON documents FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete their own documents"
    ON documents FOR DELETE
    USING (auth.uid() = user_id);

-- Service role bypass (for backend operations)
CREATE POLICY "Service role has full access to documents"
    ON documents FOR ALL
    USING (auth.jwt()->>'role' = 'service_role');

-- Chunks policies (inherit document ownership)
CREATE POLICY "Users can view chunks of their documents"
    ON chunks FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM documents
            WHERE documents.id = chunks.document_id
            AND documents.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert chunks for their documents"
    ON chunks FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM documents
            WHERE documents.id = chunks.document_id
            AND documents.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can update chunks of their documents"
    ON chunks FOR UPDATE
    USING (
        EXISTS (
            SELECT 1 FROM documents
            WHERE documents.id = chunks.document_id
            AND documents.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can delete chunks of their documents"
    ON chunks FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM documents
            WHERE documents.id = chunks.document_id
            AND documents.user_id = auth.uid()
        )
    );

-- Service role bypass for chunks
CREATE POLICY "Service role has full access to chunks"
    ON chunks FOR ALL
    USING (auth.jwt()->>'role' = 'service_role');

-- Query logs policies (inherit document ownership)
CREATE POLICY "Users can view query logs for their documents"
    ON query_logs FOR SELECT
    USING (
        document_id IS NULL OR
        EXISTS (
            SELECT 1 FROM documents
            WHERE documents.id = query_logs.document_id
            AND documents.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can insert query logs for their documents"
    ON query_logs FOR INSERT
    WITH CHECK (
        document_id IS NULL OR
        EXISTS (
            SELECT 1 FROM documents
            WHERE documents.id = query_logs.document_id
            AND documents.user_id = auth.uid()
        )
    );

-- Service role bypass for query logs
CREATE POLICY "Service role has full access to query logs"
    ON query_logs FOR ALL
    USING (auth.jwt()->>'role' = 'service_role');

-- Security comments
COMMENT ON POLICY "Users can view their own documents" ON documents IS 'RLS: Users can only see documents they uploaded';
COMMENT ON POLICY "Service role has full access to documents" ON documents IS 'RLS: Backend service can manage all documents';
COMMENT ON POLICY "Users can view chunks of their documents" ON chunks IS 'RLS: Users can only see chunks from their documents';
COMMENT ON POLICY "Service role has full access to chunks" ON chunks IS 'RLS: Backend service can manage all chunks';
COMMENT ON POLICY "Users can view query logs for their documents" ON query_logs IS 'RLS: Users can only see query logs for their documents';
