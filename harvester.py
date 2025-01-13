## The harvester will be outputing the energy harvested per clock tick.
## It can also do that with a input file for the energy harvested per clock tick.

import numpy as np
import random
from enum import Enum
import math
import logging

from interface import Subscriber

from platform import node
import pandas as pd
import numpy as np
import h5py

from multiprocessing import Pool
from multiprocessing import cpu_count
from multiprocessing import Lock

import sys
import warnings


# Taken from Bonito
class CachedDataset(object):
    """Wrapper around default h5py Dataset that accelerates single index access to the data.

    hdf5 loads data 'lazily', i.e. only loads data into memory that is explicitly indexed. This incurs high
    delays when accessing single values successively. Chunk caching should improve this, but we couldn't observe
    a gain. Instead, this class implements a simple cached dataset, where data is read into memory in blocks
    and single index access reads from that cache.

    Args:
        dataset: underlying hdf5 dataset
        cache_size: number of values to be held in memory
    """

    def __init__(self, dataset: h5py.Dataset, cache_size: int = 10_000_000):
        self._ds = dataset
        self._istart = 0
        self._iend = -1
        self._cache_size = cache_size

    def __getitem__(self, key):
        #logging.debug(f"DataReader.__getitem__ called with key: {key}")
        if isinstance(key, slice):
            return self._ds[key]
        elif isinstance(key, int):
            return self.get_cached(key)

    def __len__(self):
        return len(self._ds)

    def update_cache(self, idx):
        #logging.debug(f"CachedDataset.update_cache called for index: {idx}")
        chunk_start = (idx // self._cache_size) * self._cache_size
        chunk_end = min(len(self._ds), chunk_start + self._cache_size)
        self._buf = self._ds[chunk_start:chunk_end]
        #logging.debug(f"Accessing dataset chunk: start={chunk_start}, end={chunk_end}")
        self._istart = chunk_start
        self._iend = chunk_end

    def get_cached(self, idx):
        if idx >= self._istart and idx < self._iend:
            return self._buf[idx - self._istart]
        else:
            self.update_cache(idx)
            return self.get_cached(idx)


class DataReader(object):
    """Convenient and cached access to an hdf5 database with power traces from multiple nodes."""

    def __init__(self, path, cache_size=10_000_000):
        self.path = path
        self.cache_size = cache_size
        self._datasets = dict()
        self._lock = Lock()  # Multiprocessing lock
        self._hf = None

    def __enter__(self):
        self.open()

    def open(self):
        with self._lock:
            self._hf = h5py.File(self.path, "r")
            self.nodes = list(self._hf["data"].keys())
            self.time = self._hf["time"]
            for node in self._hf["data"].keys():
                self._datasets[node] = CachedDataset(self._hf["data"][node], self.cache_size)
        return self

    def __exit__(self, *exc):
        self._hf.close()

    def close(self):
        self._hf.close()

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._datasets[f"node{key}"]
        else:
            return self._datasets[key]

    def __len__(self):
        return len(self.time)


class harvestingmode(Enum):
    CONSTANT = 0
    GAUSSIAN = 1
    FILE = 2


class Harvester:
    def __init__(self, mode, file, clock, log_level=logging.INFO):
        self.mode = mode
        self.file = file
        self.offset = 0
        self.Ts = 0
        self.data = None
        self.data_reader = None
        self.energy_harvested = 0
        self.clock = clock
        self.subscriber = Subscriber("clock", self.clock)
        self.previous_tick = 0
        self.energy_per_clock_tick = 0
        self.mean = 0
        self.std = 0
        self.len = 0

    def close(self):
        self.subscriber.shutdown()
        self.data_reader.close()

    def set_constant(self, energy_per_clock_tick):
        self.energy_per_clock_tick = energy_per_clock_tick

    def set_gaussian(self, mean, std):
        self.mean = mean
        self.std = std

    def set_file(self, file, Ts):
        try:
            self.data_reader = DataReader(file, cache_size=500000000)
            self.file = self.data_reader.open()  # Open the file safely
            self.offset = np.random.randint(0, len(self.file))
            self.data = self.file[0]
            self.Ts = Ts
            self.len = len(self.data)  # Store the dataset length
            # Precompute cumulative sums
        except Exception as e:
            logging.error(f"Harvester: Failed to open or process file {file}: {e}")
            self.file = None
            self.data = None
            self.len = 0
            self.cumsum_data = None

    def get_energy(self):
        try:
            new_tick = self.subscriber.get_message()

            # Check clock tick consistency
            if new_tick != self.previous_tick + 1 and self.previous_tick != 0:
                logging.error(f"Clock ticks are not in order: {new_tick} {self.previous_tick}")
                return 0

            self.previous_tick = new_tick

            # Handle different harvesting modes
            if self.mode == harvestingmode.CONSTANT:
                return self.energy_per_clock_tick

            elif self.mode == harvestingmode.GAUSSIAN:
                ein = np.random.normal(self.mean, self.mean * self.std)
                ein = max(0, ein)  # Ensure non-negative energy
                logging.debug(f"Gaussian energy harvested: {ein}")
                return ein

            elif self.mode == harvestingmode.FILE:
                # Validate that data is available
                if self.data is None or self.len == 0:
                    logging.error("Energy data file is not initialized or empty.")
                    return 0

                # Calculate the slice for the current time slot
                try:
                    slice_start = self.offset
                    slice_end = (self.offset + int(self.Ts / 1e-5)) % self.len
                    energy_data = self.data[slice_start:slice_end] * 1e-5
                    energy_in = np.sum(energy_data)
                    #logging.debug(f"File energy harvested: {energy_in}")


                    # Update offset
                    self.offset = slice_end
                    return energy_in

                except Exception as e:
                    logging.error(f"Failed to read energy data from file: {e}")
                    return 0

            else:
                logging.error("No valid harvesting mode set.")
                return 0

        except Exception as e:
            logging.error(f"Error in get_energy: {e}")
            return 0


