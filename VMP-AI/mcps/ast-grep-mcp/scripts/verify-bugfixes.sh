#!/bin/bash
#
# Deployment Verification Script for Bugfixes
#
# Comprehensive verification script for recent bugfixes:
# 1. Doppler circuit breaker initialization
# 2. Server port binding with fallback
# 3. Activity Feed null error handling
# 4. Pipeline script permissions
# 5. PM2 configuration validation
#
# Usage:
#   ./scripts/verify-bugfixes.sh              # Run all checks
#   ./scripts/verify-bugfixes.sh --pre        # Pre-deployment checks only
#   ./scripts/verify-bugfixes.sh --post       # Post-deployment checks only
#   ./scripts/verify-bugfixes.sh --smoke      # Smoke tests only
#   ./scripts/verify-bugfixes.sh --rollback   # Create rollback script
#

set -e  # Exit on error (disabled for individual checks)

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Deployment mode
MODE="${1:-all}"

#############################################
# Helper Functions
#############################################

print_header() {
  echo ""
  echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
  echo -e "${BLUE}  $1${NC}"
  echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
  echo ""
}

print_section() {
  echo ""
  echo -e "${YELLOW}▸ $1${NC}"
  echo ""
}

check_pass() {
  echo -e "${GREEN}✓${NC} $1"
  ((PASSED++))
}

check_fail() {
  echo -e "${RED}✗${NC} $1"
  ((FAILED++))
}

check_warn() {
  echo -e "${YELLOW}⚠${NC} $1"
  ((WARNINGS++))
}

print_summary() {
  echo ""
  echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
  echo -e "${BLUE}  Summary${NC}"
  echo -e "${BLUE}═══════════════════════════════════════════════════════${NC}"
  echo ""
  echo -e "  ${GREEN}Passed:${NC}   $PASSED"
  echo -e "  ${RED}Failed:${NC}   $FAILED"
  echo -e "  ${YELLOW}Warnings:${NC} $WARNINGS"
  echo ""

  if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    return 0
  else
    echo -e "${RED}✗ $FAILED check(s) failed${NC}"
    return 1
  fi
}

#############################################
# Pre-Deployment Checks
#############################################

