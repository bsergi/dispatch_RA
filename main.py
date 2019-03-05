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
import sys
import datetime
from pyutilib.services import TempfileManager
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
scenario_name = "TOY" #for now

#Directory structure, using existing files rather than creating case structure for now
class DirStructure(object):
    """
    Create directory and file structure.
    """
    def __init__(self, code_directory):
        self.DIRECTORY = code_directory
        #self.DIRECTORY = os.path.join(self.CODE_DIRECTORY, "..")
        self.INPUTS_DIRECTORY = os.path.join(self.DIRECTORY, scenario_name, "inputs")
        self.RESULTS_DIRECTORY = os.path.join(self.DIRECTORY, scenario_name, "results")
        self.LOGS_DIRECTORY = os.path.join(self.DIRECTORY, "logs")

    def make_directories(self):
        if not os.path.exists(self.RESULTS_DIRECTORY):
            os.mkdir(self.RESULTS_DIRECTORY)
        if not os.path.exists(self.LOGS_DIRECTORY):
            os.mkdir(self.LOGS_DIRECTORY)
            
# Logging
class Logger(object):
    """
    The print statement will call the write() method of any object you assign to sys.stdout,
    so assign the terminal (stdout) and a log file as output destinations.
    """
    def __init__(self, directory_structure):
        self.terminal = sys.stdout
        self.log_file_path = os.path.join(directory_structure.LOGS_DIRECTORY,
                                          datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S') + "_" +
                                          str(scenario_name) + ".log")
        self.log_file = open(self.log_file_path, "w", buffering=1)

    def write(self, message):
        self.terminal.write(message)
        self.log_file.write(message)

    def flush(self):
        self.terminal.flush()
        self.log_file.flush()

            
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
    try:
        solution = solver.solve(instance, tee=True, keepfiles=False)
    except PermissionError:
        print("Yuck, a permission error")
        for file in glob.glob("*.log"):
            print("removing log files due to Permission Error")
            file_path = open(file)
            file_path.close()
            time.sleep(1)
            os.remove(file)
        return solve(instance)
    
    return solution

def load_solution(instance, results):
    """
    Load results.
    """
    instance.solutions.load_from(results)

def run_scenario(directory_structure):
    """
    Run a scenario.
    """

    # Directories
    scenario_inputs_directory = os.path.join(directory_structure.INPUTS_DIRECTORY)
    #scenario_results_directory = os.path.join(directory_structure.RESULTS_DIRECTORY) #results not needed yet
    scenario_logs_directory = os.path.join(directory_structure.LOGS_DIRECTORY)

    # Write logs to this directory
    TempfileManager.tempdir = scenario_logs_directory

    # Create problem instance
    instance = create_problem_instance(scenario_inputs_directory)
    
    # Create a 'dual' suffix component on the instance, so the solver plugin will know which suffixes to collect
    #instance.dual = Suffix(direction=Suffix.IMPORT)
    
    # Solve
    solution = solve(instance)

    print ("Done running MIP, relaxing to LP to obtain duals...")
    
    instance.commitment.fix() #fix binary variables to relax to LP
    instance.startup.fix() 
    instance.shutdown.fix()
    instance.preprocess()   
    instance.dual = Suffix(direction=Suffix.IMPORT) 
    solution = solve(instance)   #solve LP and print dual
    
    #load up the instance that was just solved
    load_solution(instance, solution)
    #instance.solutions.load_from(solution)
    #write it to an array
    #eventually this should be converted to real results writing, 
    #but for not it's just a single result
    #so OK to do this
    results_dispatch = []
    results_starts = []
    results_shuts = []
    tmps = []
    results_wind = []
    results_solar = []
    results_curtailment = []
    price_duals = []
    reserve_duals = []
    results_spinreserves = []

    for t in instance.TIMEPOINTS:
        results_wind.append(instance.windgen[t].value)
        results_solar.append(instance.solargen[t].value)
        results_curtailment.append(instance.curtailment[t].value)
        tmps.append(instance.TIMEPOINTS[t])
        price_duals.append(instance.dual[instance.LoadConstraint[t]])
        reserve_duals.append(instance.dual[instance.TotalSpinUpReserveConstraint[t]])

        for g in instance.GENERATORS:
            results_dispatch.append(instance.dispatch[t,g].value)
            results_starts.append(instance.startup[t,g].value)
            results_shuts.append(instance.shutdown[t,g].value)
            results_spinreserves.append(instance.spinreserves[t,g].value)
    
    return (results_dispatch, len(tmps), results_wind, results_solar, results_curtailment, results_starts, results_shuts, price_duals, reserve_duals, results_spinreserves)

