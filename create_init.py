# -*- coding: utf-8 -*-
"""
Created on Thu Apr 11 16:32:59 2019

@author: llavi
"""

import os
from os.path import join
import pandas as pd
import numpy as np

def create_init_file(from_directory, to_directory, hour):
    '''
    takes a results directory from a previous case, and reads 
    (1) the commitment (1/0 binary), 
    (2) the # hours online (integer, if committed)
    (3) the # hours offline (integer, if not committed)
    for each generator, and outputs them to a csv for the current case so that it knows how generators were dispatched
    in the most recent previous hour
    '''
    init_data = pd.read_csv(os.path.join(from_directory,"generator_commits_reserves.csv"))
    gens = init_data.Gen_Index.tolist() #get gens as a list while preserving order (hopefully)
    unique_gens = []
    for item in gens:
        if item not in unique_gens: unique_gens.append(item)
    
    gen_list = []
    commitment_status = []
    online_hours = []
    offline_hours = []
    for g in unique_gens:
        gen_list.append(g)
        commit_val = int(init_data.Committed[(init_data.Gen_Index==g) & (init_data.timepoint==hour)])
        on_val = int(init_data.TimeOn[(init_data.Gen_Index==g) & (init_data.timepoint==hour)])
        off_val = int(init_data.TimeOff[(init_data.Gen_Index==g) & (init_data.timepoint==hour)])
        commitment_status.append(commit_val)
        online_hours.append(on_val)
        offline_hours.append(off_val)

    out_df = pd.DataFrame(
    {'Gen_Index': gen_list,
     'commitinit': commitment_status,
     'upinit': online_hours,
     'downinit': offline_hours
    })
    
    out_df.to_csv(os.path.join(to_directory,"initialize_generators.csv"), index=False)
    
    return None