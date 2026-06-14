# --- Imports ---
from src.node.enums import RUN_TYPE, ACTION, STATE, RADIO_STATE
from src.node.builder import NodeBuilder
from src.radio.IRadio import RadioFactory
from src.clock.IClock import ClockFactory
from src.harvester.IHarvester import HarvesterFactory, harvestingmode
from src.messaging.Publisher import Publisher
from src.messaging.Subscriber import Subscriber
from src.protocol.IProtocol import ProtocolFactory

# Standard libraries
import argparse
import yaml
import random
import numpy as np
import h5py
from numpy.random import SeedSequence, default_rng
from tqdm import tqdm
import logging
import time
import os
import asyncio
from multiprocessing import cpu_count
from concurrent.futures import ProcessPoolExecutor
import json
import sys

# --- Argument Parsing ---
parser = argparse.ArgumentParser(description="Run Comparative Neighbor Discovery Simulation (BFND vs. Find)")
parser.add_argument("configs", nargs='+', help="Paths to configuration YAML files (e.g. config1.yaml config2.yaml)")
parser.add_argument("--num_nodes", type=int, default=None, help="Override number of nodes per protocol")
parser.add_argument("--num_simulations", type=int, default=None, help="Override number of simulations")
args = parser.parse_args()
config_files = args.configs
config_file = config_files[0]

# --- Load Configuration ---
configs = []
try:
    for c_file in config_files:
        with open(c_file, 'r') as stream:
            configs.append(yaml.load(stream, Loader=yaml.FullLoader))
    config = configs[0]
except FileNotFoundError as e:
    print(f"FATAL ERROR: Config file not found: {e}")
    exit(1)
except yaml.YAMLError as exc:
    print(f"FATAL ERROR: Parsing YAML: {exc}")
    exit(1)
except Exception as e:
    print(f"FATAL ERROR: Loading config: {e}")
    exit(1)

# --- Get Logging Level from Config (with default) ---
log_level_str = config.get('log_level', 'INFO').upper()
log_level_map = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}
log_level = log_level_map.get(log_level_str, logging.INFO)

# --- Logging Setup (Main Process Only) ---
log_dir = "./logs"
os.makedirs(log_dir, exist_ok=True)
timestamp = time.strftime('%Y%m%d_%H%M%S')
config_base_name = os.path.basename(config_file).replace('.yaml','')
log_filename_base = f"simulation_comparison_{config_base_name}_{timestamp}.log.txt"
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
for h in main_process_logger.handlers[:]:
    main_process_logger.removeHandler(h)
main_process_logger.addHandler(main_file_handler)
main_process_logger.addHandler(main_console_handler)

main_process_logger.info(f"Starting Comparative Simulation Run using config: {config_file}")
main_process_logger.info(f"Logging detailed output to: {log_filepath}")
main_process_logger.info(f"Initial logging level set to: {log_level_str}")

# --- Get Simulation Parameters & Log ---
try:
    NUM_SIMULATIONS = args.num_simulations if args.num_simulations is not None else config.get('num_simulations', 100)
    RANDOM_SEED = config.get('random_seed', None)
    CLOCK_FREQUENCY = config.get('clock_frequency', 1000)
    ENERGY_SCALING_FACTOR = config.get('energy_scaling_factor', 1e-2)
    DEFAULT_POWER_FACTOR = config.get('default_power_factor', 0.5)
    num_nodes_per_protocol = args.num_nodes if args.num_nodes is not None else config['num_nodes']
    config['num_nodes'] = num_nodes_per_protocol
    if args.num_simulations is not None:
        config['num_simulations'] = NUM_SIMULATIONS

    num_cycles = config['num_cycles']
    nodes_config_templates = []
    for c in configs:
        nodes_cfg = []
        for i in range(num_nodes_per_protocol):
            node_key = f'node{i + 1}'
            nodes_cfg.append(c[node_key])
        nodes_config_templates.append(nodes_cfg)
        
    # Remove unused nodes from config for clean logging
    for c in configs:
        for i in range(num_nodes_per_protocol + 1, 10):
            node_key = f'node{i}'
            if node_key in c:
                del c[node_key]

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

except KeyError as e:
    main_process_logger.error(f"Error: Required key missing in config: {e}")
    exit(1)
