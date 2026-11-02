#!/bin/sh
# Check a spec against a spec_trace.py recording over a tune list, in parallel chunks.
# fc_gate.sh PYSIDTRACKER_CHECKOUT REF.pkl.gz SPEC.play TUNES.csv [CHUNKS]
set -e
tool="$1/tools/spec_trace.py"
ref="$2"
spec="$3"
tunes="$4"
chunks="${5:-4}"
dir=$(mktemp -d)
python - "$tunes" "$dir" "$chunks" <<'PY'
import csv, sys
rows = [r["path"] for r in csv.DictReader(open(sys.argv[1], encoding="utf-8"))]
n = int(sys.argv[3])
for i in range(n):
    with open(f"{sys.argv[2]}/{i}.csv", "w", encoding="utf-8") as f:
        f.write("path\n" + "\n".join(rows[i::n]) + "\n")
PY
for i in $(seq 0 $((chunks - 1))); do
  python "$tool" check "$ref" "$spec" "$dir/$i.csv" --jobs 6 > "$dir/$i.out" 2>&1 &
done
wait
cat "$dir"/*.out | tr '\r' '\n' | grep -v 'tune/s\]' | grep -v '^$'
cat "$dir"/*.out | tr '\r' '\n' | grep '^differ' | awk '{d+=$2; t+=$4} END {print "total differ", d, "of", t}'
rm -rf "$dir"