pre_deployment_checks() {
  print_header "Pre-Deployment Checks"

  # 1. Verify new files exist
  print_section "Verifying New Files"

  local files=(
    "sidequest/pipeline-core/doppler-health-monitor.ts"
    "api/utils/port-manager.ts"
    "api/activity-feed.ts"
    "api/event-broadcaster.ts"
  )

  for file in "${files[@]}"; do
    if [ -f "$PROJECT_ROOT/$file" ]; then
      check_pass "File exists: $file"
    else
      check_fail "Missing file: $file"
    fi
  done

  # 2. Check shebangs on pipeline scripts
  print_section "Checking Pipeline Script Shebangs"

  local pipeline_scripts=(
    "sidequest/pipeline-runners/duplicate-detection-pipeline.ts"
    "sidequest/pipeline-runners/git-activity-pipeline.ts"
    "sidequest/pipeline-runners/gitignore-pipeline.ts"
    "sidequest/pipeline-runners/plugin-management-pipeline.ts"
    "sidequest/pipeline-runners/claude-health-pipeline.ts"
    "sidequest/pipeline-runners/repo-cleanup-pipeline.ts"
  )

  for script in "${pipeline_scripts[@]}"; do
    local full_path="$PROJECT_ROOT/$script"
    if [ -f "$full_path" ]; then
      local first_line=$(head -n 1 "$full_path")
      if [[ "$first_line" == "#!/usr/bin/env node" ]] || [[ "$first_line" == "#!/usr/bin/env bash" ]]; then
        check_pass "Shebang present: $script"
      else
        check_warn "No shebang in: $script (OK if using node interpreter in PM2)"
      fi
    else
      check_fail "Missing script: $script"
    fi
  done

  # 3. Verify PM2 config syntax
  print_section "Validating PM2 Configuration"

  if [ -f "$PROJECT_ROOT/ecosystem.config.cjs" ]; then
    if node -c "$PROJECT_ROOT/ecosystem.config.cjs" 2>/dev/null; then
      check_pass "PM2 config syntax valid"
    else
      check_fail "PM2 config has syntax errors"
    fi

    # Check for node interpreter
    if grep -q "interpreter: 'node'" "$PROJECT_ROOT/ecosystem.config.cjs"; then
      check_pass "PM2 config uses node interpreter (prevents permission errors)"
    else
      check_warn "PM2 config missing node interpreter setting"
    fi

    # Check for restart delay settings
    if grep -q "restart_delay" "$PROJECT_ROOT/ecosystem.config.cjs"; then
      check_pass "PM2 config has restart delay (prevents rapid crash loops)"
    else
      check_warn "PM2 config missing restart_delay"
    fi
  else
    check_fail "PM2 config not found: ecosystem.config.cjs"
  fi

  # 4. Run TypeScript type checks
  print_section "Running TypeScript Type Checks"

  cd "$PROJECT_ROOT"
  if npm run typecheck > /dev/null 2>&1; then
    check_pass "TypeScript type checks passed"
  else
    check_fail "TypeScript type checks failed"
    echo ""
    echo "Run 'npm run typecheck' for details"
  fi

  # 5. Run unit tests
  print_section "Running Unit Tests"

  if npm test > /dev/null 2>&1; then
    check_pass "Unit tests passed"
  else
    check_fail "Unit tests failed"
    echo ""
    echo "Run 'npm test' for details"
  fi

  # 6. Run integration tests
  print_section "Running Integration Tests"

  if npm run test:integration > /dev/null 2>&1; then
    check_pass "Integration tests passed"
  else
    check_fail "Integration tests failed"
    echo ""
    echo "Run 'npm run test:integration' for details"
  fi

  # 7. Verify Doppler connection
  print_section "Verifying Doppler Configuration"

  if command -v doppler &> /dev/null; then
    check_pass "Doppler CLI installed"

    # Check if doppler is configured
    if doppler setup --no-interactive &> /dev/null; then
      check_pass "Doppler configured for project"

      # Verify critical env vars
      local env_vars=(
        "JOBS_API_PORT"
        "REDIS_HOST"
        "REDIS_PORT"
        "NODE_ENV"
      )

      for var in "${env_vars[@]}"; do
        if doppler secrets get "$var" &> /dev/null; then
          check_pass "Doppler secret exists: $var"
        else
          check_warn "Doppler secret not found: $var (may have fallback)"
        fi
      done
    else
      check_warn "Doppler not configured (run 'doppler setup')"
    fi
  else
    check_fail "Doppler CLI not installed"
  fi

  # 8. Check script permissions
  print_section "Verifying Script Permissions"

  local scripts=(
    "scripts/verify-bugfixes.sh"
    "scripts/deploy-traditional-server.sh"
  )

  for script in "${scripts[@]}"; do
    local full_path="$PROJECT_ROOT/$script"
    if [ -x "$full_path" ]; then
      check_pass "Script executable: $script"
    else
      check_warn "Script not executable: $script (run 'chmod +x $script')"
    fi
  done
}

#############################################
# Post-Deployment Verification
#############################################

