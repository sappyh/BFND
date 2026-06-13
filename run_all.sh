#!/bin/bash

# Determine Python executable
if [ -d "venv" ]; then
    PYTHON="venv/bin/python"
else
    PYTHON="python"
fi

SIMULATIONS=200
NODES_LIST="2 3 4 5"


# Run pwr_office.h5 datasets (node0 to node4)
echo "=== Running Office Trace Simulations ==="
for dataset in node0 node1 node2 node3 node4
do
    for nodes in $NODES_LIST
    do
        echo "Running config_office.yaml with --dataset $dataset --num_nodes $nodes --num_simulations $SIMULATIONS"
        $PYTHON simulation_v2.py config_office.yaml --dataset $dataset --num_nodes $nodes --num_simulations $SIMULATIONS
    done
done

# Run pwr_stairs.h5 datasets (node0 to node5)
echo "=== Running Stairs Trace Simulations ==="
for dataset in node0 node1 node2 node3 node4 node5
do
    for nodes in $NODES_LIST
    do
        echo "Running config_stairs.yaml with --dataset $dataset --num_nodes $nodes --num_simulations $SIMULATIONS"
        $PYTHON simulation_v2.py config_stairs.yaml --dataset $dataset --num_nodes $nodes --num_simulations $SIMULATIONS
    done
done

echo "=== Running Cars Trace Simulations ==="
for dataset in node0 node1 node2 node3 node4 node5
do
    for nodes in $NODES_LIST
    do
        echo "Running config_cars.yaml with --dataset $dataset --num_nodes $nodes --num_simulations $SIMULATIONS"
        $PYTHON simulation_v2.py config_cars.yaml --dataset $dataset --num_nodes $nodes --num_simulations $SIMULATIONS
    done
done

echo "=== All Simulations Completed ==="
