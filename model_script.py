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

#generator types? fuel types?

###########################
# ####### PARAMS ######## #
###########################

#time-dependent params
dispatch_model.grossload = Param(dispatch_model.TIMEPOINTS, within=NonNegativeReals)
dispatch_model.windcap = Param(dispatch_model.TIMEPOINTS, within=NonNegativeReals)
dispatch_model.windcf = Param(dispatch_model.TIMEPOINTS, within=NonNegativeReals)
dispatch_model.solarcap = Param(dispatch_model.TIMEPOINTS, within=NonNegativeReals)
dispatch_model.solarcf = Param(dispatch_model.TIMEPOINTS, within=NonNegativeReals) 
#generator-dependent params
dispatch_model.capacity = Param(dispatch_model.GENERATORS, within=NonNegativeReals)
dispatch_model.fuelcost = Param(dispatch_model.GENERATORS, within=NonNegativeReals)
dispatch_model.pmin = Param(dispatch_model.GENERATORS, within=NonNegativeReals)
dispatch_model.startcost = Param(dispatch_model.GENERATORS, within=NonNegativeReals)

###########################
# ######## VARS ######### #
###########################

dispatch_model.dispatch = Var(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS,
                              within = NonNegativeReals, initialize=0)

dispatch_model.windgen = Var(dispatch_model.TIMEPOINTS,
                              within = NonNegativeReals, initialize=0)

dispatch_model.solargen = Var(dispatch_model.TIMEPOINTS,
                              within = NonNegativeReals, initialize=0)

dispatch_model.curtailment = Var(dispatch_model.TIMEPOINTS,
                                 within = NonNegativeReals, initialize=0)

#the following vars will make problem integer
dispatch_model.commitment = Var(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS,
                                within=Binary, initialize=0)

dispatch_model.startup = Var(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS,
                                within=Binary, initialize=0)

dispatch_model.shutdown = Var(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS,
                                within=Binary, initialize=0)

###########################
# ##### CONSTRAINTS ##### #
###########################

#wind output, should allow for curtailment but has $0 cost for now
def WindRule(model, t):
    return (model.windcap[t]*model.windcf[t] >= model.windgen[t])
dispatch_model.WindMaxConstraint = Constraint(dispatch_model.TIMEPOINTS, rule=WindRule)

#solar output, should allow for curtailment but has $0 cost for now
def SolarRule(model, t):
    return (model.solarcap[t]*model.solarcf[t] >= model.solargen[t])
dispatch_model.SolarMaxConstraint = Constraint(dispatch_model.TIMEPOINTS, rule=SolarRule)

#curtailment probably won't get used, but let's put it in for now
def CurtailmentRule(model, t):
    return (model.curtailment[t] == (model.windcap[t]*model.windcf[t]-model.windgen[t]) + (model.solarcap[t]*model.solarcf[t]-model.solargen[t]))
dispatch_model.CurtailmentConstraint = Constraint(dispatch_model.TIMEPOINTS, rule=CurtailmentRule)

#load/gen balance
def LoadRule(model, t):
    return (sum(model.dispatch[t,g] for g in model.GENERATORS) + model.windgen[t] + model.solargen[t] == model.grossload[t])
dispatch_model.LoadConstraint = Constraint(dispatch_model.TIMEPOINTS, rule=LoadRule)

#gen capacity
def CapacityMaxRule(model, t, g):
    return (model.capacity[g]*model.commitment[t,g] >= model.dispatch[t,g])
dispatch_model.CapacityMaxConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS, rule=CapacityMaxRule)

#pmin
def PminRule(model,t,g):
    return (model.dispatch[t,g] >= model.capacity[g]*model.commitment[t,g]*model.pmin[g])
dispatch_model.PminConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS, rule=PminRule)

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

###########################
# ###### OBJECTIVE ###### #
###########################

def objective_rule(model): 
    return(sum(sum(model.dispatch[t,g] for t in model.TIMEPOINTS)*model.fuelcost[g] for g in model.GENERATORS) +\
           sum(sum(model.startup[t,g] for t in model.TIMEPOINTS)*model.startcost[g] for g in model.GENERATORS)) #min dispatch cost for objective
    
dispatch_model.TotalCost = Objective(rule=objective_rule, sense=minimize)

end_time = time.time() - start_time
print ("time elapsed during run is " + str(end_time) + " seconds")