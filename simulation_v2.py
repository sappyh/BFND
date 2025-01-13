## import all the classes
from node import Node, RUN_TYPE, RADIO_STATE
from radio import Radio
from clock import Clock
from multiprocessing import cpu_count, Manager
from harvester import Harvester, harvestingmode
from interface import Publisher, Subscriber
import yaml
import random
from tqdm import tqdm
import logging
import time
import os
import multiprocessing

## Constants
CLOCK_FREQUENCY = 1000
ENERGY_SCALING_FACTOR = 1e-2
DEFAULT_POWER_FACTOR = 0.5
NUM_SIMULATIONS = 10000
level = logging.INFO

## Take the name of the config file and debug file from the command line
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("config_file", help="The name of the config file")
parser.add_argument("debug_file", help="The name of the debug file")
args = parser.parse_args()
config_file = args.config_file
debug_file = args.debug_file

## Create dictionary objects from config.yaml file
with open(config_file, 'r') as stream:
    try:
        config = yaml.load(stream, Loader=yaml.Loader)
    except yaml.YAMLError as exc:
        print(exc)

## Get the number of nodes
num_nodes = config['num_nodes']
## Get the number of simulation slots
num_cycles = config['num_cycles']
## Create dictionary objects for each of the n nodes and save it in an array
nodes_config = []
for i in range(num_nodes):
    nodes_config.append(config['node' + str(i + 1)])


def run_simulation():
    ## Instantiate a radio, clock, and harvester
    clock_publisher = Publisher("clock")

    ## For each node create a node object and save it in an array using the nodes_config array

    nodes = []
    radios = []
    harvesters = []
    for i in range(num_nodes):
        radio = Radio(loglevel=logging.DEBUG)
        radios.append(radio)
        clock = Clock(CLOCK_FREQUENCY, clock_publisher)
        if nodes_config[i].get('harvester').get('harvesting_mode') == 'constant':
            power = nodes_config[i].get('harvester').get('power')
            if power == "default":
                power = (DEFAULT_POWER_FACTOR * nodes_config[i].get('capacitance') * (
                        nodes_config[i].get('von') ** 2 - nodes_config[i].get('voff') ** 2)) / nodes_config[i].get(
                    'nominal_runtime')
            else:
                power = float(power)
            harvester = Harvester(harvestingmode.CONSTANT, "none", clock_publisher)
            harvester.set_constant(power)
            harvesters.append(harvester)
        elif nodes_config[i].get('harvester').get('harvesting_mode') == 'gaussian':
            mean = DEFAULT_POWER_FACTOR * nodes_config[i].get('capacitance') * (
                    nodes_config[i].get('von') ** 2 - nodes_config[i].get('voff') ** 2) / nodes_config[i].get(
                'nominal_runtime')
            std = float(nodes_config[i].get('harvester').get('std')) * mean
            harvester = Harvester(harvestingmode.GAUSSIAN, "none", clock_publisher)
            harvester.set_gaussian(mean, std)
            harvesters.append(harvester)
        elif nodes_config[i].get('harvester').get('harvesting_mode') == 'file':
            file = nodes_config[i].get('harvester').get('file')
            harvester = Harvester(harvestingmode.FILE, file, clock_publisher)
            harvester.set_file(file, ENERGY_SCALING_FACTOR)
            harvesters.append(harvester)
        offset = random.randint(0, nodes_config[i].get('nominal_runtime') - 1)

        runtype = RUN_TYPE.NORMAL
        if (nodes_config[i].get('runtype') == 'normal'):
            runtype = RUN_TYPE.NORMAL
        elif (nodes_config[i].get('runtype') == 'scanning'):
            runtype = RUN_TYPE.SCANNING
        elif (nodes_config[i].get('runtype') == 'advertising'):
            runtype = RUN_TYPE.ADVERTISING

        node = Node(i, harvester, clock_publisher, radio, offset,
                    nodes_config[i].get('alpha'),
                    nodes_config[i].get('capacitance'),
                    nodes_config[i].get('von'),
                    nodes_config[i].get('voff'),
                    nodes_config[i].get('eadv'),
                    nodes_config[i].get('escan'),
                    nodes_config[i].get('nominal_runtime'), num_cycles,
                    runtype, log_level=logging.INFO)
        nodes.append(node)

    ## Connect the radios to one another
    i = 0
    for j in range(num_nodes):
        if i != j:
            radios[i].connectto(radios[j])
            radios[j].connectto(radios[i])

    ## Run the simulation
    ## Create threads for each node

    for slot in range(num_cycles * nodes_config[0].get("nominal_runtime")):

        clock.tick()

        # Step 1: Update node states and prepare for the current time step
        for i in range(num_nodes):
            nodes[i].run_one_time_step()  # Handles internal state and energy updates

        # Step 2: Publish messages for communication
        for i in range(num_nodes):
            radios[i].publish()  # Make messages available for other nodes to process

        # Step 3: Process incoming messages
        for i in range(num_nodes):
            radios[i].subscribe()  # Update states based on received messages

        # Step 4: Update channel maps and metrics
        for i in range(num_nodes):
            nodes[i].build_channel_map()  # Adjust metrics and finalize action outcomes

        # Check if all nodes have been discovered
        if nodes[0].metrics['adv_success'] == num_nodes - 1:
            logging.info(f"Node 0 discovered all other nodes at ASN: {slot}")
            # Shutdown all subscribers
            for harvester in harvesters:
                harvester.close()
            return slot

    # If Node 0 fails to discover all other nodes, return 'N/A'
    logging.info(f"Node 0 discovered {nodes[0].metrics['adv_success']} out of {num_nodes - 1} neighbors.")
    # Shutdown all subscribers
    for harvester in harvesters:
        harvester.close()
    return 'N/A'


def worker_function(args):
    level, simulation_number = args

    logging.info(f"Worker {os.getpid()} started simulation {simulation_number}.")
    try:
        result = run_simulation()
        logging.info(f"Simulation {simulation_number} completed successfully on PID {os.getpid()}.")
    except Exception as e:
        logging.error(f"Simulation {simulation_number} failed with error: {e}")
        result = None
    return result


def main():
    # Start worker processes using concurrent.futures
    from concurrent.futures import ProcessPoolExecutor, as_completed

    with ProcessPoolExecutor(max_workers=cpu_count() - 1) as executor:
        futures = [
            executor.submit(worker_function, (level, sim_num)) for sim_num in range(NUM_SIMULATIONS)
        ]

        with tqdm(total=NUM_SIMULATIONS, desc="Overall Progress") as progress_bar:
            results = []
            for future in as_completed(futures):
                results.append(future.result())
                progress_bar.update(1)

    # Save results to file
    results_file = f"simulation_results_ourmethod_node{num_nodes}_cycles{num_cycles}_runs{NUM_SIMULATIONS}.txt"
    with open(results_file, "w") as f:
        for item in results:
            f.write(f"{item}\n")


if __name__ == "__main__":
    main()
