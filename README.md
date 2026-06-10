# BFND Simulator

A Python-based simulator for Battery-Free Neighbor Discovery (BFND). This project compares a custom protocol (`BFND`) against a baseline protocol (`Find`) for discovering neighbors in intermittent, battery-free IoT devices.

## Features

- **Asynchronous & Process-Level Parallelization**: Uses Python `asyncio` and `ProcessPoolExecutor` to parallelize multiple simulation runs concurrently across all CPU cores.
- **HDF5 Energy Traces**: Supports replaying file-based energy harvesting traces via HDF5 files.
- **Configurable**: Configured via a central `config.yaml` file to define simulation environments, node/capacitor settings, and harvesting profiles.

## Setup Instructions

To run the simulator locally, we recommend setting up a Python virtual environment:

1. **Create a virtual environment**:
   ```bash
   python3 -m venv venv
   ```

2. **Activate the virtual environment**:
   - On Linux/macOS:
     ```bash
     source venv/bin/activate
     ```
   - On Windows:
     ```cmd
     .\venv\Scripts\activate
     ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Running the Simulator

To run the comparative neighbor discovery simulations:

```bash
python simulation_v2.py config.yaml
```

Logs will be generated under the `logs/` directory, and output TSV results containing the discovery times of the respective protocols will be saved in `results/`.

---

## Baseline Protocol Implementation (Find)

The simulator evaluates the custom protocol against a state-of-the-art baseline known as **Find** (from the NSDI'21 paper *Bootstrapping Battery-free Wireless Networks*). 

The Find protocol minimizes discovery latency by appending a random delay—drawn from a specific geometric distribution—after a node has sufficiently charged. To ensure an academically rigorous and perfectly fair comparison, we derived the optimum geometric distribution scale parameters exactly as implemented by the original authors.

**How the Scale Parameter is Derived:**
1. **Mathematical Optimization:** In the original research, the geometric distribution's scale parameter (`p`) is not fixed. It is dynamically chosen based on the node's expected charging time (in slots) using Brent's method to numerically minimize expected discovery latency.
2. **Lookup Table Integration:** The authors provided an optimization script (`opt_scale.csv`) mapping charging times to their theoretically optimal scale parameters.
3. **Runtime Interpolation:** Our `Find` protocol in `src/protocol/find.py` embeds this exact lookup table. During simulation, when a node acts under the baseline protocol, it dynamically adapts to its true, observed charging time (`current_t_chr = node.ASN - last_turn_off_time`) and performs a linear interpolation against this table.

For example, if a node's charging phase takes `1000` slots, it flawlessly interpolates to the paper's exact optimal scale parameter of `~0.02846` for its next advertising delay, ensuring the baseline dynamically operates at its absolute theoretical peak during comparative tests.
