#!/bin/bash
# Real-time monitoring script for German laws ingestion pipeline

CHECKPOINT_DIR="data/checkpoints_gesetze"
RUN_ID="2025-10-29T23-01-01"
STATE_FILE="$CHECKPOINT_DIR/$RUN_ID/state.json"
LOG_FILE="logs/gesetze_timeout_protected_20251030_132350.log"

echo "=================================="
echo "German Laws Pipeline Monitor"
echo "=================================="
echo "Run ID: $RUN_ID"
echo ""

# Check if process is running
PROCESS=$(ps aux | grep "ingest_gesetze.py --resume" | grep -v grep)
if [ -z "$PROCESS" ]; then
    echo "⚠️  STATUS: Process NOT running"
else
    PID=$(echo "$PROCESS" | awk '{print $2}')
    CPU=$(echo "$PROCESS" | awk '{print $3}')
    MEM=$(echo "$PROCESS" | awk '{print $4}')
    TIME=$(echo "$PROCESS" | awk '{print $10}')
    echo "✅ STATUS: Running (PID: $PID)"
    echo "   CPU: ${CPU}% | MEM: ${MEM}% | Time: $TIME"
fi
echo ""

# Check checkpoint state
if [ -f "$STATE_FILE" ]; then
    DOCS_FETCHED=$(jq -r '.documents_fetched' "$STATE_FILE")
    CHUNKS_CREATED=$(jq -r '.chunks_created' "$STATE_FILE")
    VECTORS_UPLOADED=$(jq -r '.vectors_uploaded' "$STATE_FILE")
    STATUS=$(jq -r '.status' "$STATE_FILE")
    LAST_UPDATED=$(jq -r '.last_updated' "$STATE_FILE")

    echo "📊 PROGRESS:"
    echo "   Documents: $DOCS_FETCHED / 6593"
    echo "   Chunks: $CHUNKS_CREATED"
    echo "   Vectors: $VECTORS_UPLOADED"
    echo "   Status: $STATUS"
    echo ""

    # Calculate percentage
    if [ "$CHUNKS_CREATED" -gt 0 ]; then
        ESTIMATED_TOTAL=380000
        PERCENT=$((CHUNKS_CREATED * 100 / ESTIMATED_TOTAL))
        echo "   Progress: ${PERCENT}% (estimated)"
    fi

    echo ""
    echo "🕐 LAST ACTIVITY: $LAST_UPDATED"

    # Check time since last update
    LAST_EPOCH=$(date -d "$LAST_UPDATED" +%s 2>/dev/null || echo "0")
    NOW_EPOCH=$(date +%s)
    DIFF=$((NOW_EPOCH - LAST_EPOCH))

    if [ "$DIFF" -gt 1800 ]; then
        echo "   ⚠️  WARNING: No progress for $(($DIFF / 60)) minutes!"
    elif [ "$DIFF" -gt 0 ]; then
        echo "   ✓ Active (last update: $(($DIFF / 60)) min ago)"
    fi
else
    echo "❌ Checkpoint file not found: $STATE_FILE"
fi

echo ""

# Show latest log entries
if [ -f "$LOG_FILE" ]; then
    echo "📝 RECENT LOG (last 5 lines):"
    echo "---"
    tail -5 "$LOG_FILE"
else
    echo "❌ Log file not found: $LOG_FILE"
fi

echo ""
echo "=================================="
echo "Run: watch -n 60 ./scripts/monitor_gesetze_live.sh"
echo "=================================="
