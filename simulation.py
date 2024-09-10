## import all the classes
from node import Node, RUN_TYPE, RADIO_STATE
from radio import Radio
from clock import Clock
import threading
from harvester import Harvester
from interface import Publisher, Subscriber
from time import sleep
import yaml
import random

from harvester import harvestingmode

import logging


## Take the name of the config file and debug file from the command line
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("config_file", help="The name of the config file")
parser.add_argument("debug_file", help="The name of the debug file")
args = parser.parse_args()
config_file = args.config_file
debug_file = args.debug_file

## In case of an error, print the example usage
if config_file == None or debug_file == None:
    print("Usage: python simulation.py <config_file> <debug_file>")
    exit()

logging.basicConfig(filename=debug_file,level = logging.DEBUG)

## Create dictionary objects from config.yaml file
with open(config_file, 'r') as stream:
    try:
        config = yaml.load(stream, Loader=yaml.Loader)
    except yaml.YAMLError as exc:
        print(exc)

## Get the number of nodes
num_nodes = config['num_nodes']

## Get the number of similation slots
num_cycles = config['num_cycles']

## Create dictionary objects for each of the n nodes and save it in an array
nodes_config = []
for i in range(num_nodes):
    nodes_config.append(config['node'+str(i+1)])

# print(nodes_config)

  
    


def run_simulation():
    ## Instantiate a radio, clock , and harvester
    clock_publisher = Publisher("clock")

    ## For each node create a node object and save it in an array using the nodes_config array

    nodes = []
    radios=[]
    harvesters = []
    for i in range(num_nodes):
        radio = Radio(loglevel=logging.DEBUG)
        radios.append(radio)
        clock = Clock(1000000, clock_publisher)
        if nodes_config[i].get('harvester').get('harvesting_mode') == 'constant':
            power = nodes_config[i].get('harvester').get('power')
            if power == "default":
                power = (0.5 * nodes_config[i].get('capacitance')* (nodes_config[i].get('von')**2 - nodes_config[i].get('voff')**2))/ nodes_config[i].get('nominal_runtime')
            else:
                power = float(power)
            harvester = Harvester(harvestingmode.CONSTANT, "none", clock_publisher)
            harvester.set_constant(power)
            harvesters.append(harvester)
        elif nodes_config[i].get('harvester').get('harvesting_mode') == 'gaussian':
            # mean = float(nodes_config[i].get('harvester').get('mean'))
            mean = 0.5 * nodes_config[i].get('capacitance')* (nodes_config[i].get('von')**2 - nodes_config[i].get('voff')**2)/ nodes_config[i].get('nominal_runtime')
            std = float(nodes_config[i].get('harvester').get('std')) * mean
            harvester = Harvester(harvestingmode.GAUSSIAN, "none", clock_publisher)
            harvester.set_gaussian(mean, std)
            harvesters.append(harvester)
        elif nodes_config[i].get('harvester').get('harvesting_mode') == 'file':
            file = nodes_config[i].get('harvester').get('file')
            harvester = Harvester(harvestingmode.FILE, file, clock_publisher)
            harvester.set_file(file, 1e-2)
            harvesters.append(harvester)
        offset = random.randint(0, nodes_config[i].get('nominal_runtime')-1)

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
    # for i in range(num_nodes):
    ## Temporary assumption where we look at the discovery time of one node, considering it is in a star network
    i= 0
    for j in range(num_nodes):
            if i != j:
                # print("Connecting radio " + str(i) + " to radio " + str(j))
                radios[i].connectto(radios[j])
                radios[j].connectto(radios[i])

    ## Run the simulation
    ## Create threads for each node
    slot = 0
    done = False
    while slot < num_cycles * nodes_config[0].get("nominal_runtime") and done == False:
        clock.tick()
        slot = slot + 1

        ## Create a thread for each node and run one time step
        # threads= []
        # for i in range(num_nodes):
        #     t = threading.Thread(target=nodes[i].run_one_time_step)
        #     threads.append(t)
        
        # for t in threads:
        #     t.start()
        
        # for t in threads:
        #     t.join()
        
        # threads = []
        # ## Run the publish on all radios in separate threads
        # for i in range(num_nodes):
        #     t = threading.Thread(target=radios[i].publish)
        #     threads.append(t)

        # for t in threads:
        #     t.start()
        
        # for t in threads:
        #     t.join()
        
        # threads = []
        # ## Run the subscribe on all radios in separate threads
        # for i in range(num_nodes):
        #     t = threading.Thread(target=radios[i].subscribe)
        #     threads.append(t)
        
        # for t in threads:
        #     t.start()
        
        # for t in threads:
        #     t.join()
        
        # threads = []
        # ## Run the build channel map on all nodes
        # for i in range(num_nodes):
        #     t = threading.Thread(target=nodes[i].build_channel_map)
        #     threads.append(t)
        
        # for t in threads:
        #     t.start()
        
        # for t in threads:
        #     t.join()

        for i in range(num_nodes):
            nodes[i].run_one_time_step()
        
        for i in range(num_nodes):
            radios[i].publish()
        
        for i in range(num_nodes):
            radios[i].subscribe()
        
        for i in range(num_nodes):
            nodes[i].build_channel_map()
        
        if nodes[0].metrics['adv_success'] == num_nodes -1:
            print("Node discovered all other nodes at ASN:" + str(slot))
            return slot


import multiprocessing as mp
from tqdm import tqdm

nSimulation = 1000
results = []

def worker_function(simulation_number):
    print("Simulation number: " + str(simulation_number + 1))
    slot = run_simulation()
    return slot

# for i in range(nSimulation):
#     print("Simulation number: " + str(i+1))
    
#     ## Run the simulation using multiprocessing
    
    
    
#     slot = run_simulation()
#     results.append(slot)
#     print("Number of slots: " + str(slot))
#     print("Simulation number: " + str(i+1) + " completed")
#     print("-------------------------------------------------")

## Boxplot of the results using sns
# import matplotlib.pyplot as plt
# plt.boxplot(results)
# plt.xlabel("Number of slots")  
# plt.ylabel("Simulation number")
# plt.savefig("simulation_results_ourmethod.png")

# import seaborn as sns
# import matplotlib.pyplot as plt
# sns.boxplot(results)
# plt.xlabel("Number of slots")
# plt.ylabel("Simulation number")
# plt.savefig("simulation_results_ourmethod.png")

## Save the results to a file
import cProfile
import pstats

if __name__ == '__main__':
    pool = mp.Pool(mp.cpu_count())
    ## Run the simulation using multiprocessing and get progress bar
    # results = tqdm(pool.imap(worker_function, range(nSimulation)), total=nSimulation)
    
    results = pool.map(worker_function, range(nSimulation))
    pool.close()
    pool.join()
    
    with open("simulation_results_ourmethod_node5_1000.txt", "w") as f:
        for item in results:
            f.write("%s\n" % item)
    ## Profile the code
    
    # with cProfile.Profile() as profile:
    #     run_simulation()
    
    # profile.dump_stats("simulation.prof")
    # p = pstats.Stats("simulation.prof")
    # p.sort_stats("cumulative")
    # p.print_stats()
    

    