except Exception as e:
    main_process_logger.error(f"Error reading parameters: {e}")
    exit(1)
config_params_for_worker = {
    'clock_frequency': CLOCK_FREQUENCY,
    'num_nodes': num_nodes_per_protocol,
    'nodes_config_templates': nodes_config_templates,
    'configs': configs,
    'config_names': [os.path.basename(c).replace('.yaml', '') for c in config_files],
    'num_cycles': num_cycles,
    'energy_scaling_factor': ENERGY_SCALING_FACTOR,
    'default_power_factor': DEFAULT_POWER_FACTOR,
    'log_level': log_level
}

def setup_simulation_environment(config_params, run_seed_sequence, logger):
    current_clock_frequency = config_params['clock_frequency']
    current_num_nodes = config_params['num_nodes']
    nodes_config_templates = config_params['nodes_config_templates']
    configs = config_params['configs']
    current_default_power = config_params['default_power_factor']

    if run_seed_sequence is not None:
        random.seed(run_seed_sequence.entropy)
        rng = default_rng(run_seed_sequence)
    else:
        rng = default_rng()

    clock_publisher = Publisher("clock")
    global_clock = ClockFactory.create_clock(current_clock_frequency, clock_publisher)
    
    shared_harvesters = []
    shared_node_offsets = []
    
    nominal_runtime_first_node = nodes_config_templates[0][0].get("nominal_runtime", 1000)
    c0_nodes_cfg = nodes_config_templates[0]
    file_path_to_use = None
    for node_cfg in c0_nodes_cfg:
        if node_cfg.get('harvester', {}).get('harvesting_mode', '').lower() == 'file':
            file_path_to_use = node_cfg.get('harvester', {}).get('file')
            break
            
    shared_initial_file_offset = None
    if file_path_to_use:
        try:
            with h5py.File(file_path_to_use, 'r') as f:
                ts_in_file = 1 / current_clock_frequency
                samples_per_slot = 1
                if 'time' in f:
                    time_data = f['time']
                    if len(time_data) > 1:
                        ts_in_file = time_data[1] - time_data[0]
                        samples_per_slot = int(round((1 / current_clock_frequency) / ts_in_file))
                        samples_per_slot = max(1, samples_per_slot)
                
                dataset_length = len(f['data']['node0'])
                max_offset_samples = max(0, dataset_length - (nominal_runtime_first_node * samples_per_slot * config_params['num_cycles']))
                shared_initial_file_offset = rng.integers(0, max_offset_samples + 1)
        except Exception as e:
            logger.warning(f"Could not determine dataset length for initial offset: {e}")
            shared_initial_file_offset = 0

    component_log_level = logging.DEBUG if config_params['log_level'] == logging.DEBUG else logging.WARNING
    harvester_log_level = component_log_level

    for i in range(current_num_nodes):
        node_cfg = c0_nodes_cfg[i]
        nominal_runtime = node_cfg.get('nominal_runtime', 1000)
        harvester_cfg = node_cfg.get('harvester', {})
        mode_str = harvester_cfg.get('harvesting_mode', 'constant').lower()
        
        harvester = None
        if mode_str == 'constant':
            power = harvester_cfg.get('power', 'default')
            if power == 'default':
                cap = node_cfg['capacitance']
                von = node_cfg['von']
                voff = node_cfg['voff']
                energy_per_cycle = current_default_power * cap * (von**2 - voff**2)
                time_per_nom_cycle_s = nominal_runtime / current_clock_frequency
                default_power_watts = energy_per_cycle / time_per_nom_cycle_s if time_per_nom_cycle_s > 0 else 0
                power = default_power_watts / current_clock_frequency if current_clock_frequency > 0 else 0
            else:
                power = float(power)
            harvester = HarvesterFactory.create_harvester(
                harvestingmode.CONSTANT, clock_publisher, power=power, log_level=harvester_log_level, nominal_runtime=nominal_runtime
            )
        elif mode_str == 'gaussian':
            cap = node_cfg['capacitance']
            von = node_cfg['von']
            voff = node_cfg['voff']
            time_per_nom_cycle_s = nominal_runtime / current_clock_frequency
            energy_per_cycle = current_default_power * cap * (von**2 - voff**2)
            default_power_watts = energy_per_cycle / time_per_nom_cycle_s if time_per_nom_cycle_s > 0 else 0
            mean_power_per_tick = default_power_watts / current_clock_frequency if current_clock_frequency > 0 else 0
            std_dev_factor = float(harvester_cfg.get('std', 0.1))
            std_dev_per_tick = std_dev_factor * mean_power_per_tick
            harvester = HarvesterFactory.create_harvester(
                harvestingmode.GAUSSIAN, clock_publisher, mean=mean_power_per_tick, std=std_dev_per_tick, log_level=harvester_log_level, nominal_runtime=nominal_runtime
            )
        elif mode_str == 'file':
            ts_in_file = 1 / current_clock_frequency
            node_dataset_name = f"node{i}"
            harvester = HarvesterFactory.create_harvester(
                harvestingmode.FILE, clock_publisher, file_path=file_path_to_use, Ts=ts_in_file, initial_offset=shared_initial_file_offset, log_level=harvester_log_level, nominal_runtime=nominal_runtime, dataset_name=node_dataset_name
            )
        shared_harvesters.append(harvester)
        shared_node_offsets.append(rng.integers(0, nominal_runtime))

    networks = []
    for k, config_dict in enumerate(configs):
        protocol_name = config_dict.get('protocol', 'find').lower()
        network_nodes = []
        network_radios = []
        network_publishers = [Publisher(f"NBDiscovery_{k}_{i}") for i in range(current_num_nodes)]
        nodes_cfg = nodes_config_templates[k]
        
        for i in range(current_num_nodes):
            node_cfg = nodes_cfg[i]
            nominal_runtime = node_cfg.get('nominal_runtime', 1000)
            node_id = k * current_num_nodes + i
            
            harvester = shared_harvesters[i]
            shared_node_offset = shared_node_offsets[i]
            
            radio = RadioFactory.create_radio(publisher=network_publishers[i], log_level=component_log_level)
            network_radios.append(radio)
            
            protocol_logger = logging.getLogger(f"Protocol_{protocol_name}_{node_id}")
            protocol_logger.setLevel(component_log_level)
            
            protocol = ProtocolFactory.create_protocol(
                protocol_name,
                alpha=node_cfg.get('alpha', 0.5),
                eadv=node_cfg.get('eadv', 0),
                escan=node_cfg.get('escan', 0),
                offset=shared_node_offset,
                nominal_time_period=nominal_runtime,
                node_id=node_id,
                rng=rng,
                logger=protocol_logger,
            )
            
            node = (NodeBuilder()
                         .with_id(node_id)
                         .with_energy_harvester(harvester)
                         .with_clock(clock_publisher)
                         .with_radio(radio)
                         .with_protocol(protocol)
                         .with_energy_parameters(
                             capacitance=node_cfg['capacitance'],
                             von=node_cfg['von'],
                             voff=node_cfg['voff'],
                             v_brownout=node_cfg.get('v_brownout', 1.8),
                             eadv=node_cfg['eadv'],
                             v_max_thr=node_cfg.get('v_max_thr', 3.3)
                         )
                         .with_nominal_time_period(nominal_runtime)
                         .with_rng(rng)
                         .with_runtype(RUN_TYPE[node_cfg.get('runtype', 'normal').upper()])
                         .with_log_level(component_log_level)
                         .build())
            network_nodes.append(node)
            
        for j in range(1, current_num_nodes):
            network_radios[0].connectto(network_radios[j])
            
        networks.append({
            'nodes': network_nodes,
            'radios': network_radios,
            'publishers': network_publishers,
            'protocol_name': protocol_name,
            'config_name': config_params['config_names'][k]
        })
        
    return {
        'networks': networks,
        'global_clock': global_clock,
        'shared_harvesters': shared_harvesters,
        'rng': rng
    }

