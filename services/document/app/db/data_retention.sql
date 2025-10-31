-- Data Retention Policies for GDPR Compliance
-- Article 5(1)(e): Data should not be kept longer than necessary
--
-- Default retention periods:
-- - Document chunks: 2 years (for re-indexing and retrieval)
-- - Query logs: 90 days (for audit trail)
-- - User usage: 13 months (current + 12 previous months)

-- Add TTL columns to chunks table
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE chunks ADD COLUMN IF NOT EXISTS retention_days INT DEFAULT 730;  -- 2 years

-- Add TTL columns to query_logs table
ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS retention_days INT DEFAULT 90;  -- 90 days

-- Function to set expiration on new records
CREATE OR REPLACE FUNCTION set_expiration()
RETURNS TRIGGER AS $$
BEGIN
    -- Set expires_at based on retention_days
    IF NEW.retention_days IS NOT NULL THEN
        NEW.expires_at := NOW() + (NEW.retention_days || ' days')::INTERVAL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers to auto-set expiration
DROP TRIGGER IF EXISTS chunks_set_expiration ON chunks;
CREATE TRIGGER chunks_set_expiration
    BEFORE INSERT ON chunks
    FOR EACH ROW
    EXECUTE FUNCTION set_expiration();

DROP TRIGGER IF EXISTS query_logs_set_expiration ON query_logs;
CREATE TRIGGER query_logs_set_expiration
    BEFORE INSERT ON query_logs
    FOR EACH ROW
    EXECUTE FUNCTION set_expiration();

-- Function to purge expired data
CREATE OR REPLACE FUNCTION purge_expired_data()
RETURNS TABLE(
    chunks_deleted INT,
    logs_deleted INT,
    old_usage_deleted INT
) AS $$
DECLARE
    chunks_count INT;
    logs_count INT;
    usage_count INT;
    cutoff_month TEXT;
BEGIN
    -- Purge expired chunks
    DELETE FROM chunks
    WHERE expires_at IS NOT NULL
      AND expires_at < NOW()
    RETURNING * INTO chunks_count;
    chunks_count := COALESCE(chunks_count, 0);

    -- Purge expired query logs
    DELETE FROM query_logs
    WHERE expires_at IS NOT NULL
      AND expires_at < NOW()
    RETURNING * INTO logs_count;
    logs_count := COALESCE(logs_count, 0);

    -- Purge old user_usage records (keep last 13 months)
    cutoff_month := TO_CHAR(NOW() - INTERVAL '13 months', 'YYYY-MM');
    DELETE FROM user_usage
    WHERE month < cutoff_month
    RETURNING * INTO usage_count;
    usage_count := COALESCE(usage_count, 0);

    -- Return counts
    RETURN QUERY SELECT chunks_count, logs_count, usage_count;
END;
$$ LANGUAGE plpgsql;

-- Update existing records with expiration dates
UPDATE chunks
SET expires_at = created_at + (retention_days || ' days')::INTERVAL
WHERE expires_at IS NULL AND retention_days IS NOT NULL;

UPDATE query_logs
SET expires_at = created_at + (retention_days || ' days')::INTERVAL
WHERE expires_at IS NULL AND retention_days IS NOT NULL;

-- Create index for efficient purging
CREATE INDEX IF NOT EXISTS idx_chunks_expires_at ON chunks(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_query_logs_expires_at ON query_logs(expires_at) WHERE expires_at IS NOT NULL;

-- Comments
COMMENT ON COLUMN chunks.expires_at IS 'Automatic deletion date for GDPR compliance (2 years default)';
COMMENT ON COLUMN query_logs.expires_at IS 'Automatic deletion date for GDPR compliance (90 days default)';
COMMENT ON FUNCTION purge_expired_data IS 'Purge expired data according to retention policies';

-- Grant execute permission
GRANT EXECUTE ON FUNCTION purge_expired_data() TO authenticated;
