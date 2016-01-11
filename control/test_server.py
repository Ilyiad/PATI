#!/usr/bin/python3
import util.utilities
from util.globals import *
from util import *
from control.shell import *

import re
import shlex
import os
import sys
import atexit
import inspect
from time import sleep

# We need the pandas package for calulating the EWMA except that pandas does not exist for python3 (sudo apt-get install python3-pandas)
#import pandas 

###################################################################################################
# class test_server
#
# This class manages a Test Server
# The Test server can be stopped and started, the logging level changesd, and the logfile parsed
#
# Usage:
#
# server = test_server.test_server(testbed, server_id)
#             Where server_id is the id in the testbed of the server to manage
##################################################################################################

class test_server:
    """This class manages a dpr server on linux.  The Test server can be stopped and started, the logging level changesd, and the logfile parsed"""

    ##############################################################################################
    # contstructor(testbed, server_id)
    # server_id is the id in the testbed of the server to manage
    ##############################################################################################
    def __init__(self, testbed, server_id=1, user_id=1):

        # Get the ip addresses out of the testbed
        self.testbed      = testbed

        # 02/23/15 - DRM: To allow the root_username to be respected from the tbed cfg file
        # we have to grab it, assign it to "user" then use it in place of hardcode "root"
        self.user         = testbed.find(".//root_username[@id='" + str(user_id) + "']/name").text

        # set up test server esstials
        self.control_ip   = testbed.find(".//control_server[@id='" + str(server_id) + "']/ip").text
        self.data_ip      = testbed.find(".//test_server[@id='"     + str(server_id) + "']/ip").text
        self.tails = {}
        self.running_tails = []

        # Make sure we clean up the tail files at the end
        atexit.register(self.rm_tails)

        # We'll need a shell on the machine to manage it
        self.shell = shell(self.control_ip, self.user)

        # And a local shell file will be helpful
        self.local_shell = shell("local", "")

    ##############################################################################################
    # start()
    # Start the test server on the remote system.
    # If it is already running, the attempt to start it will display an error but the original server will be left running
    ##############################################################################################
    def start(self):
        # See if it is already running
        output = self.shell.run("service dpr_proxyd status")
        if "proxy_remote running as pid" in output:
            log('DEBUG', "Test Server running on " + self.control_ip)
        else:
            # Start the server
            # For some reason, this command doesn't return when run via ssh.  Use the launch method with the no_check flag = 1
            log('DEBUG', "Starting Test Server on " + self.control_ip)
            launch = self.shell.launch("service dpr_proxyd start", 1)
            sleep(5)
            launch.terminate()
            output = self.shell.run("service dpr_proxyd status")
            log('DEBUG', output + "\n")
        
    ##############################################################################################
    # stop()
    # Stop the Test server on the remote system.
    ##############################################################################################
    def stop(self):
        self.shell.run("service dpr_proxyd stop")
            
    ##############################################################################################
    # restart()
    # Stop and then start the dpr server on the remote system
    ##############################################################################################
    def restart(self):
        self.stop()
        self.start()
        
    ##############################################################################################
    # run(command, perror=1, redirect_err=0)
    # Run the specified command on the server system
    # If perror       is 0, the error will not be printed if the command fails
    # If redirect_err is 1, the output will be redirected (>&) to a file and the contents of that file returned as a string
    #    This is need for some commands like curl that seem to use stderr as normal output.
    ##############################################################################################
    def run(self, command, perror=1, redirect_err=0):
        output = self.shell.run(command, perror, redirect_err)
        return output
 
    ##############################################################################################
    # status()
    # Return the output from running service dpr_proxyd status on the DPR Server System
    ##############################################################################################
    def status(self):
        output = self.shell.run("service dpr_proxyd status")
        return output

    ##############################################################################################
    # pid()
    # Return the pid of the DPR Server via the status command
    # If DPR Server is not running, "" is returned
    ##############################################################################################
    def pid(self):
        output = self.status()
        pid = utilities.snip(output, "running as pid", "\n")
        return pid

    ##############################################################################################
    # status_detail()
    # Return the output from running service dpr_proxyd status_detail on the DPR Server System
    ##############################################################################################
    def status_detail(self):
        output = self.shell.run("service dpr_proxyd status detail")
        return output

    ##############################################################################################
    # get_build()
    # Return the output from running service dpr_proxyd status_detail on the DPR Server System
    ##############################################################################################
    def get_build(self):
        output = self.shell.run("service dpr_proxyd status")
        temp = output.split("\n")
        dprbuild = re.match(r'DPR VERSION:\s+(.*)', temp[1])
        if dprbuild and dprbuild.group(1):
            retval = dprbuild.group(1)
        else:
            retval = ""

        return retval

    ##############################################################################################
    # set_config(key, value)
    # Change a config parameter in the server proxy_remote.conf
    ##############################################################################################
    def set_config(self, key, value):
        cmd =  'sed -i "s/[ \t]*' + key + '[ \t]*=.*/' + key + ' = ' + str(value) + '/" /opt/dpr/bin/proxy_remote.conf'
        self.shell.run(cmd)

    ##############################################################################################
    # set_logging_level(level)
    # Set the logging level on the server.  The server does not need to restarted
    # 0 = error
    # 1 = warning
    # 2 = notice    (default after install)
    # 3 = info
    # 4 = debug
    # 5 = trace
    ##############################################################################################
    def set_logging_level(self, level):
        self.set_config("loggingLevel", level)
        self.shell.run("service dpr_proxyd config reload")
            
    ##############################################################################################
    # set_accounting_level(level)
    # Set the accounting level on the server.  The server does not need to restarted
    # 1 = ?
    # 2 = ?
    # 3 = ?       (default after install)
    ##############################################################################################
    def set_accounting_level(self, level):
        self.set_config("accountingLevel", level)
        self.shell.run("service dpr_proxyd config reload")
            
    
    ##############################################################################################
    # start_log_capture()
    # This method starts capturing the server's dpr.log file by doing a tail -f dpr.log
    # A token is returned which must be passed to stop_log_capture() and parse_log()
    ##############################################################################################
    def start_log_capture(self):
        stamp = self.local_shell.run("date +%Y_%m_%d.%H:%M")
        tail_file = "tail.dpr." + str(stamp) + ".log"
        capture = self.shell.launch("tail --follow=name /var/log/dpr.log > " + tail_file)

        # Remember the tail file name
        self.tails[capture] = tail_file
        self.running_tails.append(capture)
        return(capture)

    ##############################################################################################
    # stop_log_capture(capture)
    # This method stops the tail -f dpr.log, retrieves the file, and deletes it from the server
    # It is not necessary to call stop_log_capture before calling parse_log.
    # The log entries are not returned to the user.  Instead, parse_log(capture) may be called to retrieve info
    ##############################################################################################
    def stop_log_capture(self, capture):
        tail_file = self.tails[capture]
        
        # Stop the tail
        self.shell.stop(capture)
        
        # Get the tailed log file (and delete it from the server to avoid clutter)
        tail_file = self.tails[capture]
        self.shell.get_file(tail_file)
        self.shell.run("rm -f " + tail_file)
        self.running_tails.remove(capture)

    def get_field(self, field, record):
        reobj = re.search(field + '[ _)]*=+[ ]*([0-9]*)[, $]*.*', record)
        try:
            value=reobj.group(1)
            if value  == "":
                log('DEBUG', "dpr_server.get_field(): " + field + " not in record: " + record)
        except:
            value=""
        return value
    
    ##############################################################################################
    # parse_log(capture)
    # This method parses the log file captured via start_log_capture()
    # If stop_log_capture has not been called, the capture so far will be retrieved
    # This allows parse_log to be called multiple times before finally stopping the log capture
    #
    # A dictionary containing the parsed log data is returned
    ##############################################################################################
    def parse_log(self, capture):

        # Get the name of the logfile
        tail_file = self.tails[capture]

        # If the tail is still running, we'll have to pull over a copy of the captured log so far
        # If stop_log_capture was already called, we'll have the latest copy locally
        if capture in self.running_tails:
            self.shell.get_file(tail_file)
        fd = open(tail_file)
        log_records = fd.read()
        fd.close()
        log_records = log_records.split("\n")
        log_dict = []
        for line in log_records:
            if line != '':
                if "SESS_ID" in line:
                    sess_id = self.get_field('SESS_ID', line)
                else:
                    sess_id = ""
                    
                if any(s in line for s in ('START', 'PERIODIC', 'AGGREGATE', 'FINAL')):
                    data_line = line.split(": ")[-1]
                    data_line = data_line.split(", ")
                    try:
                        mydict = dict((k.strip(), v.strip()) for k,v in (item.split('=') for item in data_line))
                        mydict['type'] = line.split(": ")[1]
                    except:
                        log('DEBUG', "Malformed accounting message!")
                        log('DEBUG', line)
                elif "ERROR" in line:
                    mydict = {'type': "ERROR",
                              'message': line,
                              }
                elif "DEBUG" in line:
                    mydict = {'type': "DEBUG",
                              'message': line,
                              }
                elif "Thread" in line:
                    mydict = {'type': "Thread",
                              'message': line,
                              }
                elif "SIPG" in line:
                    mydict = {'type': 'SIPG',
                              'SIPG'     : self.get_field('SIPG', line),
                              }
                elif "RTT" in line:
                    mydict = {'type': 'RTT',
                              'RTT'     : self.get_field('RTT', line),
                              'SRTT'    : self.get_field('SRTT', line),
                              'SESS_ID' : sess_id,
                              }
                elif "HW=" in line:
                    mydict = {'type': 'HWLW',
                              'HW': self.get_field('HW', line),
                              'LW': self.get_field('LW', line),
                              'SESS_ID' : sess_id,
                              }
                elif "(RTO)" in line:
                    mydict = {'type': 'RTO', 
                              'RTO'        : self.get_field('RTO', line),
                              'SHOTCOUNT'  : self.get_field('tShotCount', line),
                              'SESS_ID' : sess_id,
                              }
                elif "gapTime" in line:
                    mydict = {'type': 'GAP', 
                              'GAP'        : self.get_field('gapTime', line),
                              }
                elif "ZORC" in line:
                    mydict = {'type': 'ZORC', 
                              'VER'        : self.get_field('version', line),
                              }
                else:
                    mydict = {}
                    mydict['type'] = "Unhandled"
                    mydict['message'] = line
                    
                log_dict.append(mydict)

        return(log_dict)

    ##############################################################################################
    # get_log_values(log_dict, field, count)
    # Grep out the last <count> fields from the log that was retrieved via stop_log_capture
    #
    #   log_dict    is the dictionary returned by parse_log()
    #   record_type is the type of record to parse for.  Valid types are:  ERROR, DEBUG, Thread, RTT, HWLW, START, PERIODIC, AGGREGATE, FINAL
    #   field       is the field within the record to return, e.g. "SRTT" or [DL_BPS, MEM_UTIL]
    #               See parse_log() for available field types for each record type
    #   count       is the number of most recent occurrences of record_type to return.  0 or "*" means all
    #               Default is 1 (the most recet)
    #
    #   Returns a list of the values of the specified field name in order from oldest to newest
    #   
    ##############################################################################################
    def get_log_values(self, log_dict, record_type, field, count=1):

        # Make a list of the <count> most recent records of type record_type
        values = []

        for record in reversed(log_dict):
            if record['type'] == record_type:
                if field in record: 
                    values.append(record[field])
                else:
                    log('DEBUG', record)
                    log('DEBUG', "RECORD TYPE: " + record_type + " does not contain FIELD: " + field)
                    
                if count != 0 and count != "*":
                    if len(values) == count:
                        break
                    
        return values


    ##############################################################################################
    # get_log_record(log_dict, record_type, [field], [value]
    # Return the most recent record of type record_type which contains the specified field/value pair
    # If field/value pair is not specified, just return the most recent record of type record_type
    ##############################################################################################
    def get_log_record(self, log_dict, record_type, field="", value=""):
        for record in reversed(log_dict):
            if record['type'] == record_type:
                if field == "":
                    return record
                if field in record:
                    if record[field] == value:
                        return record
        return ""
        
    ##############################################################################################
    # get_log_ewma(log_dict, count, [span])
    # Grep out the last <count> rtt value from the log dictionary and compute the Exponentially-Weighted Moving Average
    #   log_dict    is the dictionary returned by parse_log()
    #   count       is the number of last count occurrences of rtt to use in the computation.  0 or "*" means all
    #   decay       is the optional decay to specify for span (I don't know either - see http://pandas.pydata.org/pandas-docs/version/0.13.1/generated/pandas.stats.moments.ewma.html)
    #               Default is 15
    #
    #   Returns the ewma
    #   
    ##############################################################################################
    def get_log_ewma(self, log_dict, count, decay=15):

        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        # NOTE: This will bomb out until we get the pandas package for python3.  See import pandas statement at the top of this file
        # !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        
        # Find EWMA of most recent <count> RTT samples
        rtts = get_log_values(log_dict, "RTT", count)

        # EWMA needs floating point numbers
        rtts_float = []
        for rtt in rtts:
            rtts_float.append(float(rtt))
            
        return (pandas.ewma(pandas.Series(rtts_float[::-1]), span=decay))


    #########################################################################
    # rm_tails()
    # Internal cleanup function to remove log files from start_log_capture()
    # Called by atexit()
    #########################################################################
    def rm_tails(self):
        trace_enter()
        if not getOpt('NO_CLEANUP'):
            for tail in self.tails:
                self.local_shell.run("rm -f " + self.tails[tail])
        trace_exit()
        
    #########################################################################
    # install(install_file | branch)
    # Installrelease.remote.tar.gz file on the client machine
    #
    # If install_file contains "release.proxy_remote.tar.gz" it is assumed to be a full or relative path to the file
    #
    # Otherwise install_file is assumed to be a branch.  GITBASE env variable must be set (like /projects or ~/projects)
    # and the install file must exist at $GITBASE/qfactor/httpProxyNC/<branch>
    #########################################################################
    def install(self, build, os="ubuntu"):

        tarfile      = "release.proxy_remote.tar.gz"
        if os == "ubuntu":
            tarfile_path = "proxy/server/ubuntu_x86_64/"
        elif os == "centos":
            tarfile_path = "proxy/server/centos_x86_64/"
        install_file = utility.utilities.getbuild(build, tarfile_path + tarfile)
        
        # Peform the install
        log('DEBUG', "Installing " + install_file + " on DPR Server " + self.control_ip)
        self.shell.put_file(install_file)
        self.shell.run("tar -xzf " + tarfile)
        if getOpt('OS') and getOpt('OS') == "centos":
            output = self.shell.run("cd dpr_install; ./install.sh", perror=0)
        else:
            output = self.shell.run("cd dpr_install; ./install.sh")

        log('DEBUG', output)
        self.start()


    #########################################################################
    # clear_netem()
    # Clear any network impairments on all interfaces on the target machine
    #########################################################################
    def clear_netem(self):
        eths = self.shell.run('tc qdisc | grep qdisc | cut -f 5 -d " "')
        eths = shlex.split(eths, "/n")
        eths.sort()
        log('DEBUG', "Clearing netem on interfaces on server " + self.control_ip)
        for eth in eths:
            try:
#                self.shell.run("tc qdisc del dev " + eth + " root", 0)
                self.shell.run("tc qdisc del dev " + eth + " " +self.user, 0)
            except:
                pass

    #########################################################################
    # corechk()
    # Check the supplied path for a server core and if one is detected
    # then take the following actions:
    #    see if there is a directory for this build
    #    if not create one
    #    else if exists use it
    #    rename the core core_<testname>.pid
    #    move that file into the directory just created
    #########################################################################
    def corechk(self, testname, corepath, build):
        log("RUNNING CORE CHECK")
        cmd = "ls -ls " +corepath+ " | grep core_proxy_remote | wc -l"
        test_for_core = self.shell.run(cmd)
        if int(test_for_core) > 0:
            log("CORE FOUND !!")
            cmd = "if [ ! -d " +corepath+ "/" +build+ " ]; then mkdir " +corepath+ "/" +build+ "; fi"
            dirchk = self.shell.run(cmd)
            cmd = "ls " +corepath+ " | grep core_proxy_remote"
            corefile = self.shell.run(cmd)
            pid = re.match(r'core_proxy_remote.(\d+).*', corefile)
            if pid and pid.group(1) > 0:
                cmd = "mv " +corepath+ "/core_proxy_remote." +str(pid)+ " " +corepath+ "/" +str(build)+ "/core_" +testname+"." +str(pid)
                coremv = self.shell.run(cmd)
                log("CORE: " +corepath+ "/" +str(build)+ "/core_" +testname+"." +str(pid))
