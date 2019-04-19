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
import write_results
import create_init
import plotting


'''
explain purpose and use of model here
'''

start_time = time.time()
cwd = os.getcwd()

## CREATE SINGLE SCENARIO ##
#currently inactive
#scenario_name = "TOY" #for now
#for loading data from last timeperiod case to initialize this case
#load_init = False
#load_dir = "TEST2"  

## CREATE LINKED SCENARIO OVER MULTIPLE DAYS ##
#enter this as a list of tuples (probably can automate this / connect to case_inputs.py at some point)
scenario_list = [("1.4.2014",False,""), ("1.5.2014",True,"1.4.2014"), ("1.6.2014",True,"1.5.2014"), ("1.7.2014",True,"1.6.2014"),
                 ("1.8.2014",True,"1.7.2014"), ("1.9.2014",True,"1.8.2014"), ("1.10.2014",True,"1.9.2014")] 

#scenario_list = [("1.4.2014",False,"")]

# Allow user to specify solver path if needed (default assumes solver on path)
executable="/Applications/CPLEX_Studio129/cplex/bin/x86-64_osx/cplex"

#Directory structure, using existing files rather than creating case structure for now
class DirStructure(object):
    """
    Create directory and file structure.
    """
    def __init__(self, code_directory, load_init, load_dir):
        self.DIRECTORY = code_directory
        #self.DIRECTORY = os.path.join(self.CODE_DIRECTORY, "..")
        self.INPUTS_DIRECTORY = os.path.join(self.DIRECTORY, scenario_name, "inputs")
        self.RESULTS_DIRECTORY = os.path.join(self.DIRECTORY, scenario_name, "results")
        self.LOGS_DIRECTORY = os.path.join(self.DIRECTORY, "logs")
        if load_init:
            self.INIT_DIRECTORY = os.path.join(self.DIRECTORY, load_dir, "results")

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

            
def create_problem_instance(scenario_inputs_directory, load_init, scenario_from_directory):
    """
    Load model formulation and data, and create problem instance.
    """
    # Get model, load data, and solve
    print ("Reading model...")
    model = model_script.dispatch_model
    print ("...model read.")
    
    if load_init:
        print("Creating initial conditions data file...")
        create_init.create_init_file(scenario_from_directory, scenario_inputs_directory, 24)
        print("...initial conditions created.")
    
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
    Run instance of model
    """
    # ### Solve ### #
    if executable != "":
        solver = SolverFactory("cplex", executable=executable) 
    else:
        solver = SolverFactory("cplex") 
        
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

def run_scenario(directory_structure, load_init):
    """
    Run a scenario.
    """

    # Directories
    scenario_inputs_directory = os.path.join(directory_structure.INPUTS_DIRECTORY)
    scenario_results_directory = os.path.join(directory_structure.RESULTS_DIRECTORY) #results not needed yet
    scenario_logs_directory = os.path.join(directory_structure.LOGS_DIRECTORY)
    if load_init:
        scenario_createinputs_directory = os.path.join(directory_structure.INIT_DIRECTORY)
    else:
        scenario_createinputs_directory = None
    
    # Write logs to this directory
    TempfileManager.tempdir = scenario_logs_directory

    # Create problem instance
    instance = create_problem_instance(scenario_inputs_directory, load_init, scenario_createinputs_directory)
    
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
    
    # export results to csv
    write_results.export_results(instance, solution, scenario_results_directory, debug_mode=1)
    
    # THE REST OF THIS LOOP IS ONLY NEEDED FOR PLOTTING RESULTS
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
    zone_stamp = []
    results_wind = []
    results_solar = []
    results_curtailment = []
    price_duals = []
    reserve_duals = []
    results_spinreserves = []
    transmission_duals = []
    results_transmission_line_flow = []

    for t in instance.TIMEPOINTS:
        tmps.append(instance.TIMEPOINTS[t])
        reserve_duals.append(instance.dual[instance.TotalSpinUpReserveConstraint[t]])
        
        for line in instance.TRANSMISSION_LINE:
            transmission_duals.append(instance.dual[instance.TxFromConstraint[t,line]] +\
                                      instance.dual[instance.TxToConstraint[t,line]])
            results_transmission_line_flow.append(instance.transmit_power_MW[t,line].value)
        
        for z in instance.ZONES:
            results_wind.append(instance.windgen[t,z].value)
            results_solar.append(instance.solargen[t,z].value)
            results_curtailment.append(instance.curtailment[t,z].value)
            price_duals.append(instance.dual[instance.LoadConstraint[t,z]])

            
            for g in instance.GENERATORS:
                results_dispatch.append(instance.dispatch[t,g,z].value)
        for g in instance.GENERATORS:
            results_starts.append(instance.startup[t,g].value)
            results_shuts.append(instance.shutdown[t,g].value)
            results_spinreserves.append(instance.spinreserves[t,g].value)
            
    zones = pd.read_csv(join(dir_str.INPUTS_DIRECTORY, 'zones.csv'))
    for z in zones['zone']:
        zone_stamp.append(z)
    
    return (results_dispatch, len(tmps), results_wind, results_solar, results_curtailment, results_starts,\
            results_shuts, price_duals, reserve_duals, results_spinreserves, len(zone_stamp),\
            transmission_duals,results_transmission_line_flow)

### RUN MODEL ###
count_case = 0
for s in scenario_list:
    count_case+=1
    #initialize scenario data in the tuple
    scenario_name = s[0] #for now
    load_init = s[1]
    load_dir = s[2]
    
    #run the case, as usual
    code_directory = cwd
    dir_str = DirStructure(code_directory, load_init, load_dir)
    dir_str.make_directories()
    logger = Logger(dir_str)
    log_file = logger.log_file_path
    print("Running scenario " + str(count_case) + " of " + str(len(scenario_list)) + "...")
    print ("Running scenario " + str(scenario_name) + "...")
    stdout = sys.stdout
    sys.stdout = logger
    
    scenario_results = run_scenario(dir_str, load_init)
    
    sys.stdout = stdout #return to original
        
    # run diagnostic plots
    plotting.diagnostic_plots(scenario_results, dir_str)

    end_time = time.time() - start_time
    print ("time elapsed during run is " + str(end_time) + " seconds")