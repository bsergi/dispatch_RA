# -*- coding: utf-8 -*-
"""
Created on Sat Apr 13 15:46:19 2019

@author: llavi
"""
import pandas as pd
from os.path import join
import os
import numpy as _np
import scipy.signal
import time

start_time = time.time() #record start time so can know how long this version of the script takes

def load_and_run_ordc(raw_input_dir, case_dir,
                      month, hydro_cf, VOLL, lowcutLOLP, n_segments): #this should be run from the main script, if desired, with appropriate inputs
    print('running creation of new ORDC')
    #things to eventually pass
    #(1) Month of case
    #(2) hydro cf
    #(3) VOLL
    #(4) Lowcut LOLP
    #(5) number of segments in ORDC
    
    #general inputs from raw
    planned_out_df = pd.read_csv(os.path.join(raw_input_dir,"scheduled.outage.rate.by.gen.type.FULL.PERIOD.032519.csv"))
    forced_out_df = pd.read_csv(os.path.join(raw_input_dir,"Forced.outage.rates.by.temperature.and.unit.type.102918.csv"))
    
    #based on the specific case
    load_df = pd.read_csv(os.path.join(case_dir,"timepoints_zonal.csv"))
    wind_solar_df = pd.read_csv(os.path.join(case_dir,"zones.csv"))
    gen_df = pd.read_csv(os.path.join(case_dir,"PJM_generators_full.csv"))
    temp_df = pd.read_csv(os.path.join(case_dir,"timepoints_index.csv"))
    
    return create_ordc(gen_df, planned_out_df, load_df, wind_solar_df, temp_df, forced_out_df,
                       month, hydro_cf, VOLL, lowcutLOLP, n_segments)


