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

---

## BFND Protocol Implementation

Unlike `Find` which relies on geometric random delays to resolve collisions, the **BFND** (Battery-Free Neighbor Discovery) protocol is designed to be deterministic yet highly resilient to slot synchronization errors, clock drift, and energy intermittency.

### How BFND Works:
1. **State Machine & Probabilistic Choice**: Upon power-on, a node enters either `ADVERTISEMENT` state (with probability $\alpha$) or `SCAN` state (with probability $1 - \alpha$).
2. **Deterministic Scheduling with Channel Maps**: 
   - When in the `ADVERTISEMENT` state, the node does not select random slots. Instead, it schedules its next advertisement slot deterministically.
   - By default, it schedules the advertisement to occur exactly at its assigned `offset` relative to the cycle start.
   - However, if the node has previously discovered advertisements on certain slots (learned during scanning), it updates a local **channel map** (`self.channel_map`). The node then calculates the delay to all candidate slots (the default `offset` and all discovered slots in its channel map) and selects the one with the smallest delay relative to the current slot, effectively prioritizing deterministic rendezvous while avoiding active neighbors' slots.
3. **Scan State & Energy Balancing**: In the `SCAN` state, the node scans for $N_{\text{scans}}$ back-to-back slots. This enables rapid discovery of any active advertising nodes. The number of scans per charge is dynamically balanced with advertisement energy:
   $$N_{\text{scans}} = \max\left(1, \left\lfloor \frac{E_{\text{adv}}}{E_{\text{scan}}} \right\rfloor\right)$$
   Since scanning is much less energy-intensive than advertising, this allows the node to maximize its listening window for each energy charge cycle.

### Micro Jitter, Clock Drift, and Bilateral Discovery:
To capture realistic physical hardware behaviors (such as nRF52840 clock crystals and execution jitter), the simulator incorporates micro-jitter and clock drift models:
1. **Clock Drift (ppm)**: Each node is initialized with a constant clock drift rate $\Delta f \in [-20\text{ ppm}, +20\text{ ppm}]$. Over time, the node's internal slot boundary drifts relative to the global simulation timeline:
   $$\text{phase\_shift} \leftarrow (\text{phase\_shift} + \text{elapsed\_slots} \times \Delta f) \pmod{1.0}$$
2. **Phase Micro-Jitter**: In addition to clock drift, every individual radio event (advertisement or scan) has a randomized **micro-jitter** (phase dithering) of $\pm 150\ \mu\text{s}$ (i.e., $\pm 0.15$ of a slot width) added to its phase boundary. This simulates latency jitter in software execution paths, radio startup delays, and crystal startup times.
3. **Bilateral Discovery Condition**: Under the asynchronous slotted model (`AsyncRadio`), discovery occurs when both nodes advertise in the *same* slot (`ACTION.ADVERTISE`). However, due to transceiver turnaround and physical timing constraints, they only hear each other if their relative physical starting phase difference falls within a specific window:
   $$88\ \mu\text{s} \le |t_1 - t_2| \le 840\ \mu\text{s}$$
   - If the phase difference is too small ($< 88\ \mu\text{s}$), the transmissions overlap too closely, causing packet collision and corruption.
   - If the phase difference is too large ($> 840\ \mu\text{s}$), one transmission finishes before the other starts listening, resulting in a mismatch.
   - **Crucially, the micro-jitter and clock drift are not just sources of noise; they are active mechanisms.** Over multiple cycles, the clock drift slowly slides the nodes' relative phase, and the $\pm 150\ \mu\text{s}$ micro-jitter dither ensures that their relative starting times will eventually land inside this successful bilateral discovery window during a slot when both choose to advertise.

---

### Slotted Synchronization Models: Phased (Flync) and Asynchronous (Non-Phased)

The simulator supports two models for slot-level synchronization between nodes:

1. **Asynchronous Slotted Model (Default)**:
   - Evaluated using the `AsyncRadio` radio module. Nodes do **not** have to have their slot boundaries phase-synchronized.
   - Each node is initialized with a random sub-slot phase shift ($\phi \in [-0.5, 0.5]$ ticks).
   - Radio transmissions (advertisements and scans) are evaluated in continuous time based on these phase shifts.
   - The radio checks for exact timing overlaps between concurrent transmissions to compute collisions (`check_tx_overlap`) and evaluates successful discovery based on the alignment of the scanning receiver window and the advertising transmission.

2. **Implicit Phase-Synchronized Model (Find + Flync)**:
   - Evaluated using the `SimpleRadio` module. This models a scenario where slot boundaries are perfectly phase-synchronized.
   - In the original NSDI'21 paper, **Flync** is an extension that exploits 50 Hz powerline flicker to give nodes a shared, phase-synchronized 100 Hz clock.
   - By forcing all node actions exactly onto the discrete $1.0\text{ ms}$ boundaries of the `GlobalClock`, this configuration simulates the exact performance benefits of a phase-locked shared clock.
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
