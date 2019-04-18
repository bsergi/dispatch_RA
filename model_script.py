# -*- coding: utf-8 -*-
"""
Created on Sun Feb 10 13:38:29 2019

@author: llavi
"""

from __future__ import division
import os
import glob
from os.path import join
import pandas as pd
import numpy as np
import math
import time
from pyomo.environ import *

'''
this is the formulation of the Pyomo optimization model
'''

start_time = time.time()
cwd = os.getcwd()

dispatch_model = AbstractModel()

###########################
# ######## SETS ######### #
###########################

#time
dispatch_model.TIMEPOINTS = Set(domain=PositiveIntegers, ordered=True)

#generators
dispatch_model.GENERATORS = Set(ordered=True)

#operating reserve segments
dispatch_model.SEGMENTS = Set(domain=PositiveIntegers, ordered=True)

#zones
dispatch_model.ZONES = Set(doc="study zones", ordered=True)

#lines
dispatch_model.TRANSMISSION_LINE = Set(doc="tx lines", ordered=True)

#generator types? fuel types?

###########################
# ####### PARAMS ######## #
###########################

#time and zone-dependent params
dispatch_model.grossload = Param(dispatch_model.TIMEPOINTS, dispatch_model.ZONES, within=NonNegativeReals)
dispatch_model.windcf = Param(dispatch_model.TIMEPOINTS, dispatch_model.ZONES, within=NonNegativeReals)
dispatch_model.solarcf = Param(dispatch_model.TIMEPOINTS, dispatch_model.ZONES, within=NonNegativeReals)

#timepoint-dependent params
dispatch_model.temperature = Param(dispatch_model.TIMEPOINTS, within=NonNegativeReals)

#zone-dependent params
dispatch_model.windcap = Param(dispatch_model.ZONES, within=NonNegativeReals)
dispatch_model.solarcap = Param(dispatch_model.ZONES, within=NonNegativeReals)

#generator-dependent params
dispatch_model.fuelcost = Param(dispatch_model.GENERATORS, within=NonNegativeReals)
dispatch_model.pmin = Param(dispatch_model.GENERATORS, within=NonNegativeReals)
dispatch_model.startcost = Param(dispatch_model.GENERATORS, within=NonNegativeReals)
dispatch_model.canspin = Param(dispatch_model.GENERATORS, within=Binary)
dispatch_model.minup = Param(dispatch_model.GENERATORS, within=NonNegativeIntegers)
dispatch_model.mindown = Param(dispatch_model.GENERATORS, within=NonNegativeIntegers)

#generator-dependent initialization parameters
dispatch_model.commitinit = Param(dispatch_model.GENERATORS, within=Binary)
dispatch_model.upinit = Param(dispatch_model.GENERATORS, within=NonNegativeIntegers)
dispatch_model.downinit = Param(dispatch_model.GENERATORS, within=NonNegativeIntegers)

#time and zone-dependent params
dispatch_model.scheduledavailable = Param(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS, within=PercentFraction)

#generator and zone-dependent params
dispatch_model.capacity = Param(dispatch_model.GENERATORS, dispatch_model.ZONES, within=NonNegativeReals)
dispatch_model.ramp = Param(dispatch_model.GENERATORS, dispatch_model.ZONES, within=NonNegativeReals) #rate is assumed to be equal up and down
dispatch_model.rampstartuplimit = Param(dispatch_model.GENERATORS, dispatch_model.ZONES, within=NonNegativeReals) #special component of the ramping constraint on the startup hour
dispatch_model.rampshutdownlimit = Param(dispatch_model.GENERATORS, dispatch_model.ZONES, within=NonNegativeReals) #special component of the ramping constraint on the shutdown hour ---- NEW


#reserve segment-dependent params
### THESE ARE NO LONGER USED IN THE MODEL AS OF 4.14.19 ###
dispatch_model.segmentMW = Param(dispatch_model.SEGMENTS, within=NonNegativeReals)
dispatch_model.segmentprice = Param(dispatch_model.SEGMENTS, within=NonNegativeReals)

