import sys
import os
import re
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

# Adjust paths to import compare_results
WORKSPACE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(WORKSPACE_DIR / "scripts"))
import compare_results

RESULTS_DIR = WORKSPACE_DIR / "results"
OUTPUT_PDF = WORKSPACE_DIR / "results_analysis.pdf"

def load_all_results(directory):
    data = {}
    
    if not directory.exists():
        return data
        
    for tsv_file in directory.glob("**/*.tsv"):
        scenario = tsv_file.parent.name
        
        # Extract node count from name
        name_parts = tsv_file.stem.split('_')
        try:
            nodes = int(name_parts[-1])
        except ValueError:
            continue
            
        try:
            summary = compare_results.load_summary(tsv_file)
        except Exception as e:
            print(f"Error loading {tsv_file}: {e}")
            continue
            
        if scenario not in data:
            data[scenario] = {}
        data[scenario][nodes] = summary
        
    return data

def generate_pdf():
    data = load_all_results(RESULTS_DIR)
    old_data = load_all_results(WORKSPACE_DIR / "results_1000_cycles")
    unpatched_data = load_all_results(WORKSPACE_DIR / "results_unpatched")
    if not data:
        print("No simulation results found to generate PDF.")
        return False
        
    print(f"Loaded results for scenarios: {list(data.keys())}")
    
    # Set plot style for academic paper look
    plt.rcParams.update({
        'font.size': 10,
        'axes.labelsize': 11,
        'axes.titlesize': 12,
        'xtick.labelsize': 9,
        'ytick.labelsize': 9,
        'figure.titlesize': 14,
        'font.family': 'serif',
        'grid.alpha': 0.3,
        'grid.linestyle': '--'
    })
    
    # Colors matching a professional academic palette (vibrant yet clean)
    color_bfnd = '#E68A00'      # Academic Amber
    color_find = '#CC3333'      # Professional Red
    
    with PdfPages(OUTPUT_PDF) as pdf:
        
        # ------------------ PAGE 1: TITLE & SUMMARY TABLE ------------------
        fig, ax = plt.subplots(figsize=(8.5, 11))
        ax.axis('off')
        
        # Title block
        fig.text(0.5, 0.95, "Battery-Free Neighbor Discovery (BFND) Simulation Analysis", 
                 ha='center', va='top', fontsize=15, weight='bold')
        fig.text(0.5, 0.92, "Comparative Evaluation: Pure BFND vs. FIND", 
                 ha='center', va='top', fontsize=12, style='italic')
        fig.text(0.5, 0.89, f"Generated on: {np.datetime64('now')}", 
                 ha='center', va='top', fontsize=9, color='gray')
        
        # Executive Summary text
        summary_text = (
            "Executive Summary:\n"
            "This report evaluates the performance of the Battery-Free Neighbor Discovery (BFND) protocol "
            "against the baseline FIND protocol under a realistic, non-phased asynchronous slotted time model. "
            "We compare two protocol configurations: (1) Pure BFND (deterministic slot selection, advDelay=0) "
            "and (2) FIND. Simulations were run using raw time-synchronized energy harvesting traces from 5 scenarios: "
            "Office, Stairs, Washer, Jogging, and Cars. Discovery latency is evaluated for networks of 2 to 5 nodes. "
            "A timeout is declared after 5,000 cycles."
        )
        fig.text(0.1, 0.80, summary_text, ha='left', va='top', fontsize=10, wrap=True)
        
        # Table of key results
        table_data = [["Scenario", "Nodes", "BFND Mean", "FIND Mean", "BFND-TO %", "FIND-TO %"]]
        
        for scenario in sorted(data.keys()):
            for nodes in sorted(data[scenario].keys()):
                if scenario in data and nodes in data[scenario]:
                    s = data[scenario][nodes]
                    total = s.total_rows if s.total_rows > 0 else 1
                    bfnd_mean = f"{s.bfnd_mean:.1f}" if s.bfnd_mean is not None else "Timeout"
                    find_mean = f"{s.find_mean:.1f}" if s.find_mean is not None else "Timeout"
                    bfnd_to_pct = f"{(s.bfnd_missing / total)*100:.1f}%"
                    find_to_pct = f"{(s.find_missing / total)*100:.1f}%"
                    
                    table_data.append([
                        scenario.capitalize(),
                        str(nodes),
                        bfnd_mean,
                        find_mean,
                        bfnd_to_pct,
                        find_to_pct
                    ])
                
        # Draw table
        if len(table_data) > 1:
            table = ax.table(cellText=table_data, loc='center', cellLoc='center', 
                             colWidths=[0.2, 0.1, 0.2, 0.2, 0.15, 0.15])
            table.auto_set_font_size(False)
            table.set_fontsize(8.5)
            # Make header bold
            for (row, col), cell in table.get_celld().items():
                if row == 0:
                    cell.set_text_props(weight='bold')
                    cell.set_facecolor('#E6F2FF')
                elif row % 2 == 0:
                    cell.set_facecolor('#F9F9F9')
                    
        pdf.savefig(fig)
        plt.close(fig)
        
        # ------------------ PAGE 2: IMPACT OF DRIFT, JITTER & BOUNDARY FIX ------------------
        fig, ax = plt.subplots(figsize=(8.5, 11))
        ax.axis('off')
        
        fig.text(0.5, 0.95, "Impact of Jitter, Clock Drift, and Cross-Slot Overlap Checks", 
                 ha='center', va='top', fontsize=13, weight='bold')
        fig.text(0.5, 0.92, "Comparing Unpatched (no sleep cost bug), Old (idealized slotted), and New (physical overlap) models", 
                 ha='center', va='top', fontsize=9, style='italic')
                 
        explanation = (
            "This section analyzes the transition of our simulator from the simplified discrete models to realistic continuous-time physics:\n"
            "- Unpatched Model: Had a critical energy accounting bug (sleep cost self.esleep was not deducted for FIND/idle states).\n"
            "  This gave nodes virtually unlimited sleep energy, causing artificially low timeout rates (~0-1%).\n"
            "- Old Model (Patched, No Drift/Overlap Fix): Sleep energy is correctly accounted for, but slot boundary overlaps\n"
            "  are strictly ignored. Nodes had to be in the exact same slot (self.ASN == message.ASN) to hear each other. This created blind spots\n"
            "  and inflated the timeout rate (~17-19% for 2 nodes, ~34-37% for 3 nodes).\n"
            "- New Model (With Drift/Overlap Fix): Models crystal frequency drift (+/-20 ppm), start jitter (+/-10 us), and absolute\n"
            "  physical continuous-time overlaps. This resolves the slot-boundary blind spots, recovering valid interactions\n"
            "  and successfully lowering timeout rates (~11-14% for 2 nodes, ~24-27% for 3 nodes)."
        )
        fig.text(0.08, 0.89, explanation, ha='left', va='top', fontsize=8.5, wrap=True)
        
        # Build comparison table
        comp_table_data = [["Scenario", "Nodes", "Model Version", "BFND Mean", "FIND Mean", "BFND-TO %", "FIND-TO %"]]
        for scenario in ('office', 'stairs', 'washer'):
            for nodes in (2, 3):
                # Unpatched row
                if scenario in unpatched_data and nodes in unpatched_data[scenario]:
                    u = unpatched_data[scenario][nodes]
                    u_tot = u.total_rows if u.total_rows > 0 else 1
                    comp_table_data.append([
                        scenario.capitalize(),
                        str(nodes),
                        "Unpatched (No Sleep Cost)",
                        f"{u.bfnd_mean:.1f}" if u.bfnd_mean is not None else "Timeout",
                        f"{u.find_mean:.1f}" if u.find_mean is not None else "Timeout",
                        f"{(u.bfnd_missing / u_tot)*100:.1f}%",
                        f"{(u.find_missing / u_tot)*100:.1f}%"
                    ])
                # Old row
                if scenario in old_data and nodes in old_data[scenario]:
                    o = old_data[scenario][nodes]
                    o_tot = o.total_rows if o.total_rows > 0 else 1
                    comp_table_data.append([
                        "",
                        "",
                        "Old (No Drift/Overlap Fix)",
                        f"{o.bfnd_mean:.1f}" if o.bfnd_mean is not None else "Timeout",
                        f"{o.find_mean:.1f}" if o.find_mean is not None else "Timeout",
                        f"{(o.bfnd_missing / o_tot)*100:.1f}%",
                        f"{(o.find_missing / o_tot)*100:.1f}%"
                    ])
                # New row
                if scenario in data and nodes in data[scenario]:
                    n = data[scenario][nodes]
                    n_tot = n.total_rows if n.total_rows > 0 else 1
                    comp_table_data.append([
                        "",
                        "",
                        "New (With Drift/Overlap)",
                        f"{n.bfnd_mean:.1f}" if n.bfnd_mean is not None else "Timeout",
                        f"{n.find_mean:.1f}" if n.find_mean is not None else "Timeout",
                        f"{(n.bfnd_missing / n_tot)*100:.1f}%",
                        f"{(n.find_missing / n_tot)*100:.1f}%"
                    ])
        
        # Render table
        if len(comp_table_data) > 1:
            table = ax.table(cellText=comp_table_data, loc='center', cellLoc='center',
                             colWidths=[0.14, 0.08, 0.32, 0.16, 0.16, 0.1, 0.1])
            table.auto_set_font_size(False)
            table.set_fontsize(7.5)
            # Styling: header, alternating rows, bolding version names
            for (row, col), cell in table.get_celld().items():
                if row == 0:
                    cell.set_text_props(weight='bold')
                    cell.set_facecolor('#E6F2FF')
                elif row > 0:
                    # Highlight 'New' row version in light green to show improvement
                    if (row - 1) % 3 == 2:
                        cell.set_facecolor('#E6F7E6')
                    elif (row - 1) % 3 == 1:
                        cell.set_facecolor('#FFF2E6')
                    else:
                        cell.set_facecolor('#FFFFFF')
                        
        pdf.savefig(fig)
        plt.close(fig)
        
        # ------------------ PAGE 3: LATENCY COMPARISON PLOTS ------------------
        scenarios = sorted(data.keys())
        fig, axes = plt.subplots(3, 2, figsize=(8.5, 11))
        axes = axes.flatten()
        
        fig.suptitle("Mean Discovery Latency comparison (ASNs)\n(Lower is better)", fontsize=13, y=0.98, weight='bold')
        
        for idx, scenario in enumerate(scenarios):
            ax = axes[idx]
            node_counts = sorted(data[scenario].keys())
            
            bfnd_means = []
            find_means = []
            valid_nodes = []
            
            for nodes in node_counts:
                s = data[scenario][nodes]
                bfnd_means.append(s.bfnd_mean if s.bfnd_mean is not None else np.nan)
                find_means.append(s.find_mean if s.find_mean is not None else np.nan)
                valid_nodes.append(nodes)
            
            if valid_nodes:
                ax.plot(valid_nodes, bfnd_means, marker='^', color=color_bfnd, label='BFND', linewidth=2)
                ax.plot(valid_nodes, find_means, marker='s', color=color_find, label='FIND', linewidth=2)
                
            ax.set_title(f"{scenario.capitalize()} Trace")
            ax.set_xlabel("Number of Nodes")
            ax.set_ylabel("Mean ASN")
            ax.set_xticks(node_counts)
            ax.grid(True)
            if idx == 0:
                ax.legend()
                
        # Hide any unused subplots
        for idx in range(len(scenarios), len(axes)):
            fig.delaxes(axes[idx])
            
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        pdf.savefig(fig)
        plt.close(fig)
        
        # ------------------ PAGE 4: TIMEOUT RATE COMPARISON ------------------
        fig, axes = plt.subplots(3, 2, figsize=(8.5, 11))
        axes = axes.flatten()
        
        fig.suptitle("Timeout/Failure Rates comparison (% of runs)\n(Lower is better)", fontsize=13, y=0.98, weight='bold')
        
        for idx, scenario in enumerate(scenarios):
            ax = axes[idx]
            node_counts = sorted(data[scenario].keys())
            
            bfnd_to = []
            find_to = []
            
            for nodes in node_counts:
                s = data[scenario][nodes]
                total = s.total_rows if s.total_rows > 0 else 1
                bfnd_to.append((s.bfnd_missing / total) * 100.0)
                find_to.append((s.find_missing / total) * 100.0)
                
            x = np.array(node_counts)
            width = 0.35
            
            ax.bar(x - width/2, bfnd_to, width, color=color_bfnd, label='BFND')
            ax.bar(x + width/2, find_to, width, color=color_find, label='FIND')
            
            ax.set_title(f"{scenario.capitalize()} Trace")
            ax.set_xlabel("Number of Nodes")
            ax.set_ylabel("Timeout Rate (%)")
            ax.set_xticks(node_counts)
            ax.grid(True, axis='y')
            if idx == 0:
                ax.legend()
                
        for idx in range(len(scenarios), len(axes)):
            fig.delaxes(axes[idx])
            
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        pdf.savefig(fig)
        plt.close(fig)
        
        # ------------------ PAGE 5: LATENCY CDF CURVES (3-node case) ------------------
        fig, axes = plt.subplots(3, 2, figsize=(8.5, 11))
        axes = axes.flatten()
        
        fig.suptitle("Cumulative Distribution Function (CDF) of Discovery Latency (3 Nodes)\n(Steeper/further left is better)", fontsize=13, y=0.98, weight='bold')
        
        target_nodes = 3
        
        for idx, scenario in enumerate(scenarios):
            ax = axes[idx]
            if target_nodes not in data[scenario]:
                ax.text(0.5, 0.5, f"No 3-node data for {scenario}", ha='center', va='center')
                ax.set_title(f"{scenario.capitalize()} Trace")
                continue
                
            s = data[scenario][target_nodes]
            
            # Compute CDFs
            if s.bfnd_values:
                sorted_bfnd = np.sort(s.bfnd_values)
                y_bfnd = np.arange(1, len(sorted_bfnd) + 1) / len(sorted_bfnd)
                y_bfnd = y_bfnd * (len(s.bfnd_values) / s.total_rows)
                ax.plot(sorted_bfnd, y_bfnd, color=color_bfnd, label='BFND', linewidth=2)
                
            if s.find_values:
                sorted_base = np.sort(s.find_values)
                y_base = np.arange(1, len(sorted_base) + 1) / len(sorted_base)
                y_base = y_base * (len(s.find_values) / s.total_rows)
                ax.plot(sorted_base, y_base, color=color_find, label='FIND', linewidth=2)
                
            ax.set_xscale('log')
            ax.set_title(f"{scenario.capitalize()} Trace")
            ax.set_xlabel("Discovery Latency (ASNs)")
            ax.set_ylabel("P(Discovery <= X)")
            ax.set_xlim(100, 1000000)
            ax.set_ylim(0, 1.0)
            ax.grid(True, which="both", ls="-")
            if idx == 0:
                ax.legend()
                
        for idx in range(len(scenarios), len(axes)):
            fig.delaxes(axes[idx])
            
        plt.tight_layout(rect=[0, 0, 1, 0.95])
        pdf.savefig(fig)
        plt.close(fig)
        
        # ------------------ PAGE 6: REPRESENTATIVE TIMELINE ------------------
        timeline_img_path = WORKSPACE_DIR / "timeline_comparison.png"
        if timeline_img_path.exists():
            fig, ax = plt.subplots(figsize=(8.5, 11))
            ax.axis('off')
            fig.text(0.5, 0.95, "Representative Protocol State & Voltage Timeline Comparison", 
                     ha='center', va='top', fontsize=13, weight='bold')
            fig.text(0.5, 0.92, "Capacitor voltages and active states (ADVERTISE / SCAN) over time", 
                     ha='center', va='top', fontsize=10, style='italic')
            
            img = plt.imread(str(timeline_img_path))
            ax_img = fig.add_axes([0.05, 0.1, 0.9, 0.75])
            ax_img.imshow(img)
            ax_img.axis('off')
            
            pdf.savefig(fig)
            plt.close(fig)
            
    print(f"Successfully generated results analysis PDF: {OUTPUT_PDF}")
    return True

if __name__ == "__main__":
    generate_pdf()
