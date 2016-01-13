#!/usr/bin/python3

#
# Copyright 2016, Dan Malone, All Rights Reserved
#
from util import *
from .shell import *

local_shell = shell("local")

###################################################################################################
#
# MODULE (Class): netem
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
class netem:
    """This class manages a netem system"""

    ##############################################################################################
    #
    # METHOD: __init__(testbed, netem_id, user_id)
    #
    # DESCRIPTION: This is the initialization constructor:
    #                  testbed  - testbed device map data from .xml
    #                  netem_id - the id of the netem device configured in  testbed 
    #                  user_id  - the accessing user (root/<username>) running the test, required if
    #                             non-root, some commands must be sudo'd etc. derived from the tbed
    #                             configuration (default is root)
    #
    ##############################################################################################
    def __init__(self, testbed, netem_id, user_id):
        """__init__(testbed, netem_id, user_id)
              This is the initialization constructor:
                 testbed  - testbed device map data from .xml
                 netem_id - the id of the netem device configured in  testbed
                 user_id  - the accessing user (root/<username>) running the test, required if
                            non-root, some commands must be sudo'd etc. derived from the tbed
                            configuration (default is root)
                            """

        # Get the ip addresses out of the testbed
        self.testbed    = testbed

        # To allow the root_username to be respected from the tbed cfg file
        # we have to grab it, assign it to "user" then use it in place of hardcode "root"
        self.user       = testbed.find(".//root_username[@id='" + str(user_id) + "']/name").text

        # grab netem essentials
        self.control_ip = testbed.find(".//netem_server[@id='" + str(netem_id) + "']/ip").text
        self.method     = testbed.find(".//netem_server[@id='" + str(netem_id) + "']/method").text
        
        # We'll need a shell on the remote machine
        self.netem_shell = shell(self.control_ip, self.user)

        # this is a kludge to allow executing inline tc cmds if non-root we create a set of
        # netem scripts on the fly (delete, create and change) to control from the device itself.
        if self.user != "root":
            
            ##### DELETE #####
            log("VERIFYING OR CREATING NETEM_DELETE.SH")
            ndelete_bash = "#!/bin/bash\n\nDEV=\$1\ntc qdisc del dev \$DEV root\n"
            self.netem_shell.run("if [ ! -f netem_delete.sh ]; then echo \"" +ndelete_bash+ "\" > netem_delete.sh; chmod 777 netem_delete.sh; fi") 
            
            ##### CHANGE #####
            log("VERIFYING OR CREATING NETEM_CHANGE.SH")
            nchange_bash = "#!/bin/bash\n\nDEV=\$1\nALG=\$2\nRATE=\$3\nDELAY=\$4\nLIMIT=\$5\nPING=\$6\n\nif [ \$LIMIT -gt 0 ]; then tc class change dev \$DEV parent 10: classid 0:1 \$ALG rate \$RATE ceil \$RATE\n\ntc qdisc change dev \$DEV parent 10:1 handle 11: netem delay \$DELAY limit \$LIMIT\n\nping -c 1 \$PING;\nelse\n tc class change dev \$DEV parent 10: classid 0:1 \$ALG rate \$RATE ceil \$RATE\n\ntc qdisc change dev \$DEV parent 10:1 handle 11: netem delay \$DELAY\n\nping -c 1 \$PING;\n fi"
            self.netem_shell.run("echo \"" +nchange_bash+ "\" > netem_change.sh; chmod 777 netem_change.sh;") 
            
            ##### CREATE #####
            log("VERIFYING OR CREATING NETEM_CREATE.SH")            
            ncreate_bash = "#!/bin/bash\n\nDEV=\$1\nALG=\$2\nRATE=\$3\nDELAY=\$4\nLIMIT=\$5\nPING=\$6\n\nif [ \$LIMIT -gt 0 ]; then tc qdisc add dev \$DEV root handle 1: prio bands 10\n\ntc qdisc add dev \$DEV parent 1:1 handle 10: \$ALG default 1\n\ntc class add dev \$DEV parent 10: classid 0:1 \$ALG rate \$RATE ceil \$RATE\n\ntc qdisc add dev \$DEV parent 10:1 handle 11: netem delay \$DELAY limit \$LIMIT\n\ntc filter add dev \$DEV protocol ip parent 1:0  prio 1 u32 match ip src 0.0.0.0/0 match ip dst 0.0.0.0/0 flowid 10:1\n\nping -c 1 \$PING\nelse\ntc qdisc add dev \$DEV root handle 1: prio bands 10\n\ntc qdisc add dev \$DEV parent 1:1 handle 10: \$ALG default 1\n\ntc class add dev \$DEV parent 10: classid 0:1 \$ALG rate \$RATE ceil \$RATE\n\ntc qdisc add dev \$DEV parent 10:1 handle 11: netem delay \$DELAY\n\ntc filter add dev \$DEV protocol ip parent 1:0  prio 1 u32 match ip src 0.0.0.0/0 match ip dst 0.0.0.0/0 flowid 10:1\n\nping -c 1 \$PING;\n fi"
            self.netem_shell.run("echo \"" +ncreate_bash+ "\" > netem_create.sh; chmod 777 netem_create.sh;") 
            
        # Don't leave impairment in place if we bomb out
        atexit.register(self.clear_netem)
        
    #########################################################################
    #
    # METHOD: clear_netem()
    #
    # DESCRIPTION: This method will clear any network impairments on all interfaces 
    #              on the target netem machine.
    #
    #########################################################################
    def clear_netem(self):
        """clear_netem():
              This method will clear any network impairments on all interfaces
              on the target netem machine.
              """

        trace_enter()
        eths = self.netem_shell.run('tc qdisc | grep qdisc | cut -f 5 -d " "')
        eths = shlex.split(eths, "/n")
        eths.sort()
        log('DEBUG', "Clearing netem on interfaces on server " + self.control_ip)
        for eth in eths:
            try:
                if self.user != "root":
                    self.netem_shell.run("./netem_delete.sh " +eth)
                else:
                    self.netem_shell.run("tc qdisc del dev " + eth + " root", 0)
            except:
                pass
        trace_exit()
        
    ##############################################################################################
    #
    # METHOD: run(command, perror=1, redirect_err=0)
    #
    # DESCRIPTION: This method runs the specified command on the target system
    #                 If perror is 0, the error will not be printed if the command fails
    #                 If redirect_err is 1, the output will be redirected (>&) to a file and 
    #                    the contents of that file returned as a string
    #              This is needed for some commands like curl that seem to use stderr as normal 
    #              output.
    #
    ############################################################################################## 
    def run(self, command, perror=1, redirect_err=0):
        """run(command, perror=1, redirect_err=0):
              This method runs the specified command on the target system
                 If perror is 0, the error will not be printed if the command fails
                 If redirect_err is 1, the output will be redirected (>&) to a file and 
                    the contents of that file returned as a string
              This is needed for some commands like curl that seem to use stderr as normal
              output.
              """
 
        output = self.netem_shell.run(command, perror, redirect_err)
        return output

    #########################################################################
    # 
    # METHOD: set(profile)
    #
    # DESCRIPTION: Set netem using the values in the profile
    #
    #              Profile can either be:
    #                 The name of an entry in ../netem_scripts/netem_testcases.csv
    #                 or a dictionary of the form: {'name' ; 'myprofile'} which is the name of an entry in netem_testcases.csv
    #                 or a dictionary of the form: {'name' : 'myprofile',  'delay' : 300,  'loss': 0, 'jitter' : 0, 'bandwidth' : 20000}
    #                 or a dictionary of the form: {'delay' : 300,  'loss': 0, 'jitter' : 0, 'bandwidth' : 20000} where the name will be set to 'default'
    #
    #              Returns the profile as a dictionary of the form: {'name' : 'myprofile',  'delay' : 300,  'loss': 0, 'jitter' : 0, 'bandwidth' : 20000}
    #              even if what was passed in was just the name of a profile in netem_testcases.csv
    #
    #              The update only field allows tc updates without tearing down the existing tc qdisc
    #
    #              The dynamic queue limit param provides dynamic queue length adjustment based off passed delay (RTT)
    #              a future would be to test for RTT and use that value
    #
    #########################################################################
    def set(self, profile, update_only=0, dynQlim=0, exec_ping=0):
        """set(profile):
              Set netem using the values in the profile
              Profile entry can either be:
                 The name of an entry in a specifc netem_scripts directory as a .csv file (../netem_scripts/netem_testcases.csv)
                 or a dictionary of the form: {'name' ; 'myprofile'} which is the name of an entry in netem_testcases.csv
                 or a dictionary of the form: {'name' : 'myprofile',  'delay' : 300,  'loss': 0, 'jitter' : 0, 'bandwidth' : 20000}
                 or a dictionary of the form: {'delay' : 300,  'loss': 0, 'jitter' : 0, 'bandwidth' : 20000} where the name will be set to 'default'
              Returns the profile as a dictionary of the form: {'name' : 'myprofile',  'delay' : 300,  'loss': 0, 'jitter' : 0, 'bandwidth' : 20000}
              even if what was passed in was just the name of a profile in netem_testcases.csv
              The update only field allows tc updates without tearing down the existing tc qdisc
              The dynamic queue limit param provides dynamic queue length adjustment based off passed delay (RTT)
              a future would be to test for RTT and use that value
              """

        # FIgure out whether they passed in a profile name as a string, a dictionary with just the name, or a dictionary with all the values
        if isinstance(profile, dict):
            # They passed in a dictionary.  Is it a full one or does it just contain the name of the profile
            if 'name' in profile:
                name = profile['name']
                if not 'delay' in profile:
                    # They passed in a dictionary with just the name.  We'll look it up in the csv file as if they had passed in just the name as a string
                    profile = profile['name']
            else:
                # It is a dictionary but they did not specify a name.  Default the name
                name = 'default'
        else:
            # They just passed in the profile name as a string
            name = profile

        if not isinstance(profile, dict):
            # This is a profile in the netem_testcases.csv file
            if not csvReader.profileInCsv(profile):
                msg = 'Profile does not exist in ../netem_scripts/netem_testcases.csv'
                msg = "\nERROR: " + self.__class__.__name__ + "(" + name + ") " + msg + "\n"
                log(msg)
                sys.exit(msg)
                
            loss      = csvReader.getFieldFromCsv(profile, "loss")
            delay     = csvReader.getFieldFromCsv(profile, "delay")
            jitter    = csvReader.getFieldFromCsv(profile, "jitter")
            bandwidth = csvReader.getFieldFromCsv(profile, "bandwidth")
            profile   = {'name' : profile, 'loss': loss, 'delay' : delay, 'jitter' : jitter, 'bandwidth' : bandwidth}
            
        elif not 'delay' in profile:
            msg = self.__class__.__name__ + "(" + name + ") Profile dictionary must contain delay:, loss:, jitter:, bandwidth:"
            log(msg)
            sys.exit(msg)

        # we should have what we need do ome text formatting to make 
        # it easier to create the commands
        loss      = str(profile['loss']) + "%"
        delay     = str(float(profile['delay']/2)) + "ms"
        jitter    = str(float(profile['jitter']/2)) + "ms"
        bandwidth = str(profile['bandwidth']) + "kbit"

        # netem allows the use of a predefined distribution file to
        # administer pseudo RTT over time. Check for and set up use.
        rttdist   = ""
        dvary     = ""
        if "rttdist" in profile:
            rttdist = str(profile['rttdist'])
            if "dvary" in profile and rttdist != "":
                # set up sigma delay value for above distribution if included
                dvary = str(float(profile['dvary']/2)) + "ms"

        # check for reorder directive and set up if found
        reorder   = ""
        if "reorder" in profile:
            reorder = str(profile['reorder'])            

        # Best to clear the netem first if not just doing an update.  
        # tc qdisc add sometimes errors with RTNETLINK answers: File exists
        if not update_only and dynQlim == 0:
            self.clear_netem()

        # get ip from "eth" and set up for ip ping marker if pcap-ing
        ping_ip = exec_ping
        log("NETEM PING IP : " +str(ping_ip))

        # Apply netem config to all interfaces listed in config
        log('DEBUG', 'Applying netem profile "' + name + '": ' + str(profile))
        for element in self.testbed.find("netem_server").findall("interface"):

            eth = element.find("name").text
            log("FOUND NETEM INTF : " + eth)

            # Again if not doing an update clear out the old settings (although this
            # appears to be redundant as we did a clear netem above)
            if not update_only and dynQlim == 0:
                self.netem_shell.run("tc qdisc del dev " + eth + " root", 0)
            
            # if indicated size the netem queue limit dynamically based of bandwidth and delay
            limit = 0
            if dynQlim:

                # this is for buffer bloat experimentation (congestion network) by allowing a multiplier
                # for qdepth we can simulate network buffering along the pipe.
                if 'bwmult' in profile:
                    bwmult = profile['bwmult']
                    # calculate qdepth based on full RTT if < 30 use 30 as base limit else use calculated.
                    limit = int(1.2 * (((int(profile['bandwidth']) * 1024) * ((int(profile['delay']))/1000))/11160)) + 30
                    limit = int(limit * bwmult)
                else:
                    # calculate qdepth based on full RTT if < 30 use 30 as base limit else use calculated.
                    limit = int(1.2 * (((int(profile['bandwidth']) * 1024) * ((int(profile['delay']))/1000))/11160)) + 30

                log("HTB QLIMIT Formula( limit = 1.2 * (<bandwidth> * 1024) * ((delay/2)/1000) /<data bits in pkt>)")
                log("UNI-DIRECTIONAL Q LIMIT : "+str(limit))
                log("BANDWIDTH               : "+str(profile['bandwidth']))
                log("DELAY IN MS             : "+str(profile['delay']))

            # Here we set up netem according to the kernel as it varies between: >= 3.8 vs < 3.8
            if self.method == "2":
                log('DEBUG', "Setting netem method 2 3.8 kernel or >")

                # see if we are only doing a tc qdisc dynamic update
                if update_only:

                    # just make the update on the same netem instance(s).. note: if we are root we handle it
                    # via shell else we have to call the scripts placed earlier on the target device.
                    if self.user == "root":
                        # this is a root user based update we can use the shell
                        cmd = "tc class change dev "  + eth + " parent 10: classid 0:1 htb rate " + bandwidth + " ceil " + bandwidth

                        # if we have a dynamic queue length then use it
                        if dynQlim:
                            cmd += "; tc qdisc change dev "  + eth + " parent 10:1 handle 11: netem"
                            if int(profile['delay']) > 0:
                                # see if we are implimwenting a distirbution
                                if rttdist == "":
                                    # no.. use delay as is
                                    cmd += " delay " +delay
                                else:
                                    # this is a distribution table file request apply dvary and dist
                                    cmd += " delay " +delay+ " " +dvary+ " distribution " +rttdist
                            if reorder != "":
                                # apply a reorder
                                cmd += " reorder " +reorder
                            if int(profile['jitter']) > 0:
                                # apply a jitter
                                cmd += " " + jitter
                            if float(profile['loss']) > 0.0:
                                # apply a loss
                                cmd += " loss " +loss
                            # all else.. apply a qlimit
                            cmd += " limit " +str(limit)
                                                
                            # append a ping if we requested (allows us to mark the change within a tshark)
                            if ping_ip:
                                cmd += "; ping -c 1 " +ping_ip
                        else:
                            # standard qlimit
                            cmd = "tc class change dev "  + eth + " parent 10: classid 0:1 htb rate " + bandwidth + " ceil " + bandwidth
                            self.netem_shell.run(cmd+ "; tc qdisc change dev "  + eth + " parent 10:1 handle 11: netem delay " + delay + " " + jitter + " loss " + loss)
                    else:
                        # non-root user.. use the scripts on the target machine (note: DRM add distribution if deemed necessary - future)
                        cmd = "./netem_change.sh " +str(eth)+ " htb " +str(bandwidth)+ " " +str(delay)+ " " +str(limit)+ " " +str(ping_ip)

                    # execute update
                    self.netem_shell.run(cmd)

                else:
                    # create a new tc qdisc and instantiate a new netem instance
                    if self.user == "root":
                        # this is a root user request.. set it all up as one command line for efficiency
                        cmd = "tc qdisc add dev "  + eth + " root handle 1: prio bands 10; tc qdisc add dev "  + eth + " parent 1:1 handle 10: htb default 1; tc class add dev "  + eth + " parent 10: classid 0:1 htb rate " + bandwidth + " ceil " + bandwidth

                        # if we have a dynamic queue length then use it (note: DRM think about a method for this might be cleaner)
                        if dynQlim:
                            cmd += "; tc qdisc add dev "  + eth + " parent 10:1 handle 11: netem"             
                            if int(profile['delay']) > 0:
                                # see if we are implimwenting a distirbution
                                if rttdist == "":
                                    # no.. use delay as is
                                    cmd += " delay " +delay
                                else:
                                    # this is a distribution table file request apply dvary and dist
                                    cmd += " delay " +delay+ " " +dvary+ " distribution " +rttdist
                            if reorder != "":
                                # apply reorder
                                cmd += " reorder " +reorder
                            if int(profile['jitter']) > 0:
                                # apply jitter
                                cmd += " " + jitter
                            if float(profile['loss']) > 0.0:
                                # apply loss
                                cmd += " loss " +loss
                            # all else apply qlimit
                            cmd += " limit " +str(limit)
                                
                        else:
                            # standard qlimit
                            cmd += "; tc qdisc add dev "  +eth+ " parent 10:1 handle 11: netem delay " +delay+ " " +jitter+ " loss " +loss

                        # fimish with a generic filter
                            cmd += "; tc filter add dev " + eth + " protocol ip parent 1:0  prio 1 u32 match ip src 0.0.0.0/0 match ip dst 0.0.0.0/0 flowid 10:1"
                        
                        # add ping if requested (allows us to mark the change within a tshark)
                        if ping_ip:
                            cmd += "; ping -c 1 " +ping_ip

                    else:
                        # non-root user.. use the scripts on the target machine (note: DRM add distribution if deemed necessary - future)
                        cmd = "./netem_create.sh " +str(eth)+ " htb " +str(bandwidth)+ " " +str(delay)+ " " +str(limit)+ " " +str(ping_ip)

                    # execute create
                    self.netem_shell.run(cmd)

                    # Verify the settings took. (NOT_TO_SELF:  work on this later when hardware is in place)