#reserve segment *and* timepoint dependent params
dispatch_model.MW = Param(dispatch_model.TIMEPOINTS, dispatch_model.SEGMENTS, within=NonNegativeReals)
dispatch_model.price = Param(dispatch_model.TIMEPOINTS, dispatch_model.SEGMENTS, within=NonNegativeReals)

#transmission line only depedent params
dispatch_model.old = Param(dispatch_model.TRANSMISSION_LINE, within=PercentFraction)

#time and transmission line-dependent params
dispatch_model.transmission_from = Param(dispatch_model.TIMEPOINTS, dispatch_model.TRANSMISSION_LINE, within=dispatch_model.ZONES)
dispatch_model.transmission_to = Param(dispatch_model.TIMEPOINTS, dispatch_model.TRANSMISSION_LINE, within=dispatch_model.ZONES)
dispatch_model.transmission_from_capacity = Param(dispatch_model.TIMEPOINTS, dispatch_model.TRANSMISSION_LINE, within=Reals)
dispatch_model.transmission_to_capacity = Param(dispatch_model.TIMEPOINTS, dispatch_model.TRANSMISSION_LINE, within=Reals)
dispatch_model.line_losses_frac = Param(dispatch_model.TIMEPOINTS, dispatch_model.TRANSMISSION_LINE, within=PercentFraction)

###########################
# ######## VARS ######### #
###########################

dispatch_model.dispatch = Var(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS, dispatch_model.ZONES,
                              within = NonNegativeReals, initialize=0)

dispatch_model.spinreserves = Var(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS,
                                  within = NonNegativeReals, initialize=0)

dispatch_model.segmentreserves =  Var(dispatch_model.TIMEPOINTS, dispatch_model.SEGMENTS,
                                      within = NonNegativeReals, initialize=0)

dispatch_model.windgen = Var(dispatch_model.TIMEPOINTS, dispatch_model.ZONES,
                              within = NonNegativeReals, initialize=0)

dispatch_model.solargen = Var(dispatch_model.TIMEPOINTS, dispatch_model.ZONES,
                              within = NonNegativeReals, initialize=0)

dispatch_model.curtailment = Var(dispatch_model.TIMEPOINTS,  dispatch_model.ZONES,
                                 within = NonNegativeReals, initialize=0)

dispatch_model.transmit_power_MW = Var(dispatch_model.TIMEPOINTS, dispatch_model.TRANSMISSION_LINE,
                                       within = Reals, initialize=0)

#the following vars will make problem integer when implemented
dispatch_model.commitment = Var(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS,
                                within=Binary, initialize=0)

dispatch_model.startup = Var(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS,
                               within=Binary, initialize=0)

dispatch_model.shutdown = Var(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS,
                               within=Binary, initialize=0)

###########################
# ##### CONSTRAINTS ##### #
###########################

## RENEWABLES ##

#wind output, should allow for curtailment but has $0 cost for now
def WindRule(model, t, z):
    return (model.windcap[z]*model.windcf[t,z] >= model.windgen[t,z])
dispatch_model.WindMaxConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.ZONES, rule=WindRule)

#solar output, should allow for curtailment but has $0 cost for now
def SolarRule(model, t, z):
    return (model.solarcap[z]*model.solarcf[t,z] >= model.solargen[t,z])
dispatch_model.SolarMaxConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.ZONES, rule=SolarRule)

#curtailment probably won't get used, but let's put it in for now
def CurtailmentRule(model, t, z):
    return (model.curtailment[t,z] == (model.windcap[z]*model.windcf[t,z]-model.windgen[t,z]) + (model.solarcap[z]*model.solarcf[t,z]-model.solargen[t,z]))
dispatch_model.CurtailmentConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.ZONES, rule=CurtailmentRule)

## TRANSMISSION LINES ##