#run model
code_directory = cwd
dir_str = DirStructure(code_directory)
dir_str.make_directories()
logger = Logger(dir_str)
log_file = logger.log_file_path
print ("Running scenario " + str(scenario_name) + "...")
stdout = sys.stdout
sys.stdout = logger

scenario_results = run_scenario(dir_str)

sys.stdout = stdout #return to original
            
#plot some basic results with matplotlib
scenario_results_np = np.reshape(scenario_results[0], (int(scenario_results[1]), int(len(scenario_results[0])/scenario_results[1])))
start_results_np = np.reshape(scenario_results[5], (int(scenario_results[1]), int(len(scenario_results[5])/scenario_results[1])))
shut_results_np = np.reshape(scenario_results[6], (int(scenario_results[1]), int(len(scenario_results[6])/scenario_results[1])))
spin_results_np = np.reshape(scenario_results[9], (int(scenario_results[1]), int(len(scenario_results[9])/scenario_results[1])))
gens = pd.read_csv(join(dir_str.INPUTS_DIRECTORY, 'PJM_generators_full.csv'))

gens_list = []
y = []
start = []
shut = []
spinreserves = []

for g in gens['Category'].unique():
    print(g)
    gen_type = (gens['Category']==g)
    y.append(np.dot(scenario_results_np,np.array(gen_type)))
    start.append(np.dot(start_results_np,np.array(gen_type)))
    shut.append(np.dot(shut_results_np,np.array(gen_type)))
    spinreserves.append(np.dot(spin_results_np,np.array(gen_type)))
# Your x and y axis
x=range(1,int(scenario_results[1])+1)
#y is made above

# Basic stacked area chart.
plt.plot([],[],color='b', label='Hydro', linewidth=5)
plt.plot([],[],color='m', label='Nuclear', linewidth=5)
plt.plot([],[],color='k', label='Coal', linewidth=5)
plt.plot([],[],color='orange', label='Gas CC', linewidth=5)
plt.plot([],[],color='sienna', label='Gas CT', linewidth=5)
plt.plot([],[],color='g', label='Oil', linewidth=5)
plt.plot([],[],color='silver', label='Demand Response', linewidth=5)
plt.plot([],[],color='cyan', label='Wind', linewidth=5)
plt.plot([],[],color='yellow', label='Solar', linewidth=5)
plt.plot([],[],color='red', label='Curtailment', linewidth=5)

plt.stackplot(x,y[4],y[5],y[2],y[0],y[1],y[3],y[6],
              np.asarray(scenario_results[2]),np.asarray(scenario_results[3]),np.asarray(scenario_results[4]),
              colors=['b','m','k','orange','sienna','g','silver','cyan','yellow','red'])
plt.ylabel('Load (MW)')
plt.xlabel('Hour')
plt.legend(loc=4)
plt.show()

#do also for starts
plt.plot([],[],color='b', label='Hydro', linewidth=5)
plt.plot([],[],color='m', label='Nuclear', linewidth=5)
plt.plot([],[],color='k', label='Coal', linewidth=5)
plt.plot([],[],color='orange', label='Gas CC', linewidth=5)
plt.plot([],[],color='sienna', label='Gas CT', linewidth=5)
plt.plot([],[],color='g', label='Oil', linewidth=5)

plt.stackplot(x,start[4],start[5],start[2],start[0],start[1],start[3],
              colors=['b','m','k','orange','sienna','g'])
plt.ylabel('StartUps (# Plants)')
plt.xlabel('Hour')
plt.legend()
plt.show()

#and for the held spin reserves by generator type
plt.plot([],[],color='b', label='Hydro', linewidth=5)
plt.plot([],[],color='m', label='Nuclear', linewidth=5)
plt.plot([],[],color='k', label='Coal', linewidth=5)
plt.plot([],[],color='orange', label='Gas CC', linewidth=5)
plt.plot([],[],color='sienna', label='Gas CT', linewidth=5)
plt.plot([],[],color='g', label='Oil', linewidth=5)

plt.stackplot(x,spinreserves[4],spinreserves[5],spinreserves[2],spinreserves[0],spinreserves[1],spinreserves[3],
              colors=['b','m','k','orange','sienna','g'])
plt.ylabel('Held Spin Reserves (MW)')
plt.xlabel('Hour')
plt.legend()
plt.show()


#and finally, plot the energy LMP dual and then the reserve dual
plt.plot(x, np.asarray(scenario_results[7]), color='r')
plt.ylabel('Energy Price ($/MWh)')
plt.xlabel('Hour')
plt.show()

plt.plot(x, np.asarray(scenario_results[8]), color='black')
plt.ylabel('Reserve Price ($/MW)')
plt.xlabel('Hour')
plt.show()

end_time = time.time() - start_time
print ("time elapsed during run is " + str(end_time) + " seconds")