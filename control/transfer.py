#!/usr/local/bin/python3.5

#
# Copyright 2016, Dan Malone, All Rights Reserved
#
import util.utilities
from util.globals import *

import re
import shlex
import os
import sys
import atexit
import inspect
from time import sleep, strftime, gmtime
import threading

###################################################################################################
#
# MODULE (Class): transfer
#
# DESCRIPTION   : This class manages a netem system. It provides the methods to set up and manipulate
#                 netem controls
#
# AUTHOR        : Dan Malone
#
# CREATED       : 01/13/16
#
# Usage:
#
# server = netem.netem(testbed, netem_id)
#
#    (Where netem_id is the id of the netem system in the testbed)
#
##################################################################################################

###################################################################################################
#
# MODULE (Class): class transfer
#
# DESCRIPTION: This class manages file transfer on a client server
#
# AUTHOR        : Dan Malone
#
# CREATED       : 01/13/16
#
# Usage:
#
# transfer =  transfer.transfer(test_client)
#             Where test_client is a test_client object
#
# transfer.start(options={})
#             Start a  transfer.
#             options is a dictionary of optional options, such as {CONTINUOUS:0, COUNT:1}
#             See the transfer.start implementation for details on options
#
#
#             Default is to start 1 transfer over 1 client session if COUNT is not specified in the options dictionary
#             This class can simultaneously start any number of transfers through multiple test  sessions as long as
#             the Test Client passed to this object initiated multiple sessions.
#             COUNT specified the number of serial transfers to perform (not in parallel).  
#            For parallel transfers, use multple transfer objects with the same (or different) dtestclients
#             A COUNT of 0 is interpretted as 1
#
# transfer.get_stats()
#    Returns the list of stats records.  Each record is a dictionary containing stats for the transfer include throughput
#
# transfer.clear_stats()
#    Clears the recorded stats for all transfers
#
##################################################################################################
class transfer:
    """This class manages file transfers started on the Test Client"""

    ##############################################################################################
    #
    # METHOD: __init__(testbed, netem_id, user_id)
    #
    # DESCRIPTION: This is the initialization constructor:
    #                 test_client - test_client object
    #
    ##############################################################################################
    def __init__(self, test_client):
        """__init__(testbed, netem_id, user_id)
             This is the initialization constructor:
                test_client - client object
                """

        # Get the default content server
        self.test_client = test_client
        self.testbed = self.test_client.testbed
        self.content_server = self.testbed.find(".//content_server[@id='"  + str(1) + "']/ip").text

        # Keep track of the active transfer threads
        self.threads = []

        # Keep track of the transfer statistics in a list of dictionaries.  Each dictionary contains info about the transfer such as THROUGHPUT
        self.stats = []

    ###################################################################################################
    #
    # METHOD: transfer.start(options={})
    #
    # DESCRIPTION: Start one or more  transfers in seperate threads
    #                 options - a dictionary of optional options, such as {CONTINUOUS:0, COUNT:1}
    #                           See the the code below for details on options
    #
    ##################################################################################################
    def start(self, options={}):

        ############################
        # Set default options
        ############################
        defaults={}
        defaults['FILE']  = "test100M"

        defaults['PROXY'] = 'PROXY';   # DIRECT     : Do NOT transfer through the DPR client proxy.
                                       # HTTP_PROXY : Do transfer through the HTTP client proxy

        defaults['COUNT'] = 1;     # 1: Start 1 transfer
                                   # 0: Start 1 transfer
                                   # n: Start <n> transfers in serial (not in parallel).  For parallel transfers, use multple transfer objects with the same (or different) dpr_clients

        defaults['CONTINUOUS']  = 0; # 0: Perform the transfer once (may be interrupted by calling transfer.stop)
                                     # 1: Perform the transfer continuously until transfer.stop() is called

        defaults['OUTFILE']  = "";   # Name of output file.  If "", output file will be given a name containing the transfer session id

        options = utilities.set_dictionary_defaults(defaults, options)

        # Prepend the content server if there is not already a content server on it
        self.transfer_filenames = []

        if isinstance(options['FILE'], str):
            # If they only have one file as a string, we need to turn it into a list of 1 file
            file = options['FILE']
            options['FILE'] = []
            options['FILE'].append(file)

        for file in options['FILE']:
            if not "://" in file:
                # a bit hokey but we need to circumvent the cserv attach
                # as the files reside locally for uploads.
                if 'UPLOAD' not in options:
                    file = self.content_server + "/" + file
            self.transfer_filenames.append(file)

        # Start transfer
        self.threads = []

        # Create a thread to start the transfer(s)
        thread = transferThread(self, self.dpr_client, self.transfer_filenames, options, 0)
        thread.daemon = True
        thread.start()
        self.threads.append(thread)

        return self.threads

    ##############################################################################
    # transfer.stop()
    # Stops all transfers
    ##############################################################################
    def stop(self, kill=1):
        for thread in self.threads:
            try:
                thread.stop_transfer = 1
            except:
                continue

        if kill:
            # Kill all the curl's on the client system
            # TODO: We should only kill the specific curl for each thread.  To do this, Tte thread needs to record the PID when it starts the curl
            output = self.dpr_client.shell.run('sudo pkill curl', 1, 1)


    ##############################################################################
    # transfer.wait()
    # Waits for all transfers to end
    # 02/06/15 - DRM: Added an option to provide a limiter to the wait. I found
    #                 with the multi-client tests I would sometimes get wedged
    #                 waiting for the transfer thread to complete and never return.
    ##############################################################################
    def wait(self, limit=0):
        for thread in self.threads:
            # see if we are limiting
            if limit:
                # loop only until the thread clears or limit goes to 0
                while thread.transfer_running == 1 and limit:
                    sleep(1)
                    limit -= 1
            else:
                # loop until thread clears
                while thread.transfer_running == 1:
                    sleep(1)

    ##############################################################################
    # transfer.check()
    # Check to see how many transfers are running
    ##############################################################################
    def check(self):
        runners = 0
        for thread in self.threads:
            if thread.transfer_running == 1:
                runners += 1
        return runners

    ##############################################################################
    # transfer.clear_stats()
    # Clears the recorded stats for all transfers
    ##############################################################################
    def clear_stats(self):
        self.stats = []

    ##############################################################################
    # transfer.get_stats()
    # Returns the list of stats records.  Each record is a dictionary containing stats for the transfer
    #    09/25/14 - DRM: Added an assert override deafult is to assert explicit passed 0 means ignore
    ##############################################################################
    def get_stats(self, errassert=1):
        #print("                                IN TRANFER GOT STATS:   " + str(self.stats))
        for stat in self.stats:
            if "error" in stat:
                if stat["error"] != "":
                    if errassert:
                        assert False, stat["error"]
        return self.stats