#flow rules, simple for now but could eventually include ramp limits or etc.
def TxFromRule(model, t, line):
    return (model.transmit_power_MW[t,line] >= model.transmission_from_capacity[t, line])
dispatch_model.TxFromConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.TRANSMISSION_LINE, rule=TxFromRule)

def TxToRule(model, t, line):
    return (model.transmission_to_capacity[t, line] >= model.transmit_power_MW[t,line])
dispatch_model.TxToConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.TRANSMISSION_LINE, rule=TxToRule)


## LOAD BALANCE ##

#load/gen balance
def LoadRule(model, t, z):
    
    #implement total tx flow
    imports_exports = 0
    for line in model.TRANSMISSION_LINE:
        if model.transmission_to[t, line] == z or model.transmission_from[t, line] == z:
            if model.transmission_to[t, line] == z:
                imports_exports += model.transmit_power_MW[t, line]*(1-model.line_losses_frac[t, line])
            elif model.transmission_from[t, line] == z:
                imports_exports -= model.transmit_power_MW[t, line]*(1-model.line_losses_frac[t, line])
    #full constraint, with tx flow now
    return (sum(model.dispatch[t,g,z] for g in model.GENERATORS) + model.windgen[t,z] +\
            model.solargen[t,z] + imports_exports == model.grossload[t,z])
dispatch_model.LoadConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.ZONES, rule=LoadRule)

## GENERATORS ###

#gen capacity with scheduled outage factored in
def CapacityMaxRule(model, t, g, z):
    return (model.capacity[g,z]*model.commitment[t,g]*model.scheduledavailable[t,g] >= model.dispatch[t,g,z])
dispatch_model.CapacityMaxConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS, dispatch_model.ZONES, rule=CapacityMaxRule)

#pmin
def PminRule(model,t,g,z):
    return (model.dispatch[t,g,z] >= model.capacity[g,z]*model.commitment[t,g]*model.pmin[g])
dispatch_model.PminConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS, dispatch_model.ZONES, rule=PminRule)

## GENERATOR RAMP ##

def GeneratorRampUpRule(model,t,g,z):
    if t==1:
        return Constraint.Skip
    else:
        return (model.dispatch[t-1,g,z] + model.ramp[g,z]*model.commitment[t-1,g] + model.startup[t,g]*model.rampstartuplimit[g,z]  >= model.dispatch[t,g,z])
dispatch_model.GeneratorRampUpConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS, dispatch_model.ZONES, rule=GeneratorRampUpRule)

def GeneratorRampDownRule(model,t,g,z): ### NEW
    if t==1: ##guessing it's worthwhile to have this to guard against weirdness, even though a generator will never "get shutdown" in hour 1... 
        return Constraint.Skip 
    else:
        return (model.dispatch[t,g,z] >= model.dispatch[t-1,g,z] - model.ramp[g,z]*model.commitment[t-1,g] + model.shutdown[t,g]*model.rampshutdownlimit[g,z])
dispatch_model.GeneratorRampDownConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS, dispatch_model.ZONES, rule=GeneratorRampDownRule)

## GENERATOR STARTUP/SHUTDOWN ##

#startups
def StartUpRule(model,t,g):
    if t==1:
        return 1-model.commitinit[g] >= model.startup[t,g]
    else:
        return (1-model.commitment[t-1,g] >= model.startup[t,g])
dispatch_model.StartUpConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS, rule=StartUpRule)

#shutdowns
def ShutDownRule(model,t,g):
    if t==1:
        return model.commitinit[g] >= model.shutdown[t,g]
    else:
        return (model.commitment[t-1,g] >= model.shutdown[t,g])
dispatch_model.ShutDownConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS, rule=ShutDownRule)

