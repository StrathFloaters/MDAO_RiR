#!/usr/bin/env python3
"""
Parallel WEIS Optimisation Launcher
====================================
Launches multiple WEIS optimisations in parallel, each with a unique combination
of (input_option, modelling_option, analysis_option).

For each run the script:
  1. Creates a modified copy of RiR_raft_opt_analysis_ptfm.yaml with a unique
     ``fname_output`` value so outputs do not collide.
  2. Creates a temporary driver script with the correct option variables.
  3. Launches the driver as a subprocess (one per CPU core, configurable).

Usage
-----
  python run_weis_parallel.py                       # run all combinations
  python run_weis_parallel.py --max-workers 4       # limit to 4 parallel jobs
  python run_weis_parallel.py --dry-run              # print jobs without executing
"""

import os
import sys
import copy
import shutil
import argparse
import textwrap
import subprocess
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

try:
    import yaml          # PyYAML  (pip install pyyaml)
except ImportError:
    import ruamel.yaml as yaml   # fallback

# ---------------------------------------------------------------------------
# 1.  Define the parameter space (explicit combinations)
# ---------------------------------------------------------------------------
# Each tuple is (input_option, modelling_option, analysis_option).
# List exactly the combinations you want to run.

COMBINATIONS = [
    # # --- Tower optimisation, starting from original IEA 15MW design ---
    # ("1", "A", "towr"),
    # ("1", "B", "towr"),
    # ("1", "C", "towr"),
    # # --- Tower + platform optimisation ---
    # ("1", "A", "tower_ptfm"),
    # ("1", "B", "tower_ptfm"),
    # ("1", "C", "tower_ptfm"),
    # --- Platform only, after tower optimisation (sequential) ---
    ("1A", "A", "ptfm"),
    ("1B", "B", "ptfm"),
    ("1C", "C", "ptfm"),
]

# Base directory: assumed to be the directory that contains this launcher AND
# the original driver / YAML files.
BASE_DIR = Path(__file__).resolve().parent

# Template analysis YAML (only modified when analysis_option involves "ptfm")
ANALYSIS_PTFM_YAML = BASE_DIR / "RiR_raft_opt_analysis_ptfm.yaml"

# Original driver script used as a template
ORIGINAL_DRIVER    = BASE_DIR / "RiR_raft_opt_analysis_driver.py"

# Directory where per-run artefacts (modified YAMLs, driver copies) are stored
GENERATED_DIR      = BASE_DIR / "outputs"


# ---------------------------------------------------------------------------
# 2.  Helper functions
# ---------------------------------------------------------------------------

def _make_run_tag(input_opt: str, model_opt: str, analysis_opt: str) -> str:
    """Return a short, filesystem-safe tag for this combination."""
    return f"inp{input_opt}_mod{model_opt}_ana{analysis_opt}"


def _create_modified_yaml(run_tag: str, run_dir: Path, analysis_opt: str) -> Path:
    if analysis_opt == "towr":
        base_yaml = BASE_DIR / "RiR_raft_opt_analysis_twr.yaml"
    elif analysis_opt == "ptfm":
        base_yaml = BASE_DIR / "RiR_raft_opt_analysis_ptfm.yaml"
    elif analysis_opt == "tower_ptfm":
        base_yaml = BASE_DIR / "RiR_raft_opt_analysis_twr_ptfm.yaml"
    else:
        raise ValueError(f"Unknown analysis option {analysis_opt}")

    with open(base_yaml, "r") as fh:
        data = yaml.safe_load(fh)

    def _set_key(d, key, value):
        if isinstance(d, dict):
            for k, v in d.items():
                if k == key:
                    d[k] = value
                else:
                    _set_key(v, key, value)
        elif isinstance(d, list):
            for item in d:
                _set_key(item, key, value)

    _set_key(data, "fname_output", run_tag)
    _set_key(data, "file_name", f"log_opt_{run_tag}.sql")

    out_yaml = run_dir / f"RiR_raft_opt_analysis_{analysis_opt}_{run_tag}.yaml"
    with open(out_yaml, "w") as fh:
        yaml.dump(data, fh, default_flow_style=False, sort_keys=False)

    return out_yaml



