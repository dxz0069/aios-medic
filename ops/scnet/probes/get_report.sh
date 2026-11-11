#!/bin/bash
cat /public/home/acotxxttog/aios-medic/experiments/spike1/results/spike1_report.md
echo "=== aggregate ==="
python3 -c "import json; d=json.load(open(\"/public/home/acotxxttog/aios-medic/experiments/spike1/results/spike1_results.json\")); print(json.dumps(d[\"aggregate\"], ensure_ascii=False, indent=1))"
