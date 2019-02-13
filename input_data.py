# -*- coding: utf-8 -*-
"""
Created on Sun Feb 10 13:41:25 2019

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
from pyomo.opt import SolverFactory

import model_script

start_time = time.time()
cwd = os.getcwd()

def scenario_inputs(inputs_directory):
    data = DataPortal()
    
    data.load(filename=os.path.join(inputs_directory, "timepoints.csv"),
              index=model_script.dispatch_model.TIMEPOINTS,
              param=(model_script.dispatch_model.grossload,
                     model_script.dispatch_model.windcap,
                     model_script.dispatch_model.windcf,
                     model_script.dispatch_model.solarcap,
                     model_script.dispatch_model.solarcf)
              )
    
    data.load(filename=os.path.join(inputs_directory, "PJM_generators.csv"),
              index=model_script.dispatch_model.GENERATORS,
              param=(model_script.dispatch_model.capacity,
                     model_script.dispatch_model.fuelcost,
                     model_script.dispatch_model.pmin,
                     model_script.dispatch_model.startcost)
              )
    
    
    return data

end_time = time.time() - start_time
print ("time elapsed during run is " + str(end_time) + " seconds")