#!/usr/local/bin/python3

#
# Copyright 2016, Dan Malone, All rights reserved
#

import util.utilities

from util.globals import *
from .shell import *

import re
import shlex
import sys
import atexit
import inspect
from time import sleep

import copy
import json

###################################################################################################
# class client_linux
#
# This class manages a TEST Client running on linux.
# The client program can be stopped and started and the client config can be changed
#
# Usage:
#
# test_client =  test_client_linux.client_linux(testbed, client_id, server_id)
#                Where client_id is the id in the testbed for the client to managed
#                server_id is the id in the testbed for the server that the client should connect to
##################################################################################################

class test_client_linux:
    """This class manages a test client on linux.  The client program can be stopped and started and the client config can be changed"""

    ##############################################################################################
    # contstructor(testbed, client_id, server_id)
    # client_id is the id in the testbed for the client to manage
    # server_id is the id in the testbed for the server that the client should connect to
    ##############################################################################################
    def __init__(self, testbed, client_id, server_id, user_id):

        # Get the ip addresses out of the testbed
        self.testbed      = testbed

        # 02/23/15 - DRM: To allow the root_username to be respected from the tbed cfg file
        # we have to grab it, assign it to "user" then use it in place of hardcode "root"
        self.user         = testbed.find(".//root_username[@id='" + str(user_id) + "']/name").text

        # set up test client essetials
        self.control_ip   = testbed.find(".//control_client[@id='" + str(client_id) + "']/ip").text
        self.data_ip      = testbed.find(".//test_client[@id='"      + str(server_id) + "']/ip").text
        self.client_path  = testbed.find(".//control_client[@id='"  + str(client_id) + "']/path").text
        self.proxy_local  = ""
        self.sessions = []
        self.time_started = 0

        # We'll need a shell on the client machine to manage it
        self.shell = shell(self.control_ip, self.user)

        # Get the current configuration
        self.defaultClientConfig = self.get_config()
        self.currentClientConfig = copy.deepcopy(self.defaultClientConfig)

        # Let's also get the control and data ip of the server this client will attach to
        self.server_control_ip  = testbed.find(".//control_server[@id='" + str(server_id) + "']/ip").text
        self.server_data_ip     = testbed.find(".//test_server[@id='"     + str(server_id) + "']/ip").text

        # And a server shell so we can get this client's session id
        self.server_shell = shell(self.server_control_ip, self.user)
        

    ##############################################################################################
    # set_default_config()
    # Using the copy of proxy_local.conf that was saved during install, reset the client config
    # Set the serverAddress in the config to the address of the test server
    ##############################################################################################
    def set_default_config(self):

        log('DEBUG', "Resetting client config on " + self.control_ip)

        # proxy_local.conf
        cmd = "sudo cp " +self.client_path+ "default.proxy_local.conf " +self.client_path+ "proxy_local.conf; sudo chmod ugo+w " +self.client_path+ "default.proxy_local.conf"
        self.shell.run(cmd)

        # profile.json
        cmd = "if [ -f " +self.client_path+ "default.profile.json ]; then sudo cp " +self.client_path+ "default.profile.json " +self.client_path+ "profile.json; sudo chmod ugo+w " +self.client_path+ "default.profile.json; fi"
        self.shell.run(cmd)
        
        # Set this as the default configuration and the current configuration
        self.defaultClientConfig = self.get_config()
        self.currentClientConfig = copy.deepcopy(self.defaultClientConfig)

        # Update the Test Server Address
        profile = {}
        profile['client.serverAddress'] = self.server_data_ip

        self.update_config(profile)

        # Now with the Test server address configured, set this as the new default configuration and the current configuration
        self.defaultClientConfig = self.get_config()
        self.currentClientConfig = copy.deepcopy(self.defaultClientConfig)

        
    ##############################################################################################
    # update_config(profile, oldcfg=0, tag="default)
    #
    #    profile: test run profile with all options including config items
    #    oldcfg : switch to go all in on configuring via proxy_local.conf ONLY (1 means yes)
    #    tag    : this is the nettype tag for now to allow configing of nettype data as well as default
    #
    # Update_config has changed and now handles both proxy_local.conf and profile.json. Unfortunately,
    #     I decided to support both going forward as there may be a need to execute images before the change
    #     was put into place in order to walk backwards on older images to verify issues are new/regressions.
    #     This makes for a litle bit of necessary ugliness in the code.
    #     Update the client configuration using a combination of defaults and what is specified in the profile parameter
    #     profile is a dictionary
    #
    # Update the client configuration with any values in the profile which have key which starts with "client."
    #     For oldcfg OR with "client." for those specific elements now under proxy_local.conf ONLY:
    #
    #         client.serverAddress
    #         client.proxyPort"
    #         client.networktype_key
    #         client.networktype
    #
    #     for new config schema ALL other params MUST be prefenced with "json." ex: json.loggingLevel
    #
    # NOTE: If you are unsure about the naming convention for the param in profile.json check the file
    #     as some names have changed with respect to proxy_local.conf or check with development. If you
    #     chose oldcfg all "json." preferenced params will be handled correctly
    #
    # Example of use:
    #
    #     profile[client.serverAddress] = "172.172.172.172"
    #     profile[json.loggingLevel] = 3
    #
    #     New:
    #         test_client.update_config(profile)
    #
    #     With nettype specified (new only):
    #
    #        profile[client.serverAddress] = "172.172.172.172"
    #        profile[json.loggingLevel] = 3
    #
    #        test_client.update_config(profile, tag="LTE")
    #
    #    profile can also be expressed as a dictionary of terms:
    #
    #        e.g. test_client.update({client.serverAddress : "172.171.172.172", json.loggingLevel : 3)
    #
    #    This would set serverAddress to "172.171.172.172" in proxy_local.conf and loggingLevel to 3 
    #    in profile.json in this case.
    #
    # If a value is NOT specified in the dictionary, by default the value will be set from the defaults
    # or in the case of JSON will be added as specified so be warned that you can kill loading of 
    # profile.json without warning.
    #
    ##############################################################################################
    def update_config(self, profile, oldcfg=0, tag="default"):

    
        # #####################################
        # Process Proxy Local first if new config ONLY process allowed params
        # #####################################

        # Get the default configuration
        config  = copy.deepcopy(self.defaultClientConfig)

        # Modify it with what they want to change
        for key in profile:
            if re.match("^client.", key) or (oldcfg and re.match("^json.", key)):
                # restrict params if not old config
                if oldcfg or ("client.serverAddress" in key \
                              or "client.proxyPort" in key \
                              or "client.networktype_key" in key \
                              or "client.networktype" in key):

                    key = key.split(".")[1]
                    config[key] = profile["client." + key]

        # Now go and set each value.  If the value is already set on the client, do nothing.
        # If it is not already set. modify the client and set the dirty bit so we know to restart
        for key in config:
            new_value = config[key]
            original_value = getKey(self.currentClientConfig, key, "")
            if original_value == "":
                msg = "ERROR: = Attempt to set client configuration parameter in proxy_local.conf, but no such key exists: " + key
                log(msg)
                sys.exit(msg)

            if not key in self.currentClientConfig or not self.currentClientConfig[key] == new_value:
                if getOpt('VERBOSE'):
                    log('DEBUG', "Modifying client config value for " + key + " from " + str(original_value) + " to " + str(new_value))
                    
                cmd =  'sed -i "s/[ \t]*' + key + '[ \t]*=.*/' + key + ' = ' + str(new_value) + '/" '  + self.client_path + 'proxy_local.conf'

                self.shell.run(cmd)
                self.currentClientConfig[key] = new_value
                self.configChanged = 1
        
        if not oldcfg:
            
            # #####################################
            # Process Profile if new config ONLY
            # #####################################

            try:
                with open("/usr/proxy_local/profile.json") as json_file:
                    json_data = json.load(json_file)
                    
                    # Now go and set each value.  If the value is already set on the client, do nothing.
                    # If it is not already set. modify the client and set the dirty bit so we know to restart
                    for key in profile:
                        if re.match("^json.", key):
                            log("PROCESSING JSON KEY : " +str(key))

                            jkey = key.split("json.")
                            new_value = profile[key]
                            try:
                                org_value = json_data["dpr"][tag][key]
                            except Exception:
                                org_value = "NONE"
                                # hopefully you knew what you were doing and the filed is not in the file
                                log("ADDING JSON FIELD : " +str(jkey[1])+ " with value " +str(new_value))
                    
                            if not jkey[1] in json_data["dpr"][tag] or json_data["dpr"][tag][jkey[1]] != new_value:
                                if getOpt('VERBOSE'):
                                    log('DEBUG', "Modifying client JSON config value for " + jkey[1] + " from " + str(org_value) + " to " + str(new_value))
                                json_data["dpr"][tag][jkey[1]] = new_value
                                self.configChanged = 1
                    
                            if self.configChanged:
                                self.shell.run("sudo chmod 777 /usr/proxy_local/profile.json")
                                with open('/usr/proxy_local/profile.json', 'w') as outfile:
                                    outfile.write(json.dumps(json_data, indent=4, sort_keys=True))

            except Exception:
                log("UPDATE_CONFIG(): PROFILE.JSON FILE NOT FOUND")

    ##############################################################################################
    # force_proxy_local_port_update(profile)
    # Update the client configuration using a combination of defaults and what is specified in the profile parameter
    # profile is a dictionary
    #
    # Update the client configuration with any values in the profile which have key which starts with "client."
    #
    # e.g. testclient.update({client.zorcEnabled : false, client.n : 5,  bandwidth : 30000})
    # This would set zorcEnabled to false and n to 5 but do nothing with the bandwidth parameter
    #
    # If a value is NOT specified in the dictionary, the value will be set from the defaults
    ##############################################################################################
    def force_proxy_local_port_update(self, key, new_value, oldcfg=0):

        if re.match("^client.", key) or (oldcfg and re.match("^json.", key)):
            original_value = getKey(self.currentClientConfig, key, "")
        
            if getOpt('VERBOSE'):
                log('DEBUG', "Modifying client config value for " + key + " from " + str(original_value) + " to " + str(new_value))
                    
            # if we select oldcfg that means modify all via proxy_local or ONLY the inclusions listed all else in json
            cmd =  'sed -i "s/[ \t]*' + key + '[ \t]*=.*/' + key + ' = ' + str(new_value) + '/" '  + self.client_path + 'proxy_local.conf'
            
            self.shell.run(cmd)
            self.currentClientConfig[key] = new_value
            self.configChanged = 1

    ##############################################################################################
    # force_proxy_local_port_update_json(profile)
    # Update the client configuration using a combination of defaults and what is specified in the profile parameter
    # profile is a dictionary
    #
    # Update the client configuration with any values in the profile which have key which starts with "client."
    #
    # e.g. test_client.update({client.zorcEnabled : false, client.n : 5,  bandwidth : 30000})
    # This would set zorcEnabled to false and n to 5 but do nothing with the bandwidth parameter
    #
    # If a value is NOT specified in the dictionary, the value will be set from the defaults
    ##############################################################################################
    def force_config_update(self, key, new_value, oldcfg=0, tag="default"):

        # if we select oldcfg that means modify all via proxy_local or ONLY the inclusions listed all else in json
        if oldcfg or ("serverAddress" in key or "proxyPort" in key or "nonDprProxyPort" in key or "networktype_key" in key or "networktype" in key):

            if re.match("^client.", key) or (oldcfg and re.match("^json.", key)):
                original_value = getKey(self.currentClientConfig, key, "")
                
                if getOpt('VERBOSE'):
                    log('DEBUG', "Modifying client config value for " + key + " from " + str(original_value) + " to " + str(new_value))
                    
                # if we select oldcfg that means modify all via proxy_local or ONLY the inclusions listed all else in json
                cmd =  'sed -i "s/[ \t]*' + key + '[ \t]*=.*/' + key + ' = ' + str(new_value) + '/" '  + self.client_path + 'proxy_local.conf'
            
                self.shell.run(cmd)
                self.currentClientConfig[key] = new_value
                self.configChanged = 1

        else:
            try:
                with open("/usr/proxy_local/profile.json") as json_file:
                    json_data = json.load(json_file)

                    if re.match("^json.", key):
                        log("PROCESSING JSON KEY : " +str(key))

                        jkey = key.split("json.")
                        new_value = profile[key]
                        try:
                            org_value = json_data["dpr"][tag][key]
                        except Exception:
                            org_value = "NONE"

                        # hopefully you knew what you were doing and the filed is not in the file
                        log("ADDING JSON FIELD : " +str(key)+ " with value " +str(new_value))

                        if not key in json_data["dpr"][tag] or json_data["dpr"]["default"][key] != new_value:
                            if getOpt('VERBOSE'):
                                log('DEBUG', "Modifying client config value for " + key + " from " + str(org_value) + " to " + str(new_value))
                            json_data["dpr"][tag][key] = new_value
                            self.configChanged = 1

                        if self.configChanged:
                            with open('/usr/proxy_local/profile.json', 'w') as outfile:
                                outfile.write(json.dumps(json_data, indent=4, sort_keys=True))

            except Exception:
                log("FORCE_CONFIG_UPDATE(): PROFILE.JSON FILE NOT FOUND")

    ##############################################################################################
    # add_new_config(profile)
    # Update the client configuration using a combination of defaults and what is specified in the profile parameter
    # profile is a dictionary
    #
    # Update the client configuration with any values in the profile which have key which starts with "client."
    #
    # e.g. test_client.update({client.zorcEnabled : false, client.n : 5,  bandwidth : 30000})
    # This would set zorcEnabled to false and n to 5 but do nothing with the bandwidth parameter
    #
    # If a value is NOT specified in the dictionary, the value will be set from the defaults
    ##############################################################################################
    def add_new_config(self, key, new_value, oldcfg=0, tag="default"):

        # if we select oldcfg that means modify all via proxy_local or ONLY the inclusions listed all else in json
        if oldcfg or ("serverAddress" in key or "proxyPort" in key or "nonDprProxyPort" in key or "networktype_key" in key or "networktype" in key):
            original_value = getKey(self.currentClientConfig, key, "")
            if original_value != "":
                if getOpt('VERBOSE'):
                    log("CODE ERROR: " +str(key)+ " with value " +str(original_value)+ " exists, please use update or force_proxy_local")
            else:
                if getOpt('VERBOSE'):
                    log('DEBUG', "ADDING client config value for " + key + " with value " + str(new_value))
                    
                cmd = 'sed -i -e \'$a ' +key+ ' = ' +new_value+ '\' /'  + self.client_path + 'proxy_local.conf'
                self.shell.run(cmd)
                self.currentClientConfig[key] = new_value
                log("KEYED : " +str(self.currentClientConfig[key]))
                self.configChanged = 1
        else:
            try:
                with open("/usr/proxy_local/profile.json") as json_file:
                    json_data = json.load(json_file)

                    if re.match("^json.", key):
                        log("PROCESSING JSON KEY : " +str(key))

                        jkey = key.split("json.")
                        new_value = profile[key]
                        try:
                            org_value = json_data["dpr"]["tag"][key]
                        except Exception:
                            org_value = "NONE"

                        # hopefully you knew what you were doing and the filed is not in the file
                        log("ADDING JSON FIELD : " +str(key)+ " with value " +str(new_value))

                        if not key in json_data["dpr"][tag] or json_data["dpr"][tag][key] != new_value:
                            if getOpt('VERBOSE'):
                                log('DEBUG', "Modifying client config value for " + key + " from " + str(org_value) + " to " + str(new_value))
                            json_data["dpr"][tag][key] = new_value
                            self.configChanged = 1

                        if self.configChanged:
                            with open('/usr/proxy_local/profile.json', 'w') as outfile:
                                outfile.write(json.dumps(json_data, indent=4, sort_keys=True))

            except Exception:
                log("ADD_NEW_CONFIG(): PROFILE.JSON FILE NOT FOUND")

    ##############################################################################################
    # remove_config(profile)
    # Update the client configuration using a combination of defaults and what is specified in the profile parameter
    # profile is a dictionary
    #
    # Update the client configuration with any values in the profile which have key which starts with "client."
    #
    # e.g. test_client.update({client.zorcEnabled : false, client.n : 5,  bandwidth : 30000})
    # This would set zorcEnabled to false and n to 5 but do nothing with the bandwidth parameter
    #
    # If a value is NOT specified in the dictionary, the value will be set from the defaults
    ##############################################################################################
    def remove_config(self, key, oldcfg=0, tag="default"):

        # if we select oldstyle that means modify all via proxy_local or ONLY the inclusions listed all else in json
        if oldcfg or ("serverAddress" in key or "proxyPort" in key or "nonDprProxyPort" in key or "networktype_key" in key or "networktype" in key):
            cmd = "sudo sed -i '/zorcVersion/d' " +self.client_path+ "proxy_local.conf"

            log("REMOVING : " +str(cmd))
            #        cmd = "sed -i '\'s\/' +key+ '\' = ' +new_value+ '\' /'  + self.client_path + 'proxy_local.conf'
            self.shell.run(cmd)
            #        self.currentClientConfig[key] = new_value
            self.configChanged = 1
        else:
            try:
                with open("/usr/proxy_local/profile.json") as json_file:
                    json_data = json.load(json_file)

                    if re.match("^json.", key):
                        log("PROCESSING JSON KEY : " +str(key))

                        jkey = key.split("json.")

                        # hopefully you knew what you were doing and the filed is not in the file
                        log("DELETING JSON FIELD : " +str(key))

                        if not key in json_data["dpr"][tag]:
                            if getOpt('VERBOSE'):
                                log('DEBUG', "JSON Key: " +str(key)+ " NOT FOUND")
                        else:
                            del json_data["dpr"][tag][key]
                            self.configChanged = 1

                        if self.configChanged:
                            with open('/usr/proxy_local/profile.json', 'w') as outfile:
                                outfile.write(json.dumps(json_data, indent=4, sort_keys=True))

            except Exception:
                log("REMOVE_CONFIG(): PROFILE.JSON FILE NOT FOUND")

    ##############################################################################################
    # get_config(key="")
    # Return the value for the specified key from client proxy_local.conf
    # If the value only contains 0-9, an int will be returned. Otherwise a string will be returned
    # If the key parameter is not supplied, then a dictionary of all key/value pairs in the current client config file will be returned.
    ##############################################################################################
    def get_config(self, key="", oldcfg=0, tag="default"):

        if key == '':
            # Get the full config and return it as a dictionary
            client_config = {}
            if oldcfg:
                output = self.shell.run('grep -v \# /usr/proxy_local/proxy_local.conf')
            else:
                proxycfg = self.shell.run('grep -v \# /usr/proxy_local/proxy_local.conf')
                proxyconfig = proxycfg.split('\n')
                for item in proxyconfig:
                    if "serverAddress" in item or "proxyPort" in item or "nonDprProxyPort in item":
                        key_value = item.split('=')
                        if not len(key_value) == 2:
                            continue
                        (key, value) = key_value
                        client_config[key.strip()] = value.strip()
                        
            return(client_config)

        else:

            # if we select oldstyle that means modify all via proxy_local or ONLY the inclusions listed all else in json
            if oldcfg or ("serverAddress" in key or "proxyPort" in key or "nonDprProxyPort" in key or "networktype_key" in key or "networktype" in key):
                # Just return the requested value or bomb out if it does not config
                value = getKey(self.currentClientConfig, key)
                
            else:
                try:
                    with open("/usr/proxy_local/profile.json") as json_file:
                        json_data = json.load(json_file)

                        log("PROCESSING JSON KEY : " +str(key))
                        if re.match("^json.", key):
                            jkey = key.split("json.")
                            jkey = jkey[1]
                        else:
                            jkey = key

                        try:
                            value = json_data["dpr"][tag][jkey]                       
                            if getOpt('VERBOSE'):
                                log('DEBUG', "JSON Key: " +str(jkey)+ " FOUND")

                        except Exception:
                            if getOpt('VERBOSE'):
                                log('DEBUG', "JSON Key: " +str(jkey)+ " NOT FOUND")
                            return ""

                except Exception:
                    log("GET_CONFIG(): PROFILE.JSON FILE NOT FOUND")

            # Return an int or a string
            if re.match('[0-9]+', str(value)):
                # check that we did not test an ip addr
                if re.match('[0-9]+.[0-9]+.[0-9]+.[0-9]+', str(value)):
                    return(str(value))
                return int(value)
            else:
                return(str(value))
                
    ##############################################################################################
    # start()
    # Start the dpr client on the remote system.
    # If it is already running, the attempt to start it will generate an error,
    # but the original instance will continue to run
    ##############################################################################################
    def start(self, verify=1, profile="", teeout=0, ignorefail=0, nobuff=0, newsleep=0):
        client_connected = 0
        log('DEBUG', "Starting DPR Client on " + str(self.control_ip) + ":" + str(self.get_config('proxyPort'))+ " to " +str(self.get_config('serverAddress')))

