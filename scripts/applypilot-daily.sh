#!/usr/bin/env bash
# ApplyPilot Daily Multi-Track Harness (Isolated Runtime Mode)
# Runs ApplyPilot across multiple role tracks concurrently or sequentially.
# It uses APPLYPILOT_DIR to completely isolate configs, databases, and logs per role.

set -euo pipefail

# Configuration
LOCK="/tmp/applypilot-daily-isolated.lock"
RUN_ID="$(date +%Y%m%d_%H%M%S)"
TRACKS=("pm" "swe" "content" "accessibility" "ops")
SUMMARY_FILE="/tmp/applypilot_summary_$RUN_ID.tsv"

# 1. Acquire Lock (prevent concurrent cron runs)
exec 9>"$LOCK"
if ! flock -n 9; then
    echo "ERROR: ApplyPilot daily run is already active. Exiting."
    exit 1
fi

echo "=========================================================="
echo "🚀 Starting Isolated Daily Run: $RUN_ID"
echo "=========================================================="
echo -e "Track\tSession_ID\tApply_Status\tCount" > "$SUMMARY_FILE"

# 2. Sequential Discovery / Scoring Loop
for track in "${TRACKS[@]}"; do
    RUNTIME_DIR="$HOME/.applypilot_$track"
    
    # Skip if track config directory doesn't exist
    if [[ ! -d "$RUNTIME_DIR" ]]; then
        echo "[-] Skipping track '$track' (Directory $RUNTIME_DIR not found)"
        continue
    fi

    echo "----------------------------------------------------------"
    echo "🎯 [STAGE 1] Discovery & Score: Track [ $track ]"
    echo "----------------------------------------------------------"

    export APPLYPILOT_DIR="$RUNTIME_DIR"
    OUT_DIR="$RUNTIME_DIR/runs/$RUN_ID"
    mkdir -p "$OUT_DIR"

    # Preflight Check for this specific track
    if ! applypilot doctor > "$OUT_DIR/doctor.log" 2>&1; then
        echo "ERROR: Preflight failed for $track! Check $OUT_DIR/doctor.log."
        continue
    fi

    # Hard Guardrail: Prevent Discovery Volume Spikes
    SEARCH_CONF="$RUNTIME_DIR/searches.yaml"
    if [[ -f "$SEARCH_CONF" ]]; then
        if ! python3 -c "import sys, yaml; c=yaml.safe_load(open('$SEARCH_CONF')); sys.exit(0 if c.get('defaults', {}).get('results_per_site', 41) <= 40 else 1)" 2>/dev/null; then
            echo "[-] ERROR: Track '$track' discovery budget too high!"
            echo "    -> Change 'defaults.results_per_site' to <= 40 in $SEARCH_CONF"
            echo "    -> Skipping track to prevent API overspend."
            continue
        fi
    fi

    SID="${track}_${RUN_ID}"
    echo "[*] Session ID: $SID"

    # Hard Quota: Cap the number of jobs we score today to control API costs (e.g., max 400 per track)
    # We enforce this by "hiding" excess jobs (temporarily setting their fit_score to an ignored value or just relying on a DB quota script if it exists)
    # Since native quotas aren't built yet, we use a simple sqlite trick to ignore older jobs this run if there are too many.
    MAX_SCORE=400
    if [[ -f "$RUNTIME_DIR/applypilot.db" ]]; then
        echo "[*] Enforcing Token Budget: Capping pending scoring queue to $MAX_SCORE..."
        sqlite3 "$RUNTIME_DIR/applypilot.db" "
            UPDATE jobs SET fit_score = -1 
            WHERE id NOT IN (
                SELECT id FROM jobs 
                WHERE fit_score IS NULL AND full_description IS NOT NULL 
                ORDER BY discovered_at DESC LIMIT $MAX_SCORE
            ) AND fit_score IS NULL;
        "
    fi

    # Run pipeline up to tailoring (No cover letters to save $$, min score 8)
    if ! timeout 10800 applypilot run discover dedupe enrich score tailor --min-score 8 --workers 4 --session-id "$SID" > "$OUT_DIR/run.log" 2>&1; then
        echo "[-] WARNING: Pipeline run timed out or failed for track $track."
    fi
done

# 3. Parallel Apply Loop (Safer after discovery limits are respected)
echo "=========================================================="
echo "🚀 [STAGE 2] Parallel Auto-Apply"
echo "=========================================================="
PIDS=()

for track in "${TRACKS[@]}"; do
    RUNTIME_DIR="$HOME/.applypilot_$track"
    if [[ ! -d "$RUNTIME_DIR" ]]; then continue; fi

    export APPLYPILOT_DIR="$RUNTIME_DIR"
    OUT_DIR="$RUNTIME_DIR/runs/$RUN_ID"
    SID="${track}_${RUN_ID}"
    
    echo "[*] Launching auto-apply for $track in background..."
    
    # Run apply in background (Hard limit to 10 top-tier jobs per track to control ROI)
    timeout 10800 applypilot apply --workers 2 --session-id "$SID" --limit 10 --min-score 8 > "$OUT_DIR/apply.log" 2>&1 &
    PIDS+=($!)
done

# Wait for all background apply jobs to finish
wait "${PIDS[@]}" || true

# 4. Extract Metrics
echo "=========================================================="
echo "📊 Extracting Metrics"
echo "=========================================================="
for track in "${TRACKS[@]}"; do
    RUNTIME_DIR="$HOME/.applypilot_$track"
    if [[ ! -d "$RUNTIME_DIR" ]]; then continue; fi
    
    DB_PATH="$RUNTIME_DIR/applypilot.db"
    SID="${track}_${RUN_ID}"
    
    if [[ -f "$DB_PATH" ]]; then
        sqlite3 "$DB_PATH" \
            "SELECT '$track', '$SID', COALESCE(apply_status, 'pending/filtered'), COUNT(*) FROM jobs WHERE session_id='$SID' GROUP BY apply_status;" \
            >> "$SUMMARY_FILE"
    fi
done

echo "=========================================================="
echo "✅ ApplyPilot Daily Run Complete: $RUN_ID"
echo "=========================================================="
echo "Summary Report ($SUMMARY_FILE):"
column -t -s $'\t' "$SUMMARY_FILE"
echo "=========================================================="