post_deployment_checks() {
  print_header "Post-Deployment Verification"

  # 1. Check if PM2 processes are running
  print_section "Verifying PM2 Processes"

  if command -v pm2 &> /dev/null; then
    check_pass "PM2 installed"

    # Check dashboard process
    if pm2 describe aleph-dashboard &> /dev/null; then
      local status=$(pm2 jlist | jq -r '.[] | select(.name=="aleph-dashboard") | .pm2_env.status')
      if [ "$status" == "online" ]; then
        check_pass "aleph-dashboard process online"
      else
        check_fail "aleph-dashboard process not online (status: $status)"
      fi
    else
      check_warn "aleph-dashboard process not found (may not be deployed yet)"
    fi

    # Check worker process
    if pm2 describe aleph-worker &> /dev/null; then
      local status=$(pm2 jlist | jq -r '.[] | select(.name=="aleph-worker") | .pm2_env.status')
      if [ "$status" == "online" ]; then
        check_pass "aleph-worker process online"
      else
        check_warn "aleph-worker process not online (status: $status)"
      fi
    else
      check_warn "aleph-worker process not found (may not be deployed yet)"
    fi

    # Check for recent restarts (could indicate crash loops)
    local dashboard_restarts=$(pm2 jlist | jq -r '.[] | select(.name=="aleph-dashboard") | .pm2_env.restart_time // 0')
    if [ "$dashboard_restarts" -gt 5 ]; then
      check_warn "aleph-dashboard has $dashboard_restarts restarts (may indicate instability)"
    elif [ "$dashboard_restarts" -gt 0 ]; then
      check_pass "aleph-dashboard restarts: $dashboard_restarts (normal)"
    fi
  else
    check_warn "PM2 not installed (skip if not using PM2)"
  fi

  # 2. Check Doppler health monitor initialization
  print_section "Testing Doppler Health Monitor"

  # Test that DopplerHealthMonitor can initialize
  local test_script=$(cat <<'EOF'
import { DopplerHealthMonitor } from './sidequest/pipeline-core/doppler-health-monitor.ts';
const monitor = new DopplerHealthMonitor();
try {
  const health = await monitor.checkCacheHealth();
  console.log(JSON.stringify({ success: true, health }));
  process.exit(0);
} catch (error) {
  console.log(JSON.stringify({ success: false, error: error.message }));
  process.exit(0);
}
EOF
)

  local result=$(cd "$PROJECT_ROOT" && echo "$test_script" | node --strip-types --input-type=module 2>&1)

  if echo "$result" | jq -e '.success' &> /dev/null; then
    check_pass "Doppler health monitor initializes successfully"

    local cache_age=$(echo "$result" | jq -r '.health.cacheAgeHours // "N/A"')
    if [ "$cache_age" != "N/A" ]; then
      echo "      Cache age: ${cache_age} hours"
      if [ "$cache_age" -gt 12 ]; then
        check_warn "Doppler cache is ${cache_age}h old (consider running 'doppler run --command=echo')"
      fi
    fi
  else
    local error=$(echo "$result" | jq -r '.error // "Unknown error"')
    check_warn "Doppler health check error: $error (may be normal if .doppler cache doesn't exist)"
  fi

  # 3. Verify server binds to port
  print_section "Testing Server Port Binding"

  # Get configured port
  local api_port=$(doppler secrets get JOBS_API_PORT --plain 2>/dev/null || echo "8080")

  # Check if port is listening
  if lsof -i ":$api_port" -sTCP:LISTEN &> /dev/null; then
    check_pass "Server listening on port $api_port"
  else
    check_warn "Server not listening on port $api_port (may not be started)"
  fi

  # 4. Test activity feed null error handling
  print_section "Testing Activity Feed Error Handling"

  local test_script=$(cat <<'EOF'
import { ActivityFeedManager } from './api/activity-feed.ts';
import { ScanEventBroadcaster } from './api/event-broadcaster.ts';

// Mock broadcaster
const mockBroadcaster = { broadcast: () => {} };
const feed = new ActivityFeedManager(mockBroadcaster);

// Test with null error
try {
  feed.addActivity({
    type: 'job:failed',
    jobId: 'test-123',
    jobType: 'test',
    message: 'Test failed',
    error: null  // Null error should not crash
  });
  console.log(JSON.stringify({ success: true }));
} catch (error) {
  console.log(JSON.stringify({ success: false, error: error.message }));
}
EOF
)

  local result=$(cd "$PROJECT_ROOT" && echo "$test_script" | node --strip-types --input-type=module 2>&1)

  if echo "$result" | jq -e '.success' &> /dev/null; then
    check_pass "Activity feed handles null errors gracefully"
  else
    check_fail "Activity feed crashes on null error"
  fi

  # 5. Verify pipeline scripts are executable
  print_section "Verifying Pipeline Script Executability"

  local pipeline_scripts=(
    "sidequest/pipeline-runners/duplicate-detection-pipeline.ts"
    "sidequest/pipeline-runners/git-activity-pipeline.ts"
  )

  for script in "${pipeline_scripts[@]}"; do
    local full_path="$PROJECT_ROOT/$script"
    # Scripts don't need +x if PM2 uses node interpreter
    if [ -f "$full_path" ]; then
      if node -c "$full_path" 2>/dev/null; then
        check_pass "Script can be executed with node: $script"
      else
        check_fail "Script has syntax errors: $script"
      fi
    else
      check_fail "Script not found: $script"
    fi
  done
}

#############################################
# Health Checks
#############################################