#        if getOpt('VERBOSE'):
#            for key in sorted(self.currentClientConfig):
#                log("   " + key + "=" + str(self.currentClientConfig[key]))

        if teeout == 1:
            if nobuff:
                # create command with explicit arguments and tee output we need it for examination within the run
                cmd = "cd " + self.client_path + "; sudo stdbuf -oL ./proxy_local --proxyPort " + str(self.get_config('proxyPort')) + " --nonDprProxyPort " +  str(self.currentClientConfig['nonDprProxyPort'])+ " --profile /usr/proxy_local/profile.json &> proxy_loc." +str(self.control_ip)+ "-" +str(self.get_config('proxyPort'))+ ".log"
            else:
                cmd = "cd " + self.client_path + "; sudo ./proxy_local --proxyPort " + str(self.get_config('proxyPort')) + " --nonDprProxyPort " +  str(self.currentClientConfig['nonDprProxyPort'])+ " --profile /usr/proxy_local/profile.json 1> proxy_loc." +str(self.control_ip)+ "-" +str(self.get_config('proxyPort'))+ ".log"

            log("TEEING OUTPUT TO tee proxy_loc." +str(self.control_ip)+ ".log Client path: " +str(self.client_path))
        else:
            # create command with explicit arguments (as requested by Vitaliy.
            cmd = "cd " + self.client_path + "; sudo ./proxy_local --proxyPort " + str(self.get_config('proxyPort')) + " --nonDprProxyPort " + str(self.currentClientConfig['nonDprProxyPort'])+ " --profile /usr/proxy_local/profile.json"

        # Sometimes the connect fails so retry.  We need to look into this
        for i in range(4):

            # there is a possibility of a real connection error to occur
            # that will execute a system exit on the first encounter. We
            # really only want it to happen on the 3'rd try
            if i < 3:
                # launch with error redirect to prevent system exit
                self.proxy_local = self.shell.launch(cmd, 2, redirect_err=1)
                log("ATTEMPTING CONNECT : " + str(i+1))
            else:
                # okay, last three failed if this fails then there is a
                # real issue allow the system exit
                log("ATTEMPTING FINAL CONNECT " +str(i+1))
                self.proxy_local = self.shell.launch(cmd, 2, redirect_err=1)

            if not newsleep:
                sleep(2)
            else:
                sleep(newsleep)

            # isolate the client instance by port to verify it started fields are PID "proxyPort" and "<port in question>"
            test = self.shell.run("ps ax | grep proxy_local | awk '/0:00 .\/proxy_local --proxyPort " +str(self.get_config('proxyPort'))+ "/ {print $1, $6, $7}'")
            log("Client Connect Check : " +str(test))
            if str(self.get_config('proxyPort')) in test:
                client_connected = 1
                break
            
        if self.proxy_local == "" and ignorefail == 0:
            msg = "ERROR: Client would not connect to server after " + str(i+1) + " tries"
            log(msg)
            sys.exit(msg)
        elif self.proxy_local == "":
            msg = "INFORM: Client would not connect to server after " + str(i+1) + " tries"
            log(msg)

        # Record when we started.  The time_running method uses this value
        self.time_started = int(time.time())
        
        if verify == 0:
            self.dpr_session_id = 0
        else:
            # Get the session id from the server (it is the last id displayed in session detail)
            for i in range(3):
                sleep(1)
                output = self.server_shell.run("sudo service dpr_proxyd status detail")
                index = output.rfind("Session ")
                if index == -1:
                    continue
                sleep(1)
            
            if index == -1:
                output = self.shell.stop(self.proxy_local)
                log('DEBUG', "")
                log('DEBUG', output)
                msg = "DPR Client did not connect to server after 6 seconds"
                parms=""
                msg = "ERROR: " + self.__class__.__name__ + "(" + parms + ") " + msg + "\n"
                log(msg)
                sys.exit(msg)
                
            self.dpr_session_id = output[index:].split(',')[0].split(' ')[1]
            
        info = {}
        info['PORT'] = self.get_config('proxyPort')
        info['DPR_SESSION_ID'] = self.dpr_session_id
        self.proxyPort = info['PORT']
        self.sessions.append(info)
        #log('DEBUG', "DPR Client session " + self.dpr_session_id + " launched on " + self.control_ip + ":" + str(self.proxyPort)  + " PID: " + str(self.proxy_local.pid))

        # Now that we have restarted the client, the config now matches what is running
        self.configChanged = 0

        return int(client_connected)

    ##############################################################################################
    # stop()
    # Stop the dpr client on the remote system.
    ##############################################################################################
    def stop(self):
        self.time_started = 0
        if (self.proxy_local != ""):
            pid = self.proxy_local.pid
            output = self.shell.stop(self.proxy_local, self.get_config('proxyPort'))
            self.proxy_local = ""

            log('DEBUG', "Stopped test_client: " + self.control_ip + ":" + str(self.get_config('proxyPort')) + " PID: " + str(pid))
            if getOpt('VERBOSE') and output:
                for line in output.split("\n"):
                    if not "Client Establishing TCP connection" in line:
                        log('DEBUG', line)

            # let the child process clean up with the parent
            os.waitpid(pid, os.WNOHANG)

    ##############################################################################################
    # restart()
    # Stop and then start the dpr client on the remote system
    ##############################################################################################
    def restart(self, verify=1):
        self.stop()
        sleep(1)
        self.start(verify)
        
    ##############################################################################################
    # stop_all()
    # Stop all dpr clients on the remote system
    ##############################################################################################
    def stopall(self):
        self.shell.run("sudo pkill proxy_local")
        

    ##############################################################################################
    # time_running()
    # Return the number of seconds proxy_local has been running
    ##############################################################################################
    def time_running(self):
        elapsed = 0
        if (self.time_started != 0):
            now = int(time.time())
            elapsed = now - self.time_started
            
        return (elapsed)
    
    ##############################################################################################
    # is_running()
    # Return the pid of the client if running else 0
    ##############################################################################################
    def is_running(self):
        pid = 0
        test = self.shell.run("ps -C proxy_local -o pid=")
        if test:
            pid = test

        return (pid)
    
    ##############################################################################################
    # run(command, perror=1, redirect_err=0)
    # Run the specified command on the client system
    # If perror       is 0, the error will not be printed if the command fails
    # If redirect_err is 1, the output will be redirected (>&) to a file and the contents of that file returned as a string
    #    This is need for some commands like curl that seem to use stderr as normal output.
    ##############################################################################################
    def run(self, command, perror=1, redirect_err=0):
        output = self.shell.run(command, perror, redirect_err)
        return output
        

    #########################################################################
    # install(install_file | branch)
    # Installrelease.proxy_local.tar.gz file on the client machine
    #
    # If install_file contains "release.proxy_local.tar.gz" it is assumed to be a full or relative path to the file
    #
    # Otherwise install_file is assumed to be a branch.  GITBASE env variable must be set (like /projects or ~/projects)
    # and the install file must exist at $GITBASE/qfactor/httpProxyNC/<branch>
    #########################################################################
    def install(self, build, os="ubuntu"):

        # Get the build they want
        tarfile      = "release.proxy_local.tar.gz"
        if os == "centos":
            tarfile_path = "proxy/client/centos_x86_64/"
        else:
            tarfile_path = "proxy/client/ubuntu_x86_64/"

        install_file = utility.utilities.getbuild(build, tarfile_path + tarfile)
        
        # Stop all instances of the client on that system
        self.stopall()

        # Transfer the tar file to the home directory on that system
        log('DEBUG', "Installing " + install_file + " on DPR Client " + self.control_ip)
        self.shell.put_file(install_file)

        # Untar it
        self.shell.run("sudo rm -rf proxy_local")
        self.shell.run("tar -xzf " + tarfile)
        self.shell.run("sudo rm -rf /usr/proxy_local")
        self.shell.run("sudo mv proxy_local /usr")
        self.shell.run("sudo cp /usr/proxy_local/proxy_local.conf /usr/proxy_local/default.proxy_local.conf")
        self.shell.run("if [ -f /usr/proxy_local/profile.json ]; then sudo cp /usr/proxy_local/profile.json /usr/proxy_local/default.profile.json; fi")

    #########################################################################
    # clear_netem()
    # Clear any network impairments on all interfaces on the target machine
    #########################################################################
    def clear_netem(self):
        eths = self.shell.run('tc qdisc | grep qdisc | cut -f 5 -d " "')
        eths = shlex.split(eths, "/n")
        eths.sort()
        log('DEBUG', "Clearing netem on interfaces on client " + self.control_ip)
        for eth in eths:
            try:
                self.shell.run("tc qdisc del dev " + eth + " " +self.user, 0)
            except:
                pass

