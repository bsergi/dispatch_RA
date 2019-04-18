# -*- coding: utf-8 -*-
"""
Created on Fri Mar  8 13:40:19 2019

@author: llavi
"""

#general imports
import os
import glob
from os.path import join
import pandas as pd
import numpy as np
import math
import time
import sys
import datetime

#other scripts that are used
import raw_data_imports
import create_ordc
import data_to_csvs

start_time = time.time()
cwd = os.getcwd()

#scenario_name = "TEST2" cases are now named below based on their corresponding date
make_init = True
create_supp_ordc = True #this really should always be true so may get rid of it later

#Directory structure for creation of files
class DirStructure(object):
    """
    Create directory and file structure for the case
    """
    def __init__(self, code_directory):
        self.DIRECTORY = code_directory
        self.INPUTS_DIRECTORY = os.path.join(self.DIRECTORY, "raw_data")
        self.SCENARIO_INPUTS_DIRECTORY = os.path.join(self.INPUTS_DIRECTORY, "case_creation_input")
        
    def case_directories(self):
        self.CASE_DIRECTORY = os.path.join(self.DIRECTORY, scenario_name)
        self.RESULTS_DIRECTORY = os.path.join(self.CASE_DIRECTORY, "inputs")

    def make_directories(self):
        if not os.path.exists(self.CASE_DIRECTORY):
            os.mkdir(self.CASE_DIRECTORY)
        if not os.path.exists(self.RESULTS_DIRECTORY):
            os.mkdir(self.RESULTS_DIRECTORY)

## USER CHOICES FOR CASE CREATION ##  
#currently done in input csvs, not here

## LOAD RELEVANT DATA ##
code_directory = cwd
#create input data directory
dir_str = DirStructure(code_directory)

#name and create case from input folder
base_inputs = pd.read_csv(os.path.join(dir_str.SCENARIO_INPUTS_DIRECTORY,"base_inputs.csv"),index_col=0)
date = base_inputs.loc['Begin Date']['value']
date = date.replace('/', '.')
print("creating case for " + str(date) + "...")
if make_init:
    print("make_init is " + str(make_init) + " for this case, so it should be the day that initializes your run")
else:
    print("make_init is " + str(make_init) + " for this case, so it should draw on a prior case to initialize its dispatch when run")
scenario_name = date

#create directory for storing case data
dir_str.case_directories()
dir_str.make_directories()


## ADDITONAL INPUTS TO BE PASSED FOR ORDC ##
#(1) Month of case
month_rename_list = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"] #this must be same as scheduled.outage.rate.by.gen.type.FULL.PERIOD.032519 month naming convention
numeric_month = int(scenario_name.split('.')[0]) #assumes date will list month first, as is standard in USA
month = month_rename_list[numeric_month-1] #-1 b/c Python lists index from 0
#(2) hydro cf
hydro_cf = float(base_inputs.loc['hydro_cf']['value'])
#(3) VOLL
VOLL = base_inputs.loc['VOLL']['value'].strip('$')
VOLL =  int(VOLL.replace(',',''))
#(4) Lowcut LOLP
lowcutLOLP = float(base_inputs.loc['lowcutLOLP']['value'])
#(5) number of segments in ORDC
n_segments = int(base_inputs.loc['Demand Curve Segments']['value'])

#pull case-level data
data = raw_data_imports.load_data(os.path.join(dir_str.INPUTS_DIRECTORY), os.path.join(dir_str.SCENARIO_INPUTS_DIRECTORY))
#run and create the main set of csvs
data_to_csvs.write_data(data, dir_str.RESULTS_DIRECTORY, make_init, dir_str.SCENARIO_INPUTS_DIRECTORY)
#create an additional dynamic ORDC file, if desired
if create_supp_ordc:

    ordc_df = create_ordc.load_and_run_ordc(dir_str.INPUTS_DIRECTORY, dir_str.RESULTS_DIRECTORY,
                                            month, hydro_cf, VOLL, lowcutLOLP, n_segments)
    ordc_df.to_csv(os.path.join(dir_str.RESULTS_DIRECTORY,"full_ordc.csv"), index=False)
else:
    print('no ORDC overwrite selected, so we are done, though this may be an issue for running the model')

#how long?
end_time = time.time() - start_time
print ("time elapsed during run is " + str(end_time) + " seconds")