import os
import sys
import json
import time
import subprocess
from pathlib import Path

# Constants for expected trace file sizes
EXPECTED_JOGGING_SIZE = 15202906863
EXPECTED_CARS_SIZE = 33152357624

TRACES_DIR = Path("/Users/fehmi/BFND_traces")
WORKSPACE_DIR = Path("/Users/fehmi/Library/CloudStorage/GoogleDrive-fehmi8@gmail.com/My Drive/sics/projects/saptarshi/code/BFND_saptarshi/BFND-1")
STATE_FILE = WORKSPACE_DIR / "logs" / "monitor_state.json"
RESULTS_DIR = WORKSPACE_DIR / "results"

def format_bytes(size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"

def get_file_info(file_name, expected_size):
    path = TRACES_DIR / file_name
    if not path.exists():
        return 0, 0.0, False
    size = path.stat().st_size
    pct = (size / expected_size) * 100.0 if expected_size > 0 else 0.0
    is_done = size >= expected_size
    return size, pct, is_done

def check_active_simulations():
    # Find any running python processes executing simulation.py using ps
    sims = []
    try:
        output = subprocess.check_output(["ps", "aux"], text=True)
        for line in output.splitlines():
            if "simulation.py" in line and "grep" not in line and "monitor.py" not in line:
                parts = line.split(None, 10)
                if len(parts) >= 11:
                    pid = parts[1]
                    cmd = parts[10]
                    sims.append({"pid": pid, "cmd": cmd})
    except Exception:
        pass
    return sims

def count_simulation_results():
    if not RESULTS_DIR.exists():
        return {}
    
    progress = {}
    # Structure: results/<scenario>/results_config_<scenario>_*.tsv
    for scenario_dir in RESULTS_DIR.iterdir():
        if not scenario_dir.is_dir():
            continue
        scenario = scenario_dir.name
        progress[scenario] = {}
        for tsv_file in scenario_dir.glob("*.tsv"):
            # Count lines in TSV excluding header
            try:
                with open(tsv_file, 'r') as f:
                    lines = f.readlines()
                rows = len(lines) - 1 if len(lines) > 0 else 0
                # Extract node count from filename
                name_parts = tsv_file.stem.split('_')
                nodes = name_parts[-1]
                progress[scenario][nodes] = rows
            except Exception:
                pass
    return progress

def load_compare_results():
    sys.path.append(str(WORKSPACE_DIR / "scripts"))
    try:
        import compare_results
        input_paths = sorted(RESULTS_DIR.glob("**/*.tsv"))
        summaries = []
        for path in input_paths:
            if path.exists():
                try:
                    summaries.append(compare_results.load_summary(path))
                except Exception:
                    pass
        return summaries
    except Exception as e:
        return []

def main():
    os.makedirs(WORKSPACE_DIR / "logs", exist_ok=True)
    
    # Load previous state
    state = {}
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
        except Exception:
            pass

    current_time = time.time()
    
    # Check trace files
    j_size, j_pct, j_done = get_file_info("pwr_jogging.h5", EXPECTED_JOGGING_SIZE)
    c_size, c_pct, c_done = get_file_info("pwr_cars.h5", EXPECTED_CARS_SIZE)
    
    # Calculate download speeds
    last_time = state.get("last_time", current_time)
    time_diff = current_time - last_time
    
    j_speed = 0.0
    c_speed = 0.0
    if time_diff > 0.5:
        last_j_size = state.get("last_jogging_size", j_size)
        last_c_size = state.get("last_cars_size", c_size)
        j_speed = max(0.0, (j_size - last_j_size) / time_diff)
        c_speed = max(0.0, (c_size - last_c_size) / time_diff)
        
    # Estimate times remaining
    j_eta = (EXPECTED_JOGGING_SIZE - j_size) / j_speed if j_speed > 1000 and not j_done else 0.0
    c_eta = (EXPECTED_CARS_SIZE - c_size) / c_speed if c_speed > 1000 and not c_done else 0.0

    # Save state
    new_state = {
        "last_time": current_time,
        "last_jogging_size": j_size,
        "last_cars_size": c_size
    }
    with open(STATE_FILE, 'w') as f:
        json.dump(new_state, f, indent=2)

    # Print output
    print("# Trace Downloads Status")
    print(f"| File | Size / Expected | Progress | Speed | ETA | Status |")
    print(f"| --- | --- | --- | --- | --- | --- |")
    
    j_speed_str = f"{format_bytes(j_speed)}/s" if j_speed > 0 else "-"
    j_eta_str = f"{j_eta/60.0:.1f} min" if j_eta > 0 else "-"
    j_status = "Done" if j_done else "Downloading"
    print(f"| `pwr_jogging.h5` | {format_bytes(j_size)} / {format_bytes(EXPECTED_JOGGING_SIZE)} | {j_pct:.2f}% | {j_speed_str} | {j_eta_str} | {j_status} |")
    
    c_speed_str = f"{format_bytes(c_speed)}/s" if c_speed > 0 else "-"
    c_eta_str = f"{c_eta/60.0:.1f} min" if c_eta > 0 else "-"
    c_status = "Done" if c_done else "Downloading"
    print(f"| `pwr_cars.h5` | {format_bytes(c_size)} / {format_bytes(EXPECTED_CARS_SIZE)} | {c_pct:.2f}% | {c_speed_str} | {c_eta_str} | {c_status} |")
    
    print("\n---")
    
    # Check simulation status
    sim_procs = check_active_simulations()
    print("\n# Simulation Processes")
    if sim_procs:
        print(f"Active simulation processes found: {len(sim_procs)}")
        for proc in sim_procs:
            print(f"- **PID {proc['pid']}**: `{proc['cmd']}`")
    else:
        print("No active simulation processes found.")

    # Check simulation progress
    progress = count_simulation_results()
    print("\n# Simulation Progress (Completed Runs / 1000)")
    if progress:
        print("| Scenario | Nodes: 2 | Nodes: 3 | Nodes: 4 | Nodes: 5 |")
        print("| --- | --- | --- | --- | --- |")
        for scenario, node_counts in sorted(progress.items()):
            n2 = node_counts.get('2', 0)
            n3 = node_counts.get('3', 0)
            n4 = node_counts.get('4', 0)
            n5 = node_counts.get('5', 0)
            print(f"| {scenario.capitalize()} | {n2} | {n3} | {n4} | {n5} |")
    else:
        print("No simulation results generated yet.")

    # Compare results if available
    summaries = load_compare_results()
    if summaries:
        print("\n# Results Comparison (BFND vs FIND)")
        print("| File | Runs | BFND Mean | FIND Mean | BFND TO | FIND TO |")
        print("| --- | --- | --- | --- | --- | --- |")
        for s in summaries:
            bfnd_mean = f"{s.bfnd_mean:.1f}" if s.bfnd_mean is not None else "-"
            find_mean = f"{s.find_mean:.1f}" if s.find_mean is not None else "-"
            print(f"| `{s.path.name}` | {s.total_rows} | {bfnd_mean} | {find_mean} | {s.ours_missing} | {s.baseline_missing} |")

    # Timing metrics
    times = parse_simulation_times()
    if times:
        print("\n# Simulation Execution Times")
        print("| Config | Total Wall Time | Runs | Amortized Wall Time/Run | Est. CPU Time/Run (15 workers) |")
        print("| --- | --- | --- | --- | --- |")
        for t in times:
            wall = t['time_seconds']
            avg_wall = wall / 1000.0
            avg_cpu = (wall * 15) / 1000.0
            print(f"| `{t['config']}` | {wall:.2f} s | 1000 | {avg_wall*1000:.1f} ms | {avg_cpu:.3f} s |")
            
    # Output triggers
    if j_done and c_done:
        print("\n[ALL_DOWNLOADS_COMPLETE]")
    else:
        print("\n[DOWNLOADS_IN_PROGRESS]")

def parse_simulation_times():
    import re
    log_dir = WORKSPACE_DIR / "logs"
    times = []
    for log_file in sorted(log_dir.glob("simulation_comparison_config_*.log.txt")):
        if "worker" in log_file.name:
            continue
        try:
            with open(log_file, 'r') as f:
                content = f.read()
            matches = re.findall(r"Completed remaining simulations for config '([^']+)' in ([\d\.]+) seconds", content)
            for match in matches:
                times.append({
                    "config": match[0],
                    "time_seconds": float(match[1])
                })
        except Exception:
            pass
    # Deduplicate by config name keeping the latest
    dedup = {}
    for t in times:
        dedup[t['config']] = t
    return sorted(dedup.values(), key=lambda x: x['config'])

if __name__ == "__main__":
    main()