def execute_simulation_loop(env, total_slots, current_num_nodes, logger):
    networks = env['networks']
    global_clock = env['global_clock']

    discovery_asns = ['N/A'] * len(networks)
    network_discovered = [False] * len(networks)

    last_slot_run = -1
    for slot in range(total_slots):
        last_slot_run = slot
        global_clock.tick()
        
        for k, net in enumerate(networks):
            if not network_discovered[k]:
                for node in net['nodes']:
                    node.run_one_time_step()
        
        for k, net in enumerate(networks):
            if not network_discovered[k]:
                for radio in net['radios']:
                    radio.publish()
                
        for k, net in enumerate(networks):
            if not network_discovered[k]:
                for radio in net['radios']:
                    radio.subscribe()
            
        for k, net in enumerate(networks):
            if not network_discovered[k]:
                for node in net['nodes']:
                    node.evaluate_time_step()
            
        for k, net in enumerate(networks):
            if not network_discovered[k]:
                if net['nodes'][0].metrics.get('adv_success', 0) >= current_num_nodes - 1:
                    discovery_asns[k] = slot
                    network_discovered[k] = True
                    logger.warning(f"{net['config_name']} ({net['protocol_name']}) discovered at ASN: {slot}")
                    
                    for node in net['nodes']:
                        if hasattr(node, 'clock_subscriber') and node.clock_subscriber:
                            node.clock_subscriber.unsubscribe()
                        if hasattr(node, 'energy_harvester') and node.energy_harvester and hasattr(node.energy_harvester, 'clock_subscriber') and node.energy_harvester.clock_subscriber:
                            node.energy_harvester.clock_subscriber.unsubscribe()
                    
        if all(network_discovered):
            logger.warning("All networks discovered.")
            break

    if not all(network_discovered):
        if last_slot_run >= total_slots - 1:
            logger.warning(f"Reached max slots ({total_slots}) before full discovery.")
            for k in range(len(networks)):
                if not network_discovered[k]:
                    discovery_asns[k] = 'Timeout'

    return discovery_asns

