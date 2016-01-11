#!/usr/bin/python3
from util.globals import *
from testlink import *

import re
import shlex
import os
import sys
import atexit
import inspect

from time import sleep

# Testlink library imports
from testlink.testlink import TestLink
from testlink.testlinkhelper import TestLinkHelper
from testlink.testlinkapi import *
from testlink.testlinkapigeneric import *
from testlink.testlinkerrors import *
#from testlinkhelper import TestLinkHelper
#from testlinkapi import *
#from testlinkapigeneric import *
#from testlinkerrors import *

# ##################################################################################################
# class tltrack
#
# This class manages the testlink tracking for a test in a test suite under automation
#
# Usage:
#
# tltrack = = tltrack.tltrack()
#
# report.expected       Set to a dictionary containing a key/value pairs of expected values
# report.actual         Set to a dictionary containing a key/value pairs of actual values
# report.compar4e()
# #################################################################################################

class tl_track:

    # ##################################################################################################
    # Constructor
    # ##################################################################################################
    def __init__(self):
        self.script = snip(sys.argv[0], 0, ".py")
        self.testcase_file = getOpt('TESTCASE_FILE')
        self.testcase_name = getOpt('TESTCASE_NAME')
        self.testcase_desc = getOpt('TESTCASE_DESC')
        self.tl_track      = getOpt('TESTLINK')
        self.tl_project    = ""
        self.tl_testplan   = ""
        self.tl_platform   = ""
        self.tl_build      = ""
        self.tl_testid     = 0
        
    ###################################################################################################
    # send test results to testlink 
    ###################################################################################################
    def tl_teststatus_update(self, teststatus):

        status = 1

        if self.tl_track:
            log("TESTLINK: Tracking Test Metrics - test = " +teststatus)
            tl_helper = TestLinkHelper()
            tls = tl_helper.connect(TestlinkAPIClient)
            tpid = tls.getTestPlanByName(self.tl_project, self.tl_testplan)
            tl_testplanid = tpid[0]['id']
                                                
            # Check is test plan is open and active
            if tpid[0]['is_open'] != '1' or tpid[0]['active'] != '1':
                status = 0
                log("ERROR : Testlink Result Report TestPlan \"" +TL_TEST_PLAN+ "\" is not open or active")
                
            temp = tls.reportTCResult(self.tl_testid, tl_testplanid, self.tl_build, teststatus, "", platformname=self.tl_platform)
            log("TESTLINK: " +str(temp))
        else:
            if getOpt('JENKINS_TRACK'):
                log("JENKINS: Tracking Test Metrics - test = " +teststatus)
                local_shell = shell("local")
                datetime = local_shell.run("date +\"%m-%d-%Y-%T\"", 0)
                temp = local_shell.run("ls -ls ~/runfiles")
                #log("DIR : " +temp)
                log("Tracking Test Metrics To: ~/runfiles/" + str(self.tl_build) + "_test_results.csv")
                resfile = os.path.expanduser("~/runfiles/") + self.tl_build + "_test_results.csv"
                try:
                    file = open(resfile, 'a+')
                except IOError:
                    file = open(resfile, 'w+')

                if teststatus == "p": 
                    file.write("PASS, " +datetime+ ", " +self.tl_build+ ", " +self.testcase_name+ "\n")
                else:
                    file.write("FAIL, " +datetime+ ", " +self.tl_build+ ", " +self.testcase_name+ "\n")
                
                file.close()

        return status
    
    def tl_verify_build(self, uri="", key="", project="", testplan="", build=""):

        tl_helper = TestLinkHelper()
        tls = tl_helper.connect(TestlinkAPIClient)
        tpid = tls.getTestPlanByName(project, testplan)
        tl_testplanid = tpid[0]['id']

        testit = tls.getLatestBuildForTestPlan(tl_testplanid)
        log("BUILD " +str(testit['name']))

        if build != "":
            if build not in str(testit['name']):
                log("CREATING TESTLINK BUILD")

        return str(testit['name'])
