#!/usr/local/bin/python3.5

#
# Copyright 2016, Dan Malone, All Rights Reserved
#
from util import *
from .shell import *

import time
import os
import re
import pprint

local_shell = shell("local")

###################################################################################################
#
# MODULE (Class): gnuplot
#
# DESCRIPTION   : This class manages data plotting using gnuplot of various data etc.
#
# AUTHOR        : Dan Malone
#
# CREATED       : 01/13/16
#
##################################################################################################
class gnuplot:

    ##############################################################################################
    #
    # METHOD: __init__(testbed_objects)
    #
    # DESCRIPTION: This is the initialization constructor:
    #                  testbed_objects  - testbed objects as specified/required
    #
    ##############################################################################################
    def __init__(self, testbed_objects):
        """__init__(testbed_objects)
              This is the initialization constructor:
                  testbed_objects  - testbed objects as specified/required
                  """

        # set up the basic gnuplot reqs and pull only the necessary objects
        self.plot_commands ='set term png font "calibri,10" size 640,480\n'
        self.client = testbed_objects['CLIENT_DEVICE']
        self.transfer_device = testbed_objects['TRANSFER_DEVICE']
    
    # ############################################################
    #
    # Method: generic_tplot()
    #
    # Description: Time based (XAxis) plot utility that will allow 1..n
    #              line plotting of time based data points. Note: the format of the 
    #              plotfile data line must be "<time-index> <value>" as this is a 
    #              simple generic plot tool.
    #
    #              Plot file names must (for now) have the extension ".txt" and should
    #              named appropriately as the titel will be used as a lable for the
    #              plotline.
    #
    #              graph_data is a simple python list of plot file names allowing any
    #              number of plots to be pushed to this method.
    #
    #              Appending "DOT" as part of the .txt filename (ex: mygraphDOT.txt) will
    #              force the graph mechanism to use dot plotting otherwise line format
    #              is the default.
    #
    # ############################################################
    def generic_tplot(self, dprc, title, x_axis_label, y_axis_label, path, graph_data=[], ymax=0):
        """generic_tplot():
              Time based (XAxis) plot utility that will allow 1..n
                 line plotting of time based data points. Note: the format of the 
                 plotfile data line must be "<time-index> <value>" as this is a 
                 simple generic plot tool.
              Plot file names must (for now) have the extension ".txt" and should
                 named appropriately as the titel will be used as a lable for the
                 plotline.
              graph_data is a simple python list of plot file names allowing any
                 number of plots to be pushed to this method.
                 Appending "DOT" as part of the .txt filename (ex: mygraphDOT.txt) will
                 force the graph mechanism to use dot plotting otherwise line format
                 is the default.
                 """

        # create the gp filename
        build = re.match(r'(.*):\w+.*', title)
        label = re.match(r'.*:(.* .* .*) \[.*', title)
        if not label:
            label = re.match(r'.*:(.*)', title)
        filename = label.group(1).replace(" ", "-") + "_" + str(int(time.time()))+".gp"

        # start building the plot commands
        self.plot_commands = 'set term png font "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf,10" size 640,480\n' \
                             'set key top\n'

        # create the outfile and path extension
        pngfile = str(int(time.time())) + "-gput-"+ x_axis_label.replace(" ", "-") +".png"
        outfile = path + "/" + pngfile

        # if no ymax passed in use deafult of 60 (no reason why)
        if ymax == 0:
            ymax = 60

        # preset the gnuplot setup
        self.plot_commands += 'set output "'+ outfile +'"\n' \
                              'set term png size 1200,800\n' \
                              'set title "'+ title +'"\n' \
                              'set xlabel "Time \(secs\)"\n' \
                              'set ylabel "'+ y_axis_label +'"\n' \
                              'set xrange [0:]\n' \
                              'set yrange [:' +str(ymax)+ ']\n'

        plotlines_info = []

        # march through the plot list and process each file passed in
        for idx in range(0, len(graph_data)):
            plot_file = graph_data[idx]
            plot_title = str(plot_file).strip(".txt")
            
            # add some flexibility (NOTE_TO_SELF: This can be done better))
            if "DOT" in plot_title:
                # plot using dot format
                plot_title = str(plot_file).strip("DOT.txt")

                self.plot_commands = plot_command_init
                plotlines_info.append('"' + path + str(plot_file) +'" u 1:2 w p pt 1 t "' + plot_title + '"')

            else:
                # default to line format
                plotlines_info.append('"' + path + str(plot_file) +'" u 1:2 w l lw 2 t "' + plot_title + '"')

        plotlines_info_cmd = 'plot ' + ",".join(plotlines_info) + '\n'
        self.plot_commands += plotlines_info_cmd

        # run the plot
        dprc.shell.run("echo '" + self.plot_commands + "'" + " > " + path + filename)
        dprc.shell.run("gnuplot " + path + filename)

        return pngfile

    # ############################################################
    #
    # Method: g_plot()
    #
    # Description: This is a somewhat generic plot utility that will allow
    # multiple types of plot scenarios and plot poimt types. The currently supported
    # plot scenarios are:
    #       DEFAULT    - Single X/Y Axies
    #       MULTIYAXIS - Dual Y Axies left side/right side appropriately scaled
    #       MULTIPLOT  - Single x/y Aixies, plot within the main plot
    #
    # Plot point types supported:
    #       AXES - for plotting againts different y-axes with MULTIYAXIS
    #       LINE - basic line graph
    #       MARK - point based data plotting
    #       STEP - squared between data points
    # 
    # Inputs:
    #       cobj         - client object to make gnuplot calls
    #       title        - graph title
    #       path         - directory path to data files or ""
    #       x_axis_label - label for the x-axis
    #       y_axis_label - can be an 1-2 element array (list) of y-axis labels
    #       graph_data1  - for single graph, an array of arrays (lists) two element
    #                      currently of the format:
    #                         graph_data1[1-n][0] = <data-filename>
    #                         graph_data1[1-n][1] = <plot-point-type: AXIS, LINE, MARK, STEP>
    #       plot_type    - DEFAULT, MULTIYAXIS, MULTIPLOT
    #       graph_data2  - for MULTIGRAPH plot_type graph, an array of arrays (lists) two element
    #                      currently of the format:
    #                         graph_data1[1-n][0] = <data-filename>
    #                         graph_data1[1-n][1] = <plot-point-type: AXIS, LINE, MARK, STEP>
    #       y_axis_max   - where you know the bulk of the graph is in a low area you can limit to
    #                      enhance readability.
    #
    # File Format is a basic two element time vs value line item i.e.:
    #
    #       1.25 10.6
    #       1.75  0.5
    #           .
    #           .
    #       25.25  23.245
    #
    # space or tab deliniated.
    #
    # ############################################################
    def g_plot(self, cobj, title, path, x_axis_label, y_axis_label=[], graph_data1=[], plot_type="DEFAULT", graph_data2=[], y_axis_max=0):
        """g_plot()
              This is a somewhat generic plot utility that will allow
              multiple types of plot scenarios and plot poimt types. The currently supported
              plot scenarios are:
                 DEFAULT    - Single X/Y Axies
                 MULTIYAXIS - Dual Y Axies left side/right side appropriately scaled
                 MULTIPLOT  - Single x/y Aixies, plot within the main plot
              (see method header for more detailed description)
        """

        # create the gp filename
        filename = title.replace(" ", "-") + "_" + str(int(time.time()))+".gp"

        # check plot type
        if plot_type != "MULTIPLOT":
            # single plot
            self.plot_commands = 'set term png font "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf,10" size 1200,800\n' \
                                 'set key top\n'

        # create the outfile and path extension
        pngfile = str(int(time.time())) + "-gput-"+ x_axis_label.replace(" ", "-") +".png"
        outfile = path + "/" + pngfile

        # if not multiplot then handle as a single box plot
        if plot_type != "MULTIPLOT":

            # preset the gnuplot setup
            self.plot_commands += 'set output "'+ outfile +'"\n' \
                                  'set term png size 1200,800\n' \
                                  'set title "'+ title +'"\n' \
                                  'set xlabel "' +x_axis_label+ '"\n' \
                                  'set ylabel "' +y_axis_label[0]+ '"\n' \
                                  'set xrange [0:]\n'

            if y_axis_max != 0:
                self.plot_commands +='set yrange [:' +str(y_axis_max)+ ']\n'
            else:
                self.plot_commands +='set yrange [0:]\n'
            
            if plot_type == "MULTIYAXIS":
                self.plot_commands += 'set y2range [0:]\n' \
                                      'set y2tics \n' \
                                      'set y2label "' +y_axis_label[1]+ '"\n'

            plotlines_info = []
            
            # march through the plot list and process each file passed in
            for idx in range(0, len(graph_data1)):
                if "txt" in graph_data1[idx][0]:
                    plot_file = graph_data1[idx][0]
                    plot_title = str(plot_file).strip(".txt")
                    if graph_data1[idx][1] == "MARK":
                        plotlines_info.append('"' + path + str(plot_file) +'" u 1:2 w p pt 1 t "' + plot_title + '"')
                    elif graph_data1[idx][1] == "LINE":
                        plotlines_info.append('"' + path + str(plot_file) +'" u 1:2 w l lw 2 t "' + plot_title + '"')
                    elif graph_data1[idx][1] == "STEP":
                        plotlines_info.append('"' + path + str(plot_file) +'" u 1:2 w steps t "' + plot_title + '"')
                    elif graph_data1[idx][1] == "AXIS":
                        plotlines_info.append('"' + path + str(plot_file) +'" u 1:((1373*8)/$2) axes x1y2 w p t "' + plot_title + '"')
                    else:
                        plotlines_info.append('"' + path + str(plot_file) +'" u 1:2 w l lw 2 t "' + plot_title + '"')

            plotlines_info_cmd = 'plot ' + ",".join(plotlines_info) + '\n'
            self.plot_commands += plotlines_info_cmd

        else:
            # GRAPH1 - preset the multiplot setup for graph1 - primary
            self.plot_commands += 'set multiplot\n' \
                                  'set size 1,1\n' \
                                  'set origin 0,0\n' \
                                  'set title "'+ title +'"\n' \
                                  'set xlabel "' +x_axis_label+ '"\n' \
                                  'set ylabel "'+ y1_axis_label +'"\n' \
                                  'set xrange [0:]\n' \
                                  'set yrange [:' +str(ymax1)+ ']\n'

            plotlines_info = []

            # march through the graph1 plot list and process each file passed in
            for idx in range(0, len(graph_data1)):
                plot_file = graph_data1[idx]
                plot_title = str(plot_file).strip(".txt")
                if "DOT" in plot_title:
                    plot_title = str(plot_file).strip("DOT.txt")
                    plotlines_info.append('"' + path + str(plot_file) +'" u 1:2 w p pt 1 t "' + plot_title + '"')
                else:
                    plotlines_info.append('"' + path + str(plot_file) +'" u 1:2 w l lw 2 t "' + plot_title + '"')

            # set up the plot command for this data
            plotlines_info_cmd = 'plot ' + ",".join(plotlines_info) + '\n'
            self.plot_commands += plotlines_info_cmd

            plotlines_info = []

            # GRAPH2 - preset the gnuplot setup for graph2 - secondary
            self.plot_commands += 'set size 0.6,0.4\n' \
                                  'set origin 0.35,0.3\n' \
                                  'set title ""\n' \
                                  'set xlabel "' +x_axis_label+ '"\n' \
                                  'set ylabel "' +y2_axis_label+ '"\n' \
                                  'set xrange [0:]\n' \
                                  'set yrange [:' +str(ymax2)+ ']\n'

            # march through the graph2 plot list and process each file passed in
            for idx in range(0, len(graph_data2)):
                plot_file = graph_data2[idx]
                plot_title = str(plot_file).strip(".txt")
                if "DOT" in plot_title:
                    plot_title = str(plot_file).strip("DOT.txt")
                    plotlines_info.append('"' + path + str(plot_file) +'" u 1:2 w p pt 1 t "' + plot_title + '"')
                else:
                    plotlines_info.append('"' + path + str(plot_file) +'" u 1:2 w l lw 2 t "' + plot_title + '"')

            # set up the plot command for this data
            plotlines_info_cmd = 'plot ' + ",".join(plotlines_info) + '\n'
            self.plot_commands += plotlines_info_cmd

            # unset mutliplot before we leave
            self.plot_commands += 'unset multiplot\n'

        cobj.shell.run("echo '" + self.plot_commands + "'" + " > " + path + filename)
        cobj.shell.run("gnuplot " + path + filename)

        return pngfile
