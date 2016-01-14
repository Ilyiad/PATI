#!/usr/bin/python3
from control import organizer
from util.globals import getOpt
from control.test_server import *
from control.test_client_linux import *
from control.netem import *

# A dictionary is returned of the form:
# {
#     'CLIENT'  : <test_client_linux_object>,
#     'SERVER'  : <test_server_object>,
#     'NETEM'   : <netem_object>,
#     'TRANFER' : <transfer_object>,
#     'TESTBED' : <testbed_object>,
#     'REPORT'  : <report_object>
# }
#
################################################################

def testinit(profiles=['']):
    
    # Get the information out of the testbed file
    config_tree = organizer.TestBed()
    testbed_object = config_tree.get_config()

    # Find out what type of client they are using, linux or a device
    client_name = testbed_object.find(".//control_client[@id='" + str(1) + "']/name")
    if client_name == None:
        client_name = getOpt('CLIENT_NAME')
        if client_name == "":
            client_name="Linux"
    
    # Create a Test server object so we can control the server (stop/start/change logging level)
    test_server_object = test_server(testbed_object, 1, 1)

    # Create either a Linux or Device client object
    client_object = None
    client_device_object = None
    if client_name == "Linux":
        # Create a client object so we can control the client (stop/start/change config)
        # Specify that we will use client id 1 and it will attach to server id 1
        # In the case of a device, this "client" will actually be the qtest command server
        client_object = test_client_linux(testbed_object, 1, 1, 1)
    else:
        # If we are running against a device, create a client device object 
        # This object contains the IP of the Command Server and contains method for creating the command files on that IP
        client_device_object = testclient_device(testbed_object, 1, 1, 1)

    # Create a netem object so we can control the netem system
    netem_object = netem.netem(testbed_object, 1, 1)
    
    # See if they are running only some of the profiles
    if profiles != ['']:
        profileNameList = getOpt('PROFILES').split(',')
        if not profileNameList == ['']:
            allProfiles = profiles
            profiles = []
            for profileName in profileNameList:
                added = 0
                for profile in allProfiles:
                    if profile['name'] == profileName:
                        profiles.append(profile)
                        added = 1
                        if not added:
                            msg = profileName + " is not a valid profile name"
                            log(msg)
                            sys.exit(msg)

        log("")
        log("Running profiles:")
        for profile in profiles:
            log(profile['name'])
        log("")

    if getOpt('DEBUG'):
        log("Skipping clearing of netem due to DEBUG == 1")
    else:
        # Clear out any netem cruft on the systems in the testbed
        server_object.clear_netem()
        netem_object.clear_netem()
        if client_name == "Linux":
            client_object.clear_netem()

    if client_name == "Linux":
        log( "TestClient(" + client_object.data_ip + ") ==> Test Server(" + server_object.data_ip + ")")
        # Test the interfaces
        ping_test(client_object, server_object)
    else:
        log("Device Client(" + client_device_object.client_name + ") ==> Test Server(" + server_object.data_ip + ")")

    if getOpt('INSTALL'):
        # Install the server and client software
        oschk = server_object.run("lsb_release -a", perror=0) 
        if getOpt('OS') and getOpt('OS') == "centos" and oschk == "CentOS":
            server_object.install(getOpt('BUILD'), getOpt('OS'))
        else:            
            server_object.install(getOpt('BUILD'))
        log("CLIENT NAME : " +str(client_name))
        if client_name == "Linux":
#        if client_name == "Linux" or client_name=="LINUX":
            client_object.install(getOpt('BUILD'))

        # the way we run tests from py.test this carries
        # for each def test reset it for one and done so
        # we do not reinstall for every test in the run
        setOpt('INSTALL', "0")

    # Start the server if it is not already running
    server_object.start()

    if client_name == "Linux":
        # Create a file transfer object for linux client
        transfer_object = transfer(client_object)
        transfer_device_object = None
        
        # Get the client configuration into a known state
        client_object.set_default_config()
    else:
        # Create a file transfer object for devices
        transfer_device_object = transfer_device(client_device_object, server_object)
        transfer_object = None

    # Set up the report
    run_time = strftime("%Y%m%d_%H%M%S", gmtime())

    report_object = report()

    # Get a shell on the content server
    content_ip = testbed_object.find(".//control_content[@id='"  + str(1) + "']/ip").text
    content_shell = shell(content_ip)

    objects = {}
    objects['CLIENT']        = client_object
    objects['CLIENT_DEVICE'] = client_device_object
    objects['SERVER']        = server_object
    objects['NETEM']         = netem_object
    objects['TRANSFER']      = transfer_object
    objects['TRANSFER_DEVICE']  = transfer_device_object
    objects['TESTBED']       = testbed_object
    objects['REPORT']        = report_object
    objects['PROFILES']      = profiles
    objects['CONTENT']       = content_shell
    
    # Automatically cleanup and generate the report when we exit
    atexit.register(testfinish, objects)
    
    return objects

##########################################################
# testfinish
# This is called via atexit which was setup in testinit
##########################################################
def testfinish(objects):
    trace_enter()
    
    # Turn off debug server logging
    objects['SERVER'].set_logging_level(2)

    # Stop any transfers
    if objects['TRANSFER'] != None:
        objects['TRANSFER'].stop()

    # Stop any transfers on devices
    if objects['TRANSFER_DEVICE'] != None:
        objects['TRANSFER_DEVICE'].stop()

    # Stop the client
    if objects['CLIENT'] != None:
        objects['CLIENT'].stop()
        
        # Reset the client config
        objects['CLIENT'].set_default_config()
        
    # Stop the client devices
    if objects['CLIENT_DEVICE'] != None:
        objects['CLIENT_DEVICE'].stop()
        
        # Reset the client config for devices
        objects['CLIENT_DEVICE'].set_default_config()

    trace_exit()

