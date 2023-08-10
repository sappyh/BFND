## Core functionalities
## Takes in clock tick
## Takes in enenrgy and computes energy level
## Depending on the energy level, it will decide whether to advertise or scan or sleep
## Takes in offset and saves it as internal state

import random
import math
from enum import Enum
import numpy as np
from interface import Subscriber
import logging

class ACTION(Enum):
    SLEEP = 0
    ADVERTISE = 1
    SCAN = 2

class STATE(Enum):
    ON = 1
    OFF = 0

class RADIO_STATE(Enum):
    SUCCESS = 1
    FAILURE = 0

class Node():
    def __init__ (self, id, energy_harvester, clock, radio, offset, alpha, capacitance, von, voff, eadv, escan, nominal_time_period, run_time = 100, log_level=logging.INFO):
        self.energy_harvester = energy_harvester
        self.clock = Subscriber("clock", clock)
        self.radio = radio
        self.id = id
       

        ## Take in all the parameters
        self.capacitance = capacitance
        self.offset = offset
        self.alpha = alpha
        self.von = von
        self.voff = voff
        self.eadv = eadv
        self.escan = escan
        self.nominal_time_period = nominal_time_period
        self.run_time = run_time
        self.channel_map = np.zeros(nominal_time_period)
        
        self.current_run_time = 0
        self.ASN = 0
        self.next_wakeup = 0
        self.action = ACTION.SLEEP

        self.state = STATE.OFF
        self.energy_level = 0.5*self.capacitance*(self.voff**2)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)

        ## Create a dictionary object for metrics
        self.metrics = {}
        self.metrics["adv_sent"] = 0
        self.metrics["scan_sent"] = 0
        self.metrics["adv_success"] = 0
        self.metrics["scan_success"] = 0

    def compute_energy_level(self, energy_in):
        self.energy_level = self.energy_level + energy_in

        ## Change energy to voltage
        voltage  = math.sqrt(2* self.energy_level / self.capacitance)
        if voltage > self.von:
            self.state = STATE.ON
        elif voltage < self.voff:
            self.state = STATE.OFF

    def do_action(self, action):
        if self.state == STATE.ON:
            if action == ACTION.ADVERTISE:
                self.compute_energy_level(-self.eadv)
                self.radio.advertise(self.ASN, self.id)
                self.metrics["adv_sent"] += 1
            elif action == ACTION.SCAN:
                self.compute_energy_level(-self.escan)
                self.radio.scan(self.ASN, self.id)
                self.metrics["scan_sent"] += 1
            elif action == ACTION.SLEEP:
                self.radio.sleep()
    
    def build_channel_map(self):
        if self.radio.get_message() == RADIO_STATE.SUCCESS:
            self.channel_map[self.ASN % self.nominal_time_period] += 1
            if self.action == ACTION.ADVERTISE:
                self.logger.info("Advertise Success")
                self.metrics["adv_success"] += 1
            elif self.action == ACTION.SCAN:
                self.logger.info("Scan Success")
                self.metrics["scan_success"] += 1
        else:
            self.channel_map= 0.95 * self.channel_map

    def print_stats(self):
        print("Node" + str(self.id) + " Metrics")
        print("Adv Sent: " + str(self.metrics["adv_sent"]))
        print("Scan Sent: " + str(self.metrics["scan_sent"]))
        print("Adv Success: " + str(self.metrics["adv_success"]))

    def run_one_time_step(self):
            if(self.clock.get_message() == self.ASN+1):
                self.ASN += 1
            
            if self.ASN > self.offset:
                self.compute_energy_level(self.energy_harvester.get_energy())
            
            if self.state == STATE.ON:
                self.logger.debug("Node" + str(self.id) +" is on at ASN: " + str(self.ASN))

                # Woke up at perfectly the right time
                if self.ASN % self.nominal_time_period == self.offset or self.current_run_time == 0 :
                    self.current_run_time += 1

                    ## Check channel map to see if we should advertise or scan
                    if self.channel_map[self.ASN % self.nominal_time_period] > 0.8:
                        self.action = ACTION.SLEEP
                        self.next_wakeup = self.ASN + np.argmax(self.channel_map)
                        self.do_action(ACTION.SLEEP)
                    else:
                        self.next_wakeup = self.ASN + self.nominal_time_period
                        if(random.uniform(0,1) < self.alpha):
                            self.action = ACTION.ADVERTISE
                            self.do_action(ACTION.ADVERTISE)
                        else:
                            self.action = ACTION.SCAN
                            self.do_action(ACTION.SCAN)
                
                # Woke up at the after the right time
                elif self.ASN  > self.next_wakeup:
                    self.next_wakeup = (math.floor(self.ASN/self.nominal_time_period) + 1) * self.nominal_time_period
                    self.current_run_time += 1
                    self.action = ACTION.SCAN
                    self.do_action(ACTION.SCAN)
                    
                # Woke up before the right time
                elif self.ASN < self.next_wakeup:
                    ## Check if this is because we are scanning
                    if self.action == ACTION.SCAN:
                        self.do_action(ACTION.SCAN)
                    else:
                        self.do_action(ACTION.SLEEP)
                
                elif self.ASN == self.next_wakeup:
                    self.next_wakeup = (math.floor(self.ASN/self.nominal_time_period) + 1) * self.nominal_time_period
                    self.action = ACTION.ADVERTISE
                    self.do_action(ACTION.ADVERTISE)


            