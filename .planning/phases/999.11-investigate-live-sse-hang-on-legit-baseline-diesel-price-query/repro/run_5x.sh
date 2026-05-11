#!/usr/bin/env bash
# D-09 live verification bar: 5 fresh-uvicorn runs, each must produce
# an `answer` SSE event within 30,000 ms.
#
# Each run spawns its OWN uvicorn subprocess (probe_legit_baseline.py
# handles spawn + shutdown). The 5 runs reuse port 8765 sequentially;
# the shutdown wait inside the probe ensures the port is free before
# the next run starts.
#
# Usage:
#   bash .planning/phases/999.11-.../repro/run_5x.sh [extra-probe-flags...]
#
# Extra flags are forwarded verbatim to every probe invocation, e.g.:
#   bash run_5x.sh --skip-coldstart-refresh
#   bash run_5x.sh --warmup-first
#   bash run_5x.sh --skip-coldstart-refresh --warmup-first
set -u
set -o pipefail

REPRO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS_DIR="${REPRO_DIR}/logs"
SUMMARY="${LOGS_DIR}/summary.jsonl"

mkdir -p "${LOGS_DIR}"
: > "${SUMMARY}"

EXTRA_ARGS=("$@")

for i in 001 002 003 004 005; do
  echo "=== Run ${i} ==="
  SSE_OUT="${LOGS_DIR}/run-${i}-sse.log"
  STDERR_OUT="${LOGS_DIR}/run-${i}-uvicorn.stderr"
  # Note: ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} is the bash incantation for
  # "expand the array if defined, expand to nothing otherwise" — required
  # under `set -u` because plain "${EXTRA_ARGS[@]}" trips unbound-variable
  # when zero extra args were passed (Step-1 baseline case).
  python "${REPRO_DIR}/probe_legit_baseline.py" \
    --run-id "${i}" \
    --sse-out "${SSE_OUT}" \
    --stderr-out "${STDERR_OUT}" \
    ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"} \
    | tee -a "${SUMMARY}"
  echo "---"
done

# Pass/fail report. The heredoc uses an unquoted delimiter so bash
# interpolates ${SUMMARY} into the Python source. Python itself sees
# only a literal string after substitution — no further $-expansion.
python <<PY
import json, sys
summary_path = "${SUMMARY}"
ok = 0
total = 0
rows = []
with open(summary_path) as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            s = json.loads(line)
        except json.JSONDecodeError:
            # Non-JSON lines (probe debug output) are ignored.
            continue
        total += 1
        verdict = s.get("verdict")
        first_ans = s.get("first_answer_ms")
        rows.append((s.get("run_id"), verdict, first_ans))
        if verdict == "PASS_UNDER_30S":
            ok += 1
print()
print(f"=== D-09 live bar: {ok}/{total} runs PASS_UNDER_30S ===")
for run_id, verdict, first_ans in rows:
    print(f"  run {run_id}: verdict={verdict} first_answer_ms={first_ans}")
sys.exit(0 if ok == 5 and total == 5 else 1)
PY
