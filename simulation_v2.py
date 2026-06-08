# --- Imports ---
from node import Node, RUN_TYPE
from radio import Radio
from clock import Clock
from harvester import Harvester, harvestingmode # REMOVED: DataReader import
from interface import Publisher, Subscriber
# Standard libraries
import argparse
import yaml
import random
import numpy as np
from numpy.random import SeedSequence, default_rng
from tqdm import tqdm
import logging
import time
import os
from multiprocessing import cpu_count, current_process
from concurrent.futures import ProcessPoolExecutor, as_completed
import json
import sys

# --- Argument Parsing ---
parser = argparse.ArgumentParser(description="Run Comparative Neighbor Discovery Simulation (Ours vs. Baseline)")
parser.add_argument("config_file", help="Path to the YAML configuration file")
args = parser.parse_args()
config_file = args.config_file

# --- Load Configuration ---
try:
    with open(config_file, 'r') as stream:
        config = yaml.load(stream, Loader=yaml.FullLoader)
except FileNotFoundError: print(f"FATAL ERROR: Config file '{config_file}' not found."); exit(1)
except yaml.YAMLError as exc: print(f"FATAL ERROR: Parsing YAML '{config_file}': {exc}"); exit(1)
except Exception as e: print(f"FATAL ERROR: Loading config: {e}"); exit(1)


# --- Get Logging Level from Config (with default) ---
log_level_str = config.get('log_level', 'INFO').upper()
log_level_map = {'DEBUG': logging.DEBUG, 'INFO': logging.INFO, 'WARNING': logging.WARNING, 'ERROR': logging.ERROR, 'CRITICAL': logging.CRITICAL}
log_level = log_level_map.get(log_level_str, logging.INFO)


# --- Logging Setup (Main Process Only) ---
log_dir = "./logs"
os.makedirs(log_dir, exist_ok=True)
timestamp = time.strftime('%Y%m%d_%H%M%S') # Generate timestamp once
log_filename_base = f"simulation_comparison_{os.path.basename(config_file).replace('.yaml','')}_{timestamp}.log.txt"
log_filepath = os.path.join(log_dir, log_filename_base)
main_file_handler = logging.FileHandler(log_filepath)
main_file_handler.setLevel(log_level)
main_file_formatter = logging.Formatter('%(asctime)s - %(process)d - %(levelname)s - %(name)s - %(message)s')
main_file_handler.setFormatter(main_file_formatter)
main_console_handler = logging.StreamHandler(stream=sys.stderr)
main_console_handler.setLevel(log_level)
main_console_formatter = logging.Formatter('%(levelname)s - %(name)s - %(message)s')
main_console_handler.setFormatter(main_console_formatter)
main_process_logger = logging.getLogger()
main_process_logger.setLevel(log_level)
for h in main_process_logger.handlers[:]: main_process_logger.removeHandler(h)
main_process_logger.addHandler(main_file_handler)
main_process_logger.addHandler(main_console_handler)
main_process_logger.info(f"Starting Comparative Simulation Run using config: {config_file}")
main_process_logger.info(f"Logging detailed output to: {log_filepath}")
main_process_logger.info(f"Initial logging level set to: {log_level_str}")


# --- Get Simulation Parameters & Log ---
try:
    NUM_SIMULATIONS = config.get('num_simulations', 100)
    RANDOM_SEED = config.get('random_seed', None) # Master seed
    CLOCK_FREQUENCY = config.get('clock_frequency', 1000)
    ENERGY_SCALING_FACTOR = config.get('energy_scaling_factor', 1e-2)
    DEFAULT_POWER_FACTOR = config.get('default_power_factor', 0.5)
    num_nodes_per_protocol = config['num_nodes']
    num_cycles = config['num_cycles'] # Used to control simulation length
    nodes_config_template = []
    for i in range(num_nodes_per_protocol):
        node_key = f'node{i + 1}'; nodes_config_template.append(config[node_key])

    main_process_logger.info(f"--- Simulation Settings ---")
    main_process_logger.info(f"NUM_SIMULATIONS: {NUM_SIMULATIONS}")
    main_process_logger.info(f"MASTER_RANDOM_SEED: {RANDOM_SEED if RANDOM_SEED is not None else 'Not Set (Random)'}")
    main_process_logger.info(f"CLOCK_FREQUENCY: {CLOCK_FREQUENCY}")
    main_process_logger.info(f"ENERGY_SCALING_FACTOR: {ENERGY_SCALING_FACTOR}")
    main_process_logger.info(f"DEFAULT_POWER_FACTOR: {DEFAULT_POWER_FACTOR}")
    main_process_logger.info(f"Nodes per protocol: {num_nodes_per_protocol}")
    main_process_logger.info(f"Cycles per run (Timeout Limit): {num_cycles}")
    main_process_logger.info(f"---------------------------")
    main_process_logger.info(f"--- Full Configuration Start ---\n{json.dumps(config, indent=2)}\n--- Full Configuration End ---")

