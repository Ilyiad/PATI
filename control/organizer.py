#!/usr/bin/python3
from util import utilities
from util.globals import getOpt

import re
import shlex
import os
import sys
import atexit
import inspect
from time import sleep
import xml.etree.ElementTree as etree

class TestComplete:
    """Class for a finished test run to publish its result"""
    
    def __init__(self):

        # File to write results to
        self.results_filename = utilities.snip(sys.argv[0], 0, ".py") + ".results.log"
            
        self.result = "N/A"
        self.elapsed_time = "N/A"
        self.number_passed=0
        self.number_failed=0
        self.number_warning=0
        self.number_skipped=0
        self.total_number_of_tests=0
        self.remark=" "
        self.result_file=""

    def publish(self, results):
        """Publish the result for a test run"""

        self.number_passed = results.test_successes
        self.number_failed = results.test_failures
        self.number_warning = results.test_warnings
        self.total_number_of_tests = results.test_total
        self.result_file = results.report_file
        self.result = results.result
        self.remark = results.remark
        
        if re.search(r"\/+", results.elapsed_time):
            self.elapsed_time = results.elapsed_time
        else:
            elapsed = results.elapsed_time
            match = re.search(r"^([\d\:]+\.*\d{0,2})", elapsed)
            self.elapsed_time = match.group(1)
        
        file = open(self.results_filename, 'w')
        file.write("Result: {0}!,! Elapsed Time: {1}!,! Number Failed: {2}!,! Number Passed: {3}!,! Total Tests: {4}!,! Result Details: {5}!,! Remark: {6}". \
               format(self.result,self.elapsed_time,self.number_failed,self.number_passed,self.total_number_of_tests,self.result_file,self.remark))
        file.close()

class TestBed:
    """Class for handling Test Bed configuration"""
    def __init__(self):

        self.testbed_id = getOpt('TESTBED_ID')
        self.testbed_xml    = getOpt('TESTBED_XML')
    
        # Testbed xml file may be in the home directory
        self.testbed_config_file = os.environ['HOME'] + "/" + self.testbed_xml
        
        # Or it is expected to be in the current directory or be a full path
        if not os.path.isfile(self.testbed_config_file):
            self.testbed_config_file = self.testbed_xml
        
        print("Using testbed config: " + self.testbed_config_file + '  test_bed=<"' + str(self.testbed_id) + '">')

    def get_config(self):
        """Returns the xml tree structure"""
        tree = etree.parse(self.testbed_config_file)
        root = tree.getroot()
        testbed = root.find(".//test_bed[@id='"+ str(self.testbed_id) +"']")
        return (testbed)
