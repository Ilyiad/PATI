#!/usr/bin/python
import os
import sys
import time
import re

#########################################################################################
# globals
#
# This module contains "global" settings which can be used in any part of the infrastructure
# The values of the global keys may come from the defaults in this file, KEY=VALUE argument on the command line, or shell environment variable
#
# Usage:
#   import getOpt from globals
#   getOpt('VERBOSE')
#
# If VERBOSE=1 was passed on the command line, that value will be returned
# Else if the environment variable VERBOSE is set, that value will be returned
# Else if VERBOSE is set here in defaults, that value will be returned
# Else if a default value was passed to GetOpt (e.g. GetOpt('VERBOSE', 0), that value will be returned
# Else "" will be returned
#  
# These are NOT intended to replace values in the testbed file.  They are simply a convient
# place to set test options like VERBOSE, PACKET_CAPTURE, etc.
#
#########################################################################################

#########################################################################################
#
# Module      : constants.py
#
# Author      : Dan Malone
#
# Created     : 06/23/14
#
# Description :
#
#               This is the constants module to allow constant definitions that can be used
#               throught all code modules but have one area for change wetc.
#
###########################################################################################
const_proxy = {'DIRECT':'0', 'DPR_PROXY':'1', 'HTTP_PROXY':'2'}
const_curl_opts = {'CURL-UNSECURE':'-k', 'CURL-COMPRESS':'--compressed'}

########################################
# Universal Test Option Defaults
########################################
GLOBALS = {}
GLOBALS['TEST_LOOP_COUNT'] = 0   ;  # Set to the number of test loops (with corresponding profile) to run.  0 for all.  For a sanity test, run just 1 loop
GLOBALS['PACKET_CAPTURE']  = 0   ;  # Set to 1 to perform packet capture on client and server systems
GLOBALS['DEBUG']           = 0   ;  # Set to 1 to make the test go quicker to debug the script
GLOBALS['VERBOSE']         = 0   ;  # Set to 1 to print out more information for debugging
GLOBALS['NOPROMPT']        = 0   ;  # Set to 1 to not be prompted for verification within utility scripts (like gentestbed)
GLOBALS['TRACE']           = 0   ;  # Set to 1 to print all trace_enter() and trace_exit() statements
GLOBALS['NO_CLEANUP']      = 0   ;  # Set to 1 to not cleanup files like retrieved log files, etc.
GLOBALS['PAUSE']           = 0   ;  # Set to 1 to pause at convient points in the script (like when netem has been setup and client started)
GLOBALS['PROFILES']        = ""  ;  # Set to the name of profiles to run.  Leave as "" to run all profiles
GLOBALS['TESTLINK']        = 0   ;  # Set to 1 to activate Testlink tracking
GLOBALS['DPRSERV']         = ""  ;  # Set to the DPR Server Of Choice
GLOBALS['CDNSERV']         = ""  ;  # Set to the CDN Content Server Of Choice
GLOBALS['SENDMAIL']        = 0   ;  # Set to 1 if you want test reults for any run sent

GLOBALS['NO_OUTPUT']       = 0   ;  # Set to 1 to disable the log method from printing to stdou.  It will still be logged to the log file. print() statements will still go to stdout
GLOBALS['ANYOPT']          = 0   ;  # Set to 1 to allow any options. On command line or shell script have it be the first option. In python, instead just set the variable:  anyopt = 1 before import GLOBALS

# INSTALL
# A Client and Server install may be performed by running a test with the command line argurments:  INSTALL=1 BRANCH=PROXY_R1.3
# The Environment variable GITBASE must be set to the project directory (e.g. ~/projects)
#
GLOBALS['INSTALL']         = 0   ;  
GLOBALS['BRANCH']          = ""

GLOBALS['CONFIG_BASE']     = ""
GLOBALS['TESTBED_XML']     = "QSilver_Testbed_Config.xml"
GLOBALS['TESTBED_ID']      = 1
GLOBALS['NETWORK']         = "DEV";  # Set AWS enviornment (DEV, STAGING, PRODUCTION)


# These globals get updated as each testcase is run so tests/reports can access the test case name, description, and the file the test is contained in
GLOBALS['TESTCASE_NAME']   = ""
GLOBALS['TESTCASE_DESC']   = ""
GLOBALS['TESTCASE_FILE']   = "dummy.py"

# ######################
# TESTLINK SERVER
# ######################
os.environ['TESTLINK_API_PYTHON_SERVER_URL'] = "http://172.16.0.86/testlink/lib/api/xmlrpc/v1/xmlrpc.php"
os.environ['TESTLINK_API_PYTHON_DEVKEY'] = "345c8d2c3f94d60976bcd8745ba56f37"

GLOBALS['TESTLINK_TRACK']   = 0
GLOBALS['JENKINS_TRACK']    = 0