except KeyError as e: main_process_logger.error(f"Error: Required key missing in config: {e}"); exit(1)
except Exception as e: main_process_logger.error(f"Error reading parameters: {e}"); exit(1)


def run_simulation(sim_num, config_params, run_seed_sequence):
    """ Runs a single instance of the comparative simulation. """
    sim_start_time = time.time()
    logger = logging.getLogger(f"SimRun_{sim_num}")
    logger.setLevel(config_params['log_level']) # Use global level for this logger too
    logger.propagate = True

    # Keep this at INFO - indicates start of a specific run
    logger.info(f"Starting simulation run {sim_num} on PID {os.getpid()}")

    # Access parameters
    current_clock_frequency = config_params['clock_frequency']
    current_num_nodes = config_params['num_nodes']
    current_nodes_config = config_params['nodes_config']
    current_num_cycles = config_params['num_cycles']
    current_default_power = config_params['default_power_factor']

    # --- Seed RNGs ---
    if run_seed_sequence is not None:
        # Reverted to INFO: Show seeding entropy for each run
        logger.info(f"Seeding RNGs with SeedSequence entropy: {run_seed_sequence.entropy}")
        random.seed(run_seed_sequence.entropy)
        rng = default_rng(run_seed_sequence)
    else:
        # Reverted to INFO: Indicate if no seed was provided
        logger.info("No specific run seed sequence provided, using system time/entropy.")
        rng = default_rng()

    # --- Setup Shared Resources (Clock, Radio Publishers) ---
    clock_publisher = Publisher("clock")
    global_clock = Clock(current_clock_frequency, clock_publisher)
    radio_publisher_ours = Publisher("radio_ours")
    radio_publisher_baseline = Publisher("radio_baseline")

    # --- Instantiate Components ---
    nodes_ours, radios_ours, harvesters_ours = [], [], []
    nodes_baseline, radios_baseline, harvesters_baseline = [], [], []
    try:
        # Set component log level based on global config (usually WARNING unless DEBUG is set)
        component_log_level = logging.DEBUG if config_params['log_level'] == logging.DEBUG else logging.WARNING
        harvester_log_level = component_log_level

        # Need to get file_path_to_use for Harvester if file mode is used
        file_path_to_use = None
        file_mode_needed = False # Use a flag
        for node_cfg_check in current_nodes_config:
             harvester_cfg_check = node_cfg_check.get('harvester', {})
             if harvester_cfg_check.get('harvesting_mode', '').lower() == 'file':
                  file_mode_needed = True # Set flag
                  file_path_to_use = harvester_cfg_check.get('file')
                  if not file_path_to_use:
                      logger.error("File mode specified but no file path.")
                      return 'SetupError', 'SetupError'
                  break # Found file path

        # Log file mode detection once if needed
        if file_mode_needed:
             # Reverted to INFO: Indicate if file mode is being used
             logger.info(f"File mode detected. Harvesters will use: {file_path_to_use}")

        for i in range(current_num_nodes):
            node_cfg = current_nodes_config[i]
            node_id_ours = i; node_id_baseline = i + current_num_nodes
            nominal_runtime = node_cfg.get('nominal_runtime', 1000)
            harvester_cfg = node_cfg.get('harvester', {})
            mode_str = harvester_cfg.get('harvesting_mode', 'constant').lower()
            current_file_path = file_path_to_use if mode_str == 'file' else None
            initial_file_offset = None

            # Harvester creation (no DataReader passed)
            harvester_ours = Harvester(harvestingmode[mode_str.upper()], clock_publisher, file_path=current_file_path, log_level=harvester_log_level, nominal_runtime=nominal_runtime)
            if mode_str == 'constant':
                 # ... (constant setup) ...
                 power = harvester_cfg.get('power', 'default')
                 if power == 'default':
                      cap=node_cfg['capacitance']; von=node_cfg['von']; voff=node_cfg['voff'];
                      energy_per_cycle = current_default_power * cap * (von**2 - voff**2); time_per_nom_cycle_s = nominal_runtime / current_clock_frequency
                      default_power_watts = energy_per_cycle / time_per_nom_cycle_s if time_per_nom_cycle_s > 0 else 0; power = default_power_watts / current_clock_frequency if current_clock_frequency > 0 else 0
                 else: power = float(power)
                 harvester_ours.set_constant(power)
            elif mode_str == 'gaussian':
                 # ... (gaussian setup) ...
                 cap=node_cfg['capacitance']; von=node_cfg['von']; voff=node_cfg['voff'];
                 time_per_nom_cycle_s = nominal_runtime / current_clock_frequency; energy_per_cycle = current_default_power * cap * (von**2 - voff**2)
                 default_power_watts = energy_per_cycle / time_per_nom_cycle_s if time_per_nom_cycle_s > 0 else 0; mean_power_per_tick = default_power_watts / current_clock_frequency if current_clock_frequency > 0 else 0
                 std_dev_factor = float(harvester_cfg.get('std', 0.1)); std_dev_per_tick = std_dev_factor * mean_power_per_tick
                 harvester_ours.set_gaussian(mean_power_per_tick, std_dev_per_tick)
            elif mode_str == 'file':
                 ts_in_file = 1 / current_clock_frequency
                 initial_file_offset = rng.integers(0, 2**31)
                 # Reverted to INFO: Show the initial offset chosen
                 logger.info(f"Node pair {i} ('ours' harvester) initial file offset: {initial_file_offset} (before modulo)")
                 harvester_ours.set_file(ts_in_file, initial_offset=initial_file_offset)
            harvesters_ours.append(harvester_ours)

            harvester_baseline = Harvester(harvestingmode[mode_str.upper()], clock_publisher, file_path=current_file_path, log_level=harvester_log_level, nominal_runtime=nominal_runtime)
            if mode_str == 'constant':
                 # ... (constant setup) ...
                 power = harvester_cfg.get('power', 'default')
                 if power == 'default':
                      cap=node_cfg['capacitance']; von=node_cfg['von']; voff=node_cfg['voff'];
                      energy_per_cycle = current_default_power * cap * (von**2 - voff**2); time_per_nom_cycle_s = nominal_runtime / current_clock_frequency
                      default_power_watts = energy_per_cycle / time_per_nom_cycle_s if time_per_nom_cycle_s > 0 else 0; power = default_power_watts / current_clock_frequency if current_clock_frequency > 0 else 0
                 else: power = float(power)
                 harvester_baseline.set_constant(power)
            elif mode_str == 'gaussian':
                 # ... (gaussian setup) ...
                 cap=node_cfg['capacitance']; von=node_cfg['von']; voff=node_cfg['voff'];
                 time_per_nom_cycle_s = nominal_runtime / current_clock_frequency; energy_per_cycle = current_default_power * cap * (von**2 - voff**2)
                 default_power_watts = energy_per_cycle / time_per_nom_cycle_s if time_per_nom_cycle_s > 0 else 0; mean_power_per_tick = default_power_watts / current_clock_frequency if current_clock_frequency > 0 else 0
                 std_dev_factor = float(harvester_cfg.get('std', 0.1)); std_dev_per_tick = std_dev_factor * mean_power_per_tick
                 harvester_baseline.set_gaussian(mean_power_per_tick, std_dev_per_tick)
            elif mode_str == 'file':
                 ts_in_file = 1 / current_clock_frequency
                 initial_file_offset = rng.integers(0, 2**31)
                 # Reverted to INFO: Show the initial offset chosen
                 logger.info(f"Node pair {i} ('baseline' harvester) initial file offset: {initial_file_offset} (before modulo)")
                 harvester_baseline.set_file(ts_in_file, initial_offset=initial_file_offset)
            harvesters_baseline.append(harvester_baseline)

            # Create Radios and Nodes
            radio_ours = Radio(loglevel=component_log_level); radios_ours.append(radio_ours)
            radio_baseline = Radio(loglevel=component_log_level); radios_baseline.append(radio_baseline)
            shared_node_offset = rng.integers(0, nominal_runtime)
            # Reverted to INFO: Show node offset
            logger.info(f"Node pair {i}: Shared node offset: {shared_node_offset} for 'ours'")
            node_ours = Node(id=node_id_ours, energy_harvester=harvester_ours, clock=clock_publisher, radio=radio_ours, offset=shared_node_offset, alpha=node_cfg['alpha'], capacitance=node_cfg['capacitance'], von=node_cfg['von'], voff=node_cfg['voff'], eadv=node_cfg['eadv'], escan=node_cfg['escan'], nominal_time_period=nominal_runtime, protocol_type='ours', rng=rng, runtype=RUN_TYPE[node_cfg.get('runtype', 'normal').upper()], log_level=component_log_level)
            nodes_ours.append(node_ours)
            node_baseline = Node(id=node_id_baseline, energy_harvester=harvester_baseline, clock=clock_publisher, radio=radio_baseline, offset=0, alpha=0, capacitance=node_cfg['capacitance'], von=node_cfg['von'], voff=node_cfg['voff'], eadv=node_cfg['eadv'], escan=0, nominal_time_period=nominal_runtime, protocol_type='baseline', rng=rng, runtype=RUN_TYPE.NORMAL, log_level=component_log_level)
            nodes_baseline.append(node_baseline)

        # --- Connect Radios ---
        for i in range(current_num_nodes):
            for j in range(current_num_nodes):
                if i != j:
                    radios_ours[i].connectto(radios_ours[j], radio_publisher_ours)
                    radios_baseline[i].connectto(radios_baseline[j], radio_publisher_baseline)
        # Reverted to INFO: Confirm radio connection
        logger.info("Radios connected.")

        # --- Simulation Loop ---
        nominal_runtime_first_node = current_nodes_config[0].get("nominal_runtime", 1000)
        if not isinstance(nominal_runtime_first_node, int) or nominal_runtime_first_node <= 0:
            logger.error(f"Invalid nominal_runtime '{nominal_runtime_first_node}'. Using 1000.")
            nominal_runtime_first_node = 1000
        total_slots = current_num_cycles * nominal_runtime_first_node
        # Reverted to INFO: Show loop start details
        logger.info(f"Starting simulation loop for {total_slots} slots (based on num_cycles).")
        discovery_asn_ours = 'N/A'; discovery_asn_baseline = 'N/A'
        ours_discovered = False; baseline_discovered = False
        all_nodes = nodes_ours + nodes_baseline
        all_radios = radios_ours + radios_baseline
        last_slot_run = -1

        for slot in range(total_slots):
            last_slot_run = slot
            global_clock.tick()
            for node in all_nodes: node.run_one_time_step()
            for i, radio in enumerate(radios_ours):
                 msg = radio.publish();
                 if msg: radio_publisher_ours.publish(msg)
            for i, radio in enumerate(radios_baseline):
                 msg = radio.publish();
                 if msg: radio_publisher_baseline.publish(msg)
            for radio in all_radios: radio.subscribe()
            for node in all_nodes: node.build_channel_map()

            # Keep discovery events as WARNING
            if not ours_discovered and nodes_ours[0].metrics['adv_success'] >= current_num_nodes - 1:
                discovery_asn_ours = slot; ours_discovered = True
                logger.warning(f"Ours discovered at ASN: {slot}")
            if not baseline_discovered and nodes_baseline[0].metrics['adv_success'] >= current_num_nodes - 1:
                discovery_asn_baseline = slot; baseline_discovered = True
                logger.warning(f"Baseline discovered at ASN: {slot}")

            if ours_discovered and baseline_discovered:
                logger.warning("Both discovered."); break

        # --- Check if loop finished due to reaching total_slots ---
        if not ours_discovered or not baseline_discovered:
             if last_slot_run >= total_slots - 1:
                 # Keep timeout warning
                 logger.warning(f"Simulation run {sim_num} reached max slots ({total_slots}) before full discovery.")
                 if not ours_discovered: discovery_asn_ours = 'Timeout'
                 if not baseline_discovered: discovery_asn_baseline = 'Timeout'

    except Exception as main_loop_error:
        logger.error(f"Error during run {sim_num}: {main_loop_error}", exc_info=True)
        if 'discovery_asn_ours' not in locals(): discovery_asn_ours = 'N/A'
        if 'discovery_asn_baseline' not in locals(): discovery_asn_baseline = 'N/A'
        discovery_asn_ours = 'RunError' if discovery_asn_ours == 'N/A' else discovery_asn_ours
        discovery_asn_baseline = 'RunError' if discovery_asn_baseline == 'N/A' else discovery_asn_baseline
    finally:
        # --- Simulation End & Cleanup ---
        if 'discovery_asn_ours' not in locals(): discovery_asn_ours = 'CleanupError'
        if 'discovery_asn_baseline' not in locals(): discovery_asn_baseline = 'CleanupError'
        if 'nodes_ours' not in locals(): nodes_ours = []
        if 'nodes_baseline' not in locals(): nodes_baseline = []
        if 'harvesters_ours' not in locals(): harvesters_ours = []
        if 'harvesters_baseline' not in locals(): harvesters_baseline = []

        sim_end_time = time.time()
        # Keep run summary as INFO
        logger.info(f"Run {sim_num} finished in {sim_end_time - sim_start_time:.2f}s. Ours={discovery_asn_ours}, Baseline={discovery_asn_baseline}")

        # Keep failure/timeout warnings
        if discovery_asn_ours == 'N/A': logger.warning(f"Ours failed to discover: {nodes_ours[0].metrics['adv_success'] if nodes_ours else 'N/A'}/{current_num_nodes - 1} found.")
        elif discovery_asn_ours == 'Timeout': logger.warning(f"Ours timed out (reached max slots).")

        if discovery_asn_baseline == 'N/A': logger.warning(f"Baseline failed to discover: {nodes_baseline[0].metrics['adv_success'] if nodes_baseline else 'N/A'}/{current_num_nodes - 1} found.")
        elif discovery_asn_baseline == 'Timeout': logger.warning(f"Baseline timed out (reached max slots).")

        # Close harvester subscribers
        all_harvesters = harvesters_ours + harvesters_baseline
        for h in all_harvesters:
             if hasattr(h, 'close'):
                 try: h.close()
                 except Exception as e: logger.warning(f"Error closing harvester subscriber for run {sim_num}: {e}")

    return discovery_asn_ours, discovery_asn_baseline


