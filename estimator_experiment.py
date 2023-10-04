from estimator import Kalman_Estimator, PieceWiseEstimator
import numpy as np
import random
import collections
from matplotlib import pyplot as plt

## Create a Gausssian random generator
## with mean 1000 and variance 450
mean = 1000
std = 450
gaussian_generator = np.random.default_rng()

## Try the estimator
# estimator = Kalman_Estimator(100)
estimator= PieceWiseEstimator(0.9, 0.5)

estimates = []
errors = []

sample_buffer = collections.deque(maxlen=5)

previous_sample = 0

## Bootstrap the estimator with 100 samples
for i in range(10):
    sample =  gaussian_generator.normal(mean, std)
    sample_buffer.append(sample)
    deviation = np.std(sample_buffer)
    # estimator.update(sample, deviation)
    estimator.update(sample)
    

for i in range(1000):
    sample =  gaussian_generator.normal(mean, std)
    sample_buffer.append(sample)
    deviation = np.std(sample_buffer)

    estimate = estimator.estimate()

    estimates.append(estimate)

    # estimator.update(sample, deviation)
    estimator.update(sample)
     
    error = sample - estimate
    if error < 0:
        error = 0
    errors.append(error)
    
    print("sample: ", sample, "previous_sample: ", previous_sample, "error: ", error)
    print("estimate: ", estimate)
    print("")
    previous_sample = sample

## Plot the estimates and errors
plt.plot(estimates)
plt.plot(errors)
plt.savefig("estimates.png")