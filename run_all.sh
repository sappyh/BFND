#!/bin/bash

# Determine Python executable
if [ -d "venv" ]; then
    PYTHON="venv/bin/python"
else
    PYTHON="python"
fi

# Run pwr_cars.h5 datasets (node0 to node5)
echo "=== Running Cars Trace Simulations ==="
for dataset in node0 node1 node2 node3 node4 node5
do
    echo "Running config_cars.yaml with --dataset $dataset"
    $PYTHON simulation_v2.py config_cars.yaml --dataset $dataset
done

# Run pwr_jogging.h5 datasets (node0 to node4)
echo "=== Running Jogging Trace Simulations ==="
for dataset in node0 node1 node2 node3 node4
do
    echo "Running config_jogging.yaml with --dataset $dataset"
    $PYTHON simulation_v2.py config_jogging.yaml --dataset $dataset
done

# Run pwr_stairs.h5 datasets (node0 to node5)
echo "=== Running Stairs Trace Simulations ==="
for dataset in node0 node1 node2 node3 node4 node5
do
    echo "Running config_stairs.yaml with --dataset $dataset"
    $PYTHON simulation_v2.py config_stairs.yaml --dataset $dataset
done

echo "=== All Simulations Completed ==="