# ##############################
# DRM - 04/24/15
# 
# testinit_slave() - temp for fairness.. will probably incorp into original
#                        testinstall()
# 
################################
def testinit_slave(client_id=1, server_id=1, netem_id=1, content_id=1):
    
    # Get the information out of the testbed file
    config_tree = organizer.TestBed()
    testbed_object = config_tree.get_config()

    # Find out what type of client they are using, linux or a device
    client_name = testbed_object.find(".//control_client[@id='" + str(client_id) + "']/name")
    if client_name == None:
        client_name = getOpt('CLIENT_NAME')
        if client_name == "":
            client_name="Linux"
    
    # Create a test server object so we can control the server (stop/start/change logging level)
    server_object = test_server(testbed_object, server_id, 1)

    # Create either a Linux or Device client object
    client_object = None
    client_device_object = None
    if client_name == "Linux":
        # Create a client object so we can control the client (stop/start/change config)
        # Specify that we will use client id 1 and it will attach to server id 1
        # In the case of a device, this "client" will actually be the qtest command server
        client_object = test_client_linux(testbed_object, client_id, server_id, 1)
    else:
        # If we are running against a device, create a client device object 
        # This object contains the IP of the Command Server and contains method for creating the command files on that IP
        client_device_object = test_client_device(testbed_object, client_id, server_id, 1)

    # Create a netem object so we can control the netem system
    netem_object = netem.netem(testbed_object, netem_id, 1)
            
    if getOpt('DEBUG'):
        log("Skipping clearing of netem due to DEBUG == 1")
    else:
        # Clear out any netem cruft on the systems in the testbed
        server_object.clear_netem()
        netem_object.clear_netem()
        if client_name == "Linux":
            client_object.clear_netem()
        
    if client_name == "Linux":
        log( "Slave Client(" + client_object.data_ip + ") ==> Test Server(" + server_object.data_ip + ")")
        # Test the interfaces
        ping_test(client_object, server_object)
    else:
        log("Slave Client(" + client_device_object.client_name + ") ==> Test Server(" + server_object.data_ip + ")")

    log("INSTALL STATUS : " +str(getOpt('INSTALL')))
    if getOpt('INSTALL'):
        log("INSTALLING SLAVE !!!!!!!!!!!!")
        # Install the server and client software
        oschk = server_object.run("lsb_release -a", perror=0) 
        if server_id > 1:
            if oschk == "CentOS":
                server_object.install(getOpt('BUILD'), "centos")
            else:            
                server_object.install(getOpt('BUILD'))

        log("CLIENT NAME : " +str(client_name))
        if client_name == "Linux":
            oschk = client_object.run("lsb_release -a", perror=0)
            log("CLIENT TYPE : " +oschk)
            if "CentOS" in oschk:
                client_object.install(getOpt('BUILD'), os="centos")
            else:            
                client_object.install(getOpt('BUILD'))

        # the way we run tests from py.test this carries
        # for each def test reset it for one and done so
        # we do not reinstall for every test in the run
        setOpt('INSTALL', "0")

    # Start the server if it is not already running
    if server_id > 1:
        server_object.start()

    if client_name == "Linux":
        # Create a file transfer object for linux client
        transfer_object = transfer(client_object)
        transfer_device_object = None
        
        # Get the client configuration into a known state
        client_object.set_default_config()
    else:
        # Create a file transfer object for devices
        transfer_device_object = transfer_device(client_device_object, server_object)
        transfer_object = None

    # Set up the report
    run_time = strftime("%Y%m%d_%H%M%S", gmtime())

    report_object = report()

    # Get a shell on the content server
    content_ip = testbed_object.find(".//content_server[@id='"  + str(content_id) + "']/ip").text
    content_shell = shell(content_ip)

    objects = {}
    objects['CLIENT']        = client_object
    objects['CLIENT_DEVICE'] = client_device_object
    objects['SERVER']        = server_object
    objects['NETEM']         = netem_object
    objects['TRANSFER']      = transfer_object
    objects['TRANSFER_DEVICE']  = transfer_device_object
    objects['TESTBED']       = testbed_object
    objects['REPORT']        = report_object
    objects['CONTENT']       = content_shell
    
    # Automatically cleanup and generate the report when we exit
    atexit.register(testfinish, objects)
    
    return objects

##########################################################
# system_cleanup
#   simple method to provide cleanup
##########################################################
def system_cleanup(remote, cmd, path, filetypes):
    log("Deleting [" +str(filetypes)+ "] for directory path: " +str(path))

    for ftype in filetypes:
        cmd = "sudo " +cmd+ " " +str(path)+ "/" +str(ftype)
        remote.run(cmd)

def zorc_min_allowable_bw(nettype="", rtt=0):
    log("Calculating Zorc Minimum Bandwidth")

    if nettype == "" or rtt == 0:
        assert False, "zorc_min_allowable_bw() requires a nettype and rtt value"

    LTE   = {'20':5400, '40':2700, '60':1800, '80':1350, '100':1080, '200':540, '400':270, '600':180}
    EHRPD = {'20':2160, '40':1080, '60':720, '80':540, '100':432, '200':216, '400':108, '600':72}

    BWTBLS = {'LTE':LTE, 'EHRPD':EHRPD}

    MINBWTBL = BWTBLS[str(nettype)]

    bw = MINBWTBL[str(rtt)]
        
    log("MINIMUM BANDWIDTH CALCULATED = : " +str(bw))

    return bw
