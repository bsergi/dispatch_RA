#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Apr 18 08:46:48 2019

@author: bsergi
"""

#scenario_name = "TEST2" cases are now named below based on their corresponding date

# initialization boolean list should match length of dates
make_init_list = [True, False, False, False, False, False, False]
create_supp_ordc = True #this really should always be true so may get rid of it later

#(1) specify dates to run in list (note: each day is run separately)
dates = ['1.4.2014', '1.5.2014', '1.6.2014', '1.7.2014', '1.8.2014', '1.9.2014', '1.10.2014']

#(2) hydro cf
hydro_cf = 0.3

#(3) VOLL (in US $)
VOLL = 3500

#(4) Lowcut LOLP
lowcutLOLP = 0.00001

#(5) number of segments in ORDC
n_segments = 10

#(6) number of days to run after each start date
days = 1

#(7) forecast errors
wfe = 0.01
sfe = 0.01
lfe = 0.01

#(8) use zones?
zones = True

#(9) contingency reserves shed (US $)
contingency = 850