def _create_driver_script(
    input_opt: str,
    model_opt: str,
    analysis_opt: str,
    run_tag: str,
    run_dir: Path,
    analysis_yaml_path: Path | None = None,
) -> Path:
    """
    Generate a self-contained driver script for one WEIS run.

    * Sets the three option variables to the requested values.
    * If a custom analysis YAML was generated (for ptfm-related runs),
      overrides the path after the match block so the modified YAML is used.
    """
    # Read the original driver as a template
    with open(ORIGINAL_DRIVER, "r") as fh:
        src = fh.read()

    # Replace the option assignments
    src = src.replace('input_option        = "1"',       f'input_option = "{input_opt}"',    1)
    src = src.replace('modelling_option    = "A"',    f'modelling_option = "{model_opt}"', 1)
    src = src.replace('analysis_option     = "towr"',  f'analysis_option = "{analysis_opt}"', 1)

    # If we generated a custom ptfm YAML, inject an override right before
    # the weis_main() call so that file is used instead.
    if analysis_yaml_path is not None:
        override_line = (
            f'\n# >>> Override analysis YAML for this parallel run\n'
            f'fname_analysis_options = r"{analysis_yaml_path}"\n'
        )
        src = src.replace(
            "wt_opt, modeling_options, opt_options = weis_main(",
            override_line + "wt_opt, modeling_options, opt_options = weis_main(",
            1,
        )

    driver_path = run_dir / f"driver_{run_tag}.py"
    with open(driver_path, "w") as fh:
        fh.write(src)

    return driver_path


def _run_single(driver_path: Path, run_tag: str) -> dict:
    """
    Execute one driver script in a subprocess.
    Returns a dict with status info.
    """
    print(f"[START]  {run_tag}")
    result = subprocess.run(
        [sys.executable, str(driver_path)],
        capture_output=True,
        text=True,
    )
    status = "OK" if result.returncode == 0 else "FAIL"
    print(f"[{status}]  {run_tag}  (return code {result.returncode})")

    # Persist logs
    log_dir = driver_path.parent
    (log_dir / f"{run_tag}_stdout.log").write_text(result.stdout)
    (log_dir / f"{run_tag}_stderr.log").write_text(result.stderr)

    return {
        "run_tag":     run_tag,
        "returncode":  result.returncode,
        "stdout_tail": result.stdout[-500:] if result.stdout else "",
        "stderr_tail": result.stderr[-500:] if result.stderr else "",
    }


# ---------------------------------------------------------------------------
# 3.  Main entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Launch WEIS optimisations in parallel."
    )
    parser.add_argument(
        "--max-workers", type=int, default=os.cpu_count(),
        help="Maximum number of parallel processes (default: all CPUs).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the jobs that would be launched without executing them.",
    )
    args = parser.parse_args()

    # Use the explicitly defined combinations
    combos = COMBINATIONS
    print(f"Total combinations: {len(combos)}")
    print(f"Max parallel workers: {args.max_workers}\n")

    # Prepare output directory for generated artefacts
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Generate per-run artefacts
    # ------------------------------------------------------------------
    jobs: list[tuple[Path, str]] = []

    for input_opt, model_opt, analysis_opt in combos:
        run_tag = _make_run_tag(input_opt, model_opt, analysis_opt)
        run_dir = GENERATED_DIR / run_tag
        run_dir.mkdir(parents=True, exist_ok=True)

        analysis_yaml_path = _create_modified_yaml(run_tag, run_dir, analysis_opt)

        driver_path = _create_driver_script(
            input_opt, model_opt, analysis_opt,
            run_tag, run_dir,
            analysis_yaml_path=analysis_yaml_path,
        )
        jobs.append((driver_path, run_tag))

        # ------------------------------------------------------------------
        # Execute (or dry-run)
        # ------------------------------------------------------------------
        if args.dry_run:
            print("=== DRY RUN – the following jobs would be launched ===")
            for driver_path, tag in jobs:
                print(f"  {tag}  ->  {driver_path}")
            return

    results = []
    with ProcessPoolExecutor(max_workers=args.max_workers) as executor:
        future_to_tag = {
            executor.submit(_run_single, dp, tag): tag
            for dp, tag in jobs
        }
        for future in as_completed(future_to_tag):
            tag = future_to_tag[future]
            try:
                res = future.result()
                results.append(res)
            except Exception as exc:
                print(f"[ERROR] {tag}: {exc}")
                results.append({"run_tag": tag, "returncode": -1,
                                "stdout_tail": "", "stderr_tail": str(exc)})

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    n_ok   = sum(1 for r in results if r["returncode"] == 0)
    n_fail = len(results) - n_ok
    print(f"  Succeeded: {n_ok}")
    print(f"  Failed:    {n_fail}")
    if n_fail:
        print("\nFailed runs:")
        for r in results:
            if r["returncode"] != 0:
                print(f"  - {r['run_tag']}  (code {r['returncode']})")
                if r["stderr_tail"]:
                    print(f"    stderr: ...{r['stderr_tail'][-200:]}")


if __name__ == "__main__":
    main()