def worker_function(sim_num, config_params, run_seed_sequence, log_filepath):
    """
    Wrapper function for multiprocessing.
    Configures logging specifically for this worker process (file only).
    """
    # --- Worker Logging Setup ---
    worker_logger = logging.getLogger()
    for h in worker_logger.handlers[:]: worker_logger.removeHandler(h)
    
    # Avoid lock contention by writing to separate files per worker process
    base, ext = os.path.splitext(log_filepath)
    if base.endswith('.log'):
        base = base[:-4]
        worker_log_filepath = f"{base}_worker_{os.getpid()}.log.txt"
    else:
        worker_log_filepath = f"{base}_worker_{os.getpid()}{ext}"

    worker_file_handler = logging.FileHandler(worker_log_filepath)
    
    # Optimize worker logging level: suppress verbose INFO logs in workers to reduce file writes,
    # unless logging level is explicitly set to DEBUG.
    worker_log_level = config_params['log_level']
    if worker_log_level == logging.INFO:
        worker_log_level = logging.WARNING
        
    worker_file_handler.setLevel(worker_log_level)
    worker_formatter = logging.Formatter('%(asctime)s - %(process)d - %(levelname)s - %(name)s - %(message)s')
    worker_file_handler.setFormatter(worker_formatter)
    worker_logger.addHandler(worker_file_handler)
    worker_logger.setLevel(worker_log_level)

    # --- Run Simulation ---
    result_ours, result_baseline = 'Error', 'Error'
    try:
        result_ours, result_baseline = run_simulation(sim_num, config_params, run_seed_sequence)
    except Exception as e:
        logging.getLogger(f"WorkerCritical_{os.getpid()}").error(f"Sim {sim_num} failed critically in worker: {e}", exc_info=True)
    return result_ours, result_baseline