def run_one_simulation(sim_num, config_params, run_seed_sequence):
    sim_start_time = time.time()
    logger = logging.getLogger(f"SimRun_{sim_num}")
    logger.setLevel(config_params['log_level'])
    logger.propagate = True

    logger.info(f"Starting simulation run {sim_num} on PID {os.getpid()}")

    current_num_nodes = config_params['num_nodes']
    current_num_cycles = config_params['num_cycles']
    current_nodes_config = config_params['nodes_config_templates'][0]

    env = None
    num_configs = len(config_params['configs'])
    discovery_asns = ['N/A'] * num_configs

    try:
        env = setup_simulation_environment(config_params, run_seed_sequence, logger)
        
        nominal_runtime_first_node = current_nodes_config[0].get("nominal_runtime", 1000)
        total_slots = current_num_cycles * nominal_runtime_first_node
        
        logger.info(f"Starting simulation loop for {total_slots} slots.")
        discovery_asns = execute_simulation_loop(env, total_slots, current_num_nodes, logger)

    except Exception as main_loop_error:
        logger.error(f"Error during run {sim_num}: {main_loop_error}", exc_info=True)
        discovery_asns = ['RunError' if asn == 'N/A' else asn for asn in discovery_asns]
    finally:
        shared_harvesters = env['shared_harvesters'] if env else []
        for h in shared_harvesters:
             if hasattr(h, 'close'):
                  try:
                      h.close()
                  except Exception as e:
                      logger.warning(f"Error closing harvester subscriber for run {sim_num}: {e}")

        sim_end_time = time.time()
        logger.info(f"Run {sim_num} finished in {sim_end_time - sim_start_time:.2f}s.")

    return discovery_asns

def worker_function(sim_num, config_params, run_seed_sequence, log_filepath):
    worker_logger = logging.getLogger()
    for h in worker_logger.handlers[:]:
        worker_logger.removeHandler(h)
    
    base, ext = os.path.splitext(log_filepath)
    if base.endswith('.log'):
        base = base[:-4]
        worker_log_filepath = f"{base}_worker_{os.getpid()}.log.txt"
    else:
        worker_log_filepath = f"{base}_worker_{os.getpid()}{ext}"

    worker_file_handler = logging.FileHandler(worker_log_filepath)
    
    worker_log_level = config_params['log_level']
    if worker_log_level == logging.INFO:
        worker_log_level = logging.WARNING
        
    worker_file_handler.setLevel(worker_log_level)
    worker_formatter = logging.Formatter('%(asctime)s - %(process)d - %(levelname)s - %(name)s - %(message)s')
    worker_file_handler.setFormatter(worker_formatter)
    worker_logger.addHandler(worker_file_handler)
    worker_logger.setLevel(worker_log_level)

    num_configs = len(config_params['configs'])
    results = ['Error'] * num_configs
    try:
        results = run_one_simulation(sim_num, config_params, run_seed_sequence)
    except Exception as e:
        logging.getLogger(f"WorkerCritical_{os.getpid()}").error(f"Sim {sim_num} failed critically in worker: {e}", exc_info=True)
    return results