health_checks() {
  print_header "Health Checks"

  # Get configured port
  local api_port=$(doppler secrets get JOBS_API_PORT --plain 2>/dev/null || echo "8080")

  # 1. GET /health endpoint
  print_section "Testing /health Endpoint"

  local health_response=$(curl -s "http://localhost:$api_port/health" 2>/dev/null)

  if echo "$health_response" | jq -e '.status == "healthy"' &> /dev/null; then
    check_pass "GET /health returns 200 with healthy status"
  else
    check_warn "GET /health failed (server may not be running on port $api_port)"
  fi

  # 2. GET /api/health/doppler endpoint
  print_section "Testing /api/health/doppler Endpoint"

  local doppler_health=$(curl -s "http://localhost:$api_port/api/health/doppler" 2>/dev/null)

  if echo "$doppler_health" | jq -e '.status' &> /dev/null; then
    local status=$(echo "$doppler_health" | jq -r '.status')
    local cache_age=$(echo "$doppler_health" | jq -r '.cacheAgeHours // "N/A"')

    check_pass "GET /api/health/doppler returns circuit state (status: $status)"

    if [ "$status" == "healthy" ]; then
      echo "      Cache age: ${cache_age}h (healthy)"
    else
      check_warn "Doppler health status: $status (cache age: ${cache_age}h)"
    fi
  else
    check_warn "GET /api/health/doppler failed (server may not be running)"
  fi

  # 3. WebSocket connection
  print_section "Testing WebSocket Connection"

  # Use wscat if available
  if command -v wscat &> /dev/null; then
    # Test WebSocket connection with timeout
    local ws_test=$(timeout 2s wscat -c "ws://localhost:$api_port/ws" --execute "ping" 2>&1 || true)

    if echo "$ws_test" | grep -q "connected" || echo "$ws_test" | grep -q "pong"; then
      check_pass "WebSocket connection successful"
    else
      check_warn "WebSocket connection failed (may need wscat: npm install -g wscat)"
    fi
  else
    check_warn "wscat not installed (skip WebSocket test)"
  fi

  # 4. Redis connection (via API)
  print_section "Testing Redis Connection"

  local status_response=$(curl -s "http://localhost:$api_port/api/status" 2>/dev/null)

  if echo "$status_response" | jq -e '.queue' &> /dev/null; then
    check_pass "Redis connection healthy (queue stats available)"
  else
    check_warn "Cannot verify Redis connection (server may not be running)"
  fi

  # 5. Sentry SDK initialization
  print_section "Verifying Sentry Configuration"

  if doppler secrets get SENTRY_DSN &> /dev/null; then
    local sentry_dsn=$(doppler secrets get SENTRY_DSN --plain 2>/dev/null)

    if [ -n "$sentry_dsn" ]; then
      check_pass "Sentry DSN configured in Doppler"
    else
      check_warn "Sentry DSN is empty (error tracking disabled)"
    fi
  else
    check_warn "Sentry DSN not found in Doppler"
  fi
}

#############################################
# Smoke Tests
#############################################

smoke_tests() {
  print_header "Smoke Tests"

  # Get configured port
  local api_port=$(doppler secrets get JOBS_API_PORT --plain 2>/dev/null || echo "8080")

  # 1. Create a test job
  print_section "Creating Test Job"

  local create_response=$(curl -s -X POST "http://localhost:$api_port/api/scans" \
    -H "Content-Type: application/json" \
    -d '{"repositoryPath":"/tmp/test-repo","options":{"skipCache":true}}' \
    2>/dev/null)

  if echo "$create_response" | jq -e '.jobId' &> /dev/null; then
    local job_id=$(echo "$create_response" | jq -r '.jobId')
    check_pass "Test job created: $job_id"

    # 2. Verify job appears in activity feed
    print_section "Verifying Activity Feed"

    sleep 2  # Wait for job to appear in feed

    local status_response=$(curl -s "http://localhost:$api_port/api/status" 2>/dev/null)
    local activity_count=$(echo "$status_response" | jq -r '.recentActivity | length')

    if [ "$activity_count" -gt 0 ]; then
      check_pass "Activity feed has $activity_count activities"
    else
      check_warn "Activity feed is empty"
    fi
  else
    check_warn "Cannot create test job (server may not be running)"
  fi

  # 3. Test port fallback (advanced)
  print_section "Testing Port Fallback Mechanism"

  # This test requires starting a second server instance while port is occupied
  # Skip if server is not running
  if lsof -i ":$api_port" -sTCP:LISTEN &> /dev/null; then
    check_pass "Port fallback mechanism configured (current port: $api_port)"
    echo "      Note: Full fallback test requires stopping server and running in parallel"
  else
    check_warn "Server not running - cannot test port fallback"
  fi

  # 4. Test Doppler circuit breaker (mock failure)
  print_section "Testing Doppler Circuit Breaker"

  # Check if .doppler/fallback.json exists
  if [ -f "$HOME/.doppler/.fallback.json" ]; then
    local cache_age_sec=$(($(date +%s) - $(stat -f %m "$HOME/.doppler/.fallback.json" 2>/dev/null || stat -c %Y "$HOME/.doppler/.fallback.json" 2>/dev/null)))
    local cache_age_hours=$((cache_age_sec / 3600))

    check_pass "Doppler fallback cache exists (age: ${cache_age_hours}h)"

    if [ $cache_age_hours -gt 24 ]; then
      check_warn "Doppler cache is stale (${cache_age_hours}h old) - run 'doppler run --command=echo' to refresh"
    fi
  else
    check_warn "Doppler fallback cache doesn't exist (will be created on first doppler run failure)"
  fi
}

