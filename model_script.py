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
#generator-dependent params
dispatch_model.capacity = Param(dispatch_model.GENERATORS, within=NonNegativeReals)
dispatch_model.fuelcost = Param(dispatch_model.GENERATORS, within=NonNegativeReals)

###########################
# ######## VARS ######### #
###########################

dispatch_model.dispatch = Var(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS,
                              within = NonNegativeReals, initialize=0)

###########################
# ##### CONSTRAINTS ##### #
###########################

#load/gen balance
def LoadRule(model, t):
    return (sum(model.dispatch[t,g] for g in model.GENERATORS) == model.grossload[t])
dispatch_model.LoadConstraint = Constraint(dispatch_model.TIMEPOINTS, rule=LoadRule)

#gen capacity
def CapacityMaxRule(model, t, g):
    return (model.capacity[g] >= model.dispatch[t,g])
dispatch_model.CapacityMaxConstraint = Constraint(dispatch_model.TIMEPOINTS, dispatch_model.GENERATORS, rule=CapacityMaxRule)

###########################
# ###### OBJECTIVE ###### #
###########################

def objective_rule(model): 
    return(sum(sum(model.dispatch[t,g] for t in model.TIMEPOINTS)*model.fuelcost[g] for g in model.GENERATORS)) #min dispatch cost for objective
    
dispatch_model.TotalCost = Objective(rule=objective_rule, sense=minimize)

end_time = time.time() - start_time
print ("time elapsed during run is " + str(end_time) + " seconds")