###################################################################################################
# class transferThread
#
# This object is a thread for doing the transfer.  It is intended to only be invoked by transfer.start()
###################################################################################################

class transferThread(threading.Thread):

    ############################################################################
    # constructor(dpr_client, options, session)
    #     dpr_client  is the dpr_client object.  Required even if this is a TCP transfer.  It represent the system that curl will be run on
    #     file        file (including prepended content server) to retrieve
    #     options     is the dictionary of options.  All defaults are assumed to be set
    #     transfer_id is a number corresponding to the transfer (for simultaneous transfers)
    ############################################################################

    def __init__(self, transfer_parent, dpr_client, transfer_filenames, options, transfer_id):
        super(transferThread, self).__init__()
        self.transfer_parent = transfer_parent
        self.dpr_client = dpr_client
        self.transfer_filenames = transfer_filenames
        self.options = options
        self.transfer_id = transfer_id
        self.data = {}
        self.stop_transfer = 0
        self.transfer_running = 1
        self.thread_name = utilities.snip(str(self), "(", ",")
        try:
            self.count = options['COUNT']
        except:
            self.count = 1

    def wait(self):
        while self.transfer_running == 1:
            sleep(1)

    def run(self):

        # Indicate that we have a transfer thread running
        self.transfer_running = 1

        # Set up the transfer command as part of this thread we are in
        # sadly the upload sequence needs the proxy before the upload cmds
        if 'UPLOAD' in self.options and self.options['PROXY'] != 'DIRECT':
            cmd = ""
        else:
            # pageload requires a different transfer strategy. Mote: page files objects 
            # for transfer MUST be loaded on a local server accessable by the test server.
            if 'PAGELOAD' in self.options:
                cmd = "cd /home/qfreleng/testmget; export http_proxy=127.0.0.1:10080; mget -r -p -nc -H --max-redirect 1 --num-threads " +str(self.options['PAGELOAD'])+ " --level 1 "
            else:
                cmd = "curl"

        # Check if they want HTTP 1.0
        if 'http' in self.options and self.options['http'] == '1.0':
            cmd = cmd + " -0"

        # check and verify curl options if any
        if 'curlopt' in self.options:
            if const_curl_opts[self.options['curlopt']]:
                cmd = cmd + " " +  const_curl_opts[self.options['curlopt']]

        outfile = self.options['OUTFILE']
        outfiles = []
        upld_cmd = ""

        dnldpath = ""
        if 'CURL_DNLD_DIR' in self.options:
            dnldpath = self.options['CURL_DNLD_DIR']

        i = 1
        j = 0
        for file in self.transfer_filenames:
            if outfile == "":
                # when in continuous transfer mode a new file of size n gets created every time
                # it runs which means depending on the length of the run the HD starts to fill up.
                # and can eventually max out. So to protect against that use a more common name for resuse.
                if self.options['CONTINUOUS']:
                    if not self.options['PROXY'] == "HTTP_PROXY":
                        # going direct
                        if 'UPLOAD' in self.options:
                            cmd += cmd + " -F 'uploaded=@" +str(file)+ "; filename=" +os.path.split(file)[1] + ".CONT." + str(self.dpr_client.proxyPort) + "." +self.thread_name+ "." +str(i)+".tmp' -H \"Expect:\" http://" +self.options['CSERVER']+ "/cgi-bin/upload.php"
                            log("UPLOAD")
                        else:
                            outfile = dnldpath + os.path.split(file)[1] + ".CONT." + str(self.dpr_client.proxyPort) + "." + self.thread_name + "." + str(i) + ".tmp"
                    else:
                        # DRM http proxy
                        if 'UPLOAD' in self.options:
                            cmd += cmd + " -F 'uploaded=@" +str(file)+ "; filename=" +os.path.split(file)[1] + ".CONT." + str(self.dpr_client.currentClientConfig['nonDprProxyPort']) + "." +self.thread_name+ "." +str(i)+".tmp' -H \"Expect:\" http://" +self.options['CSERVER']+ "/cgi-bin/upload.php"
                        else:
                            outfile = dnldpath + os.path.split(file)[1] + "." + str(self.dpr_client.proxyPort) + "." + str(i) + ".tmp"
                else:
                    if 'UPLOAD' in self.options:
                        # add in the upload xfer directives and temp file name.. index needs to be i-1
                        cmd += cmd + " -F 'uploaded=@" +str(file)+ "; filename=" +os.path.split(file)[1] + "." + str(self.dpr_client.proxyPort) + "." +self.thread_name+ "." +str(i)+".tmp' -H \"Expect:\" http://" +self.options['CSERVER']+ "/cgi-bin/upload.php"
                    else:
                        outfile = dnldpath + os.path.split(file)[1] + "." + self.thread_name + "." + str(i) + ".tmp"
                        log("UPLOAD")
                    i += 1

            if 'UPLOAD' not in self.options:
                # pageload is file/obj based cannot redirect output here
                if 'PAGELOAD' in self.options:
                    cmd = cmd + " " +file
                else:
                    cmd = cmd + " " + file + " -o " + outfile

            outfiles.append(outfile)
            outfile=""

        log("CURL CMD : " + cmd)

        # NOTE_TO_SELF - Change to .launch and check for completion while looking if the user called stop thread
        while not self.stop_transfer:

            # Start the transfer
            if getOpt('VERBOSE_TRANSFER'):
                log('DEBUG', "Transfer " + self.thread_name + ":" + str(self.transfer_id) + " started via: " + cmd)

            output = self.test_client.shell.run(cmd, 1, 1, 1, 0)

            if getOpt('VERBOSE_TRANSFER'):
                log('DEBUG', "Transfer" + self.thread_name + ":" + str(self.transfer_id) + " ended \nLOCAL FILE: " + str(outfiles) + "\nCURL OUTPUT:\n" + output)

            # Parse the output for errors
            errmsg = utilities.snip(output, "curl: ")

            # Get each stat line
            lines = output.split("\r")

            # Get the values from the last line of output (this will have the best average, but the intermediate ones are available
            values = lines[-1].split()
            stats = {}
            stats["time_finished"] = strftime("%m/%d/%y %H:%M:%S", gmtime())

            if errmsg:
                stats["error"] = self.__class__.__name__ + "() " + errmsg + "\n"
                self.stop_transfer = 1
            else:
                try:
                    stats["total_%"]       = values[0]
                    stats["total_bytes"]   = values[1]
                    stats["rcvd_%"]        = values[2]
                    stats["rcvd_bytes"]    = values[3]
                    stats["xfer_%"]        = values[4]
                    stats["xfer_bytes"]    = values[5]
                    stats["avg_dload"]     = values[6]
                    stats["avg_uload"]     = values[7]
                    stats["time_total"]    = values[8]
                    stats["time_spent"]    = values[9]
                    stats["time_left"]     = values[10]
                    stats["current_speed"] = values[11]
                except:
                    if output.strip() != "":
                        errmsg = "Transfer encountered abnormal output: " + str(output)
                        if "ssh_exchange_identification" in output:
                            errmsg = errmsg + "\nConsider modifying /etc/ssh/ssd_config on the client machine:  MaxStartups 30     (remove the :10:20)"
                        log(errmsg)
                        stats["error"] = self.__class__.__name__ + "() " + errmsg + "\n"
                        self.stop_transfer = 1

                else:
            
                    if not 'UPLOAD' in self.options:
                        # Process curl download stats. The throughput numbers like avg_dload are like 12K. 
                        # Make them graphable like 12300
                        stats["down_throughput"] = 0
                        if stats["avg_dload"] != "":
                            for unit in ['k', 'M', 'G', 'none']:
                                if unit in stats["avg_dload"]:
                                    break
                                if unit == 'none':
                                    stats["avg_dload"] = stats["avg_dload"] + "B"
                                    unit = "B"

                                avg_dload = utilities.snip(stats["avg_dload"], 0, unit)

                                # There appears to be a bug in Python where sometimes a string like "13.8" 
                                # when passed to float has unseen garbage.  Maybe it's a fault of utilities.snip
                                # Anyway, reassigning the variable seems to clean up the garbage
                                if avg_dload == "":
                                    avg_dload = 0
                                x = avg_dload

                                # 02/06/15 - DRM: well the above does not always work. Multi-client
                                # force kill causes garbage to be collected as avg_dload and the float
                                # aborts on string data this will overide the Python val error
                                try:
                                    y = float(x)
                                except ValueError:
                                    y = float(0)
                                    if getOpt('VERBOSE_TRANSFER'):
                                        log("FLOAT ERROR: converting: " +x+ " to float")

                                multiplier = {"B":1, "k":1024, "M":1024*1024, "G":1024*1024*1024}
                                y = multiplier[unit] * y
                                down_throughput = float(int(y))
                                stats["down_throughput"] = str(down_throughput)

                    else:
                        # Process curl upload stats. The throughput numbers like avg_dload are like 12K. 
                        # Make them graphable like 12300
                        stats["up_throughput"] = 0
                        if stats["avg_uload"] != "":
                            for unit in ['k', 'M', 'G', 'none']:
                                if unit in stats["avg_uload"]:
                                    break
                                if unit == 'none':
                                    stats["avg_uload"] = stats["avg_uload"] + "B"
                                    unit = "B"

                                avg_uload = utilities.snip(stats["avg_uload"], 0, unit)

                                # There appears to be a bug in Python where sometimes a string like "13.8" 
                                # when passed to float has unseen garbage.  Maybe it's a fault of utilities.snip
                                # Anyway, reassigning the variable seems to clean up the garbage
                                x = avg_uload

                                # 02/06/15 - DRM: well the above does not always work. Multi-client
                                # force kill causes garbage to be collected as avg_dload and the float
                                # aborts on string data this will overide the Python val error
                                try:
                                    y = float(x)
                                except ValueError:
                                    y = float(0)
                                    if getOpt('VERBOSE_TRANSFER'):
                                        log("FLOAT ERROR: converting: " +x+ " to float")

                                multiplier = {"B":1, "k":1024, "M":1024*1024, "G":1024*1024*1024}
                                y = multiplier[unit] * y
                                up_throughput = float(int(y))
                                stats["up_throughput"] = str(up_throughput)

            # Append the stats dictionary onto the parents lists of transfer statistics
            #print("              IN THREAD APPENDING STATS: " + str(stats))
            self.transfer_parent.stats.append(stats)

            # Quit if we got a curl error
            if not errmsg == "" and not self.stop_transfer:
                if getOpt('VERBOSE'):
                    msg = "Transfer: " + cmd + " encountered an error:\n\n" + cmd + "\n\n" + output + "\n"
                    msg = self.__class__.__name__ + "() " + msg
                    log('ERROR', "")
                    log('ERROR', "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                    log('ERROR', msg)
                    log('ERROR', "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                    log('ERROR', "")
                break

            # They may have requested a single transfer or continuous or multiple transfers
            if self.count > 0:
                self.count -= 1

            if not self.options['CONTINUOUS'] and self.count <= 0:
                self.stop_transfer = 1

            if 'DELAY_XFER_RESTART' in self.options:
                time.sleep(self.options['DELAY_XFER_RESTART'])

        # Indicate we are no longer running
        self.transfer_running = 0