GLOBALS['TESTLINK_PROJECT']   = ""
GLOBALS['TESTLINK_PLATFORM']  = ""
GLOBALS['TESTLINK_BUILD']     = ""
GLOBALS['TESTLINK_TESTPLAN']  = ""
GLOBALS['TESTLINK_TESTID']    = ""

# ######################
# summary reuslts
# ######################
SUMMARY_RESULTS = []

# ######################
# Email Recipent lists
# ######################

#QAENG = "dmalone@kwicr.com erussell@kwicr.com"
QAENG = "dmalone@kwicr.com"
COREENG = [""]
CLIENTENG = [""]
DATAPFORMENG = [""]
ALLENG = [""]

# ######################
try:
    anyopt
except:
    anyopt = 1

################################################################
# getOpt(key)
#
# Usage (with VERBOSE as an example)
#   import getOpt from globals
#   value = getOpt('VERBOSE')
#
# The key (in this example, VERBOSE, MUST exists in globals above
# If VERBOSE=1 was passed on the command line, that value will be returned
# Else if the environment variable VERBOSE is set, that value will be returned
# Else if VERBOSE is set here in globals, that value will be returned
# Else an error will occur.
# The reason an optional default value is not supported is because it is important that
#   all options are documented in the globals section above otherwise no one will know what options are available
#   other than grepping the code (and even then, there will be no explantion of the option)
################################################################
def getOpt(key):
    
    try:
        value = str(GLOBALS[key])
    except:
        if anyopt:
            value = ""
        else:
            msg = 'getOpt("' + key + '"): ' + key + ' is not a supported option. It must be added to the GLOBALS dictionary in globals.py'
            log(msg)
            sys.exit(msg)

    # Be nice and return a string or number
    if re.match('[0-9]+$', value):
        # Contains only digits, treat like an int
        value = int(value)
        
    elif re.match('[0-9]+.[0-9]+$', value):
        # Contains only digts and one '.' in the middle.  Treat like a float
        value = float(value)
        
    return value
    
################################################################
# setOpt(key, value)
#
# This is used to set an option programattically.
# It is in general frowned upon as it will overwrite anything in GLOBALS, on the command line, or in the environment variables
# However there are some occassions where it is helpful, such as turning on NO_CLEANUP when a server or client issue is detected
# The key must exist in the GLOBALS dictionary or else an error occurs (see getOpt description for why this is a good rule to enforce)
################################################################
def setOpt(key, value):
    if not key in GLOBALS:
        msg = 'setOpt("' + key + '"): ' + key + ' is not a supported option.  It must be added to the GLOBALS dictionary in globals.py'
        log(msg)
        sys.exit(msg)

    GLOBALS[key] = value
    
################################################################
# getKey(dictionary, key, default="")
#
# This is used to retrieve a value from a dictionary and if the key does not exist,
# return the specified default value (or "" if default is not specified)
################################################################
def getKey(dictionary, key, default=""):
    if not key in dictionary:
        return default

    value = str(dictionary[key])

    # Be nice and return a string or number
    if re.match('^-*[0-9]+$', value):
        # Contains only digits, treat like an int
        value = int(value)
        
    elif re.match('^-*[0-9]+.[0-9]+$', value):
        # Contains only digts and one '.' in the middle.  Treat like a float
        value = float(value)
        
    return value

################################################################
# getMatchingKeys(dictionary, pattern)
#
# This is used to retrieve the keys from a dictionary which match a pattern
# Example:
# getMatchinKeys(mydict, "^client\.")
# returns all keys that start with "client."
################################################################
def getMatchingKeys(dictionary, pattern):

    matching = []
    for key in dictionary.keys():
        if re.search(pattern, key):
            matching.append(key)
        
    return(matching)

def add(arg1, arg2):
    """Add arg1 and arg2 and return the result"""
    result = arg1 + arg2
    return(result)

def setLogFileName(delete=1, fileName = 'dummy.log'):
    global logFileName

    if fileName == 'dummy.log':
        # Change "script.py" to "script.log"
        script = getOpt("TESTCASE_FILE")
        base = snip(script, 0, ".py")
        logFileName = base + ".log"
    else:
        logFileName = fileName
    if delete:
        try:
            os.remove(logFileName)
        except:
            log("Could not remove log file " + logFileName)
        else:
            log("Cleared log file:    " + logFileName)
            
    
def log(parm1="", parm2=""):
    """
    ################################################################
    # log(level, message)
    # log(message)
    #
    # This is used to log a message at a specified level to both stdout and the log file
    # Level may be "ERROR", "INFO", "DEBUG", "TRACE", "SHELL", "ALWAYS"
    # If ther first parameter is not one of the valid levels, the first parameter is assumed to be the log message and will be logged at level "INFO"
    ################################################################
    """

    global logFileName

    if logFileName == "":
        setLogFileName(0)
        
    if parm1 in ["ERROR", "INFO", "DEBUG", "TRACE", "SHELL", "ALWAYS"]:
        level = parm1
        string = parm2
    elif parm2 in ["ERROR", "INFO", "DEBUG", "TRACE", "SHELL", "ALWAYS"]:
        level = parm1
        string = parm2
    else:
        level="INFO"
        string = parm1
    
    now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
    msg = now
    if not level == 'ALWAYS':
        msg = msg + " " + level
    msg = msg + " " + string
    fd = open(logFileName, 'a')
    fd.write(msg + "\n")
    fd.close()

    if not getOpt('NO_OUTPUT') or level == 'ALWAYS':
        print(msg)

