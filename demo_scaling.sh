#!/bin/bash
set -e

if ! curl -s -f http://localhost:8000/scaling/metrics > .scaling_metrics.json; then
    echo "ERROR: Could not reach the server at http://localhost:8000"
    exit 1
fi

python -c "
import json, sys
try:
    with open('.scaling_metrics.json') as f:
        data = json.load(f)
    print('\n=== SCALING METRICS DEMO ===')
    print('CONNECTIONS:')
    c = data.get('connections', {})
    print(f\"  Active: {c.get('current_active')} / {c.get('max_allowed')} ({c.get('utilization_percent')}%) \")
    print('\nTABLE SIZES:')
    for k, v in data.get('table_sizes', {}).items():
        print(f'  {k}: {v}')
    print('\n>>> NEXT SCALING STEP <<<')
    print(data.get('next_scaling_step', ''))
    print('============================\n')
except Exception as e:
    print(f'Error parsing json: {e}')
    sys.exit(1)
"
rm -f .scaling_metrics.json
