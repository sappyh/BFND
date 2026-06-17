# BFND Simulator

A Python-based simulator for Battery-Free Neighbor Discovery (BFND). This project compares a custom protocol (`BFND`) against a baseline protocol (`Find`) for discovering neighbors in intermittent, battery-free IoT devices.

## Features

- **Asynchronous & Process-Level Parallelization**: Uses Python `asyncio` and `ProcessPoolExecutor` to parallelize multiple simulation runs concurrently across all CPU cores.
- **HDF5 Energy Traces**: Supports replaying file-based energy harvesting traces via HDF5 files.
- **Configurable**: Configured via a central `config.yaml` file to define simulation environments, node/capacitor settings, and harvesting profiles.
- **Simulation Checkpointing & Resume**: Supports automatic checkpointing and resuming of long-running simulations. If a simulation is interrupted, it will automatically resume from the last completed run and append results dynamically to avoid data loss.

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
python simulation.py config.yaml
```

Logs will be generated under the `logs/` directory, and output TSV results containing the discovery times of the respective protocols will be saved in `results/`.

### Checkpointing & Resuming Simulations

The simulator features a robust resume system for long-running Monte Carlo simulations:
- **Automatic Resume**: When a simulation starts, it checks if the results file (e.g., `results/washer/results_config_washer_bfnd_5.tsv`) already exists and contains valid results. It will skip already completed runs and resume exactly where it was interrupted.
- **Incremental Writing**: Results are appended to the TSV file dynamically as each worker process finishes, ensuring no progress is lost in case of a crash, manual pause, or power interruption.

---

## Baseline Protocol Implementation (Find)

The simulator evaluates the custom protocol against a state-of-the-art baseline known as **Find** (from the NSDI'21 paper *Bootstrapping Battery-free Wireless Networks*). 

The Find protocol minimizes discovery latency by appending a random delay—drawn from a specific geometric distribution—after a node has sufficiently charged. To ensure an academically rigorous and perfectly fair comparison, we derived the optimum geometric distribution scale parameters exactly as implemented by the original authors.

**How the Scale Parameter is Derived:**
1. **Mathematical Optimization:** In the original research, the geometric distribution's scale parameter (`p`) is not fixed. It is dynamically chosen based on the node's expected charging time (in slots) using Brent's method to numerically minimize expected discovery latency.
2. **Lookup Table Integration:** The authors provided an optimization script (`opt_scale.csv`) mapping charging times to their theoretically optimal scale parameters.
3. **Runtime Interpolation:** Our `Find` protocol in `src/protocol/find.py` embeds this exact lookup table. During simulation, when a node acts under the baseline protocol, it dynamically adapts to its true, observed charging time (`current_t_chr = node.ASN - last_turn_off_time`) and performs a linear interpolation against this table.
4. **Mathematical Extrapolation for Dim Environments:** In the original repository, the lookup table only goes up to 2600 slots (2.6 seconds at a 1.0ms slot duration). However, in realistic indoor harvesting scenarios (like our `office` and `stairs` datasets), charging times can easily exceed 5 to 10 seconds (5000 to 10000 slots). To ensure the baseline doesn't suffer from suboptimal plateauing, we applied a fitted mathematical extrapolation ($p \approx 2.2896 \cdot t_{chr}^{-0.62955}$) for large charging times to correctly maintain theoretically optimal performance under any environment.

For example, if a node's charging phase takes `5000` slots (5 seconds), it seamlessly extrapolates the theoretically optimal scale parameter for its next advertising delay, ensuring the baseline operates at its peak during comparative tests.

### Implicit `Find + Flync` Simulation
It is important to note that because of the time-slotted nature of our simulator (where all nodes act exactly on the boundaries of the `1000 Hz` discrete `GlobalClock`), we are actually modeling **Find + Flync** rather than pure continuous-time Find.

In the original paper, "Flync" is an extension that exploits 50 Hz powerline flicker to give distributed nodes a shared, phase-synchronized 100 Hz clock, allowing them to discretize time into aligned slots and drastically boosting their collision probability. Because our simulator's architecture rigidly forces all actions onto a global 1.0ms grid, it implicitly simulates the exact benefits of this shared, phase-synchronized clock (albeit at 1000 Hz instead of 100 Hz).
### Active Discharging and `ACTION.BUSY_WAIT`

To address the race condition where a node remains permanently in the `ON` state after successfully transmitting an advertisement (due to high harvesting rates or large capacitance), the simulator replicates the physical active discharging behavior of the original Find firmware.

When a node using the `Find` protocol has no scheduled advertisement but remains in the `ON` state, it returns `ACTION.BUSY_WAIT` instead of `ACTION.SLEEP`. During this period, the radio is disabled, but the CPU remains active, causing it to consume active mode energy until it naturally drains below $V_{off}$ and resets.

**Energy Consumption Math:**
- **Active Current ($I$):** $103\ \mu\text{A}$ (based on MSP430FR5969 active current)
- **Voltage ($V$):** $3\text{ V}$
- **Active Power ($P$):** $103\ \mu\text{A} \times 3\text{ V} = 309\ \mu\text{W}$
- **Slot/Tick Duration ($t$):** $1\text{ ms}$
- **Energy Cost per Slot ($E_{\text{active}}$):** $309\ \mu\text{W} \times 1\text{ ms} = \mathbf{309\text{ nJ}}$ ($309 \times 10^{-9}\text{ J}$)

This active power consumption is handled in the `Node.do_action` method for `ACTION.BUSY_WAIT`, ensuring the simulation behaves identically in both the Python model and the C++ implementation.
