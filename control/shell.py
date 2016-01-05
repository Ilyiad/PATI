#!/usr/bin/python

#
# Malone Corp Confidential
#
# Copyright 2016, Malone Corp, All Rights Reserved.
#
from utility import *
from .shell import *

import re
import shlex
import os
import sys
import pxssh
import getpass
import atexit
import inspect
from time import sleep
from subprocess import Popen, PIPE, call

# ################################################################################################
# 
# CLASS: shell
#
# AUTHOR: Dan Malone
#
# CREATED: 01/05/2016
#
# DESCRIPTION:
#
# This class is used to invoke shell based commands on a local or remote system. 
# The constructor takes two arguments, ip and user. If [ ip ] is "local", then commands will be run 
# locally. If [ ip ] is an ip address, the commands will be run on the remote system as the specified 
# user [ user ].
#
# There are two modes of operation, run to completion and run as a thread:
#
# The "run" method will run the specified command, wait for completion, and return the output.
#
# The "launch" method will run the specified command in a thread and return, not waiting for completion,
# launch returns a stream. This stream is then used to get the pid of the remote process or to stop the 
# remote process. It is possible to launch multiple programs concurrently with the same shell object as 
# long as the caller keeps track of the respective returned stream. After a process is launched it is 
# also possible to call the run method while the launched process is still running
#
# If the script crashes or ctrl-c, all the remote programs will be terminated
#
# Usage Examples:
#
# localsys = shell("local", "")
# remotesys = shell("172.16.0.33", "root")
# day = localsys.run("date | cut -f 1")
# remote_day = remotesys.run("date | cut -f 1")
# tcpdump = remotesys.launch("tcpdump -i any port 7077 -w <named>.pcap)
# pid = remotesys.pid(tcpdump)    # This returns the pid of tcpdump on the remote system (if it is still running), not the local ssh. 
# remotesys.stop(tcpdump)
# remotesys.getfile("<named>.pcap")
#
# #################################################################################################
class shell:

    # #############################################################################################
    # constructor(ip, user)
    # If ip is "local", user may be omitted or ""
    # #############################################################################################
    def __init__(self, ip, user="root"):
        self.launched_cmds = {}
        self.ip = ip
        self.user = user
        if ip == "local" or ip == "127.0.0.1" or ip == "localhost":
            self.local=1
        else:
            self.local=0
            
    ##############################################################################################
    # run(command)
    # Run a command locally or remotely and wait for completion. NOTE: For remote accesses this can
    # ONLY be used if the remote is set up for passwordless SSH connections.
    #
    # If perror       is 0, the error will not be printed if the command fails
    # If redirect_err is 1, the output will be redirected (>2) and that stderr will be appended to the output
    #    This is need for some commands like curl that seem to use stderr as normal output.
    ##############################################################################################
    def run(self, cmd, perror=1, redirect_err=0, decode=1, pcommand=1):

        if redirect_err:
            # Make the err be part of the output
            cmd = cmd
            
        if self.local:
            # Run it locallyinport             if getOpt('VERBOSE') and pcommand:
                log(cmd)
                
            stream = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        else:
            if pcommand:
                if getOpt('VERBOSE'):
                    log('ssh ' + self.user + '@'+ self.ip + " "+ cmd)

            if self.user == "root":
                stream = Popen(['ssh', self.user +'@' + self.ip, cmd], stdin=PIPE, stdout=PIPE, stderr=PIPE)
            else:
                # sadly, as non-root certain commands have certain complaints if not handled correctly.. neeed to do this better
                if "grep" in cmd or "service" in cmd or "sed" in cmd or "ps" in cmd or "pkill" in cmd or ("ps -e" in cmd and "cd" in cmd):
                    newcmd = "sudo " +cmd
                elif "cd" in cmd or "bash" in cmd or "curl" in cmd or "ls" in cmd or ("if" in cmd and "tc" in cmd) or "if" in cmd or "exit" in cmd or "tcpdump" in cmd:
                    newcmd = cmd
                elif "bash" in cmd:
                    newcmd = "sudo -i \"" +cmd+ "\""
                else:
                    newcmd = "sudo " +cmd
                    
                cmd = newcmd
                stream = Popen(['ssh', self.user +'@' + self.ip, cmd], stdin=PIPE, stdout=PIPE, stderr=PIPE)
            
        # Wait for completion (this is a "run", not a "launch")
        stream.wait()
        if decode:
            out = stream.stdout.read().decode('utf-8')
            err = stream.stderr.read().decode('utf-8')
        else:
            out = stream.stdout.read()
            err = stream.stderr.read()

        if redirect_err:
            # Make the err be part of the output
            out = out + err
            err = ""
            
        if err != "" and perror:
            # Ruh roh, print out the error
            if self.local:
                msg=cmd
            else:
                msg = "ssh " + self.user + '@' + self.ip + " " + cmd
            parms=""
            sys.exit("\nERROR: " + self.__class__.__name__ + "(" + parms + ") " + msg +  "    " + err.strip() + "\n")
            return ""
            
        # Return the output of the command
        if decode:
            return out.strip()
        else:
            return out

    ##############################################################################################
    # run_wpasswd(command)
    # Run a command locally or remotely and wait for completion
    # If perror       is 0, the error will not be printed if the command fails
    # If redirect_err is 1, the output will be redirected (>2) and that stderr will be appended to the output
    #    This is need for some commands like curl that seem to use stderr as normal output.
    ##############################################################################################
    def run_wpasswd(self, cmd, perror=1, redirect_err=0, decode=1, pcommand=1):

        if redirect_err:
            # Make the err be part of the output
            cmd = cmd
            
        if self.local:
            # Run it locallyinport             if getOpt('VERBOSE') and pcommand:
                log(cmd)
                
            stream = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        else:
            try:
                s = pxssh.pxssh()
                hostname = raw_input(self.ip)
                username = raw_input(self.user)
                password = raw_input(self.passwd)
                s.login(hostname, username, password)
                s.sendline('uptime')   # run a command
                s.prompt()             # match the prompt
                print(s.before)        # print everything before the prompt.
                s.sendline('ls -l')
                s.prompt()
                print(s.before)
                s.sendline('df')
                s.prompt()
                print(s.before)
                s.logout()
            except pxssh.ExceptionPxssh as e:
                print("pxssh failed on login.")
                print(e)

