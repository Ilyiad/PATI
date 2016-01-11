#!/usr/local/bin/python3.5

#
# Copyright 2016, Dan Malone, All Rights Reserved.
#
from util.globals import *
from util.utilities import *
from control import *

import sys
import time
from time  import gmtime, strftime
from numpy import ceil, floor
import os
import re

#########################################################################################
# Sanity Test
#
# If INSTALL=1 and BUILD=<DEV-nnn> are specified on the command line, running this test
# will perform a  Server and linux local client install 
# The test then does a simple transfer to verify that the DPR client connection and transfer work.
#
###########################################################################################

def test_linuxSanity():
    """Run a simple transfer.  If INSTALL-1 and BUILD=<DEV-nnn> are specified, an install will be done first"""

    #####################################################
    # The various profiles to test with
    #####################################################
    profiles = []

    profiles.append({'name' : 'loss_0.0_delay_20',   'delay' : 20,    'loss': 0.0, 'jitter' : 0, 'bandwidth' : 20000, 'COUNT' : 1})

    run_linuxPerformance_profiles(profiles)

def run_linuxPerformance_profiles(profiles):
    
    ##########################################################
    # Set up the test objects and get the server started
    ##########################################################
    objects      = testinit(profiles)
    testbed      = objects['TESTBED']
    test_client  = objects['CLIENT']
    test_server  = objects['SERVER']
    netem_server = objects['NETEM']
    transfer     = objects['TRANSFER']
    report       = objects['REPORT']
    profiles     = objects['PROFILES']
    content      = objects['CONTENT']

    # Start the client
    test_client.start()
    
    # Create a csv file to keep results
    headers = ['delay', 'loss', 'jitter', 'bandwidth', 'TCP']
    csv = utilities.create_csv(headers)
    
    # File to transfer
    xferFile = "files/test5M"
        
    ###########################################################################
    # Loop through the profiles
    ###########################################################################
    for profile in profiles:

        profile_name = profile['name']
        testname = str(profile)
        if "COUNT" in profile:
            count = profile['COUNT']
        else:
            count = 5
        
        log('ALWAYS', "-----------------------------------------------------------------------------------------------------------")
        log('ALWAYS', "Starting test: " + profile_name)
        log('ALWAYS', str(profile))
        log('ALWAYS', "-----------------------------------------------------------------------------------------------------------")

        # Update the client configuration if they are changing the client config (all "client.<parm>" in profile)
        test_client.update_config(profile)
        
        # If we have changed anything in the current client config, restart the client
        if test_client.configChanged:
            log("Restarting client due to changed config values")
            test_client.restart()

        # Set the impairment on the netem server
        netem_server.clear_netem()
        netem_server.set(profile)

        # Run transfers with and without DPR
        average_bw = {}
        for proxy in ['DIRECT', 'DPR_PROXY']:

            # We are just going to loop an extra time if the first time doesn't work
            triedAgain = False
            while True:
                # Collect transfer stats 
                transfer.clear_stats()

                # Start a transfers
                log("Starting " + str(count) + " Transfers (PROXY = " + proxy + ")")
                xfer = transfer.start({"PROXY" : proxy, "FILE" : xferFile, "COUNT" : count}) 

                # Wait till transfers are done
                xfer = transfer.wait()
            
                # Stop the transfers
                transfer.stop()
            
                # Get the timings and check for error
                stats = transfer.get_stats()

                # Sometimes we get no stats - we have to figure that out, but for now try the transfer again
                if len(stats) == 0:
                    msg = "WARNING:  We did not receive any stats for the " + proxy + " transfer"
                    if triedAgain:
                        assert False, msg + " after 2 attempte"
                    else:
                        log(msg)
                        log("Trying a second time")
                        triedAgain = True
                        continue

                # The transfer worked and we got stats
                break
                
            # Get the results from curl and keep track of the average througput
            total_throughput = 0.0
            i = 1
            for xfer in stats:
                throughput =  xfer['down_throughput']
                total_throughput += float(throughput)
                running_avg_throughput = total_throughput / i
                i += 1
                
                #csvline = [profile_name, throughput, proxy, profile['delay'], profile['loss'], profile['jitter'], profile['bandwidth'], 0]
                #csv.writerow(csvline)
                
            average_bw[proxy] = str(running_avg_throughput)
            
            log(proxy + ' avg_throughput=' + str(running_avg_throughput) + ' delay=' + str(profile['delay']) + ' loss=' + str(profile['loss']) + ' jitter=' + str(profile['jitter']) + ' bandwidth=' + str(profile['bandwidth']))
            
        csvline = [profile['delay'], profile['loss'], profile['jitter'], profile['bandwidth'], str(average_bw['DPR_PROXY']), str(average_bw['DIRECT'])]
        csv.writerow(csvline)

        ###################################
        # Go on to the next profile
        ###################################

    ###############################################
    log("All profiles are complete")
    ###############################################
    
    # Stop the transfer
    transfer.stop()
    
    # Stop the client
    test_client.stop()
    
    # Reset the client config
    test_client.set_default_config()

    # Test is complete.  Report object will be be published automatically because we used dpr_testinit()
