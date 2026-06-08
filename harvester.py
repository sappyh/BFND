## The harvester will be outputing the energy harvested per clock tick.
## It can also do that with a input file for the energy harvested per clock tick.

import numpy as np
import random
from enum import Enum
import math
import logging
from interface import Subscriber
import h5py
import sys
import os

# REMOVED: DEFAULT_HDF5_CACHE_SIZE and CachedDataset/DataReader dependencies

# MODIFIED: Increased Harvester buffer size (in ticks) to reduce HDF5 disk reads
DEFAULT_HARVESTER_BUFFER_TICKS = 10000 # Increased from 100 to reduce read frequency

# Enum for harvesting modes
class harvestingmode(Enum): CONSTANT = 0; GAUSSIAN = 1; FILE = 2

# Harvester class definition
class Harvester:
    """ Simulates energy harvesting. Opens/closes HDF5 on each buffer load for FILE mode. """
    # MODIFIED: Removed data_reader parameter
    def __init__(self, mode, clock_publisher, file_path=None, log_level=logging.INFO, nominal_runtime=1000):
        self.mode = mode
        self.file_path = file_path # Keep file path for direct opening
        # REMOVED: self.data_reader
        # REMOVED: self.data (will be accessed directly from file)
        self.len = 0 # Will be read from file when needed
        self.offset = 0
        self.Ts = 0
        self.nominal_runtime = nominal_runtime

        self.clock_publisher = clock_publisher
        self.hf = None # Persistent HDF5 file handle
        subscriber_topic = f"harvester_clock_sub_{id(self)}"
        self.clock_subscriber = Subscriber(subscriber_topic, self.clock_publisher)
        self.previous_tick = 0

        self.energy_per_clock_tick = 0
        self.mean = 0; self.std = 0

        self.energy_buffer = None; self.buffer_ptr = 0
        self.buffer_start_tick = -1; self.samples_per_tick = 1
        self.buffer_size_ticks = DEFAULT_HARVESTER_BUFFER_TICKS
        self.file_sample_period = 1e-5 # Assuming this is the sample period within the HDF5 file

        self.logger = logging.getLogger(f"Harvester_{id(self)}_{mode.name}")
        self.logger.setLevel(log_level)

        # No need to check for data_reader here
        if self.mode == harvestingmode.FILE and self.file_path is None:
             raise ValueError("File path must be provided for FILE harvesting mode.")

    def close(self):
        """ Closes subscriber and HDF5 file handle. """
        self.logger.debug("Closing harvester subscriber.")
        if self.clock_subscriber:
             try: self.clock_subscriber.shutdown()
             except Exception as e: self.logger.warning(f"Error shutting subscriber: {e}")
        self.energy_buffer = None # Clear buffer
        if hasattr(self, 'hf') and self.hf is not None:
             try:
                 self.hf.close()
                 self.logger.debug("Closed HDF5 file handle.")
             except Exception as e:
                 self.logger.warning(f"Error closing HDF5 file: {e}")
             self.hf = None

    def set_constant(self, energy_per_clock_tick):
        if self.mode != harvestingmode.CONSTANT: self.logger.warning(f"Setting const params but mode is {self.mode.name}")
        self.energy_per_clock_tick = energy_per_clock_tick
        self.logger.info(f"Set mode=CONSTANT, energy_per_tick={self.energy_per_clock_tick}")

    def set_gaussian(self, mean, std):
        if self.mode != harvestingmode.GAUSSIAN: self.logger.warning(f"Setting Gauss params but mode is {self.mode.name}")
        self.mean = mean; self.std = std
        self.logger.info(f"Set mode=GAUSSIAN, mean={self.mean}, std={self.std}")

    def set_file(self, Ts, initial_offset=None):
        """ Sets parameters for FILE mode. Does NOT open the file here. """
        if self.mode != harvestingmode.FILE:
             self.logger.warning(f"set_file called but mode is {self.mode.name}"); return
        if self.file_path is None:
             self.logger.error("set_file called but file_path is None."); return

        self.Ts = Ts
        if self.file_sample_period <= 0:
             self.logger.error("File sample period must be positive.")
             self.samples_per_tick = 1
        else:
             self.samples_per_tick = max(1, int(round(self.Ts / self.file_sample_period)))

        self.logger.info(f"Configuring FILE mode: Ts={self.Ts}, FileSamplePeriod={self.file_sample_period}, SamplesPerTick={self.samples_per_tick}, BufferSizeTicks={self.buffer_size_ticks}")

        # We need the length for wrap-around and initial offset, so open/close briefly
        temp_hf = None
        try:
            abs_path = os.path.abspath(self.file_path)
            self.logger.debug(f"set_file: Temporarily opening {abs_path} to get length.")
            temp_hf = h5py.File(self.file_path, "r")
            if "data" not in temp_hf or "node0" not in temp_hf["data"]:
                 raise KeyError("Dataset '/data/node0' not found in HDF5 file.")
            dataset = temp_hf["data"]["node0"]
            self.len = len(dataset)
            if self.len == 0: raise ValueError("Empty dataset '/data/node0'")
            self.logger.debug(f"set_file: Dataset length self.len = {self.len}")

            if initial_offset is not None: self.offset = initial_offset % self.len
            else: self.offset = np.random.randint(0, self.len)
            self.logger.info(f"Initial HDF5 offset set to: {self.offset}")

            self.energy_buffer = None; self.buffer_ptr = 0; self.buffer_start_tick = -1
        except Exception as e:
            self.logger.error(f"FILE mode setup failed during length check: {e}", exc_info=True)
            self.len = 0 # Ensure length is 0 on error
            self.energy_buffer = None
        finally:
             if temp_hf:
                 try: temp_hf.close()
                 except Exception: pass # Ignore close errors during setup check

    # --- Modified _load_file_buffer ---
    def _load_file_buffer(self, current_tick):
        """ Reads a chunk from HDF5 into the internal numpy buffer, handling wrap-around. Opens file once and keeps it open. """
        if self.file_path is None or self.len == 0: # Check length determined during set_file
            self.logger.error(f"Cannot load buffer: file_path ({self.file_path}) or dataset length ({self.len}) invalid.")
            return False

        samples_to_read = self.buffer_size_ticks * self.samples_per_tick
        self.logger.debug(f"Loading buffer tick {current_tick}. Reading {samples_to_read} samples from HDF5 offset {self.offset}.")

        slice_start = self.offset
        slice_end = self.offset + samples_to_read
        try:
            # Open the HDF5 file once and keep it open
            if not hasattr(self, 'hf') or self.hf is None:
                self.hf = h5py.File(self.file_path, "r")
            
            # Access the dataset directly - assumes node0 for simplicity
            if "data" not in self.hf or "node0" not in self.hf["data"]:
                 raise KeyError("Dataset '/data/node0' not found in HDF5 file during buffer load.")
            dataset = self.hf["data"]["node0"]
            current_len = len(dataset) # Re-check length in case file changed? Unlikely but safe.
            if current_len != self.len:
                self.logger.warning(f"HDF5 dataset length changed! Expected {self.len}, got {current_len}. Updating.")
                self.len = current_len
                if self.len == 0: raise ValueError("Dataset became empty.")
                # Adjust offset if it's now out of bounds
                self.offset %= self.len
                slice_start = self.offset
                slice_end = self.offset + samples_to_read

            # Check for wrap-around using the current length
            if slice_end > self.len:
                num_part1 = self.len - slice_start
                num_part2 = slice_end - self.len
                self.logger.debug(f"Wrap-around read: Part 1 [{slice_start}:{self.len}], Part 2 [0:{num_part2}]")
                part1 = dataset[slice_start : self.len]
                part2 = dataset[0 : num_part2]
                if not isinstance(part1, np.ndarray): part1 = np.array(part1)
                if not isinstance(part2, np.ndarray): part2 = np.array(part2)
                self.energy_buffer = np.concatenate((part1, part2))
            else:
                # Read a single contiguous slice
                self.energy_buffer = dataset[slice_start : slice_end]

            # Ensure buffer is a numpy array
            if not isinstance(self.energy_buffer, np.ndarray):
                 self.energy_buffer = np.array(self.energy_buffer)

            # Reset buffer pointer and update HDF5 offset
            self.buffer_ptr = 0
            self.offset = slice_end % self.len # New offset after reading
            self.buffer_start_tick = current_tick
            self.logger.debug(f"Buffer loaded. Size: {len(self.energy_buffer)} samples. Next HDF5 offset: {self.offset}")
            return True

        except Exception as e:
            self.logger.error(f"Failed load energy buffer from HDF5 (path={self.file_path}, start={slice_start}, end={slice_end}): {e}", exc_info=True)
            self.energy_buffer = None
            return False
    # --- End Modified _load_file_buffer ---

    def get_energy(self):
        """ Calculates and returns the energy harvested using buffered reading for FILE mode. """
        try:
            new_tick = self.clock_subscriber.get_message()
            if new_tick is None: return 0.0
            self.previous_tick = new_tick

            if self.mode == harvestingmode.CONSTANT: return self.energy_per_clock_tick
            elif self.mode == harvestingmode.GAUSSIAN:
                return max(0, random.gauss(self.mean, self.std))
            elif self.mode == harvestingmode.FILE:
                if self.energy_buffer is None or self.buffer_ptr >= len(self.energy_buffer):
                    # _load_file_buffer now handles file open/close
                    if not self._load_file_buffer(new_tick): return 0.0
                    if self.energy_buffer is None: return 0.0

                try:
                    # --- Buffer processing logic remains the same ---
                    buffer_slice_start = self.buffer_ptr
                    buffer_slice_end = self.buffer_ptr + self.samples_per_tick

                    if buffer_slice_start >= len(self.energy_buffer):
                         self.logger.warning(f"Buffer pointer ({buffer_slice_start}) beyond buffer length ({len(self.energy_buffer)}). Reloading buffer.")
                         if not self._load_file_buffer(new_tick): return 0.0
                         if self.energy_buffer is None: return 0.0
                         buffer_slice_start = self.buffer_ptr
                         buffer_slice_end = self.buffer_ptr + self.samples_per_tick

                    if buffer_slice_end > len(self.energy_buffer):
                        buffer_slice_end = len(self.energy_buffer)
                        self.logger.debug(f"Adjusted buffer slice end to {buffer_slice_end}")

                    if buffer_slice_start >= buffer_slice_end:
                        self.logger.warning(f"Buffer slice start ({buffer_slice_start}) >= end ({buffer_slice_end}). Returning 0 energy.")
                        return 0.0

                    energy_data_slice = self.energy_buffer[buffer_slice_start : buffer_slice_end]
                    energy_in = np.sum(energy_data_slice) * self.file_sample_period
                    self.buffer_ptr = buffer_slice_end
                    return energy_in
                except IndexError as ie:
                     self.logger.error(f"IndexError processing energy buffer slice: Start={buffer_slice_start}, End={buffer_slice_end}, BufLen={len(self.energy_buffer)}. Error: {ie}", exc_info=True)
                     self.energy_buffer = None; return 0.0
                except Exception as e:
                    self.logger.error(f"Error processing energy buffer slice: {e}", exc_info=True)
                    self.energy_buffer = None; return 0.0
            else:
                self.logger.error("No valid harvesting mode set."); return 0.0
        except Exception as e:
            self.logger.error(f"Critical error in get_energy: {e}", exc_info=True); return 0.0
