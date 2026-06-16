import os
import yaml
import subprocess
import csv
import statistics
from pathlib import Path

# Sweeps definition
datasets = ["washer", "office", "stairs"]
# A list of dictionaries defining the sweep
sweeps = [
    # Sweep 1: Alpha
    {"sweep_type": "alpha", "sweep_value": "0.5", "alpha": 0.5, "capacitance": 22.0e-6},
    {"sweep_type": "alpha", "sweep_value": "0.7", "alpha": 0.7, "capacitance": 22.0e-6},
    {"sweep_type": "alpha", "sweep_value": "0.9", "alpha": 0.9, "capacitance": 22.0e-6},
    
    # Sweep 2: Capacitance (Alpha = 0.7, 22uF is already covered above)
    {"sweep_type": "capacitance", "sweep_value": "47uF", "alpha": 0.7, "capacitance": 47.0e-6},
    {"sweep_type": "capacitance", "sweep_value": "100uF", "alpha": 0.7, "capacitance": 100.0e-6},
]

# Set up directories
os.makedirs("parameter_sweeps/configs", exist_ok=True)
os.makedirs("parameter_sweeps/results", exist_ok=True)

# Determine python executable
python_cmd = "venv/bin/python" if os.path.exists("venv") else "python"

num_simulations = 1000
num_nodes = 5
results = []

for dataset in datasets:
    base_config_path = f"comparison_configs/config_{dataset}_bfnd.yaml"
    if not os.path.exists(base_config_path):
        print(f"Base config {base_config_path} not found. Skipping...")
        continue
        
    with open(base_config_path, "r") as f:
        base_config = yaml.safe_load(f)
        
    for sweep in sweeps:
        alpha = sweep["alpha"]
        capacitance = sweep["capacitance"]
        
        # We uniquely name the config to avoid collisions and track it
        # Replace decimal point in sweep_value with an underscore or just use it if it's safe
        config_name = f"config_{dataset}_bfnd_alpha_{str(alpha).replace('.', 'p')}_cap_{sweep['sweep_value']}"
        temp_config_path = f"parameter_sweeps/configs/{config_name}.yaml"
        
        # Modify the config
        modified_config = yaml.safe_load(yaml.dump(base_config)) # deep copy
        for i in range(1, num_nodes + 1):
            node_key = f"node{i}"
            if node_key in modified_config:
                modified_config[node_key]["alpha"] = alpha
                modified_config[node_key]["capacitance"] = capacitance
                
        # Write modified config
        with open(temp_config_path, "w") as f:
            yaml.dump(modified_config, f, default_flow_style=False)
            
        print(f"Running simulation for {dataset} - {sweep['sweep_type']}: {sweep['sweep_value']}")
        # Run simulation
        cmd = [python_cmd, "simulation_v2.py", temp_config_path, "--num_nodes", str(num_nodes), "--num_simulations", str(num_simulations)]
        subprocess.run(cmd, check=True)
        
        tsv_path = f"results/{dataset}/results_{config_name}_{num_nodes}.tsv"
        
        if not os.path.exists(tsv_path):
            print(f"Error: Output file {tsv_path} not found!")
            continue
            
        # Read the TSV and calculate metrics
        asn_values = []
        timeouts = 0
        with open(tsv_path, "r") as f:
            reader = csv.DictReader(f, delimiter="\t")
            asn_col = f"ASN_{config_name}"
            
            if reader.fieldnames and asn_col in reader.fieldnames:
                for row in reader:
                    val = row.get(asn_col)
                    if val and val not in ["", "N/A", "Timeout", "RunError", "FutureError"]:
                        try:
                            asn_values.append(int(float(val)))
                        except ValueError:
                            timeouts += 1
                    else:
                        timeouts += 1
            else:
                print(f"Warning: Column {asn_col} not found in {tsv_path}")
                timeouts = num_simulations
        
        def get_percentile(data, p):
            if not data:
                return "N/A"
            sdata = sorted(data)
            k = (len(sdata) - 1) * p / 100.0
            f = int(k)
            c = f + 1
            if c >= len(sdata):
                return sdata[-1]
            return sdata[f] + (k - f) * (sdata[c] - sdata[f])
            
        p5 = get_percentile(asn_values, 5)
        p25 = get_percentile(asn_values, 25)
        median = get_percentile(asn_values, 50)
        p75 = get_percentile(asn_values, 75)
        p95 = get_percentile(asn_values, 95)
        mean_asn = statistics.fmean(asn_values) if asn_values else "N/A"
        
        results_dict = {
            "Dataset": dataset,
            "Sweep_Type": sweep["sweep_type"],
            "Sweep_Value": sweep["sweep_value"],
            "Alpha": alpha,
            "Capacitance": capacitance,
            "Mean_ASN": mean_asn,
            "P5_ASN": p5,
            "P25_ASN": p25,
            "Median_ASN": median,
            "P75_ASN": p75,
            "P95_ASN": p95,
            "Timeouts": timeouts
        }
        results.append(results_dict)
        
        # Append to CSV incrementally
        output_csv = "parameter_sweeps/sweep_results.csv"
        file_exists = os.path.exists(output_csv)
        fieldnames = ["Dataset", "Sweep_Type", "Sweep_Value", "Alpha", "Capacitance", "Mean_ASN", "P5_ASN", "P25_ASN", "Median_ASN", "P75_ASN", "P95_ASN", "Timeouts"]
        with open(output_csv, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(results_dict)

print(f"Done! Results written to {output_csv}")