def main():
    """ Main function to run simulations in parallel and save results. """
    main_logger = logging.getLogger("main")
    main_logger.info(f"Starting {NUM_SIMULATIONS} comparative simulations.")
    num_workers = max(1, cpu_count() - 1)
    main_logger.info(f"Using {num_workers} worker processes.")

    # --- Generate child SeedSequence objects ---
    child_seed_sequences = [None] * NUM_SIMULATIONS
    if RANDOM_SEED is not None:
        main_logger.info(f"Generating {NUM_SIMULATIONS} child SeedSequences from master seed {RANDOM_SEED}...")
        ss = SeedSequence(RANDOM_SEED)
        child_seed_sequences = ss.spawn(NUM_SIMULATIONS)
        main_logger.info("Child SeedSequences generated.")
    else:
        main_logger.info("No master seed provided. Each run will use an independent random seed.")

    # --- Prepare config params for workers ---
    config_params_for_worker = {
        'clock_frequency': CLOCK_FREQUENCY, 'num_nodes': num_nodes_per_protocol,
        'nodes_config': nodes_config_template, 'num_cycles': num_cycles,
        'energy_scaling_factor': ENERGY_SCALING_FACTOR, 'default_power_factor': DEFAULT_POWER_FACTOR,
        'log_level': log_level
    }

    # --- Set Console Handler Level ---
    found_console_handler = False
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
            main_logger.info(f"Setting Console log level to CRITICAL+1 to suppress worker logs.")
            handler.setLevel(logging.CRITICAL + 1)
            found_console_handler = True
            break
    if not found_console_handler:
         main_logger.warning("Could not find StreamHandler in main process to adjust level.")

    start_time = time.time()
    results = []

    # --- Execute Runs in Parallel ---
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(worker_function, sim_num, config_params_for_worker, child_seed_sequences[sim_num], log_filepath): sim_num
                   for sim_num in range(NUM_SIMULATIONS)}
        with tqdm(total=NUM_SIMULATIONS, desc="Comparative Simulations", position=0, leave=True, file=sys.stdout, mininterval=1.0, maxinterval=10.0, smoothing=0.1) as progress_bar:
            for future in as_completed(futures):
                sim_num = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    main_logger.error(f"Error retrieving result for sim {sim_num}: {e}", exc_info=True)
                    results.append(('FutureError', 'FutureError'))
                progress_bar.update(1)

    end_time = time.time()
    main_logger.info(f"All {NUM_SIMULATIONS} simulations completed in {end_time - start_time:.2f} seconds.")

    # --- Save Results ---
    results_dir = "./results"
    os.makedirs(results_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(config_file))[0]
    results_filename = f"simulation_results_comparison_{base_name}_nodes{num_nodes_per_protocol}_cycles{num_cycles}_runs{NUM_SIMULATIONS}_{timestamp}.tsv.txt"
    results_filepath = os.path.join(results_dir, results_filename)
    try:
        with open(results_filepath, "w") as f:
            f.write("ASN_Ours\tASN_Baseline\n")
            for res_ours, res_baseline in results: f.write(f"{res_ours}\t{res_baseline}\n")
        main_logger.info(f"Comparison results saved to {results_filepath}")
    except IOError as e: main_logger.error(f"Error writing results to '{results_filepath}': {e}")
    except Exception as e: main_logger.error(f"Unexpected error writing results: {e}")


if __name__ == "__main__":
    main()
