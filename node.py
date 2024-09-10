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
from matplotlib import pyplot as plt

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

class RUN_TYPE(Enum):
    SCANNING= 0
    ADVERTISING = 1
    NORMAL = 2

class Node():
    def __init__ (self, id, energy_harvester, clock, radio, offset, alpha, capacitance, von, voff, eadv, escan, nominal_time_period, run_time = 100, runtype= RUN_TYPE.NORMAL, log_level=logging.INFO):
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
        self.esleep = 10.5e-9
        self.nominal_time_period = nominal_time_period
        self.run_time = run_time
        self.channel_map = np.zeros(nominal_time_period)
        self.runtype = runtype
        # print( self.id, self.runtype)
        
        self.current_run_time = 0
        self.prev_run_time = 0
        self.ASN = 0
        self.next_wakeup = 0
        self.action = ACTION.SLEEP

        self.state = STATE.OFF
        self.energy_level = 0 #0.5*self.capacitance*(self.voff**2)
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(log_level)
        
        self.logger.disabled = True
        self.n = 15 #int((0.5 * self.capacitance * (self.von**2 - self.voff**2))/self.escan)
        self.scan_slots  = np.zeros(self.n)
        self.nScan = 0

        ## Create a dictionary object for metrics
        self.metrics = {}
        self.metrics["adv_sent"] = 0
        self.metrics["scan_sent"] = 0
        self.metrics["adv_success"] = 0
        self.metrics["scan_success"] = 0
        
        ## Parameters for the node
        self.done = False
        self.action_decided = False
        self.ran_once = False

    def compute_energy_level(self, energy_in):
        self.energy_level = self.energy_level + energy_in

        ## Change energy to voltage
        voltage  = math.sqrt(2* self.energy_level / self.capacitance)
        if voltage < 1.8 and self.ran_once:
            self.reset()
        
        if voltage > self.von:
            self.state = STATE.ON
        elif voltage < self.voff:
            self.state = STATE.OFF

    def do_action(self, action):
        if self.state == STATE.ON:
            if action == ACTION.ADVERTISE:
                self.radio.advertise(self.ASN, self.id)
                self.metrics["adv_sent"] += 1
            elif action == ACTION.SCAN:
                self.radio.scan(self.ASN, self.id)
                self.metrics["scan_sent"] += 1
            elif action == ACTION.SLEEP:
                self.radio.sleep()
    
    def build_channel_map(self):
        if self.radio.get_message() == RADIO_STATE.SUCCESS and self.state == STATE.ON:
            if self.action == ACTION.ADVERTISE:
                self.logger.info("Node: %s, ASN: %s, Advertise Success", self.id, self.ASN)
                
                ## Updates as the nodes are successful in advertising, hence it will be moving to communication state
                if (self.id  == 0):
                    self.channel_map[self.ASN % self.nominal_time_period] = 0
                    self.offset = np.random.randint(0, self.nominal_time_period)
                else:
                    self.done = True
                
                self.metrics["adv_success"] += 1
            elif self.action == ACTION.SCAN:
                self.logger.info("Node: %s, ASN: %s, Scan Success", self.id, self.ASN)
                self.metrics["scan_success"] += 1
                self.channel_map[self.ASN % self.nominal_time_period] += 1
        
        self.logger.debug("Node: %s, ASN: %s, self.radio message: %s, self.state= %s", self.id, self.ASN, self.radio.get_message(), self.state)
        
        ## Update the energy level now
        if self.action == ACTION.ADVERTISE:
            self.compute_energy_level(-self.eadv)
        elif self.action == ACTION.SCAN:
            self.compute_energy_level(-self.escan)
        elif self.action == ACTION.SLEEP:
            if self.ran_once:
                self.compute_energy_level(-self.esleep)
            
            
        
        
    def show_channel_map(self):
        plt.plot(self.channel_map)
        plt.savefig("channel_map.png")

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
            
            if self.done:
                self.action = ACTION.SLEEP
                self.do_action(ACTION.SLEEP)
                return
            
            if self.state == STATE.ON:
                self.ran_once = True
                if self.runtype == RUN_TYPE.NORMAL:                        
                    self.logger.debug("Node" + str(self.id) +" is on at ASN: " + str(self.ASN))

                    self.action = ACTION.SLEEP
                    ## Node wakes up and checks what should be the right slot for it
                    ## Check the channel map to see if we have any time slot where we had a scan success
                    ## Define the action for this time period
                    
                    # if int(self.ASN/self.nominal_time_period) > self.prev_run_time:
                        # self.prev_run_time = int(self.ASN/self.nominal_time_period)
                        # self.build_channel_map()
                    if self.action_decided == False:
                        if random.random() < self.alpha:
                            self.action = ACTION.ADVERTISE
                            # self.scan_slots = []
                            self.nScan = 0
                        else:
                            self.action = ACTION.SLEEP
                            self.nScan = self.n
                        self.action_decided = True
                    
                        
                    if  self.action == ACTION.ADVERTISE:
                        if any(self.channel_map > 0):
                            ## Check if the current ASN is beyond the argmax of the channel map
                            if self.ASN % self.nominal_time_period > np.argmax(self.channel_map):
                                self.next_wakeup_offset = self.nominal_time_period - self.ASN % self.nominal_time_period + np.argmax(self.channel_map)
                            else:
                                self.next_wakeup_offset = np.argmax(self.channel_map) - self.ASN % self.nominal_time_period
                            self.next_wakeup = self.ASN + self.next_wakeup_offset
                            self.action = ACTION.SLEEP
                            self.do_action(ACTION.SLEEP)
                        else:
                            if self.ASN % self.nominal_time_period > self.offset:
                                self.next_wakeup = self.ASN + self.nominal_time_period - self.ASN % self.nominal_time_period + self.offset
                                self.action = ACTION.SLEEP
                                self.do_action(ACTION.SLEEP)
                            else:
                                if self.ASN % self.nominal_time_period == self.offset:
                                    self.action = ACTION.ADVERTISE
                                    self.do_action(ACTION.ADVERTISE)
                                    self.action_decided = False
                                    self.next_wakeup = self.ASN + self.nominal_time_period
                                else: 
                                    self.next_wakeup = self.ASN + self.offset - self.ASN % self.nominal_time_period
                                    self.action = ACTION.SLEEP
                                    self.do_action(ACTION.SLEEP)
                           
    
                    
                    if(self.ASN == self.next_wakeup):
                        self.action = ACTION.ADVERTISE
                        self.do_action(ACTION.ADVERTISE)
                        self.action_decided = False
                    
                    if self.nScan > 0:
                        if random.random() < self.n/self.nominal_time_period:
                            self.action = ACTION.SCAN
                            self.nScan -= 1
                            if self.nScan == 0:
                                self.action_decided = False
                            self.do_action(ACTION.SCAN)
                        else:
                            self.action = ACTION.SLEEP
                            self.do_action(ACTION.SLEEP)
                    
                    # if len(self.scan_slots)> 0:
                    #     if self.ASN == self.scan_slots[0]:
                    #         self.action = ACTION.SCAN
                    #         ## discard the scan slot
                    #         if len(self.scan_slots) != 1:
                    #             self.scan_slots = self.scan_slots[self.scan_slots != self.ASN]
                    #         else:
                    #             self.scan_slots = []
                    #             self.action_decided = False
                                
                    #         self.do_action(ACTION.SCAN)
                        
                    #     elif self.ASN > self.scan_slots[0]:
                    #         ## Find the first element that is greater than the current ASN, discard all the elements before that
                    #         self.logger.info("Node: %s, ASN: %s, Scan slots: %s: Missed Scan Slot", self.id, self.ASN, self.scan_slots)
                    #         self.scan_slots = self.scan_slots[self.scan_slots > self.ASN]
                    #         if len(self.scan_slots) == 0:
                    #             self.action_decided = False
                            

                elif self.runtype == RUN_TYPE.ADVERTISING:
                    self.logger.debug("Node" + str(self.id) +" is on at ASN: " + str(self.ASN))
                    self.current_run_time += 1
                    self.action = ACTION.ADVERTISE
                    self.do_action(ACTION.ADVERTISE)
                
                elif self.runtype == RUN_TYPE.SCANNING:
                    self.logger.debug("Node" + str(self.id) +" is on at ASN: " + str(self.ASN))
                    self.current_run_time += 1
                    self.action = ACTION.SCAN
            
            else:
                self.action = ACTION.SLEEP
                self.do_action(ACTION.SLEEP)
    
    def reset(self):
        self.logger.info("Node: %s, Resetting", self.id)
        self.channel_map = np.zeros(self.nominal_time_period)
        self.next_wakeup = 0
        self.action = ACTION.SLEEP
        self.state = STATE.OFF
        self.offset = np.random.randint(0, self.nominal_time_period)
        self.ran_once = False
        self.action_decided = False
        
        

            