#this is basically just a test script for getting the ORDC formulation to work
def create_ordc(gen_df, planned_out_df, load_df, wind_solar_df, temp_df, forced_out_df,
                month, hydro_cf, VOLL, lowcutLOLP, n_segments):
    
    #create generator stack on unit marginal cost
    gen_type_capacity = gen_df
    #dec generator stack by monthly planned outages
    #month="Jan"
    planned_out_df.rename(columns ={'Unnamed: 0': "Category"}, inplace =True)
    gen_type_capacity = pd.merge(gen_type_capacity, planned_out_df, on='Category')
    gen_type_capacity["Month_Capacity"]=gen_type_capacity["Capacity"]-gen_type_capacity[month]*gen_type_capacity["Capacity"]
    gen_type_capacity = gen_type_capacity.set_index("Gen_Index")
    gen_type_capacity = gen_type_capacity.sort_values("Fuel_Cost")
    #derate hydro by cf
    #hydro_cf = 0.5
    derate_capacity = []
    for g in list(gen_type_capacity.index):
        if gen_type_capacity.loc[g]["Category"]=="HD":
            derate_capacity.append(gen_type_capacity.loc[g]["Month_Capacity"]*hydro_cf) 
        else:
            derate_capacity.append(gen_type_capacity.loc[g]["Month_Capacity"])
    gen_type_capacity['Month_Capacity_Derated'] = derate_capacity
    
    #create hourly load
    hourly_loads = load_df.groupby("timepoint")["gross_load"].sum() #as pd series
    hourly_loads = pd.DataFrame({'timepoint':hourly_loads.index, 'gross_load':hourly_loads.values})
    #dec load by wind and solar to get net load
    hourly_cf = load_df.groupby("timepoint")["wind_cf","solar_cf"].mean()
    hourly_all = pd.merge(hourly_loads, hourly_cf, on="timepoint")
    #do wind
    wind_list = [wind_solar_df.wind_cap.sum()]*len(hourly_all.index)
    hourly_all["Wind_Capacity"] = wind_list
    hourly_all["Wind_Output"] = hourly_all["Wind_Capacity"]*hourly_all["wind_cf"] 
    #do solar
    solar_list = [wind_solar_df.solar_cap.sum()]*len(hourly_all.index)
    hourly_all["Solar_Capacity"] = solar_list
    hourly_all["Solar_Output"] = hourly_all["Solar_Capacity"]*hourly_all["solar_cf"] 
    #create net load column
    hourly_all["net_load"] = hourly_all["gross_load"] - hourly_all["Solar_Output"] - hourly_all["Wind_Output"]
    hourly_all=hourly_all.set_index("timepoint")
    
    #create hourly gen stacks
    time_list = []
    gen_list = []
    gentype_list = []
    zone_list = []
    dispatch_list = []
    for t in hourly_all.index.tolist():
        load = hourly_all.loc[t]["net_load"]
        merit_order_list = gen_type_capacity.index.tolist()
        for genindex in merit_order_list:
            if load - gen_type_capacity.loc[genindex]["Month_Capacity_Derated"] < 0:
                dispatch = load
                load = 0
            else:
                dispatch = gen_type_capacity.loc[genindex]["Month_Capacity_Derated"]
                load = load-dispatch
            time_list.append(t)
            gen_list.append(genindex)
            gentype_list.append(gen_type_capacity.loc[genindex]["Category"])
            zone_list.append(gen_type_capacity.loc[genindex]["Zone"])
            dispatch_list.append(dispatch)
    
    hourly_stack = pd.DataFrame({'timepoint':time_list, 
                  'Index':gen_list,
                  'Category':gentype_list,
                  'Zone':zone_list,
                 'Dispatch':dispatch_list})
    
    #append hourly prevailing pjm temperature to df
    hourly_stack_wtemp = pd.merge(hourly_stack, temp_df, on="timepoint")
    
    #round temperatures to nearest 5 degrees, append C.
    hourly_stack_wtemp['rounded_temp']=hourly_stack_wtemp.temperature.apply(lambda x: custom_round(x, base=5))
    
    #append outage probability to the df based on said temperature and unit type
    forced_out_df.rename(columns ={'Unnamed: 0': "Category"}, inplace =True)
    try:
        forced_out_df = forced_out_df.set_index("Category")
    except KeyError:
        pass
    
    matched_forced_outage = []
    for index in hourly_stack_wtemp.index.tolist():
        match_temp = hourly_stack_wtemp.loc[index]['rounded_temp']
        match_category = hourly_stack_wtemp.loc[index]['Category']
        matched_forced_outage.append(float(forced_out_df.loc[match_category][match_temp]))
    hourly_stack_wtemp['GenFOR']=matched_forced_outage
    
    #manual outage dist for now but can add later
    manual_outage_dist = _np.array([[.05, 0.16887827],
        [.1, 0.11924128],
        [.15, 0.05676093],
        [.2, 0.0660266],
        [.25, 0.0441866],
        [.3, 0.030344],
        [.35, 0.02460712],
        [.4, 0.02042499],
        [.45, 0.02162338],
        [.5, 0.02205312],
        [.55, 0.04304062],
        [.6, 0.00962204],
        [.65, 0.0061247],
        [.7, 0.00523377],
        [.75, 0.00321084],
        [.8, 0.00336457],
        [.85, 0.00405984],
        [.9,0.01485232],
        [.95,0.00916784],
        [1.,0.32717719]])

    #voll = 3500 #probably want to input/change this at some point but OK for now
    store_lolp =[]
    store_segment = []
    store_timepoint = []
    for t in list(hourly_stack_wtemp.timepoint.unique()):
        print('original conventional dispatch for hour ' + str(t) + ' is ' + str(hourly_stack_wtemp.Dispatch[hourly_stack_wtemp.timepoint==t].sum()))
        copt_table = copt_calc(hourly_stack_wtemp[hourly_stack_wtemp.timepoint==t],manual_outage_dist)
        #hourly_copt_list.append(copt_calc(hourly_stack_wtemp[hourly_stack_wtemp.timepoint==t],manual_outage_dist))
        
        #lowcut_lolp = .00001 #cutoff lolp for min segment, probably want to do this as input but OK for now
        #n_segments = 10 #segments in ORDC, probably want to do this as input but OK for now
        
        max_disp = int(hourly_stack_wtemp.Dispatch[hourly_stack_wtemp.timepoint==(t)].sum())
        cutoff_disp_array = _np.where((_np.cumsum(copt_table[:,1])>lowcutLOLP)==True)
        cutoff_disp_index = min(cutoff_disp_array[0])
        cutoff_disp = copt_table[cutoff_disp_index,0]
        #print(cutoff_disp, max_disp, (max_disp-cutoff_disp)/n_segments)
    
        seg_length = int((max_disp-cutoff_disp)/(n_segments)) #divvy up ORDC segments in equal lengths
        
        for v in range(max_disp, int(cutoff_disp), -seg_length):
            #get midpoint
            midpoint = v - seg_length/2
            if midpoint > int(cutoff_disp):
                #find cumulative lolp at midpoint
                cutoff_array = _np.where((copt_table[:,0]<midpoint)==True)
                cutoff_index = max(cutoff_array[0])
                cumulative_lolp = max(_np.cumsum(copt_table[:(cutoff_index+1),1]))
                #store lolp*voll
                store_lolp.append(cumulative_lolp*VOLL)
                #create ordc segment
                store_segment.append(seg_length)
                #store timepoint
                store_timepoint.append(t)
    
    segment_df = pd.DataFrame({'timepoint':store_timepoint,
              'segments':list(range(1,n_segments+1))*int(max(hourly_stack_wtemp.timepoint.unique())),
              'MW':store_segment,
              'Price':store_lolp})
        
    return segment_df