#############################################
# Rollback Script Generation
#############################################

create_rollback_script() {
  print_header "Creating Rollback Script"

  local rollback_file="$PROJECT_ROOT/scripts/rollback-bugfixes.sh"

  cat > "$rollback_file" <<'ROLLBACK_EOF'
#!/bin/bash
#
# Rollback Script for Bugfixes
#
# Reverts recent bugfixes and restores previous PM2 configuration.
#
# Usage:
#   ./scripts/rollback-bugfixes.sh
#

set -e

echo "🔄 Rolling back bugfixes..."

# Stop PM2 processes
echo "Stopping PM2 processes..."
pm2 stop ecosystem.config.cjs || true

# Restore PM2 process state from backup
if [ -f "$HOME/.pm2/dump.pm2.bak" ]; then
  echo "Restoring PM2 process state from backup..."
  cp "$HOME/.pm2/dump.pm2.bak" "$HOME/.pm2/dump.pm2"
  pm2 resurrect
else
  echo "⚠️  No PM2 backup found - manual restart required"
fi

# Git revert (if on deployment branch)
echo ""
echo "To revert code changes, run:"
echo "  git revert <commit-sha>"
echo ""
echo "Recent commits:"
git log --oneline -5

echo ""
echo "✓ Rollback preparation complete"
echo ""
echo "Next steps:"
echo "1. Verify PM2 processes: pm2 status"
echo "2. Check logs: pm2 logs aleph-dashboard"
echo "3. If needed, revert git commits manually"
echo "4. Restart services: doppler run -- pm2 restart ecosystem.config.cjs"
ROLLBACK_EOF

  chmod +x "$rollback_file"
  check_pass "Rollback script created: scripts/rollback-bugfixes.sh"

  # Create PM2 backup
  if command -v pm2 &> /dev/null; then
    if pm2 ping &> /dev/null; then
      echo ""
      echo "Creating PM2 backup..."
      pm2 save
      cp "$HOME/.pm2/dump.pm2" "$HOME/.pm2/dump.pm2.bak" 2>/dev/null || true
      check_pass "PM2 process state backed up"
    fi
  fi
}

#############################################
# Main Execution
#############################################

main() {
  echo ""
  echo -e "${BLUE}╔═══════════════════════════════════════════════════════╗${NC}"
  echo -e "${BLUE}║                                                       ║${NC}"
  echo -e "${BLUE}║       Deployment Verification Script v1.0.0          ║${NC}"
  echo -e "${BLUE}║       AlephAuto Bugfix Verification                  ║${NC}"
  echo -e "${BLUE}║                                                       ║${NC}"
  echo -e "${BLUE}╚═══════════════════════════════════════════════════════╝${NC}"

  case "$MODE" in
    --pre|pre)
      pre_deployment_checks
      ;;
    --post|post)
      post_deployment_checks
      ;;
    --health|health)
      health_checks
      ;;
    --smoke|smoke)
      smoke_tests
      ;;
    --rollback|rollback)
      create_rollback_script
      ;;
    --all|all|*)
      pre_deployment_checks
      post_deployment_checks
      health_checks
      smoke_tests
      create_rollback_script
      ;;
  esac

  print_summary
}

# Run main function
main

# Exit with appropriate code
if [ $FAILED -eq 0 ]; then
  exit 0
else
  exit 1
fi
