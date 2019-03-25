# ndn-testbed-test

This repository contains an imeplementation of a NDN testbed monitoring tool. The application reads a list of nodes supporting fch from a JSON file. For each node, the application registers a distinguish prefix. After that, we periodically send Interest packets between each pair of nodes. 

The statistics (the number of successful transmisions) are stored in python pandas and written to a CSV file. The file can be then read by `display_stats.py` and displayed as a heatmap.

## INSTALLATION
The application requires python > 3.6 and pandas and PyNDN. 

It uses the default identity stored in the KeyChain on the hosting machine. 