### HELPER FUNCTIONS ###
    
def custom_round(x, base=5):
    """
    rounds temperatures to nearest 5 degrees
    then appends a C and returns as a string so it matches input format
    there is no check currently that temperatures are in-range (i.e., between -30 and 40C)
    """
    return str(int(base * round(float(x)/base)))+"C"

#create copt (use RECAP functionality to see how done in python)
def copt_calc(case_data, manual_outage_dist):
    """
    Similar to how done in RECAP, but modified for our use case
    assumes df in our format, as well as outage distribution
    returns n-by-2 numpy array of hourly capacity levels and their associated probability
    """
    COPT = _np.array([1.])

    for i in case_data.index.tolist():
        gen_capacity = case_data.loc[i]["Dispatch"]
        gen_for = case_data.loc[i]["GenFOR"]
        dist = makegendist(gen_capacity, gen_for, manual_outage_dist)
        COPT = scipy.signal.fftconvolve(COPT,
                                        space_dist(_np.vstack((_np.arange(len(dist)),dist)).T)[:,1])
            
    COPT[_np.nonzero(COPT<0)]=0
    
    lowprobcut = 10**(-9) #same as in RECAP
    min_capacity = min(_np.nonzero(_np.cumsum(COPT)>lowprobcut)[0])
    COPT/=sum(COPT)
    
    return _np.vstack((_np.arange(min_capacity,len(COPT)),COPT[min_capacity:])).T

def space_dist(dist):
    """
    Takes a distribution and spaces it in integer increments merging the probability distribution where necessary
    """
    dist = dist[dist[:,0].argsort(),] #sorts the distribution on the first column
    
    mini = dist[min(_np.nonzero(_np.cumsum(dist[:,1])>10**(-9))[0]),0]
    maxi = dist[-min(_np.nonzero(_np.cumsum(dist[::-1,1])>10**(-9))[0])-1,0]
    
    dist = dist[_np.all([dist[:,0]>=mini,dist[:,0]<=maxi], axis = 0)]
    
    temp = dist_of_zeros(mini, maxi)
    
    if _np.all(_np.round(dist[:,0])==dist[:,0]):
        temp[_np.array(_np.round(dist[:,0])-mini, dtype = int),1] = dist[:,1]
        return temp
    else:
        dist[:,0] = _np.round(dist[:,0])
        for n in _np.unique(dist[:,0]):
            temp[int(n-mini),1] = _np.sum((dist[:,0]==n)*dist[:,1])
        return temp

def dist_of_zeros(mini, maxi):
    return _np.vstack((_np.arange(round(mini), round(maxi)+1), _np.zeros(int(round(maxi))-int(round(mini))+1))).T
    
def makegendist(capacity, FOR, outagedist):
    
    if capacity<.5:
        return _np.array([1.]) #simplified for low capacity units

    dist = outage_dist(capacity, FOR, outagedist)
    dist = _np.hstack((_np.zeros(int(min(dist[:,0]))), dist[:,1]))
    
    assert round(sum(dist),6)==1. #check that distribution still makes FORs sum to 1

    return dist

def outage_dist(cap, FOR, outagedist):
    return_dist = _np.ones((len(outagedist)+1,2))
    if (1.-FOR/_np.dot(outagedist[:,0], outagedist[:,1]))>0:
        return_dist[0,1] = (1.-FOR/_np.dot(outagedist[:,0], outagedist[:,1]))
        return_dist[1:,0]-=outagedist[:,0]
        return_dist[1:,1] = outagedist[:,1]*(1-return_dist[0,1])
    else:
        return_dist[1:,1] = outagedist[:,1][:]*FOR
        return_dist[0,1] = 1-FOR
        return_dist[1:,0]-=outagedist[:,0]
        
    return_dist[:,0]*=cap
    return space_dist(return_dist)

## END HELPER FUNCTIONS ##
    
## make the call! ##
#call create_ordc
#results = create_ordc(gen_df, planned_out_df, load_df, wind_solar_df, temp_df, forced_out_df)
#print(results)
# call should now be from main script

#how long?
end_time = time.time() - start_time
print ("time elapsed during run is " + str(end_time) + " seconds")