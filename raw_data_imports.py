# -*- coding: utf-8 -*-
"""
Created on Fri Mar  8 13:40:52 2019

@author: llavi
"""

import os
from os.path import join
import pandas as pd
import numpy as np
import sys
from datetime import datetime
from datetime import timedelta
from dateutil import parser

from case_inputs import *

def load_data(inputs_directory, scenario_inputs_directory, date):
    print('begin loading data...')
    #load base data; this is not pickled so it's always re-loaded by case
    
    #load other stuff
    #this stuff is loaded from pickles for speed, but be careful if you edit the underlying file
    try:
        forced_outage_rates = pd.read_pickle(".Forced.outage.rates.by.temperature.and.unit.type.102918")
    except FileNotFoundError:
        print('loading forced outage rates from csv because not yet pickled')
        forced_outage_rates = input_to_pickle(inputs_directory, "Forced.outage.rates.by.temperature.and.unit.type.102918.csv")
    
    #load loads
    try:
        loads = pd.read_pickle(".PJM.2006.pres.loads")
    except FileNotFoundError:
        print('loading load data from csv because not yet pickled')
        loads = input_to_pickle(inputs_directory,"PJM.2006.pres.loads.csv")
        
    #load wind/solar shape
    wind_solar = pd.read_csv(os.path.join(inputs_directory,"wind_solar_hour_shape.csv"))
    
    #load wind/solar zonal capacity
    wind_capacity_df = pd.read_excel(open(os.path.join(inputs_directory,'EIA_860_2017_Wind.xlsx'), 'rb'),sheet_name='for_tool')
    solar_capacity_df = pd.read_excel(open(os.path.join(inputs_directory,'EIA_860_2017_Solar.xlsx'), 'rb'),sheet_name='for_tool')
    
    #load generator dependent stuff
    try:
        temperature_matches = pd.read_pickle(".PJM.temperature.series.forward.interp.64.WBANs.052718")
    except FileNotFoundError:
        print('loading temperature data from csv because not yet pickled')
        temperature_matches = input_to_pickle(inputs_directory,"PJM.temperature.series.forward.interp.64.WBANs.052718.csv")
    units = pd.read_csv(os.path.join(inputs_directory,"PJM.units.processed.071818.csv"))
    units_zonal_match = pd.read_csv(os.path.join(inputs_directory,"GENERATORS_LL.csv"))
    
    #load generator scheduled outages
    scheduled_outages = pd.read_csv(os.path.join(inputs_directory,"fraction.unavailable.Jan14.csv"), index_col=0)
    
    #load hydro derates
    hydro_derates = pd.read_csv(os.path.join(inputs_directory,"PJM.hydro.gen.jan.2014.csv"))
    
    #load line flow data
    line_limits = pd.read_csv(os.path.join(inputs_directory,"da_interface_flows_and_limits_full.csv"))
    
    print('end loading data, begin cleaning data...')
    
    #create cleaning dates
    startdate = parser.parse(date)
    enddate = startdate + timedelta(days, hours=-1)
    
    #clean scheduled generator outages
    clean_scheduled_outages = scheduled_outage_clean(scheduled_outages, startdate, enddate)
    
    #clean line flow limits
    clean_line_limits = line_clean(line_limits, startdate, enddate)
    
    #clean wind and solar data
    wind = vre_time_clean("wind", wind_solar, startdate, enddate)
    solar = vre_time_clean("solar", wind_solar, startdate, enddate)
    
    #clean wind and solar capacities to get the appropriate level for that month
    wind_capacity = vre_capacity_time_clean("wind", wind_capacity_df, startdate, enddate)
    solar_capacity = vre_capacity_time_clean("solar", solar_capacity_df, startdate, enddate)
    
    #clean temperatures
    temperatures = temperature_time_clean(temperature_matches, startdate, enddate)
    
    #clean gens
    gens = generator_module(units,units_zonal_match)
    gens = gens_time_clean(gens, startdate, enddate)
    
    #add dr
    DR_cost = VOLL   #cost of DR is set to the VOLL by default

    listOfSeries = [pd.Series([1846,(max(gens.X)+1),1,1,1,'DR1','DR1','NA','NA','NA','NA','NA','NA','NA','NA'
          ,'NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA'
          ,'NA','NA','NA','NA','NA','NA','1/1/1980','NA','NA','NA','NA','NA','NA','NA','NA','NA','DR'
          ,'NA',10000,'NA','NA','NA','NA','PECO',DR_cost], index=gens.columns),
    pd.Series([1847,(max(gens.X)+2),1,1,1,'DR2','DR2','NA','NA','NA','NA','NA','NA','NA','NA'
          ,'NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA'
          ,'NA','NA','NA','NA','NA','NA','1/1/1980','NA','NA','NA','NA','NA','NA','NA','NA','NA','DR'
          ,'NA',10000,'NA','NA','NA','NA','COMED',DR_cost], index=gens.columns),
    pd.Series([1848,(max(gens.X)+3),1,1,1,'DR3','DR3','NA','NA','NA','NA','NA','NA','NA','NA'
          ,'NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA'
          ,'NA','NA','NA','NA','NA','NA','1/1/1980','NA','NA','NA','NA','NA','NA','NA','NA','NA','DR'
          ,'NA',10000,'NA','NA','NA','NA','PEPCO',DR_cost], index=gens.columns),
    pd.Series([1849,(max(gens.X)+4),1,1,1,'DR4','DR4','NA','NA','NA','NA','NA','NA','NA','NA'
          ,'NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA'
          ,'NA','NA','NA','NA','NA','NA','1/1/1980','NA','NA','NA','NA','NA','NA','NA','NA','NA','DR'
          ,'NA',10000,'NA','NA','NA','NA','DOM',DR_cost], index=gens.columns),
    pd.Series([1850,(max(gens.X)+5),1,1,1,'DR5','DR5','NA','NA','NA','NA','NA','NA','NA','NA'
          ,'NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA','NA'
          ,'NA','NA','NA','NA','NA','NA','1/1/1980','NA','NA','NA','NA','NA','NA','NA','NA','NA','DR'
          ,'NA',10000,'NA','NA','NA','NA','PPL',DR_cost], index=gens.columns)]
    gens = gens.append(listOfSeries, ignore_index=True)
    
    #clean loads
    #this is the part that's taking the longest, so work on it at some point
    loadMW = loads_time_clean(loads, startdate, enddate)
    
    # summarize base_inputs for use later (note: could simplify now that inputs are via script in case_inputs.py)
    base_inputs = pd.DataFrame({"value":[date, days, wfe, sfe, lfe, zones, n_segments, VOLL, contingency, lowcutLOLP, hydro_cf]},
                               index= ["Begin Date", "Duration", "Wind forecast error", "Solar forecast error", "Load forecast error",
                                       "Zones", "Demand Curve Segments", "VOLL", "Contingency Reserve Shed", "lowcutLOLP", "hydrocf"])
    
    print('...return loaded and cleaned data')
    return (base_inputs, forced_outage_rates, gens, loadMW[0], temperatures, wind, solar, loadMW[1], 
            clean_line_limits, wind_capacity, solar_capacity, clean_scheduled_outages, hydro_derates)