############################################################
# snip(string, start_str, end_str)
# Seraches the string and returns everything from the end of start_str to the beginning of end_str
# If start_str does not exist in string, returns ""
# If end_str   does not exist in string, Returns everything from the end of start_str to the end of the string
# If start_str is 0, retruns everything from the start of the string to the beginning of end_str
# If end_str is 0 or omitted, returns everything from the end of start_str to the end of the string
#
# The returned string is stripped of beginning and ending whitespace
############################################################
def snip(string, start_str, end_str=0):

    if isinstance(start_str, int):
        start_index = 0
    else:
        start_index = string.find(start_str)
        if start_index == -1:
            return("")
        start_index += len(start_str)
        
    if isinstance(end_str, int):
        return(string[start_index:].strip())
    else:
        end_index = string.find(end_str)

    snipped = string[start_index : end_index].strip()

    return(snipped)

#############################################################
# Debug functions to print when we enter and leave code
#############################################################
import traceback
def print_stack():
    stack = traceback.extract_stack()

    print("")
    print(str(stack))
    print("")
    for i in range(len(stack)):
        print("")
        for j in range(len(stack[i])):
            print("stack[" + str(i) + "][" + str(j) + "] = " + str(stack[i][j]))
    print("")

def get_stack_frame(level=0):
    stack = traceback.extract_stack()
    return(stack[len(stack) - (level + 2)])
    
def who_am_i(level=0):
    filename, codeline, funcname, text = get_stack_frame(1)
    return funcname

def trace_enter(msg=""):
    if getOpt('TRACE'):
        filename, codeline, funcname, text = get_stack_frame(1)
        string = "TRACE ENTER: " + filename.split('/')[-1] + ":" + funcname + "()"
        if not msg == "":
            string = string + " : " + msg
        print(string)
    
def trace_exit(msg=""):
    if getOpt('TRACE'):
        filename, codeline, funcname, text = get_stack_frame(1)
        string = "TRACE EXIT:  " + filename.split('/')[-1] + ":" + funcname + "()"
        if not msg == "":
            string = string + " : " + msg
        print(string)
    
def inspect_class(klass):
    attrs = dir(klass)
    print("------------------------------------------------------")
    print(str(klass))
    print("")
    if "__doc__" in attrs:
        print(klass.__doc__)
    print("------------------------------------------------------")
    for attr in attrs:
        if not "__" in attr:
            print(str(attr))
    print("")
    
def globals_usage(msg):
    print("")
    print("Availble key=value pairs and the defaults are:")
    print("")
    for key in GLOBALS.keys():
        print("   " + key + "=" + str(GLOBALS[key]))
    print("")
    msg = msg
    log(msg)
    sys.exit(msg)
          
################################################################
# Excecute the initialization if we have not already
################################################################
try:
    globals_initialized += 1
except:

    # Place to remember the log file name
    global logFileName
    logFileName = ""

    # Get the command line arguments which are of the form key=value
    args = {}
    
    if "-anyopt" in sys.argv:
        anyopt = 1

    argv = []
    for arg in sys.argv[1:]:
        if arg == "-anyopt":
            continue
        
        if not '=' in arg:
            # This is not one of our args.  All of our args are of the form KEY=VALUE
            argv.append(arg)
            continue
        
        arg = arg.split('=')
        key = arg[0]
        value = arg[1]
        
        if anyopt == 0 and not arg[0] in GLOBALS:
            globals_usage("You specified " + key + "=" + value + " on the command line, howerver '" + key + "' is not a supported option key.  Option keys must be added to the GLOBALS dictionary in globals.py")
        args[arg[0]] = arg[1]

        if anyopt:
            GLOBALS[key] = args[key]
        
    # See if they have command line or environment variable overrides for the GLOBALS
    for key in GLOBALS.keys():
        if key in args:
            GLOBALS[key] = args[key]
            print("Using command line override option " + key + "=" + GLOBALS[key])
        elif key in os.environ:
            GLOBALS[key] = os.environ[key]
            print("Using environment  override option " + key + "=" + GLOBALS[key])

    # Add a couple more for convience
    pythonPath = os.environ['PYTHONPATH']
    if pythonPath[-1] != '/':
        pythonPath += '/'
    GLOBALS['TEST_BASE'] =  pythonPath + 'tests/'

    # Replace the sys.argv with our KEY=VALUE args removed
    # erussell: THIS CAUSES parameters to be lost when using argparser
    # I am not sure why I wanted to replace it anyway
    #sys.argv = argv

    # Don't come in here again
    globals_initialized = 1
    


