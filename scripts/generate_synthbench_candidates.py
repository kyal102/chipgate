"""Generate synthbench_v0 candidate files from built-in definitions."""
import json
import os
import sys

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chipgate.synthbench import BUILTIN_CANDIDATES

base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "benchmarks", "synthbench_v0")
candidates_dir = os.path.join(base_dir, "candidates")
os.makedirs(candidates_dir, exist_ok=True)

manifest = {"version": "1.0.0", "candidates": []}

for c in BUILTIN_CANDIDATES:
    # Write RTL file
    rtl_filename = f"{c.candidate_id}.v"
    rtl_path = os.path.join(candidates_dir, rtl_filename)
    with open(rtl_path, "w") as f:
        f.write(c.rtl_text)

    # Add to manifest
    manifest["candidates"].append({
        "candidate_id": c.candidate_id,
        "rtl_file": f"candidates/{rtl_filename}",
        "description": c.description,
        "expected_safety_status": c.expected_safety_status,
        "expected_longevity_status": c.expected_longevity_status,
        "expected_regression_status": c.expected_regression_status,
        "expected_improvement_type": c.expected_improvement_type,
    })

# Write manifest
manifest_path = os.path.join(base_dir, "candidates.json")
with open(manifest_path, "w") as f:
    json.dump(manifest, f, indent=2, sort_keys=True)

print(f"Generated {len(BUILTIN_CANDIDATES)} candidate files")
print(f"Manifest: {manifest_path}")
for entry in manifest["candidates"]:
    print(f"  {entry['candidate_id']}: {entry['expected_improvement_type']}")