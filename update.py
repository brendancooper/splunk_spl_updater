import argparse
import configparser
import os
import sys
import logging
import re

from bs4 import BeautifulSoup
from pathlib import Path
from pathlib import PurePath

parser = argparse.ArgumentParser(
    description='Bulk update Splunk dashboards and searches')
parser.add_argument('--auto', required=False,
                    help='Automatically run all steps')

## Counters to record reporting stats
scanned_searches = 0
scanned_dashboards = 0

panel_successful = 0
panel_skipped_generating_or_base = 0
panel_skipped_no_index = 0
panel_skipped_no_sourcetype = 0
panel_skipped_advanced_search = 0
panel_skipped_unknown = 0
panel_skipped_macros = 0




"""

Step 1
Read apps directory looking for apps that match the regex
    For each app that matches
        Look inside inputs.conf
        Create key value where key is index and value is the appid
        Store pair in mapping dic

Step 2
Get list of apps
    Foreach app
        Foreach default & local directories in app
            load savedsearches into config parser
            foreach search stanza
                update spl for search
            get list of dashboards from data/ui/views
            foreach dashboard in dashboards
                parse xml 😞
                look for <query> </query> xml tags

"""

def generate_mappings():
    mappings = {}
    directory = Path.cwd()
    apps_dir = PurePath.joinpath(directory,"apps")
    print("=============================")
    print("Looking for inputs.conf files")
    print("=============================")
    for root, dirs, files in os.walk(apps_dir, topdown=False):
        for name in files:
            if name == 'inputs.conf':
                path = os.path.join(root, name)
                print("found: {}".format(path))
                config = configparser.ConfigParser()
                config.read(path)
                if config.has_option('default','index') and config.has_option('default','_meta'):
                    key = config['default']['index']
                    value = config['default']['_meta']
                    print("Adding mapping for {}={}".format(key,value))
                    mappings[key] = value
    return mappings

def update(mappings):
    global scanned_dashboards
    global scanned_searches
    mappings = {}
    directory = Path.cwd()
    apps_dir = PurePath.joinpath(directory,"apps")
    print("=============================")
    print("Looking for savedsearches and dashboards")
    print("=============================")
    for root, dirs, files in os.walk(apps_dir, topdown=False):
        for name in files:
            
            if name == 'savedsearches.conf':
                path = os.path.join(root, name)
                scanned_searches += 1
                #logging.log("found savedsearches: {}".format(path))
                #TODO: Custom config parser
                """
                config = configparser.ConfigParser()
                config.read(path)
                print(config.sections())
                for stanza in config.sections():
                    if config.has_option(stanza,'search'):
                        search = config[stanza]['search'] 
                        print("Found search stanza search={}".format(search))
                """
            elif name.endswith('.xml') :
                path = os.path.join(root, name)
                
                pattern =  r"data.ui.views"
                if re.search(pattern, path) is not None:
                    scanned_dashboards += 1
                    with open(path) as f:
                        xml = f.read()
                        soup = BeautifulSoup(xml,"xml")
                        handle_dashboard(soup)
                else:
                    print("no match")

def handle_dashboard(soup):
    global panel_successful
    global panel_skipped_no_index
    global panel_skipped_no_sourcetype
    global panel_skipped_generating_or_base
    global panel_skipped_advanced_search
    global panel_skipped_macros
    global panel_skipped_unknown
    
    queries = soup.find_all("query")
    for query in queries:
        fullspl = query.text
        split = fullspl.split("|")
        first_seg = split[0]
        if first_seg.count("index=") > 1:
            panel_skipped_advanced_search += 1
        elif first_seg.count("`") > 0:
            panel_skipped_macros += 1
        elif "index=" in first_seg and "sourcetype=" in first_seg:
            updated_seg = handle_spl(first_seg)
            panel_successful += 1
        elif "index=" not in first_seg and "sourcetype=" not in first_seg:
            panel_skipped_generating_or_base += 1
        elif "index=" in first_seg:
            panel_skipped_no_sourcetype += 1
        elif "sourcetype=" in first_seg:
            panel_skipped_no_index += 1
        else:
            print(first_seg)
            panel_skipped_unknown += 1
        
def handle_spl(first_seg):
    # Look at index=<string> extract index name
    # Look at sourcetype=<string> extract sourcetype
    # Lookup index mapping dict, add appid::<appid>
    # Lookup sourcetype_mappings.csv replace index=<flockindex> with index=<sharedindex>
    flock = re.search(r"index=([\w\"]*)[ \|]",first_seg).group(1)
             
    

if __name__ == "__main__":
    logging.basicConfig(filename='update.log', filemode='w', level=logging.DEBUG)
    mappings = generate_mappings()

    update(mappings)

    print("scanned dashboards: {}".format(scanned_dashboards))
    print("scanned searches: {}".format(scanned_searches))
    print("===================================\n===== Dashboard Panel Results =====\n===================================")
    print("successful panels: {}".format(panel_successful))
    print("skipped - Generating command or base search: {}".format(panel_skipped_generating_or_base))
    print("skipped - No index specified: {}".format(panel_skipped_no_index))
    print("skipped - No sourcetype: {}".format(panel_skipped_no_sourcetype))
    print("skipped - Multi-index Search: {}".format(panel_skipped_advanced_search))
    print("skipped - Macros Detected: {}".format(panel_skipped_macros))
    print("skipped - Unknown reason: {}".format(panel_skipped_unknown))
