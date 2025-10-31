#!/usr/bin/env bash
#
# ABOUTME: Manual corpus update wrapper with pre/post stats and cost estimates
# ABOUTME: Provides user-friendly interface for running incremental updates
#
# Manual Update Wrapper for JuraGPT Corpus
#
# Features:
# - Shows current corpus status before updating
# - Runs update with Modal GPU acceleration
# - Displays results and estimated costs
# - Saves logs for troubleshooting
#
# Usage:
#   ./scripts/manual_update.sh           # Run update
#   ./scripts/manual_update.sh --dry-run # Preview changes only
#   ./scripts/manual_update.sh --stats   # Show stats only

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Change to project root
cd "$(dirname "$0")/.." || exit 1

# Create logs directory if needed
mkdir -p logs/manual_updates

# Log file
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="logs/manual_updates/update_${TIMESTAMP}.log"

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}         JuraGPT Legal Corpus - Manual Update Tool${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo -e "${RED}Error: Virtual environment not found at ./venv${NC}"
    echo "Please run: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
    exit 1
fi

# Check if Modal GPU embedder is deployed
echo -e "${YELLOW}Checking Modal GPU availability...${NC}"
if ! modal app list 2>/dev/null | grep -q "juragpt-embedder"; then
    echo -e "${YELLOW}Warning: Modal embedder not found. Deploying...${NC}"
    modal deploy src/embedding/modal_embedder.py
fi

# Pre-update stats
echo ""
echo -e "${GREEN}=== Current Corpus Status ===${NC}"
python scripts/update_corpus.py --stats

# Parse command-line arguments
if [ "$1" == "--stats" ]; then
    echo ""
    echo -e "${GREEN}Stats-only mode. Exiting.${NC}"
    exit 0
fi

if [ "$1" == "--dry-run" ]; then
    DRY_RUN="--dry-run"
    echo ""
    echo -e "${YELLOW}=== DRY RUN MODE - NO CHANGES WILL BE MADE ===${NC}"
    echo ""
else
    DRY_RUN=""
fi

# Run update
echo ""
echo -e "${GREEN}=== Running Update ===${NC}"
echo -e "Log file: ${LOG_FILE}"
echo ""

START_TIME=$(date +%s)

if python scripts/update_corpus.py ${DRY_RUN} 2>&1 | tee "${LOG_FILE}"; then
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))

    echo ""
    echo -e "${GREEN}======================================================================${NC}"
    echo -e "${GREEN}                    UPDATE SUCCESSFUL${NC}"
    echo -e "${GREEN}======================================================================${NC}"
    echo -e "Total time: ${ELAPSED} seconds"

    if [ -z "$DRY_RUN" ]; then
        # Extract vectors added from log
        VECTORS_ADDED=$(grep -E "Vectors (upserted|uploaded):" "${LOG_FILE}" | tail -1 | awk '{print $NF}' || echo "0")

        # Estimate cost (rough: $0.002 per 1000 vectors on Modal GPU)
        if [ "$VECTORS_ADDED" != "0" ]; then
            COST_ESTIMATE=$(awk "BEGIN {printf \"%.2f\", $VECTORS_ADDED * 0.002 / 1000}")
            echo -e "Vectors added: ${VECTORS_ADDED}"
            echo -e "Estimated cost: \$${COST_ESTIMATE} USD"
        fi
    fi

    echo ""
    echo -e "Log saved to: ${LOG_FILE}"
    echo -e "${GREEN}======================================================================${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}======================================================================${NC}"
    echo -e "${RED}                    UPDATE FAILED${NC}"
    echo -e "${RED}======================================================================${NC}"
    echo -e "Check log file for details: ${LOG_FILE}"
    echo ""
    echo -e "${YELLOW}Common issues:${NC}"
    echo -e "  1. OpenLegalData API down (currently experiencing issues)"
    echo -e "  2. Modal GPU timeout (try reducing --max-laws or --max-cases)"
    echo -e "  3. Qdrant connection issues (check network/credentials)"
    echo ""
    echo -e "For help, see: docs/UPDATE_GUIDE.md"
    echo -e "${RED}======================================================================${NC}"
    exit 1
fi
