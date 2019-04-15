# -*- coding: utf-8 -*-
"""
Created on Sun Apr 14 19:41:54 2019

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
#import raw_data_imports

## DATA MANIPULATION TO CREATE INPUT FILES ##

def create_gens_init(gens):
    gens = gens.sort_values('X')
    gens = gens.set_index('UNITNAME')
    gen_index = []
    commit = []
    up = []
    down = []
    for g in list(gens.index):
        gen_index.append(g)
        commit.append(0)
        up.append(0)
        down.append(100)
    df = pd.DataFrame(
    {'Gen_Index': gen_index,
     'commit_init': commit,
     'time_up_init': up,
     'time_down_init': down
    })
    return df

def create_zonal_timepoints(zone_df, zone_list, load_df, wind_shape, solar_shape):
    zone_index = []
    time_index = []
    assigned_load = []
    wind_cf = []
    solar_cf = []
    for z in zone_list:
        for t in range(1,load_df.shape[0]+1):
            time_index.append(t)
            zone_index.append(z)
            assigned_load.append(load_df.iloc[t-1]*sum(zone_df.Frac_Load[zone_df.Assigned_Zone==z]))
            wind_cf.append(wind_shape.iloc[t-1])
            solar_cf.append(solar_shape.iloc[t-1])
    df = pd.DataFrame(
    {'timepoint': time_index,
     'zone': zone_index,
     'gross_load': assigned_load,
     'wind_cf': wind_cf,
     'solar_cf': solar_cf
    })
    
    return df
'''
def create_lines(lines, zone_list):
    line_names = []
    from_zone = []
    to_zone = []
    min_flow = []
    max_flow = []
    losses_frac = []
    count_z = 0
    for z in zone_list:
        count_l = 0
        for l in zone_list:
            if len(lines[(lines.tx_from_zone==z) & (lines.tx_to_zone==l)]) == 1:
                index_val = lines[(lines.tx_from_zone==z) & (lines.tx_to_zone==l)].index[0]
                from_str = str(lines.tx_from_zone[(lines.tx_from_zone==z) & (lines.tx_to_zone==l)][index_val])
                to_str = str(lines.tx_to_zone[(lines.tx_from_zone==z) & (lines.tx_to_zone==l)][index_val])
                line_names.append((str(from_str)+"_to_"+str(to_str)))
                from_zone.append(from_str)
                to_zone.append(to_str)
                min_flow.append(lines.min_flow[(lines.tx_from_zone==z) & (lines.tx_to_zone==l)][index_val])
                max_flow.append(lines.max_flow[(lines.tx_from_zone==z) & (lines.tx_to_zone==l)][index_val])
                losses_frac.append(.02)
            elif count_l > count_z:
                line_names.append(z+"_to_"+l)
                from_zone.append(z)
                to_zone.append(l)
                min_flow.append(0)
                max_flow.append(0)
                losses_frac.append(.02)
            count_l+=1
        count_z+=1
    df = pd.DataFrame({'transmission_line': line_names,
     'transmission_from': from_zone,
     'transmission_to': to_zone,
     'min_flow': min_flow,
     'max_flow': max_flow,
     'line_losses_frac': losses_frac
    })

    return df

'''

def create_lines(lines, zone_list):
    line_names = []
    old = []
    count_z = 0
    for z in zone_list:
        count_l = 0
        for l in zone_list:
            if len(lines[(lines.tx_from_zone==z) & (lines.tx_to_zone==l)]) == 1:
                index_val = lines[(lines.tx_from_zone==z) & (lines.tx_to_zone==l)].index[0]
                from_str = str(lines.tx_from_zone[(lines.tx_from_zone==z) & (lines.tx_to_zone==l)][index_val])
                to_str = str(lines.tx_to_zone[(lines.tx_from_zone==z) & (lines.tx_to_zone==l)][index_val])
                line_names.append((str(from_str)+"_to_"+str(to_str)))
                old.append(0.1)
            elif count_l > count_z:
                line_names.append(z+"_to_"+l)
                old.append(0)
            count_l+=1
        count_z+=1
    df = pd.DataFrame({'transmission_line': line_names,
     'old': old
    })

    return df

def create_hourly_lines(lines, zone_list, load_df_for_timepoints):
    time_index = []
    line_names = []
    from_zone = []
    to_zone = []
    min_flow = []
    max_flow = []
    losses_frac = []
    count_z = 0
    #print(lines.columns)
    for z in zone_list:
        count_l = 0
        for l in zone_list:
            if len(lines[(lines.tx_from_zone==z) & (lines.tx_to_zone==l)]) >= 1:
                #print(lines[(lines.tx_from_zone==z) & (lines.tx_to_zone==l)])
                for t in range(1,load_df_for_timepoints.shape[0]+1):
                    time_index.append(t)
                    index_val = lines[(lines.tx_from_zone==z) & (lines.tx_to_zone==l)].index[t-1]
                    from_str = str(lines.tx_from_zone[(lines.tx_from_zone==z) & (lines.tx_to_zone==l)][index_val])
                    to_str = str(lines.tx_to_zone[(lines.tx_from_zone==z) & (lines.tx_to_zone==l)][index_val])
                    line_names.append((str(from_str)+"_to_"+str(to_str)))
                    from_zone.append(from_str)
                    to_zone.append(to_str)
                    min_flow.append((-1.)*lines.limit_mw[(lines.tx_from_zone==z) & (lines.tx_to_zone==l)][index_val])
                    max_flow.append(lines.limit_mw[(lines.tx_from_zone==z) & (lines.tx_to_zone==l)][index_val])
                    losses_frac.append(.02)
            elif count_l > count_z:
                for t in range(1,load_df_for_timepoints.shape[0]+1):
                    time_index.append(t)
                    line_names.append(z+"_to_"+l)
                    from_zone.append(z)
                    to_zone.append(l)
                    min_flow.append(0)
                    max_flow.append(0)
                    losses_frac.append(.02)
            count_l+=1
        count_z+=1
    df = pd.DataFrame({'timepoint': time_index,
    'transmission_line': line_names,
     'transmission_from': from_zone,
     'transmission_to': to_zone,
     'min_flow': min_flow,
     'max_flow': max_flow,
     'line_losses_frac': losses_frac
    })

    return df

def create_zones(zone_df, zone_list, wind, solar):
    zone_index = []
    wind_cap = []
    solar_cap = []
    for z in zone_list:
        zone_index.append(z)
        wind_cap.append(wind.iloc[0][str(z)])
        solar_cap.append(solar.iloc[0][str(z)])
        #wind_cap.append(sum(zone_df.wind_capacity_MW[zone_df.Assigned_Zone==z]))
        #solar_cap.append(sum(zone_df.solar_capacity_MW[zone_df.Assigned_Zone==z]))
    df = pd.DataFrame(
    {'zone': zone_index,
     'wind_cap': wind_cap,
     'solar_cap': solar_cap
    })
    
    return df

def knit_generator_zone(gens, zones):
    '''
    takes list of zones, and df of generators, and knits together to get the capacity of 
    each generator in a zone
    for now, format is for capacity to be 0 in zones where generator doesn't exist
    '''
    gens = gens.sort_values('X')
    gens = gens.set_index('UNITNAME')
    gen_index = []
    zone_index = []
    gen_zone_cap = []
    ramp_rate = []
    ramp_start = []
    ramp_shut = []
    for z in zones:
        for g in list(gens.index):
            gen_index.append(g)
            zone_index.append(z)
            if z == gens.Assigned_Zone[g]:
                gen_zone_cap.append(gens.RATINGMW_y[g])
            else:
                gen_zone_cap.append(0)
            ramp_rate.append(gens.RATINGMW_y[g]*.2)
            ramp_start.append(gens.RATINGMW_y[g]*.95)
            ramp_shut.append(gens.RATINGMW_y[g]*.1)
    df = pd.DataFrame(
    {'Gen_Index': gen_index,
     'zone': zone_index,
     'capacity': gen_zone_cap,
     'Ramp_Rate': ramp_rate,
     'Ramp_Start': ramp_start,
     'Ramp_Shutdown': ramp_shut
    })
    return df

def create_scheduled_outage_file(n_timepoints, list_gens):
    '''
    takes a number of timepoints, and a list of the generators, and creates an outage schedule
    is all ones (online) for now, but could change in the future.
    Easy way to to change would be to pass dataframe of the time/generator scheduled outage pairs, then set those to 0
    '''
    time_list = []
    gens_list = []
    scheduled_list = []
    for t in range(1,n_timepoints+1):
        for g in list_gens:
            time_list.append(t)
            gens_list.append(g)
            scheduled_list.append(1) #all ones for now, but could rewrite if want to pass scheduled outages
    df = pd.DataFrame(
    {'timepoint': time_list,
     'Gen_Index': gens_list,
     'available': scheduled_list
    })
    return df

def create_operating_reserve_curve(n_segments, price_cap):
    '''
    creates operating reserve demand curve
    is single curve for now, but should eventually be determined hourly
    quantity and price are dummy inputs for now
    '''
    segment_list = []
    segment_quantity = []
    segment_price = []
    for s in range(1,n_segments+1):
        segment_list.append(s)
        segment_quantity.append(100) #made up for now
        segment_price.append(price_cap/(s**2)) #made up for now
    df = pd.DataFrame(
    {'segments': segment_list,
     'MW': segment_quantity,
     'Price': segment_price
    })
    return df


## DUMP TO OUTPUT FILES ##

def write_data(data, results_directory, init, scenario_inputs_directory):
    print('writing results to output files...')
    loadMW = data[3]
    
    #write the timepoints of the input case to a file, just to have a record
    #this is IN NO WAY used by the optimization run
    timepoint_match_df = pd.DataFrame(
    {'model_timepoint': list(range(1,len(data[7])+1)),
     'input_datetime': list(data[7])
    })
    timepoint_match_df.to_csv(os.path.join(results_directory,"timepoint_input_record.csv"), index=False)
    
    #create segmented ORDC based on hourly load and temperature
    
    #write generators files
    gens = data[2]
    gen_types = pd.read_csv(os.path.join(scenario_inputs_directory,"gentype_inputs.csv"))
    merged_gens = pd.merge(gens, gen_types, on='ID6_y')
    merged_gens['startcost'] = merged_gens.start_scalar * merged_gens.RATINGMW_y
    merged_gens['marginalcost'] = merged_gens.FuelCost * merged_gens.GEN_HEATRATE
    merged_gens = merged_gens.sort_values('X')
    pjm_out = merged_gens[['UNITNAME','marginalcost','Pmin','startcost','can_spin','minup','mindown']]
    pjm_out.columns = ['Gen_Index',	'Fuel_Cost	','Pmin','start_cost','Can_Spin','Min_Up','Min_Down']
    pjm_out.to_csv(os.path.join(results_directory,"PJM_generators.csv"), index=False)
    
    if init:
        out_init = create_gens_init(merged_gens)
        out_init.to_csv(os.path.join(results_directory,"initialize_generators.csv"), index=False)
    pjm_out_full = merged_gens[['X','UNITNAME','ZONE','ID6_y','RATINGMW_y','marginalcost','can_spin']]
    pjm_out_full = pjm_out_full.sort_values('X')
    pjm_out_full.columns = ['Gen_Index',	'Name', 'Zone',	'Category',	'Capacity',	'Fuel_Cost',	'Can_Spin']
    pjm_out_full.to_csv(os.path.join(results_directory,"PJM_generators_full.csv"), index=False)
    
    #knit with zones, write zones file
    #this perhaps should be in the "only if zonal" clause of the script
    zone_file = pd.read_csv(os.path.join(scenario_inputs_directory,"LDA_to_zone.csv"))
    zone_list = list(zone_file.Assigned_Zone.unique())
    if len(zone_list)==5: #my purposeful pjm sorting
        print('re-ordering zones according to my criteria')
        new_zone_list = []
        for z in [0,3,4,1,2]:
            new_zone_list.append(zone_list[z])
        zone_list = new_zone_list
    gens_w_zone = pd.merge(merged_gens, zone_file, on='ZONE')
    gens_w_zone = gens_w_zone.sort_values('X')
    pjm_gens_zones = knit_generator_zone(gens_w_zone, zone_list)
    pjm_gens_zones.to_csv(os.path.join(results_directory,"PJM_generators_zone.csv"), index=False)
    
    #write scheduled outage file
    merged_gens_reindex = merged_gens.sort_values('X')
    merged_gens_reindex = merged_gens_reindex.set_index('UNITNAME')
    scheduled_outage_df = create_scheduled_outage_file(loadMW.shape[0],list(merged_gens_reindex.index))
    scheduled_outage_df.to_csv(os.path.join(results_directory,'PJM_generators_scheduled_outage.csv'), index=False)
    
    #write operating reserve file
    segment_int = int(data[0].value[6])
    cost_int = int(data[0].value[8].strip('$'))
    operating_reserve_df = create_operating_reserve_curve(segment_int,cost_int)
    operating_reserve_df.to_csv(os.path.join(results_directory,'operating_reserve_segments.csv'), index=False)
    
    #write timepoints file (just has temperatures for now)
    temperatures = pd.DataFrame(data[4])
    temperatures = temperatures.rename(columns={temperatures.columns[0]: "temperature" })
    temperatures['timepoint']=list(range(1, temperatures.shape[0]+1))
    temperatures = temperatures.iloc[:, ::-1]
    temperatures.to_csv(os.path.join(results_directory,"timepoints_index.csv"),index=False)    
    
    if data[0].value[5] == "FALSE":
        loadMW.to_csv(os.path.join(results_directory,"timepoints_zonal.csv"))
        zone_df = pd.DataFrame([["PJM", 15, 14]], columns = ['zone', 'wind_cap','solar_cap']) 
        zone_df.to_csv(os.path.join(results_directory,"zones.csv"))
    else:
        #create zones csv
        zone_df = create_zones(zone_file, zone_list, data[9], data[10]) #now adds wind and solar installed data
        zone_df.to_csv(os.path.join(results_directory,"zones.csv"), index=False)
        #create timepoints/zones csv
        timepoints_zonal_df = create_zonal_timepoints(zone_file, zone_list, loadMW, data[5], data[6])
        timepoints_zonal_df.to_csv(os.path.join(results_directory,"timepoints_zonal.csv"), index=False)
        #loadMW.to_csv(os.path.join(results_directory,"timepoints_zonal.csv"))
        #create transmission lines csv
        input_lines = pd.read_csv(os.path.join(scenario_inputs_directory,"transmission_lines_inputs.csv"))
        line_df = create_lines(input_lines, zone_list)
        line_df.to_csv(os.path.join(results_directory,"transmission_lines.csv"), index=False)
        
        #create alternate transmission lines csv
        hourly_lines = pd.merge(data[8], input_lines, on='interface_limit_name')
        hourly_line_output = create_hourly_lines(hourly_lines, zone_list, loadMW)
        hourly_line_output.to_csv(os.path.join(results_directory,"transmission_lines_hourly.csv"), index=False)
        
    print('...results written')
    return None