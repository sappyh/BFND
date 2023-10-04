import numpy as np


class Estimator:
    def __init__(self) -> None:
        pass

    def estimate(self, sample) -> np.int:
        raise NotImplementedError


class Kalman_Estimator:
    def __init__(self, process_noise):
        self.state = 0
        self.prediction = 0
        self.variance = 0
        self.K_n = 1
        self.process_noise= process_noise
    
    ## Measurement noise is the variance of the measurement, captured by find the variance in a buffer of n samples
    def update(self,measurement, measurement_noise):
        #Intialize
        if(self.state == 0):
            self.prediction = measurement
            self.variance = measurement_noise
            self.state = 1

        else:
            ## Higher variance means more weightage to recent measurements
            ## In case the error is positive, the process noise needs to be increased more than in case of negative error
            error = measurement - self.prediction
   

            self.K_n = self.variance/(self.variance + measurement_noise)


            self.variance = (1-self.K_n)*self.variance + self.process_noise
            self.prediction = self.prediction + self.K_n * error

            print("K_n: ", self.K_n, "measurement: ", measurement, "prediction: ", self.prediction, "variance: ", self.variance, "process_noise: ", self.process_noise)
    def estimate(self):
        return self.prediction + self.variance
    

class PieceWiseEstimator:
    def __init__(self, decay_rate=0.9, threshold=0.5):
        self.decay_rate = decay_rate
        self.threshold = threshold
        self.internal_state= 0
    
    def update(self, sample):
        if(sample > self.internal_state):
            self.internal_state = sample
        else:
            ## Decay rate depends on the error and std dev of the measurements
            error = self.internal_state - sample
            self.decay_rate = (1 - error/self.internal_state) * self.decay_rate

            if(self.internal_state > (1+self.threshold) * sample):
                self.internal_state = self.decay_rate * self.internal_state
            else:
                self.internal_state = sample
    
    def estimate(self):
        return self.internal_state
    
## Class Bonito Estimator
