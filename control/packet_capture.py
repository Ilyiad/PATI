#!/usr/local/bin/python3.5

import utility.utilities
from controller.shell import shell

from utility.globals import log

import re
import shlex
import os
import sys
import atexit
import inspect
from time import sleep

###################################################################################################
#
# MODULE (Class): packet_capture
#
# DESCRIPTION: This class will run tcpdump on the first server and client specified in the testbed
#              The pcap files are then transferrd to the system running this script
#              One tcpdump will be run on the server capturing all ports on all interfaces
#              One tcpdumps will be run on the client
#              One capturing all ports on the loopback interface
#              Another capturing port 7077 on all interfaces
#
# AUTHOR: Dan Malone
#
# CREATED: 01/09/16
#
# Usage:
#
#    capture = packet_capture.packet_capture(testbed)
#    capture.start("prefix")         For example:  capture.start("tcp") or capture.start("udp")
#    capture.stop()
#
##################################################################################################
class packet_capture:
    """This class will launch tcpdumps on systems in the testbed and provides methods for processing the pcap"""

    ##############################################################################################
    # 
    # METHOD: __init__()
    #
    # DESSCRIPTION: The testbed will be used to get the ip address of client 1 and server 1 etc.
    #               This can be expanded
    #
    ##############################################################################################
    def __init__(self, testbed, client_id=1, server_id=1, netem_id=1, clean=1):
        """__init__():
        """

        # Get the ip addresses out of the testbed
        self.testbed = testbed
        self.client_ip = testbed.find(".//control_client[@id='" +str(client_id)+ "']/ip").text
        self.server_ip = testbed.find(".//control_server[@id='" +str(server_id)+ "']/ip").text
        self.netem_ip  = testbed.find(".//netem_server[@id='" + str(netem_id)+ "']/ip").text
        self.cdn_ip    = testbed.find(".//content_server[@id='" + str(netem_id)+ "']/ip").text

        # get who will will run as
        self.user = testbed.find(".//root_username[@id='1']/name").text

        # We'll need a shell for all servers involved
        self.server_shell  = shell(self.server_ip, self.user)
        self.client_shell  = shell(self.client_ip, self.user)
        self.netem_shell   = shell(self.netem_ip, self.user)
        self.content_shell = shell(self.cdn_ip, self.user)

        # Shell for local processing
        self.local_shell     = shell("local")
        
        # kill any tcpdumps still running on each system and remove any residual pcaps
        if clean:
            self.server_shell.run("sudo pkill tcpdump; rm -f *.pcap")
            self.client_shell.run("sudo pkill tcpdump; rm -f *.pcap")
            self.netem_shell.run("sudo pkill tcpdump; rm -f *.pcap")
            self.content_shell.run("sudo pkill tcpdump; rm -f *.pcap")

        # Keep track of the pcaps we launch
        self.pcaps = []

        # And clean up all tcpdumps if we bomb out
        atexit.register(self.stop_all)

    ##############################################################################################
    # 
    # METHOD: start(prefix)
    #
    # DESCRIPTION: Start tcpdumps as indicated by options
    #              The pcap filenames will be:  <prefix>.<ip>:<port>.<intf>.pcap
    #                 prefix - unique identifier for the pcap
    #                 options - CAPTURE option for collection of server starts
    #
    ##############################################################################################
    def start(self, prefix, options={}):
        """start(prefix, options):
              Start tcpdumps as indicated by options
              The pcap filenames will be:  <prefix>.<ip>:<port>.<intf>.pcap
                 prefix - unique identifier for the pcap
                 options - CAPTURE option for collection of server starts
                 """

        self.prefix = prefix

        # server only
        if options == "" or utility.utilities.getKey(options, "CAPTURE", "") == "server":
            self.server_pcap     = self.run_tcpdump(self.server_shell, "server_" + prefix, "all", str(utility.utilities.getKey(options, "CAPTURE_PORT", "all")))

        # client only all interfaces
        if options == "" or utility.utilities.getKey(options, "CAPTURE", "") == "client":
            self.client_eth_pcap  = self.run_tcpdump(self.client_shell, "client_" + prefix, "all", str(utility.utilities.getKey(options, "CAPTURE_PORT", "all")))

        # client only localhost
        if options == "" or utility.utilities.getKey(options, "CAPTURE", "") == "client_loc":
            self.client_lo_pcap = self.run_tcpdump(self.client_shell, "client_" + prefix, "lo" , "all")

        # this is the garbage pail catch on all for the client
        if utility.utilities.getKey(options, "CAPTURE", "") == "cli_all":
            self.client_all_pcap  = self.run_tcpdump(self.client_shell, "client_" + prefix, "all", str(utility.utilities.getKey(options, "CAPTURE_PORT", "all")))
            self.client_lo_pcap = self.run_tcpdump(self.client_shell, "client_" + prefix, "lo" , str(utility.utilities.getKey(options, "CAPTURE_PORT", "all")))

        # Server and Client (upload). Note: tcpdump.stop is order of start based, for upload we want the server to start first
        if options == "" or utility.utilities.getKey(options, "CAPTURE", "") == "up_srvcli":
            # check and see if a specific ethernet intf (in this case we want the upload intf) was passed in,
            # can be eth, p<n>p<n> (ex: p1p1) or a em prefixed then it becomes a specific directed tcpdump
            if 'eth' in utility.utilities.getKey(options, "SERVETH", "") or "p" in utility.utilities.getKey(options, "SERVETH", "") or "em" in utility.utilities.getKey(options, "SERVETH", "") :
                # it is make it part of the dumpline
                self.server_pcap      = self.run_tcpdump(self.server_shell, "server_" + prefix, str(utility.utilities.getKey(options, "SERVETH", "")), str(utility.utilities.getKey(options, "CAPTURE_PORT", "all")))
            else:
                # generic all intf
                self.server_pcap      = self.run_tcpdump(self.server_shell, "server_" + prefix, "all", str(utility.utilities.getKey(options, "CAPTURE_PORT", "all")))

            # start the client tcpdump
            self.client_eth_pcap  = self.run_tcpdump(self.client_shell, "client_" + prefix, "all", str(utility.utilities.getKey(options, "CAPTURE_PORT", "all")))
            return
        
        # Client and Server (download). Note: tcpdump.stop is order of start based, for download we want the client to start first
        if options == "" or utility.utilities.getKey(options, "CAPTURE", "") == "dn_clisrv":
            
            # start the client tcpdump
            self.client_eth_pcap  = self.run_tcpdump(self.client_shell, "client_" + prefix, "all", str(utility.utilities.getKey(options, "CAPTURE_PORT", "all")))

            # check and see if a specific ethernet intf (in this case we want the dnload intf) was passed in,
            # can be eth, p<n>p<n> (ex: p1p1) or a em prefixed then it becomes a specific directed tcpdump
            if 'eth' in utility.utilities.getKey(options, "SERVETH", "") or "p" in utility.utilities.getKey(options, "SERVETH", "") or "em" in utility.utilities.getKey(options, "SERVETH", "") :
                self.server_pcap      = self.run_tcpdump(self.server_shell, "server_" + prefix, str(utility.utilities.getKey(options, "SERVETH", "")), str(utility.utilities.getKey(options, "CAPTURE_PORT", "all")))
            else:
                # generic all intf
                self.server_pcap  = self.run_tcpdump(self.client_shell, "server_" + prefix, "all", str(utility.utilities.getKey(options, "CAPTURE_PORT", "all")))
            return

        # this will take a list of directed client interfaces ( data and control ) as well as local incase there is multile on the clioent sderver
        if 'eth' in utility.utilities.getKey(options, "CAPTURE", "") or "p" in utility.utilities.getKey(options, "CAPTURE", "") or "em" in utility.utilities.getKey(options, "CAPTURE", "") :
            log("OUTPUT : " +str(utility.utilities.getKey(options, "CAPTURE", "")))
            temp = utility.utilities.getKey(options, "CAPTURE", "")
            intf_list = temp.split("-")
            self.client_data_pcap  = self.run_tcpdump(self.client_shell, "client_" + prefix, intf_list[0], "all")
            self.client_ctrl_pcap  = self.run_tcpdump(self.client_shell, "client_" + prefix, intf_list[1], "all")
            self.client_lo_pcap    = self.run_tcpdump(self.client_shell, "client_" + prefix, "lo" , str(utility.utilities.getKey(options, "CAPTURE_PORT", "all")))

        # this is the default.. just catch all client server
        if "ClientServer" in utility.utilities.getKey(options, "CAPTURE", ""):
            self.server_pcap  = self.run_tcpdump(self.server_shell, "server_" + prefix, "all", str(utility.utilities.getKey(options, "CAPTURE_PORT", "all")))
            self.client_pcap  = self.run_tcpdump(self.client_shell, "client_" + prefix, "all", str(utility.utilities.getKey(options, "CAPTURE_PORT", "all")))
 

        # NOTE_TO_SELF: add cdn combos as well and redo this.

    ##############################################################################################
    # 
    # METHOD: tshark(pcap, options)
    #
    # DESCRIPTION: Run tshark on the specified pcap file with the specified options
    #              Return the text file name
    #
    # NOTE_TO_SELF: Flesh out the options and see if its viable to keep
    #
    ##############################################################################################
    def tshark(self, pcap, options=""):
        """tshark(pcap, options):
              DESCRIPTION: Run tshark on the specified pcap file with the specified options
                           Return the text file name
                           """
                           
        outfile = utility.utilities.snip(pcap, 0, ".pcap") + ".tshark"
        self.local_shell.run("tshark -r " + pcap + " > " + outfile, 0)
        return outfile
        
    ##############################################################################################
    #
    # METHOD: stop()
    #
    # DESRCIPTION: Stop each of the tcpdump started by start() and retrieve the pcaps
    #              The pcap filenames may be referenced by:
    #                 packet_capture.server_pcap      (the server pcap of all ports       / all interfaces)
    #                 packet_capture.client_lo_pcap   (the client pcap of the local       / the loopback interface)
    #                 packet_capture.client_eth_pcap  (the client pcap of all intf        / all interfaces)
    #
    ##############################################################################################
    def stop(self):
        """stop():
              DESRCIPTION: Stop each of the tcpdump started by start() and retrieve the pcaps
              The pcap filenames may be referenced by:
                 packet_capture.server_pcap      (the server pcap of all ports       / all interfaces)
                 packet_capture.client_lo_pcap   (the client pcap of the local       / the loopback interface)
                 packet_capture.client_eth_pcap  (the client pcap of all intf        / all interfaces)
                 """
        # Stop each of the tcpdumps we have started and retrieve the pcap file
        for info in self.pcaps:
            shell   = info[0]
            tcpdump = info[1]
            pcap    = info[2]
            shell.stop(tcpdump)
                        
            # Retrieve the pcaps
            log("Retreiving packet capture:  " + pcap)
            shell.get_file(pcap)
            
        self.pcaps = []

    ##############################################################################################
    # 
    # METHOD: run_tcpdump(shell, prefix, intf, port)
    #
    # DESCRIPTION: Start a tcpdump using the specified shell object
    #
    #                 shell  - a shell object which has been created for the local or remote system
    #                          You may run multiple simultaneous tcpdumps using the same shell
    #                 prefix - an arbitrary string which will be used to construct the pcap filename
    #                 intf   - the interface to monitor (like eth0) or you may specify 'all' for all interfaces.
    #                 port   - the port to monitor (like 7077) or you may specify 'all' for all ports.
    #
    #              The pcap filename will be:  <prefix>.<ip>:<port>.<intf>.pcap
    #
    ##############################################################################################
    def run_tcpdump(self, shell, prefix, intf, port):
        """run_tcpdump(shell, prefix, intf, port)
              Start a tcpdump using the specified shell object
                 shell  - a shell object which has been created for the local or remote system
                          You may run multiple simultaneous tcpdumps using the same shell
                 prefix - an arbitrary string which will be used to construct the pcap filename
                 intf   - the interface to monitor (like eth0) or you may specify 'all' for all interfaces.
                 port   - the port to monitor (like 7077) or you may specify 'all' for all ports.
              The pcap filename will be:  <prefix>.<ip>:<port>.<intf>.pcap
              """

        # The output pcap name will be like tcp.172.15.34.23.eth0.7077.pcap
        pcap = prefix + '.' + shell.ip + ':' + port + '.'+ intf + '.pcap'
        
        # Get rid of the previous local and remote versions so we don't confuse ourselves with an old pcap
        os.system('rm -f ' + pcap)
        shell.run('rm -f ' + pcap)
        
        # Set up the tcpdump command based on options
        cmd = 'sudo tcpdump -B 131072 -tt -s 0 -w ' + pcap
        
        if intf == "all":
            cmd = cmd + " -i any"
        else:
            cmd = cmd + " -i " + intf

        if not port == 'all':
            cmd = cmd + " port " + port

        # Launch tcpdump on the remote system
        log("Packet Capture started on " + shell.ip + "   " + cmd)
        tcpdump = shell.launch(cmd)

        # Remember the tcpdumps we have launched and the associated pcap name
        self.pcaps.append([shell, tcpdump, pcap])

        return pcap

    ##############################################################################################
    #
    # METHOD: stop_all()
    #
    # DESCRIPTION: Blindly kill all tcpdumps on the client and server.  This is intended for the atexit
    #
    ##############################################################################################
    def stop_all(self):
        """stop_all():
              Blindly kill all tcpdumps on the client and server.  This is intended for the atexit 
              """
        # Clean out old tcpdumps on each system
        self.server_shell.run("sudo pkill tcpdump")
        self.client_shell.run("sudo pkill tcpdump")

    ##############################################################################################
    #
    # METHOD: parse_pcap()
    #
    # DESCRIPTION: Run tshark on the specified pcap file using the specified filters and extract the 
    #              specified fields. Return the information in a list of dictionaries where each dictionary 
    #              represents a line in filtered pcap file and where the keys of each dictionary correspond 
    #              to the fields requested.
    #                 pcap    -
    #                 filters -
    #                 fields  -
    #                 options - 
    #
    ##############################################################################################
    def parse_pcap(self, pcap, filters, fields, option=""):
        """parse_pcap():
              Run tshark on the specified pcap file using the specified filters and extract the 
              specified fields. Return the information in a list of dictionaries where each dictionary 
              represents a line in filtered pcap file and where the keys of each dictionary correspond 
              to the fields requested.
              """

        # check options and fields
        if option == "" and fields == "":
            # none go with just a straight filter
            cmd = 'tshark -r ' + pcap + ' -R ' + filter
        elif  option == "":
            # construct tshark command for filters and fields
            cmd = 'tshark -r ' + pcap + ' -R ' + filters + ' -T fields'
        else:
            # contruct tshark command for filters, options and fieldswith specified options and filters
            cmd = 'tshark -r ' + pcap + " " +option+ " " + filters + ' -T fields'

            # Add in the requested fields
            for field in fields:
                cmd = cmd + ' -e ' + field

        # Python seems to have an issue capturing lots of output (in this case from tshark) so redirect to a 
        # file then read in the file We can't use the -w <outfile> option of tshark because -w means write the 
        # raw binary (filtered) data to the file.  We need text
        cmd = cmd + " > __tshark.log"
        
        # Run tshark
        output = self.local_shell.run(cmd, 0)

        # Read in the redirected file
        datafile = open("__tshark.log", "r")
        content = datafile.read()
        datafile.close
        
        # Translate the content into a list of dictionaries
        info = []
        lines = content.split("\n")
        i = 0
        for line in lines:
            #log(str(i) + "\t" + line)
            line = line.split("\t")
            values={}
            j = 0
            for value in line:
                values[fields[j]] = value
                j += 1
            i += 1
            info.append(values)

        # Return the list of dictionaries
        return info

    ##############################################################################################
    #
    # METHOD: parse_pcap_w_specific_opt()
    #
    # DESCRIPTION: Run tshark on the specified pcap file using the specified filters and extract the 
    #              specified fields. Return the information in a list of dictionaries where each dictionary 
    #              represents a line in filtered pcap file and where the keys of each dictionary correspond 
    #              to the fields requested
    #                 pcap    -
    #                 filters -
    #                 options -
    #                 fields  -
    #                 addcmd  - 
    #
    ##############################################################################################
    def parse_pcap_w_specific_opt(self, pcap, option, filters, fields, addcmd):

        # Construct the tshark command with the specified filters
        cmd = 'tshark -r ' + pcap + ' ' + option + ' ' + filters

        if fields != "":
            cmd = cmd + ' -T fields '
            # Add in the requested fields
            for field in fields:
                cmd += " -e " +field

        if addcmd != "":
            cmd = cmd + ' ' +addcmd
            
        log("RUNNING TSHARK CMD : " +cmd)
        
        # Run tshark
        output = self.local_shell.run(cmd, 0)

        # Return the list of dictionaries
        return output

    ##############################################################################################
    #
    # METHOD: parse_pcap_w_preferred_config()
    #
    # DESCRIPTION: This allows specifying a "custom" tshark configuration for special case tshark setups. Case
    #              in point to turn off allowing subdissectors to reassemble TCP streams. Tshark had trouble disecting
    #              large data packets with embedded http headers so turning it off in a preferred config fix the issue.
    #              Run tshark on the specified pcap file using the specified filters and extract the specified fields
    #              Return the information in a list of dictionaries where each dictionary represents a line in filtered 
    #              pcap file and where the keys of each dictionary correspond to the fields requested
    #
    ##############################################################################################
    def parse_pcap_w_preferred_config(self, pcap, option, filters, fields, addcmd):

        # Construct the tshark command with the specified filters
        cmd = 'tshark -r ' + pcap + ' ' + option + ' ' + filters

        if fields != "":
            cmd = cmd + ' -T fields '
            # Add in the requested fields
            for field in fields:
                cmd += " -e " +field

        if addcmd != "":
            cmd = cmd + ' ' +addcmd

        log("RUNNING TSHARK CMD : " +cmd)

        # Python seems to have an issue capturing lots of output (in this case from tshark) so redirect to a file then read in the file
        # We can't use the -w <outfile> option of tshark because -w means write the raw binary (filtered) data to the file.  We need text
        cmd = cmd + " > __tshark.log"
        
        # Run tshark
        output = self.local_shell.run(cmd, 0)

        # Read in the redirected file
        datafile = open("__tshark.log", "r")
        content = datafile.read()
        datafile.close
        
        # Translate the content into a list of dictionaries
        info = []
        lines = content.split("\n")
        i = 0
        for line in lines:
            #log(str(i) + "\t" + line)
            line = line.split("\t")
            values={}
            j = 0
            for value in line:
                values[fields[j]] = value
                j += 1
            i += 1
            info.append(values)

        # Return the list of dictionaries
        return info

    ##############################################################################################
    #
    # METHOD: parse_pcap_w_awk_cmd()
    #
    # DESCRIPTION: Run AWK on the specified .txt file that was generated by running a parse_pcap on a 
    #              capture and piping the output to thext file generated.
    #
    ##############################################################################################
    def parse_pcap_w_awk_cmd(self, pcap_txt, awkcmd):
        """parse_pcap_w_awk_cmd():
              Run AWK on the specified .txt file that was generated by running a parse_pcap on a 
              capture and piping the output to thext file generated.
              """
        # cat the pcap-test file generated from parse_pcap()
        cmd = 'cat ' +pcap_txt+ ' ' +awkcmd
            
        # Run awk
        log("RUNNING AWK COMMAND ON TSHARK PARSE : " +cmd)        
        output = self.local_shell.run(cmd, 0)

        # Return the list of dictionaries
        return output