async def main_async():
    main_logger = logging.getLogger("main")
    num_workers = max(1, cpu_count() - 1)

    trace_file_path = None
    for node_cfg in config_params_for_worker['nodes_config_templates'][0]:
        harvester_cfg = node_cfg.get('harvester', {})
        if harvester_cfg.get('harvesting_mode', '').lower() == 'file':
            trace_file_path = harvester_cfg.get('file')
            break
    sub_dir_name = 'default'
    if trace_file_path:
        base_fn = os.path.basename(trace_file_path)
        if base_fn.startswith('pwr_'):
            sub_dir_name = base_fn[4:]
        else:
            sub_dir_name = base_fn
        if sub_dir_name.endswith('.h5'):
            sub_dir_name = sub_dir_name[:-3]

    main_logger.warning(f"============================================================")
    main_logger.warning(f"Starting Simulation Set: Config '{config_base_name}' under '{sub_dir_name}'")
    main_logger.warning(f"============================================================")

    child_seed_sequences = [None] * NUM_SIMULATIONS
    if RANDOM_SEED is not None:
        main_logger.info(f"Generating {NUM_SIMULATIONS} child SeedSequences from master seed {RANDOM_SEED}...")
        ss = SeedSequence(RANDOM_SEED)
        child_seed_sequences = ss.spawn(NUM_SIMULATIONS)
    else:
        main_logger.info("No master seed provided. Each run will use an independent random seed.")

    # Remove the earlier config_params_for_worker since it was duplicated inside main_async
    # Oh wait, config_params_for_worker was created outside main_async in the original file! 
    # Yes, lines 510-520 are outside. Wait, no, they are inside main_async? Let's check!
    # Ah, let's just write the rest of the file exactly as needed.
    # We already have config_params_for_worker from the global scope.

    found_console_handler = False
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
            handler.setLevel(logging.CRITICAL + 1)
            found_console_handler = True
            break

    start_time = time.time()
    results = []

    loop = asyncio.get_running_loop()
    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        tasks = [
            loop.run_in_executor(
                executor,
                worker_function,
                sim_num,
                config_params_for_worker,
                child_seed_sequences[sim_num],
                log_filepath
            )
            for sim_num in range(NUM_SIMULATIONS)
        ]
        
        with tqdm(total=NUM_SIMULATIONS, desc=f"Config {config_base_name}", position=0, leave=True, file=sys.stdout, mininterval=1.0, maxinterval=10.0, smoothing=0.1) as progress_bar:
            for fut in asyncio.as_completed(tasks):
                try:
                    result = await fut
                    results.append(result)
                except Exception as e:
                    main_logger.error(f"Error retrieving result for run: {e}", exc_info=True)
                    results.append(['FutureError'] * len(config_params_for_worker['configs']))
                progress_bar.update(1)

    end_time = time.time()
    main_logger.warning(f"Completed config '{config_base_name}' in {end_time - start_time:.2f} seconds.")

    results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results', sub_dir_name)
    os.makedirs(results_dir, exist_ok=True)
    results_filename = f"results_{config_base_name}_{num_nodes_per_protocol}.tsv"
    results_filepath = os.path.join(results_dir, results_filename)
    try:
        with open(results_filepath, "w") as f:
            headers = [f"ASN_{name}" for name in config_params_for_worker['config_names']]
            f.write("\t".join(headers) + "\n")
            for res_row in results:
                f.write("\t".join(str(r) for r in res_row) + "\n")
        main_logger.warning(f"Results for config '{config_base_name}' saved to {results_filepath}")
    except IOError as e:
        main_logger.error(f"Error writing results to '{results_filepath}': {e}")
    except Exception as e:
        main_logger.error(f"Unexpected error writing results: {e}")

def main():
    asyncio.run(main_async())

if __name__ == "__main__":
    main()