def str_to_datetime(my_str):
    '''
    used to convert pd series of dates that are originally strings to pandas datetimes
    '''
    if type(my_str) == float:
        return (my_str)
    else:
        return parser.parse(my_str)

def generator_module(units, zones):
    unit_zone = pd.merge(units, zones, on='X', how='outer')
    return unit_zone

def scheduled_outage_clean(outage_df, startdate, enddate):
    '''
    takes df of scheduled outage by unit, cleans to include only active timeperiod for case
    '''
    scheduled_outage_output = outage_df
    scheduled_outage_output['date']=scheduled_outage_output.index
    return scheduled_outage_output[(scheduled_outage_output.date.apply(str_to_datetime) >= startdate) & (enddate >= scheduled_outage_output.date.apply(str_to_datetime))]

def line_clean(lines, startdate, enddate):
    '''
    takes df of lines, subsets and outputs the active timeperiod
    '''
    line_output = lines[(lines.datetime_beginning_ept.apply(str_to_datetime) >= startdate) & (enddate >= lines.datetime_beginning_ept.apply(str_to_datetime))]
    return line_output
    
def gens_time_clean(gens, startdate, enddate):
    '''
    takes df of generators, subsets those that were active during the entire timeperiod of dispatch
    '''
    
    gens = gens[gens.COMMISSION_DATE.apply(str_to_datetime) <= startdate]
    gens = gens[(gens.RETIRED == 0) | (gens.RETIRED_DATE.apply(str_to_datetime) >= enddate)]
    
    return gens

def vre_time_clean(vre_type, vre_df, startdate, enddate):
    '''
    takes df of hourly vre normalized cap factor, subsets based on vre type what you want
    '''
    if vre_type == "solar":
        vre_df = vre_df[(vre_df.date.apply(str_to_datetime) >= startdate) & (enddate >= vre_df.date.apply(str_to_datetime))]
        return vre_df.pjm_pv_jeremy_scaled_3_28
    elif vre_type == "wind":
        vre_df = vre_df[(vre_df.date.apply(str_to_datetime) >= startdate) & (enddate >= vre_df.date.apply(str_to_datetime))]
        return vre_df.NREL_wind_scaled
    else:
        print('you can only return solar or wind data, this is a problem!!')
        return None
    
def vre_capacity_time_clean(vre_type, vre_df, startdate, enddate):
    '''
    very similar to vre_time_clean, but handles the input capacities rather than the input hourly shapes
    '''
    if vre_type == "solar":
        vre_df = vre_df[(vre_df.Equiv_End_Date.apply(str_to_datetime) >= startdate) & (enddate >= vre_df.Equiv_Begin_Date.apply(str_to_datetime))]
        return vre_df
    elif vre_type == "wind":
        vre_df = vre_df[(vre_df.Equiv_End_Date.apply(str_to_datetime) >= startdate) & (enddate >= vre_df.Equiv_Begin_Date.apply(str_to_datetime))]
        return vre_df
    else:
        print('you need to say whether this is wind or solar data. You input something else. Problem!')
        return None
    
def loads_time_clean(loads, startdate, enddate):
    '''
    takes df of loads, subsets those from the time period
    '''
    loads = loads[(loads.HourEnd.apply(str_to_datetime) >= startdate) & (enddate >= loads.HourEnd.apply(str_to_datetime))]
    return (loads.LoadMW,loads.HourEnd)

def temperature_time_clean(temps, startdate, enddate):
    '''
    takes df of temperatures, subsets and combines relevant location temperatures
    '''
    temps = temps.rename(columns={ temps.columns[0]: "date" })
    temps = temps.rename(columns={ temps.columns[1]: "usedweather" })
    temps = temps[(temps.date.apply(str_to_datetime) >= startdate) & (enddate >= temps.date.apply(str_to_datetime))]
    return temps.usedweather
    

def input_to_pickle(data_path, csv_string):
    '''
    takes input csv file and pickles it for faster loading in future
    '''
    csv_path = join(data_path, csv_string)
    df = pd.read_csv(csv_path)
    pickle_name = "." + csv_string[:-4]
    df.to_pickle(pickle_name)
    return df