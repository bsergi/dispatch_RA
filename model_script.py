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
dispatch_model.GENERATORS = Set(domain=PositiveIntegers, ordered=True)

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

#time and zone-dependent params
dispatch_model.scheduledavailable = Param(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS, within=Binary)

#generator and zone-dependent params
dispatch_model.capacity = Param(dispatch_model.GENERATORS, dispatch_model.ZONES, within=NonNegativeReals)

#reserve segment-dependent params
dispatch_model.segmentMW = Param(dispatch_model.SEGMENTS, within=NonNegativeReals)
dispatch_model.segmentprice = Param(dispatch_model.SEGMENTS, within=NonNegativeReals)

#transmission line-dependent params
dispatch_model.transmission_from = Param(dispatch_model.TRANSMISSION_LINE, within=dispatch_model.ZONES)
dispatch_model.transmission_to = Param(dispatch_model.TRANSMISSION_LINE, within=dispatch_model.ZONES)
dispatch_model.transmission_from_capacity = Param(dispatch_model.TRANSMISSION_LINE, within=Reals)
dispatch_model.transmission_to_capacity = Param(dispatch_model.TRANSMISSION_LINE, within=Reals)
dispatch_model.line_losses_frac = Param(dispatch_model.TRANSMISSION_LINE, within=PercentFraction)

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

#dispatch_model.commitment = Var(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS,
#                                within=NonNegativeReals, bounds=(0,1), initialize=0)

#dispatch_model.startup = Var(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS,
#                                within=NonNegativeReals, bounds=(0,1), initialize=0)

#dispatch_model.shutdown = Var(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS,
#                                within=NonNegativeReals, bounds=(0,1), initialize=0)

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
    return (model.transmit_power_MW[t,line] >= model.transmission_from_capacity[line])
dispatch_model.TxFromConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.TRANSMISSION_LINE, rule=TxFromRule)

def TxToRule(model, t, line):
    return (model.transmission_to_capacity[line] >= model.transmit_power_MW[t,line])
dispatch_model.TxToConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.TRANSMISSION_LINE, rule=TxToRule)


## LOAD BALANCE ##

#load/gen balance
def LoadRule(model, t, z):
    
    #implement total tx flow
    imports_exports = 0
    for line in model.TRANSMISSION_LINE:
        if model.transmission_to[line] == z or model.transmission_from[line] == z:
            if model.transmission_to[line] == z:
                imports_exports += model.transmit_power_MW[t, line]*(1-model.line_losses_frac[line])
            elif model.transmission_from[line] == z:
                imports_exports -= model.transmit_power_MW[t, line]*(1-model.line_losses_frac[line])
    #full constraint, with tx flow now
    return (sum(model.dispatch[t,g,z] for g in model.GENERATORS) + model.windgen[t,z] +\
            model.solargen[t,z] + imports_exports == model.grossload[t,z])
dispatch_model.LoadConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.ZONES, rule=LoadRule)

#    imports_exports = 0
#    for line in model.TRANSMISSION_LINES:
#        if model.transmission_to[line] == zone or model.transmission_from[line] == zone:
#            if model.transmission_to[line] == zone:
#                imports_exports += model.Transmit_Power_MW[line, timepoint]
#            elif model.transmission_from[line] == zone:
#                imports_exports -= model.Transmit_Power_MW[line, timepoint]

## GENERATORS ###

#gen capacity
def CapacityMaxRule(model, t, g, z):
    return (model.capacity[g,z]*model.commitment[t,g] >= model.dispatch[t,g,z])
dispatch_model.CapacityMaxConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS, dispatch_model.ZONES, rule=CapacityMaxRule)

#pmin
def PminRule(model,t,g,z):
    return (model.dispatch[t,g,z] >= model.capacity[g,z]*model.commitment[t,g]*model.pmin[g])
dispatch_model.PminConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS, dispatch_model.ZONES, rule=PminRule)

## STARTUP/SHUTDOWN ##

#startups
def StartUpRule(model,t,g):
    if t==1:
        return Constraint.Skip
    else:
        return (1-model.commitment[t-1,g] >= model.startup[t,g])
dispatch_model.StartUpConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS, rule=StartUpRule)

#shutdowns
def ShutDownRule(model,t,g):
    if t==1:
        return Constraint.Skip
    else:
        return (model.commitment[t-1,g] >= model.shutdown[t,g])
dispatch_model.ShutDownConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS, rule=ShutDownRule)

#assign shuts and starts
def AssignStartShutRule(model,t,g):
    if t==1:
        return Constraint.Skip
    else:
        return (model.commitment[t,g] - model.commitment[t-1,g] == model.startup[t,g] - model.shutdown[t,g])
dispatch_model.AssignStartShutConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS, rule=AssignStartShutRule)

#force de-comitted generator if unit unavailable due to scheduled outage
def ScheduledAvailableRule(model,t,g):
    if model.scheduledavailable[t,g]==0:
        return (model.scheduledavailable[t,g] == model.commitment[t,g])
    else:
        return Constraint.Skip
dispatch_model.ScheduledAvailableConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS, rule=ScheduledAvailableRule)

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
    return model.segmentMW[s] >= model.segmentreserves[t,s]
dispatch_model.SegmentReserveConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.SEGMENTS, rule=SegmentReserveRule)

###########################
# ###### OBJECTIVE ###### #
###########################

def objective_rule(model): 
    return(sum(sum(sum(model.dispatch[t,g,z] for z in model.ZONES) for t in model.TIMEPOINTS)*model.fuelcost[g] for g in model.GENERATORS) +\
           sum(sum(model.startup[t,g] for t in model.TIMEPOINTS)*model.startcost[g] for g in model.GENERATORS) -\
           sum(sum(model.segmentprice[s]*model.segmentreserves[t,s] for s in model.SEGMENTS) for t in model.TIMEPOINTS)) #min dispatch cost for objective
    
dispatch_model.TotalCost = Objective(rule=objective_rule, sense=minimize)

end_time = time.time() - start_time
print ("time elapsed during run is " + str(end_time) + " seconds")