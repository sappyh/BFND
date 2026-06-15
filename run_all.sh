#!/bin/bash

# Determine Python executable
if [ -d "venv" ]; then
    PYTHON="venv/bin/python"
else
    PYTHON="python"
fi

SIMULATIONS=1000
NODES_LIST="2 3 4 5"


# Run Office Trace Simulations
echo "=== Running Office Trace Simulations ==="
for nodes in $NODES_LIST
do
    echo "Running config_office with --num_nodes $nodes --num_simulations $SIMULATIONS"
    $PYTHON simulation_v2.py config_office_bfnd.yaml config_office_find.yaml --num_nodes $nodes --num_simulations $SIMULATIONS
done

# Run Stairs Trace Simulations
echo "=== Running Stairs Trace Simulations ==="
for nodes in $NODES_LIST
do
    echo "Running config_stairs with --num_nodes $nodes --num_simulations $SIMULATIONS"
    $PYTHON simulation_v2.py config_stairs_bfnd.yaml config_stairs_find.yaml --num_nodes $nodes --num_simulations $SIMULATIONS
done

echo "=== Running Cars Trace Simulations ==="
for nodes in $NODES_LIST
do
    echo "Running config_cars with --num_nodes $nodes --num_simulations $SIMULATIONS"
    $PYTHON simulation_v2.py config_cars_bfnd.yaml config_cars_find.yaml --num_nodes $nodes --num_simulations $SIMULATIONS
done

echo "=== All Simulations Completed ==="
