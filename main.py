# -*- coding: utf-8 -*-
"""
Created on Sun Feb 10 13:50:50 2019

@author: llavi
"""

#general imports
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
import matplotlib.pyplot as plt

#import other scripts
import input_data
import model_script

'''
explain purpose and use of model here
'''

start_time = time.time()
cwd = os.getcwd()
scenario_name = "TEST" #for now

class DirStructure(object):
    """
    Create directory and file structure.
    """
    def __init__(self, code_directory):
        self.DIRECTORY = code_directory
        #self.DIRECTORY = os.path.join(self.CODE_DIRECTORY, "..")
        self.INPUTS_DIRECTORY = os.path.join(self.DIRECTORY, "inputs")
        self.RESULTS_DIRECTORY = os.path.join(self.DIRECTORY, "results")

    def make_directories(self):
        if not os.path.exists(self.RESULTS_DIRECTORY):
            os.mkdir(self.RESULTS_DIRECTORY)
            
def create_problem_instance(scenario_inputs_directory):
    """
    Load model formulation and data, and create problem instance.
    """
    # Get model, load data, and solve
    print ("Reading model...")
    model = model_script.dispatch_model
    print ("...model read.")

    print ("Loading data...")
    data = input_data.scenario_inputs(scenario_inputs_directory)
    print ("..data read.")

    print ("Compiling instance...")
    instance = model.create_instance(data)
    print ("...instance created.")

    # example code for debugging via printing output
    # getattr(instance, 'MAIN_ZONE_THERMAL_RESOURCES').pprint()

    return instance

def solve(instance):
    """
    Select solver for the problem instance
    """
    # ### Solve ### #
    solver = SolverFactory("cplex") #change if there are issues

    print ("Solving...")
    
    # to keep human-readable files for debugging, set keepfiles = True
    solution = solver.solve(instance, tee=True)

    return solution

def run_scenario(directory_structure):
    """
    Run a scenario.
    """

    # Directories
    scenario_inputs_directory = os.path.join(directory_structure.INPUTS_DIRECTORY)
    #scenario_results_directory = os.path.join(directory_structure.RESULTS_DIRECTORY)

    # Create problem instance
    instance = create_problem_instance(scenario_inputs_directory)
    
    # Solve
    solution = solve(instance)

    print ("Done running scenario, printing solution...")
    
    #load up the instance that was just solved
    instance.solutions.load_from(solution)
    #write it to an array
    #eventually this should be converted to real results writing, 
    #but for not it's just a single result
    #so OK to do this
    results_dispatch = []
    tmps = []
    for t in instance.TIMEPOINTS:
        tmps.append(instance.TIMEPOINTS[t])
        for g in instance.GENERATORS:
            results_dispatch.append(instance.dispatch[t,g].value)
    
    return (results_dispatch, len(tmps))

#run model
code_directory = cwd
dir_str = DirStructure(code_directory)
dir_str.make_directories()
print ("Running scenario " + str(scenario_name) + "...")

scenario_results = run_scenario(dir_str)
            
#plot some basic results with matplotlib
scenario_results_np = np.reshape(scenario_results[0], (int(scenario_results[1]), int(len(scenario_results[0])/scenario_results[1])))
gens = pd.read_csv(join(dir_str.INPUTS_DIRECTORY, 'PJM_generators_full.csv'))

gens_list = []
y = []

for g in gens['Category'].unique():
    gen_type = (gens['Category']==g)
    y.append(np.dot(scenario_results_np,np.array(gen_type)))

# Your x and y axis
x=range(1,int(scenario_results[1])+1)
#y is made above

# Basic stacked area chart.
plt.plot([],[],color='b', label='Hydro', linewidth=5)
plt.plot([],[],color='m', label='Nuclear', linewidth=5)
plt.plot([],[],color='k', label='Coal', linewidth=5)
plt.plot([],[],color='orange', label='Gas CC', linewidth=5)
plt.plot([],[],color='r', label='Gas CT', linewidth=5)
plt.plot([],[],color='g', label='Oil', linewidth=5)
plt.plot([],[],color='c', label='Demand Response', linewidth=5)

plt.stackplot(x,y[4],y[5],y[2],y[0],y[1],y[3],y[6], colors=['b','m','k','orange','r','g','c'])
plt.ylabel('Load (MW)')
plt.xlabel('Hour')
plt.legend(loc=4)
plt.show()

end_time = time.time() - start_time
print ("time elapsed during run is " + str(end_time) + " seconds")