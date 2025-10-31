-- Row-Level Security Policies for JuraGPT
-- Ensures users can only access their own documents

-- Enable RLS on all tables
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE query_logs ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own documents
CREATE POLICY "Users can view own documents"
ON documents
FOR SELECT
USING (auth.uid() = user_id);

-- Policy: Users can only insert their own documents
CREATE POLICY "Users can insert own documents"
ON documents
FOR INSERT
WITH CHECK (auth.uid() = user_id);

-- Policy: Users can only update their own documents
CREATE POLICY "Users can update own documents"
ON documents
FOR UPDATE
USING (auth.uid() = user_id);

-- Policy: Users can only delete their own documents
CREATE POLICY "Users can delete own documents"
ON documents
FOR DELETE
USING (auth.uid() = user_id);

-- Policy: Users can only see chunks from their documents
CREATE POLICY "Users can view chunks from own documents"
ON chunks
FOR SELECT
USING (
    EXISTS (
        SELECT 1 FROM documents
        WHERE documents.id = chunks.document_id
        AND documents.user_id = auth.uid()
    )
);

-- Policy: Users can only see query logs from their documents
CREATE POLICY "Users can view own query logs"
ON query_logs
FOR SELECT
USING (
    EXISTS (
        SELECT 1 FROM documents
        WHERE documents.id = query_logs.document_id
        AND documents.user_id = auth.uid()
    )
);

-- Create user_usage table for quota tracking
CREATE TABLE IF NOT EXISTS user_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    month TEXT NOT NULL,  -- YYYY-MM
    tokens_used INT DEFAULT 0,
    queries_count INT DEFAULT 0,
    documents_indexed INT DEFAULT 0,
    token_quota INT DEFAULT 100000,
    query_quota INT DEFAULT 1000,
    document_quota INT DEFAULT 100,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, month)
);

-- Enable RLS on user_usage
ALTER TABLE user_usage ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own usage
CREATE POLICY "Users can view own usage"
ON user_usage
FOR SELECT
USING (auth.uid() = user_id);

-- Create index for fast usage lookups
CREATE INDEX idx_user_usage_user_month ON user_usage(user_id, month);

-- Function to check if user is within quota
CREATE OR REPLACE FUNCTION check_user_quota(
    p_user_id UUID,
    p_quota_type TEXT,
    p_amount INT DEFAULT 1
)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
    current_month TEXT;
    current_usage INT;
    quota_limit INT;
BEGIN
    current_month := TO_CHAR(NOW(), 'YYYY-MM');

    -- Get or create usage record for current month
    INSERT INTO user_usage (user_id, month)
    VALUES (p_user_id, current_month)
    ON CONFLICT (user_id, month) DO NOTHING;

    -- Check quota based on type
    IF p_quota_type = 'tokens' THEN
        SELECT tokens_used, token_quota INTO current_usage, quota_limit
        FROM user_usage
        WHERE user_id = p_user_id AND month = current_month;

    ELSIF p_quota_type = 'queries' THEN
        SELECT queries_count, query_quota INTO current_usage, quota_limit
        FROM user_usage
        WHERE user_id = p_user_id AND month = current_month;

    ELSIF p_quota_type = 'documents' THEN
        SELECT documents_indexed, document_quota INTO current_usage, quota_limit
        FROM user_usage
        WHERE user_id = p_user_id AND month = current_month;

    ELSE
        RETURN FALSE;
    END IF;

    RETURN (current_usage + p_amount) <= quota_limit;
END;
$$;

-- Function to increment usage
CREATE OR REPLACE FUNCTION increment_user_usage(
    p_user_id UUID,
    p_tokens INT DEFAULT 0,
    p_queries INT DEFAULT 0,
    p_documents INT DEFAULT 0
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    current_month TEXT;
BEGIN
    current_month := TO_CHAR(NOW(), 'YYYY-MM');

    INSERT INTO user_usage (user_id, month, tokens_used, queries_count, documents_indexed)
    VALUES (p_user_id, current_month, p_tokens, p_queries, p_documents)
    ON CONFLICT (user_id, month)
    DO UPDATE SET
        tokens_used = user_usage.tokens_used + p_tokens,
        queries_count = user_usage.queries_count + p_queries,
        documents_indexed = user_usage.documents_indexed + p_documents,
        updated_at = NOW();
END;
$$;

-- Comments
COMMENT ON TABLE user_usage IS 'Tracks user usage for quota enforcement';
COMMENT ON FUNCTION check_user_quota IS 'Check if user is within quota limits';
COMMENT ON FUNCTION increment_user_usage IS 'Increment user usage counters';
