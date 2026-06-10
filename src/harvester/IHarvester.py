from enum import Enum
import logging

class harvestingmode(Enum):
    CONSTANT = 0
    GAUSSIAN = 1
    FILE = 2

class HarvesterInterface:
    def get_energy(self) -> float:
        raise NotImplementedError

    def close(self):
        pass

class HarvesterFactory:
    @staticmethod
    def create_harvester(mode, clock_publisher, **kwargs):
        from .constant_harvester import ConstantHarvester
        from .gaussian_harvester import GaussianHarvester
        from .file_harvester import FileHarvester

        log_level = kwargs.get('log_level', logging.INFO)
        nominal_runtime = kwargs.get('nominal_runtime', 1000)

        if mode == harvestingmode.CONSTANT:
            power = kwargs.get('power', 0.0)
            return ConstantHarvester(clock_publisher, power, log_level, nominal_runtime)
        elif mode == harvestingmode.GAUSSIAN:
            mean = kwargs.get('mean', 0.0)
            std = kwargs.get('std', 0.0)
            return GaussianHarvester(clock_publisher, mean, std, log_level, nominal_runtime)
        elif mode == harvestingmode.FILE:
            file_path = kwargs.get('file_path')
            Ts = kwargs.get('Ts', 1e-2)
            initial_offset = kwargs.get('initial_offset', None)
            h = FileHarvester(clock_publisher, file_path, log_level, nominal_runtime)
            h.set_file(Ts, initial_offset)
            return h
        else:
            raise ValueError(f"Unknown harvesting mode: {mode}")
