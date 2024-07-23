#! /usr/bin/env python3
import argparse
import json
import os

parser = argparse.ArgumentParser()
parser.add_argument(
    '-p', '--path', help='Output path of the front configuration file.', default='config.json'
)

args = parser.parse_args()

# Parse env variables
API_URL = os.getenv('RK_BASE_URL', 'http://localhost')

# Generate config
config = {'apiHost': API_URL, 'apiBasePath': '/api/v1', 'logging': True}

with open(args.path, 'w', encoding='utf8') as fp:
    fp.write(json.dumps(config))