#assign shuts and starts
def AssignStartShutRule(model,t,g):
    if t==1: #binds commitment in first hour based on initialization commitment from input (could be last timeperiod of previous run)
        return model.commitment[t,g] - model.commitinit[g] == model.startup[t,g] - model.shutdown[t,g]
    else: #general rule
        return (model.commitment[t,g] - model.commitment[t-1,g] == model.startup[t,g] - model.shutdown[t,g])
dispatch_model.AssignStartShutConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS, rule=AssignStartShutRule)

#force de-comitted generator if unit unavailable due to scheduled outage
def ScheduledAvailableRule(model,t,g):
    if model.scheduledavailable[t,g]==0:
        return (model.scheduledavailable[t,g] == model.commitment[t,g])
    else:
        return Constraint.Skip
dispatch_model.ScheduledAvailableConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS, rule=ScheduledAvailableRule)

## GENERATOR MIN UP AND DOWN ##

#min uptime constraint
def MinUpRule(model,t,g):
    recent_start_bool = float() #initialize our tracker; boolean because you'll just never see multiple starts

    if t - model.minup[g] <1: #i.e. in the lookback period to the initialization condition
        if model.minup[g] >= t+model.upinit[g] and model.commitinit[g]==1: #if generator started online, and hasn't been up long enough
            return model.commitment[t,g] >= model.commitinit[g]
        else:
            return Constraint.Skip
    else: #define subperiod
        for tp in range(1, model.minup[g]+1): #b/c exclusive upper bound!
            recent_start_bool += model.startup[t-tp,g]
        return model.commitment[t,g] >= recent_start_bool
dispatch_model.MinUpConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS, rule=MinUpRule)

#min downtime constraint
def MinDownRule(model,t,g):
    recent_shut_bool = float()

    if t - model.mindown[g] <1: 
        if model.mindown[g] >= t+model.downinit[g] and model.commitinit[g]==0:
            return model.commitinit[g] >= model.commitment[t,g]
        else:
            return Constraint.Skip
    else:
        for tp in range(1, model.mindown[g]+1):
            recent_shut_bool += model.shutdown[t-tp,g]
        return (1-recent_shut_bool) >= model.commitment[t,g]
dispatch_model.MinDownConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS, rule=MinDownRule)

## HOLD SUFFICIENT RESERVES ##

#caps the amount of reserve a generator can provide as delta between its max and current power output
#and provides only if generator is eligible
def GenSpinUpReserveRule(model,t,g):
    return sum((model.capacity[g,z]*model.commitment[t,g] - model.dispatch[t,g,z]) for z in model.ZONES)*model.canspin[g] >= model.spinreserves[t,g]
dispatch_model.GenSpinUpReserveConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS, rule=GenSpinUpReserveRule)

def TotalSpinUpReserveRule(model,t):
    return (sum(model.spinreserves[t,g] for g in model.GENERATORS) >= sum(model.segmentreserves[t,s] for s in model.SEGMENTS))
dispatch_model.TotalSpinUpReserveConstraint = Constraint(dispatch_model.TIMEPOINTS, rule=TotalSpinUpReserveRule)

def SegmentReserveRule(model,t,s):
    return model.MW[t,s] >= model.segmentreserves[t,s]
dispatch_model.SegmentReserveConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.SEGMENTS, rule=SegmentReserveRule)

###########################
# ###### OBJECTIVE ###### #
###########################

def objective_rule(model): 
    return(sum(sum(sum(model.dispatch[t,g,z] for z in model.ZONES) for t in model.TIMEPOINTS)*model.fuelcost[g] for g in model.GENERATORS) +\
           sum(sum(model.startup[t,g] for t in model.TIMEPOINTS)*model.startcost[g] for g in model.GENERATORS) -\
           sum(sum(model.price[t,s]*model.segmentreserves[t,s] for s in model.SEGMENTS) for t in model.TIMEPOINTS)) #min dispatch cost for objective
    
dispatch_model.TotalCost = Objective(rule=objective_rule, sense=minimize)

end_time = time.time() - start_time
print ("time elapsed during run is " + str(end_time) + " seconds")