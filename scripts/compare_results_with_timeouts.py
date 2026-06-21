import os
import csv
import glob

def parse_val(val):
    if val is None:
        return None
    val = val.strip()
    if val in ["", "N/A", "Timeout", "RunError", "FutureError"]:
        return None
    try:
        return int(val)
    except ValueError:
        try:
            return float(val)
        except ValueError:
            return None

def main():
    results_dir = "results"
    subdirs = ["office", "stairs", "washer", "jogging", "cars"]
    
    headers = [
        "Scenario", "Nodes", "Runs", 
        "BFND Success %", "FIND Success %", 
        "BFND Mean (slots)", "FIND Mean (slots)", 
        "Mean Delta", "BFND Wins", "FIND Wins", "Ties"
    ]
    
    rows = []
    
    for subdir in subdirs:
        path_pattern = os.path.join(results_dir, subdir, "results_config_*_*.tsv")
        files = sorted(glob.glob(path_pattern))
        for filepath in files:
            # Extract nodes from filename (e.g. results_config_office_bfnd_5.tsv -> 5)
            filename = os.path.basename(filepath)
            parts = filename.replace(".tsv", "").split("_")
            nodes = parts[-1]
            
            bfnd_values = []
            find_values = []
            
            bfnd_wins = 0
            find_wins = 0
            ties = 0
            total_runs = 0
            
            with open(filepath, "r") as f:
                reader = csv.reader(f, delimiter="\t")
                header_row = next(reader)
                
                # Check column indices
                bfnd_idx = 0
                find_idx = 1
                for idx, col in enumerate(header_row):
                    if "bfnd" in col.lower():
                        bfnd_idx = idx
                    elif "find" in col.lower():
                        find_idx = idx
                        
                for row in reader:
                    if len(row) < 2:
                        continue
                    total_runs += 1
                    bfnd = parse_val(row[bfnd_idx])
                    find = parse_val(row[find_idx])
                    
                    if bfnd is not None:
                        bfnd_values.append(bfnd)
                    if find is not None:
                        find_values.append(find)
                        
                    # Compare according to requested logic:
                    if bfnd is not None and find is not None:
                        if bfnd < find:
                            bfnd_wins += 1
                        elif find < bfnd:
                            find_wins += 1
                        else:
                            ties += 1
                    elif bfnd is not None and find is None:
                        # BFND succeeded, FIND timed out -> BFND Win
                        bfnd_wins += 1
                    elif find is not None and bfnd is None:
                        # FIND succeeded, BFND timed out -> FIND Win
                        find_wins += 1
                    else:
                        # Both timed out -> Tie
                        ties += 1
            
            bfnd_success_pct = f"{(len(bfnd_values) / total_runs) * 100:.2f}%" if total_runs > 0 else "-"
            find_success_pct = f"{(len(find_values) / total_runs) * 100:.2f}%" if total_runs > 0 else "-"
            
            bfnd_mean = f"{sum(bfnd_values)/len(bfnd_values):.2f}" if bfnd_values else "-"
            find_mean = f"{sum(find_values)/len(find_values):.2f}" if find_values else "-"
            
            # Paired mean delta for cases where both succeeded (or general delta if we want)
            # Let's show mean of (FIND - BFND) for paired successes
            paired_deltas = []
            with open(filepath, "r") as f:
                reader = csv.reader(f, delimiter="\t")
                next(reader)
                for row in reader:
                    if len(row) < 2:
                        continue
                    bfnd = parse_val(row[bfnd_idx])
                    find = parse_val(row[find_idx])
                    if bfnd is not None and find is not None:
                        paired_deltas.append(find - bfnd)
            
            mean_delta = f"{sum(paired_deltas)/len(paired_deltas):.2f}" if paired_deltas else "-"
            
            # For scenario column, capitalize the subdirectory name
            scenario_name = subdir.capitalize()
            
            rows.append([
                scenario_name, nodes, total_runs,
                bfnd_success_pct, find_success_pct,
                bfnd_mean, find_mean, mean_delta,
                bfnd_wins, find_wins, ties
            ])
            
    # Print as Markdown Table
    col_widths = [max(len(str(row[i])) for row in rows + [headers]) for i in range(len(headers))]
    
    def render_row(row):
        return "| " + " | ".join(str(cell).ljust(col_widths[idx]) for idx, cell in enumerate(row)) + " |"
        
    print(render_row(headers))
    print("| " + " | ".join("-" * w for w in col_widths) + " |")
    for row in rows:
        print(render_row(row))

if __name__ == "__main__":
    main()