#                    if netem.verify(self, eth, profile['bandwidth'], profile['delay'], profile['loss'], profile['jitter']):
#                        log("NETEM CONFIGURE FAILURE")
#                        assert(False)

            elif self.method == "1":
                # earlier than 3.8 kerenls (this is really defunct but as a safety we'll keep it)
                log('DEBUG', "Setting netem method 1 (< 3.8 kernel)")
                self.netem_shell.run("tc qdisc add dev " + eth + " root handle 1: netem delay " + delay + " " + jitter + " loss " + loss + " limit " +str(limit))
                self.netem_shell.run("tc qdisc add dev " + eth + " parent 1:1 handle 10: htb default 1 r2q 10")
                self.netem_shell.run("tc class add dev " + eth + " parent 10: classid 0:1 htb rate " + bandwidth + " ceil " + bandwidth)

            else:
                msg = 'Metem method: "' + self.method + '" invalid.  Please specify "1" or "2"'
                msg = "\nERROR: " + self.__class__.__name__ + "(" + name + ") " + msg + "\n"
                log(msg)
                sys.exit(msg)

        # Display the settings
        output = self.netem_shell.run("tc qdisc")
        log('DEBUG', output)

        # Return the profile as a dictionary
        return(profile)

    #########################################################################
    #
    # METHOD: verify(<interface>, <curr_bw>, <curr_delay>, <curr_loss>, <curr_jitter>)
    #
    # DESRCRIPTION: Verify the netem settings currently configured using the values from the last set
    #                  <interface> - interface for verification
    #                  badnwidth - current bandwidth
    #                  delay     - current delay
    #                  loss      - current loss 
    #                  jitter    - current jitter
    #                  dvary     - current dvary if distribution
    #                  dist      - distribution name if supplied
    #
    #               returns 1 if any items is a fail 0 if success al items correct
    #
    # NOT_TO_SELF: Rework this when hardare is in place.
    # 
    #########################################################################
    def verify(self, eth, bandwidth=0, delay=0, loss=0, jitter=0, dvary=0, dist=""):
        """verify(<interface>, <curr_bw>, <curr_delay>, <curr_loss>, <curr_jitter>)
              Verify the netem settings currently configured using the values from the last set
                 <interface> - interface for verification
                 badnwidth - current bandwidth
                 delay     - current delay
                 loss      - current loss
                 jitter    - current jitter
                 dvary     - current dvary if distribution
                 dist      - distribution name if supploied
               returns 1 if any items is a fail 0 if success al items correct
               """

        log("ARGS : " +eth+ " " +str(bandwidth)+ " " +str(delay)+ " " +str(loss)+ " " +str(jitter))
        
        # query the current netem settings
        netem_settings = self.netem_shell.run("tc qdisc show dev " +eth)
        netem_settings.strip()
        
        lines = netem_settings.split("\n")

        log("NETEM SETTINGS " +str(lines))

        # for tracking
        idx = 0
        for i in lines:
            log("LINE" +idx+ ": " +i)
            idx += 1

        # lets process the current vs expected
        for idx in range(0, len(lines)):
            
            fail = 0
            test = re.match(r'qdisc netem', lines[idx])
            if test:
                log("HAVE THE RIGHT NETEM LINE")
                if int(bandwidth) > 0:
                    log("BANDWIDTH PRESENT > 0")
                    test = re.match(r'qdisc netem \d+: parent 10:1 limit (\d+) .*', lines[idx])
                    if test.group(1) == bandwidth:
                        log("BANDWIDTH CORRECT")
                        if  int(delay) > 0:
                            log("DELAY PRESENT")
                            test = re.match(r'qdisc netem \d+: parent 10:1 limit \d+ delay (\d+\.?\d*).*', lines[idx])
                            if test.group(1) == delay:
                                log("BANDWIDTH CORRECT")
                                if int(jitter) > 0:
                                    log("JITTER PRESENT")
                                    test = re.match(r'qdisc netem \d+: parent 10:1 limit \d+ delay \d+\.?\d*\w+ (\d+\.?\d*).*', lines[idx])
                                    if test.group(1) == jitter:
                                        log("JITTER CORRECT")
                                        if int(loss) > 0:
                                            log("LOSS PRESENT")
                                            test = re.match(r'qdisc netem \d+: parent 10:1 limit \d+ delay \d+\.?\d*\w+ \d+\.?\d*\w+ loss (\d+\.?\d*).*', lines[idx])
                                            if test.group(1) != loss:
                                                log("LOSS FAILED - " +loss+ " != " +test.group(1))
                                                fail = 1
                                    else:
                                        log("JITTER FAILED - " +jitter+ " != " +test.group(1))
                                        fail = 1
                                elif int(loss) > 0:
                                    log("LOSS PRESENT")
                                    test = re.match(r'qdisc netem \d+: parent 10:1 limit \d+ delay \d+\.?\d*\w+ \d+\.?\d*\w+ loss (\d+\.?\d*).*', lines[idx])
                                    if test.group(1) != loss:
                                        log("LOSS FAILED - " +loss+ " != " +test.group(1))
                                        fail = 1
                            else:
                                log("DELAY FAILED - " +delay+ " != " +test.group(1))
                                fail =1
                    else:
                        log("BANDWIDTH FAILED - " +str(bandwidth)+ " != " +test.group(1))
                        fail = 1
                else:
                    log("NO BANDWIDTH ERROR")
                    fail = 1
            else:
                continue

        if fail:
            log("NETEM DID MOT CONFIGURE AS REQUESTED")
        else:
            log("NETEM RECONFIGURED")
            
        return(fail)
