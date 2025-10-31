#!/bin/bash
# ABOUTME: Pre-configured load testing scenarios for Auditor API
# ABOUTME: Run different load patterns to test various aspects of the system

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
HOST="${LOAD_TEST_HOST:-http://localhost:8888}"
LOCUST_FILE="tests/performance/locustfile.py"
REPORT_DIR="tests/performance/reports"

# Create reports directory
mkdir -p "$REPORT_DIR"

echo -e "${BLUE}🚀 Auditor Load Testing Scenarios${NC}\n"

# Function to run a scenario
run_scenario() {
    local name=$1
    local users=$2
    local spawn_rate=$3
    local duration=$4
    local user_class=$5
    local description=$6

    echo -e "${GREEN}Scenario: ${name}${NC}"
    echo -e "${YELLOW}Description: ${description}${NC}"
    echo "  Users: $users"
    echo "  Spawn Rate: $spawn_rate users/sec"
    echo "  Duration: $duration"
    echo "  User Class: ${user_class:-all classes}"
    echo ""

    local timestamp=$(date +%Y%m%d_%H%M%S)
    local report_prefix="${REPORT_DIR}/${name}_${timestamp}"

    # Build locust command
    local cmd="locust -f $LOCUST_FILE --host $HOST --headless"
    cmd="$cmd -u $users -r $spawn_rate -t $duration"
    cmd="$cmd --html ${report_prefix}.html"
    cmd="$cmd --csv ${report_prefix}"
    cmd="$cmd --loglevel INFO"

    if [ -n "$user_class" ]; then
        cmd="$cmd --user-class $user_class"
    fi

    echo -e "${BLUE}Running: $cmd${NC}\n"
    eval $cmd

    echo -e "\n${GREEN}✅ Scenario completed${NC}"
    echo -e "Report: ${report_prefix}.html\n"
    echo "-----------------------------------\n"
}

# Parse command line arguments
case "${1:-menu}" in
    smoke)
        echo -e "${BLUE}Running Smoke Test...${NC}\n"
        run_scenario \
            "smoke_test" \
            10 \
            2 \
            "1m" \
            "" \
            "Quick smoke test with 10 users for 1 minute"
        ;;

    baseline)
        echo -e "${BLUE}Running Baseline Test...${NC}\n"
        run_scenario \
            "baseline" \
            50 \
            5 \
            "5m" \
            "AuditorUser" \
            "Baseline performance with 50 standard users for 5 minutes"
        ;;

    stress)
        echo -e "${BLUE}Running Stress Test...${NC}\n"
        run_scenario \
            "stress" \
            200 \
            20 \
            "5m" \
            "" \
            "Stress test with 200 users (mixed patterns) for 5 minutes"
        ;;

    spike)
        echo -e "${BLUE}Running Spike Test...${NC}\n"
        run_scenario \
            "spike" \
            500 \
            100 \
            "2m" \
            "" \
            "Spike test: rapid ramp-up to 500 users for 2 minutes"
        ;;

    burst)
        echo -e "${BLUE}Running Burst Test...${NC}\n"
        run_scenario \
            "burst" \
            100 \
            50 \
            "3m" \
            "BurstUser" \
            "Burst pattern test with 100 rapid-fire users for 3 minutes"
        ;;

    heavy)
        echo -e "${BLUE}Running Heavy Load Test...${NC}\n"
        run_scenario \
            "heavy" \
            50 \
            5 \
            "5m" \
            "HeavyUser" \
            "Heavy requests test with 50 users making large requests"
        ;;

    endurance)
        echo -e "${BLUE}Running Endurance Test...${NC}\n"
        run_scenario \
            "endurance" \
            100 \
            10 \
            "30m" \
            "AuditorUser" \
            "Endurance test: 100 users for 30 minutes (sustained load)"
        ;;

    soak)
        echo -e "${BLUE}Running Soak Test...${NC}\n"
        run_scenario \
            "soak" \
            75 \
            5 \
            "2h" \
            "AuditorUser" \
            "Soak test: 75 users for 2 hours (memory leak detection)"
        ;;

    all)
        echo -e "${BLUE}Running All Scenarios...${NC}\n"
        $0 smoke
        sleep 30
        $0 baseline
        sleep 30
        $0 stress
        sleep 30
        $0 burst
        echo -e "${GREEN}✅ All scenarios completed${NC}"
        ;;

    menu|*)
        echo -e "${YELLOW}Available Load Testing Scenarios:${NC}\n"
        echo "  smoke      - Quick smoke test (10 users, 1 min)"
        echo "  baseline   - Baseline performance (50 users, 5 min)"
        echo "  stress     - Stress test (200 users, 5 min)"
        echo "  spike      - Spike test (500 users, 2 min)"
        echo "  burst      - Burst pattern (100 rapid users, 3 min)"
        echo "  heavy      - Heavy load (50 users, large requests, 5 min)"
        echo "  endurance  - Endurance test (100 users, 30 min)"
        echo "  soak       - Soak test (75 users, 2 hours)"
        echo "  all        - Run smoke + baseline + stress + burst"
        echo ""
        echo -e "${YELLOW}Usage:${NC}"
        echo "  ./tests/performance/scenarios.sh [scenario]"
        echo ""
        echo -e "${YELLOW}Examples:${NC}"
        echo "  ./tests/performance/scenarios.sh smoke"
        echo "  ./tests/performance/scenarios.sh baseline"
        echo "  LOAD_TEST_HOST=http://production.example.com ./tests/performance/scenarios.sh stress"
        echo ""
        echo -e "${YELLOW}Environment Variables:${NC}"
        echo "  LOAD_TEST_HOST - Target host (default: http://localhost:8888)"
        echo ""
        ;;
esac
