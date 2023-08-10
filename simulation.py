## import all the classes
from node import Node
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
logging.basicConfig(level = logging.INFO)

## Create dictionary objects from config.yaml file
with open("config.yaml", 'r') as stream:
    try:
        config = yaml.load(stream)
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

print(nodes_config)

## Instantiate a radio, clock , and harvester
clock_publisher = Publisher("clock")

## For each node create a node object and save it in an array using the nodes_config array

nodes = []
radios=[]
harvesters = []
for i in range(num_nodes):
    radios.append(Radio())
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
        mean = float(nodes_config[i].get('harvester').get('mean'))
        std = float(nodes_config[i].get('harvester').get('std'))
        harvester = Harvester(harvestingmode.GAUSSIAN, "none", clock_publisher)
        harvester.set_gaussian(mean, std)
        harvesters.append(harvester)
    elif nodes_config[i].get('harvester').get('harvesting_mode') == 'file':
        file = nodes_config[i].get('harvester').get('file')
        harvester = Harvester(harvestingmode.FILE, file, clock_publisher)
        harvesters.append(harvester)
    offset = random.randint(0, nodes_config[i].get('nominal_runtime')-1)

    node = Node(i+1, harvester, clock_publisher, radios[i], offset,
                nodes_config[i].get('alpha'),
                nodes_config[i].get('capacitance'),
                nodes_config[i].get('von'),
                nodes_config[i].get('voff'),
                nodes_config[i].get('eadv'),  
                nodes_config[i].get('escan'),
                nodes_config[i].get('nominal_runtime'), num_cycles)
    nodes.append(node)

## Connect the radios to one another
for i in range(num_nodes):
    for j in range(num_nodes):
        if i != j:
            radios[i].connectto(radios[j])

## Run the simulation
## Create threads for each node
slot = 0
while slot < num_cycles * nodes_config[0].get("nominal_runtime"):
    clock.tick()
    slot = slot + 1

    ## Create a thread for each node and run one time step
    threads= []
    for i in range(num_nodes):
        t = threading.Thread(target=nodes[i].run_one_time_step)
        threads.append(t)
    
    for t in threads:
        t.start()
    
    for t in threads:
        t.join()
    
    threads = []
    ## Run the publish on all radios in separate threads
    for i in range(num_nodes):
        t = threading.Thread(target=radios[i].publish)
        threads.append(t)

    for t in threads:
        t.start()
    
    for t in threads:
        t.join()
    
    threads = []
    ## Run the subscribe on all radios in separate threads
    for i in range(num_nodes):
        t = threading.Thread(target=radios[i].subscribe)
        threads.append(t)
    
    for t in threads:
        t.start()
    
    for t in threads:
        t.join()
    
    threads = []
    ## Run the build channel map on all nodes
    for i in range(num_nodes):
        t = threading.Thread(target=nodes[i].build_channel_map)
        threads.append(t)
    
    for t in threads:
        t.start()
    
    for t in threads:
        t.join()

for i in range(num_nodes):
    nodes[i].print_stats()