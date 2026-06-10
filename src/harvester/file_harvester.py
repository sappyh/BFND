import logging
import os
import numpy as np
import h5py
from src.harvester.IHarvester import HarvesterInterface
from src.messaging.Subscriber import Subscriber

DEFAULT_HARVESTER_BUFFER_TICKS = 10000

class FileHarvester(HarvesterInterface):
    def __init__(self, clock_publisher, file_path=None, log_level=logging.INFO, dataset_name="node0"):
        self.file_path = file_path
        self.clock_publisher = clock_publisher
        subscriber_topic = f"harvester_clock_sub_{id(self)}"
        self.clock_subscriber = Subscriber(subscriber_topic, self.clock_publisher)
        self.logger = logging.getLogger(f"FileHarvester_{id(self)}")
        self.logger.setLevel(log_level)
        self.dataset_name = dataset_name
        
        self.len = 0
        self.offset = 0
        self.Ts = 0
        self.hf = None
        self.energy_buffer = None
        self.buffer_ptr = 0
        self.buffer_start_tick = -1
        self.samples_per_tick = 1
        self.buffer_size_ticks = DEFAULT_HARVESTER_BUFFER_TICKS
        self.file_sample_period = 1e-5
        self.cached_energy = 0.0
        self.last_tick = -1

        if self.file_path is None:
            raise ValueError("File path must be provided for FILE harvesting mode.")

    def set_file(self, Ts, initial_offset=None):
        self.Ts = Ts
        if self.file_sample_period <= 0:
            self.logger.error("File sample period must be positive.")
            self.samples_per_tick = 1
        else:
            self.samples_per_tick = max(1, int(round(self.Ts / self.file_sample_period)))

        temp_hf = None
        try:
            temp_hf = h5py.File(self.file_path, "r")
            if "data" not in temp_hf or self.dataset_name not in temp_hf["data"]:
                raise KeyError(f"Dataset '/data/{self.dataset_name}' not found in HDF5 file.")
            dataset = temp_hf["data"][self.dataset_name]
            self.len = len(dataset)
            if self.len == 0:
                raise ValueError(f"Empty dataset '/data/{self.dataset_name}'")

            if initial_offset is not None:
                self.offset = initial_offset % self.len
            else:
                self.offset = np.random.randint(0, self.len)

            self.energy_buffer = None
            self.buffer_ptr = 0
            self.buffer_start_tick = -1
        except Exception as e:
            self.logger.error(f"FILE mode setup failed: {e}", exc_info=True)
            self.len = 0
            self.energy_buffer = None
        finally:
            if temp_hf:
                try:
                    temp_hf.close()
                except Exception:
                    pass

    def _load_file_buffer(self, current_tick):
        if self.file_path is None or self.len == 0:
            return False

        samples_to_read = self.buffer_size_ticks * self.samples_per_tick
        slice_start = self.offset
        slice_end = self.offset + samples_to_read
        try:
            if not hasattr(self, 'hf') or self.hf is None:
                self.hf = h5py.File(self.file_path, "r")
            
            if "data" not in self.hf or self.dataset_name not in self.hf["data"]:
                raise KeyError(f"Dataset '/data/{self.dataset_name}' not found in HDF5 file.")
            dataset = self.hf["data"][self.dataset_name]
            current_len = len(dataset)
            if current_len != self.len:
                self.len = current_len
                self.offset %= self.len
                slice_start = self.offset
                slice_end = self.offset + samples_to_read

            if slice_end > self.len:
                num_part1 = self.len - slice_start
                num_part2 = slice_end - self.len
                part1 = dataset[slice_start : self.len]
                part2 = dataset[0 : num_part2]
                if not isinstance(part1, np.ndarray):
                    part1 = np.array(part1)
                if not isinstance(part2, np.ndarray):
                    part2 = np.array(part2)
                self.energy_buffer = np.concatenate((part1, part2))
            else:
                self.energy_buffer = dataset[slice_start : slice_end]

            if not isinstance(self.energy_buffer, np.ndarray):
                self.energy_buffer = np.array(self.energy_buffer)

            self.buffer_ptr = 0
            self.offset = slice_end % self.len
            self.buffer_start_tick = current_tick
            return True
        except Exception as e:
            self.logger.error(f"Failed load energy buffer from HDF5: {e}", exc_info=True)
            self.energy_buffer = None
            return False

    def get_energy(self):
        try:
            new_tick = self.clock_subscriber.get_message() if self.clock_subscriber else None
            if new_tick is None:
                return self.cached_energy

            self.last_tick = new_tick

            if self.energy_buffer is None or self.buffer_ptr >= len(self.energy_buffer):
                if not self._load_file_buffer(new_tick):
                    self.cached_energy = 0.0
                    return 0.0
                if self.energy_buffer is None:
                    self.cached_energy = 0.0
                    return 0.0

            try:
                buffer_slice_start = self.buffer_ptr
                buffer_slice_end = self.buffer_ptr + self.samples_per_tick

                if buffer_slice_start >= len(self.energy_buffer):
                    if not self._load_file_buffer(new_tick):
                        self.cached_energy = 0.0
                        return 0.0
                    if self.energy_buffer is None:
                        self.cached_energy = 0.0
                        return 0.0
                    buffer_slice_start = self.buffer_ptr
                    buffer_slice_end = self.buffer_ptr + self.samples_per_tick

                if buffer_slice_end > len(self.energy_buffer):
                    buffer_slice_end = len(self.energy_buffer)

                if buffer_slice_start >= buffer_slice_end:
                    self.cached_energy = 0.0
                    return 0.0

                energy_data_slice = self.energy_buffer[buffer_slice_start : buffer_slice_end]
                energy_in = np.sum(energy_data_slice) * self.file_sample_period
                self.buffer_ptr = buffer_slice_end
                self.cached_energy = energy_in
                return energy_in
            except Exception as e:
                self.logger.error(f"Error processing energy buffer slice: {e}", exc_info=True)
                self.energy_buffer = None
                self.cached_energy = 0.0
                return 0.0
        except Exception as e:
            self.logger.error(f"Critical error in get_energy: {e}", exc_info=True)
            return 0.0

    def close(self):
        if self.clock_subscriber:
            try:
                self.clock_subscriber.shutdown()
            except Exception as e:
                self.logger.warning(f"Error shutting subscriber: {e}")
            self.clock_subscriber = None
        self.energy_buffer = None
        if hasattr(self, 'hf') and self.hf is not None:
            try:
                self.hf.close()
            except Exception as e:
                self.logger.warning(f"Error closing HDF5 file: {e}")
            self.hf = None
                
