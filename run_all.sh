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
    $PYTHON simulation.py comparison_configs/config_office_bfnd_ble.yaml comparison_configs/config_office_bfnd.yaml comparison_configs/config_office_find.yaml --num_nodes $nodes --num_simulations $SIMULATIONS
done

# Run Stairs Trace Simulations
echo "=== Running Stairs Trace Simulations ==="
for nodes in $NODES_LIST
do
    echo "Running config_stairs with --num_nodes $nodes --num_simulations $SIMULATIONS"
    $PYTHON simulation.py comparison_configs/config_stairs_bfnd_ble.yaml comparison_configs/config_stairs_bfnd.yaml comparison_configs/config_stairs_find.yaml --num_nodes $nodes --num_simulations $SIMULATIONS
done

echo "=== Running Washer Trace Simulations ==="
for nodes in $NODES_LIST
do
    echo "Running config_washer with --num_nodes $nodes --num_simulations $SIMULATIONS"
    $PYTHON simulation.py comparison_configs/config_washer_bfnd_ble.yaml comparison_configs/config_washer_bfnd.yaml comparison_configs/config_washer_find.yaml --num_nodes $nodes --num_simulations $SIMULATIONS
done

echo "=== Running Jogging Trace Simulations ==="
for nodes in $NODES_LIST
do
    echo "Running config_jogging with --num_nodes $nodes --num_simulations $SIMULATIONS"
    $PYTHON simulation.py comparison_configs/config_jogging_bfnd_ble.yaml comparison_configs/config_jogging_bfnd.yaml comparison_configs/config_jogging_find.yaml --num_nodes $nodes --num_simulations $SIMULATIONS
done

# Run Cars Trace Simulations
echo "=== Running Cars Trace Simulations ==="
for nodes in $NODES_LIST
do
    echo "Running config_cars with --num_nodes $nodes --num_simulations $SIMULATIONS"
    $PYTHON simulation.py comparison_configs/config_cars_bfnd_ble.yaml comparison_configs/config_cars_bfnd.yaml comparison_configs/config_cars_find.yaml --num_nodes $nodes --num_simulations $SIMULATIONS
done

echo "=== All Simulations Completed ==="