#            if pcommand:
#                if getOpt('VERBOSE'):
#                    log('ssh ' + self.user + '@'+ self.ip + " "+ cmd)
#
#            if self.user == "root":
#                stream = Popen(['ssh', self.user +'@' + self.ip, cmd], stdin=PIPE, stdout=PIPE, stderr=PIPE)
#            else:
#                # sadly, as non-root certain commands have certain complaints if not handled correctly.. neeed to do this better
#                if "grep" in cmd or "service" in cmd or "sed" in cmd or "ps" in cmd or "pkill" in cmd or ("ps -e" in cmd and "cd" in cmd):
#                    newcmd = "sudo " +cmd
#                elif "cd" in cmd or "bash" in cmd or "curl" in cmd or "ls" in cmd or ("if" in cmd and "tc" in cmd) or "if" in cmd or "exit" in cmd or "tcpdump" in cmd:
#                    newcmd = cmd
#                elif "bash" in cmd:
#                    newcmd = "sudo -i \"" +cmd+ "\""
#                else:
#                    newcmd = "sudo " +cmd
#                    
#                cmd = newcmd
#                stream = Popen(['ssh', self.user +'@' + self.ip, cmd], stdin=PIPE, stdout=PIPE, stderr=PIPE)
#            
#        # Wait for completion (this is a "run", not a "launch")
#        stream.wait()
#        if decode:
#            out = stream.stdout.read().decode('utf-8')
#            err = stream.stderr.read().decode('utf-8')
#        else:
#            out = stream.stdout.read()
#            err = stream.stderr.read()
#
#        if redirect_err:
#            # Make the err be part of the output
#            out = out + err
#            err = ""
#            
#        if err != "" and perror:
#            # Ruh roh, print out the error
#            if self.local:
#                msg=cmd
#            else:
#                msg = "ssh " + self.user + '@' + self.ip + " " + cmd
#            parms=""
#            sys.exit("\nERROR: " + self.__class__.__name__ + "(" + parms + ") " + msg +  "    " + err.strip() + "\n")
#            return ""
#            
#        # Return the output of the command
#        if decode:
#            return out.strip()
#        else:
#            return out
                
    # #############################################################################################
    # launch(command)
    # Run a program locally or remotely and don't wait for completion
    # Return a stream which may be passed to launch.pid(stream) and launch.stop(stream)
    # If no_check is 1, it means launch and return.  Don't check for pid
    # 
    # Change: 02/11/15 - DRML: Need to propagate the redirect_err so if it is set we properly
    #                        pass that through to where it affects the outcome.
    # #############################################################################################
    def launch(self, cmd, no_check=0, no_atexit=0, redirect_err=0):

        if self.local:
            # Run it locally
            stream = Popen(cmd, shell=True, stdin=PIPE, stdout=PIPE, stderr=PIPE)
        else:
            if self.user == "root":
                stream = Popen(['ssh', self.user +'@' + self.ip, cmd], stdin=PIPE, stdout=PIPE, stderr=PIPE)
            else:
                # sadly, as non-root certain commands have certain complaints if not handled correctly.. need to do this better
                if "grep" in cmd or "service" in cmd or "sed" in cmd or "ps" in cmd or "pkill" in cmd or ("ps -e" in cmd and "cd" in cmd):
                    newcmd = "sudo " +cmd
                elif "cd" in cmd or "bash" in cmd or "curl" in cmd or "ls" in cmd or ("if" in cmd and "tc" in cmd) or "if" in cmd or "exit" in cmd:
                    newcmd = cmd
                elif "bash" in cmd:
                    newcmd = "sudo -i \"" +cmd+ "\""
                else:
                    newcmd = "sudo " +cmd
                    
                cmd = newcmd
                stream = Popen(['ssh', self.user +'@' + self.ip, cmd], stdin=PIPE, stdout=PIPE, stderr=PIPE)

        if no_check == 1:
            return stream
        
        # Keep track of the streams that we have launched and the corresponding command
        self.launched_cmds[stream] = cmd

        if no_atexit == 0:
            # If script bombs or ctrl-c's, make sure we kill the local or remote process that got launched
            atexit.register(self.stop, stream)

        # pass redirect_err to pid because it will execute a sys exit on fail and if
        # we allow retries upstream this (redirect_err==1) will prevent exit on first err
        pid = self.pid(stream, redirect_err)
        if pid == "":
            # Sometimes it taks an extra second to launch.  Wait and try again
            sleep(1)
            pid = self.pid(stream)
            if pid == "":
                # Ruh roh, it didn't start
                stream.terminate()
                out = stream.stdout.read().decode('utf-8')
                err = stream.stderr.read().decode('utf-8')
                msg = "ssh " + self.user + '@' + self.ip + " " + cmd + "    " + err.strip() + " - " + out.strip()
                parms=""
                log("ERROR", msg)
                
                if no_check == 2:
                    return ""
                else:
                    sys.exit("\nERROR: " + self.__class__.__name__ + "(" + parms + ") " + msg + "\n")
        else:
            if self.local:
                msg = cmd
            else:
                msg = 'ssh ' + self.user + '@' + self.ip + ' ' + cmd
                
            if getOpt('VERBOSE'):
                log("Launched: " + str(msg))

        return stream
        

    # #############################################################################################
    # pid(stream)
    # Get the pid of the launched program (for remote, the remote program, NOT the local ssh that ran it)
    # In a multi-client environment we have to grep the PID so be careful here
    #
    # Change: 02/11/15 - DRML: Need to propagate the redirect_err so if it is set we properly
    #                        pass that through to where it affects the outcome.
    # #############################################################################################
    def pid(self, stream, pid=0, redirect_err=0):
        cmd = self.launched_cmds[stream]
        if not self.local:
            # cannot assume single stream if the pid is passed then check for the specific pid
            if pid:
                pid = self.run('ps -e o pid,args | grep "' + cmd + '" | grep -v -e grep -e ssh | grep '+ str(pid))
            else:
                # no pid.. run command with redirect_err passed through in case we get rejected
                pid = self.run('ps -e o pid,args | grep "' + cmd + '" | grep -v -e grep -e ssh', redirect_err)
        else:
            # localhost is not ssh and if a cd is used it does not become part of
            # the process instantiation, remove it to get to the launched command
            if "cd" in cmd:
                realcmd = re.match(r'cd .*; (.*)', cmd)
                if realcmd and realcmd.group(1) and " 1>" in realcmd.group(1):
                    temp = realcmd.group(1).split(" 1>")
                    cmd = temp[0]
                elif realcmd and realcmd.group(1):
                    cmd = realcmd.group(1)

            if "stdbuf" in cmd:
                pid = self.run('ps -e o pid,args | grep "' + cmd + '" | grep stdbuf', redirect_err)
            else:
                pid = self.run('ps -e o pid,args | grep "' + cmd + '" | grep -v -e grep -e /bin/sh', redirect_err)

        pid = pid.strip()
        pid = pid.split(' ', 1)[0]
        return pid

    ##############################################################################################
    # stop(stream, proxyport)
    # Stop the remote or local launched program and terminate the Popen stream if it hasn't been stopped already
    # This is ALWAYS called from atexit for cleanup so we have to check it if has already been terminated
    #
    # The final output from the program is returned
    ##############################################################################################
    def stop(self, stream, proxyport=""):
        trace_enter()
        if stream in self.launched_cmds:

            # If atexit called this method, print cleanup message to remind user they should cleanup themselves
            if getOpt('VERBOSE'):
                msg =  "STOPPING: " + self.launched_cmds[stream]
                call_frame = inspect.getouterframes(inspect.currentframe(), 2)
                log("TRACE      : " + self.__class__.__name__ + "." + call_frame[0][3] + "(): " + msg)
                
            if not self.local:
                pid = self.pid(stream, str(proxyport))
                if pid != "":
                    # Using pkill -P kills the process and all of it's children (in case a script was launched which started other programs)
                    self.run("pkill -TERM -P " + pid)

                    # Make sure the kill worked.  But.. check the original PID, we cannot assume
                    # we are in a single instance environment. If not, murder it.. 
                    pid = self.pid(stream, str(proxyport))
                    
                    if pid != "":
                        # Give it a second
                        time.sleep(1)
                        if getOpt('VERBOSE'):                                                                                     
                            log("Unable to pkill " + self.launched_cmds[stream] + "   Trying kill -9") 
                        self.run("sudo pkill -9 -P " + pid)
                        pid = self.pid(stream, str(proxyport))

                    if pid != "":
                        # last ditch effort                                                                                       
                        process = re.match(r'(\w+) .*', self.launched_cmds[stream])
                        if process and process.group(1):
                            self.run("pkill -SIGTERM " +process.group(1))
                        pid = self.pid(stream, str(proxyport))
                        if pid != "":
                            log("ERROR: PID " +str(pid)+ " did NOT stop")
            else:
                # localhost needs special handling
                if proxyport != "":
                    pid = self.pid(stream, str(proxyport))
                    temp = self.run("ps ax | grep " +str(proxyport))
                    pids = pid.split("\n")
                    for elem in pids:
                        if elem != "":
                            self.run("sudo pkill -TERM -P " + elem)
                    pid = self.pid(stream, str(proxyport))
                    temp = self.run("ps ax | grep " +str(proxyport))
                    for elem in pids:
                        if elem != "":
                            self.run("sudo pkill -9 -P " + elem)
            
            stream.terminate()
            output = ""
            if not self.local:
                output = stream.stdout.read().decode('utf-8')
            del self.launched_cmds[stream]
            trace_exit()
            return(output)
        trace_exit()
                           
    # #############################################################################################
    # get_file(file)
    # Retrive a file from the remote system using scp.  The file will be placed in the local directory
    # #############################################################################################
    def get_file(self, file):
        if not self.local:
            
            if getOpt('VERBOSE'):
                log("Retrieving " + self.ip + ":" + file)

            if self.user == "root":
                run=Popen(['scp', 'root@' + self.ip + ":" + file, '.'], stdin=PIPE, stdout=PIPE, stderr=PIPE)
            else:
                run=Popen(['scp', self.user + '@' + self.ip + ":" + file, '.'], stdin=PIPE, stdout=PIPE, stderr=PIPE)
            run.wait()
            
            out = run.stdout.read().decode('utf-8')
            err = run.stderr.read().decode('utf-8')
            if err != "":
                # Ruh roh, print out the error
                msg='scp ' + 'root@' + self.ip + ":" + "." + "     " + err.strip()
                parms=""
                sys.exit("\nERROR: " + self.__class__.__name__ + "(" + parms + ") " + msg + "\n")
                return err
            else:
                return ""

            
    # #############################################################################################
    # put_file(file, dest_path)
    # Send a local file to the remote system using scp.  The file will be places in the specified destination path
    # #############################################################################################
    def put_file(self, local_file, dest_path="."):
        if getOpt('VERBOSE'):
            log("Sending local file " + local_file + " to " + self.ip + ":" + dest_path)

        if not self.local:

            if self.user == "root":
                run=Popen(['scp', local_file, 'root@' + self.ip + ":" + dest_path], stdin=PIPE, stdout=PIPE, stderr=PIPE)
            else:
                run=Popen(['scp', local_file, self.user + '@' + self.ip + ":" + dest_path], stdin=PIPE, stdout=PIPE, stderr=PIPE)

        else:
            try:
                run=Popen(['cp', local_file, dest_path], stdin=PIPE, stdout=PIPE, stderr=PIPE)
            except (RuntimeError, TypeError, NameError):
                print("RuntimeError: " + str(RuntimeError))
                print("TypeError:    " + str(TypeError))
                print("NameError:    " + str(NameError))
                print("ErrorMsg:     " + str(sys.exc_info()[0]))
                input("Press Enter to proceed")
            
        run.wait()
            
        out = run.stdout.read().decode('utf-8')
        err = run.stderr.read().decode('utf-8')

        if self.local and "are the same file" in err:
            err = ""
            
        if err != "":
            # Ruh roh, print out the error
            msg='scp ' + local_file + ' root@' + self.ip + ":" + dest_path + "     " + err.strip()
            parms=""
            sys.exit("\nERROR: " + self.__class__.__name__ + "(" + parms + ") " + msg + "\n")
            return err
        else:
            return ""
        
