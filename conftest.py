#!/usr/local/bin/python3.5

#
# Copyright 2016, Dan Malone, All rights reserved
#
import util.globals
import testlink

#########################################################################################
#
# MODULE     : conftest.py()
#
# DESCRIPTION: This module contains methods specific to running py.test and includes preparsing the 
#              command line, setting up the test, a stub for test reporting (currently has Testlink 
#              hook) and file checking as the test run traverses.
#
# AUTHOR     : Dan Malone
#
# CREATED    : 01/03/2016
#
#########################################################################################


#########################################################################################
#
# METHOD: pytest_cmdline_preparse(config, args)
#
# DESCRIPTION: This method is called automatically by pytest before executing tests but after 
#              globals.py has been imported globals.py is our local module which parses through 
#              the command line args for any parameters of the form KEY=VALUE It will take a command 
#              line argument like DEBUG=1 and put it into the "global options" dictionary Tests or 
#              Objects can then access those options via: getOpt('DEBUG') for example.
#
#              NOTE: While parsing now we have to remove those arguments from the command line argument 
#                    list or else pytest will throw a fit
#
#########################################################################################
def pytest_cmdline_preparse(config, args):
    """pytest_cmdline_preparse(config, args) - This method is called automatically by pytest before executing tests but after
              globals.py has been imported globals.py is our local module which parses through
              the command line args for any parameters of the form KEY=VALUE.
              """

    # Build up argv which will contain only the "pytest acceptable" args
    argv = []
    for arg in args:
      
        if not '=' in arg:
            # This is not one of our args.  All of our args are of the form KEY=VALUE
            argv.append(arg)
            continue
        
    # Update the args which pytest will continue to parse
    args[:] = argv


#########################################################################################
#
# METHOD: pytest_runtest_setup(item)
#
# DESCRIPTION: This method is a hook function called by py.test before each test run. It basically
#              sets up the log data for the run into a nice pretty header.
#
#########################################################################################
def pytest_runtest_setup(item):
    """pytest_runtest_setup(item) - This method is a hook function called by py.test before each test run. It basically
              sets up the log data for the run into a nice pretty header. 
              """

    # Get the name of the test
    test_function = item.name

    # Get the description of the test
    test_description = item.function.__doc__
    
    # Get the name of the path/file.py that contains the script
    script = item.fspath

    # Store info about this current testcase in globals
    util.globals.setOpt("TESTCASE_NAME", str(test_function))
    util.globals.setOpt("TESTCASE_DESC", str(test_description))
    print("")
    util.globals.log("###########################################################################################")
    util.globals.log("# Test Module: " +  util.globals.getOpt("TESTCASE_FILE"))
    util.globals.log("# Test Name:   " +  str(test_function))
    util.globals.log("# Description: " +  str(test_description))
    util.globals.log("###########################################################################################")
    

    # This is an inner method to get all the methods of a class.  Call inspect_class(<class>) to see all of it's methods
    # This function is buried inside of pytest_runtest_setup() because I was using it to examine the availble attributes of "item"
    # It had to be inside of pytest_runtest_setup because you can only have defined hook functions in conftest.py
    # but it appears conftest.py cannot access any modules outside of itself (as far as I know)
    def inspect_class(klass):

        verbose=1

        attrs = dir(klass)
        print("------------------------------------------------------")
        print(str(klass))
        print("")
        if "__doc__" in attrs:
            print(klass.__doc__)


        print("Class:    " + str(klass.Class))
        print("File:     " + str(klass.File))
        print("Function: " + str(klass.Function))
        print("Instance: " + str(klass.Instance))
        print("Item:     " + str(klass.Item))
        print("Module:   " + str(klass.Module))
        print("location: " + str(klass.location))
        print("name:     " + str(klass.name))
        print("function: " + str(klass.function))
        print("fspath:   " + str(klass.fspath))
        print("_getfslineno: " + str(klass._getfslineno()))

        print("------------------------------------------------------")

        for attr in attrs:
            if verbose:
                print(str(attr))
        print("")

    # Inspect the item object
    if 0:
        inspect_class(item)
   
#########################################################################################
#
# METHOD: pytest_runtest_makereport(item, call, __multicall__)
#
# DESCRIPTION: This method is a hook of hooks function called by py.test after each test run. 
#              It basically executes the passed reporting hook and any other exiting hooks (in
#              this case Testlink) for test case reporting. 
#
#########################################################################################
def pytest_runtest_makereport(item, call, __multicall__):
    """pytest_runtest_makereport(item, call, __multicall__) - This method is a hook of hooks 
              function called by py.test after each test run.It basically executes the passed 
              reporting hook and any other exiting hooks (in this case Testlink) for test case reporting. 
              """

    # execute all other hooks to obtain the report object
    rep = __multicall__.execute()

    # ################################
    # TESTLINK Reporting Setup (active by CLI Arg request only)
    # ################################
    tl = testlink.tl_track()
    tl.tl_project    =  util.globals.getOpt('TESTLINK_PROJECT')
    tl.tl_platform   =  util.globals.getOpt('TESTLINK_PLATFORM')
    tl.tl_build      =  util.globals.getOpt('TESTLINK_BUILD')
    tl.tl_testplan   =  util.globals.getOpt('TESTLINK_TESTPLAN')
    tl.tl_testid     =  util.globals.getOpt('TESTLINK_TESTID')

    # we only look at actual failing test calls, not setup/teardown
    if rep.when == "call" and rep.failed:
        tl.tl_teststatus_update("f")        
    elif rep.when == "call":
        tl.tl_teststatus_update("p")
        
    return rep
   
#########################################################################################
#
# METHOD: pytest_collect_file(path, parent)
#
# DESCRIPTION: This method is called everytime a file is encontered by pytest as it traverses 
#              the test directories. 
#
#########################################################################################
def pytest_collect_file(path, parent):
    """pytest_collect_file(path, parent) - This method is called everytime a file is encontered
                by pytest as it traverses the test directories.
                """
   
    # Store info about this current testcase in globals
    util.globals.setOpt("TESTCASE_FILE", str(path))
    util.globals.setLogFileName(1)
    util.globals.log("Entered test module: " + str(path))
