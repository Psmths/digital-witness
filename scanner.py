import yaml
from tinydb import TinyDB, Query
import logging
import os
import time
import subprocess
from kafka import KafkaProducer
import json

logging.basicConfig(format='%(asctime)s - %(process)d %(levelname)s %(message)s', level=logging.INFO)
logging.getLogger("kafka").setLevel(logging.ERROR)

seconds_per_unit = {'m': 60, 'h': 3600, 'd': 86400, 'w': 604800}

def convert_to_seconds(s):
    return int(s[:-1]) * seconds_per_unit[s[-1]]

with open('scanner-config.yml', 'r') as stream:
    try:
        scanner_config = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        logging.error(exc)

producer = KafkaProducer(bootstrap_servers = scanner_config['kafka_bs_servers'],value_serializer=lambda v: json.dumps(v).encode('utf-8'))

portlist = sum(((list(range(*[int(b) + c
           for c, b in enumerate(a.split('-'))]))
           if '-' in str(a) else [int(a)]) for a in scanner_config['ports']), [])

logging.info('Portlist: ' + str(portlist))

db = TinyDB('db.json')

for scan_port in portlist:
    # Check if port exists in database
    port_query = Query()
    r = db.search(port_query.port == scan_port)

    # If it doesn't exist, add it with 0 ts for last scan time (scan it this round)
    if (len(r)) == 0:
        logging.info('Port ' + str(scan_port) + ' not found in db! Adding it.')
        new_entry = {
            'port': scan_port,
            'last_scan': 0
        }
        db.insert(new_entry)

    # Check if it is time to scan that port
    r = db.search(port_query.port == scan_port)
    if (time.time() - r[0]['last_scan'] > convert_to_seconds(scanner_config['interval'])):
        logging.info('Triggering scan for port ' + str(scan_port))

        for network in scanner_config['networks']:
            logging.info('Triggering scan network ' + str(network))

            results = subprocess.run(['zmap',
                            network,
                            '--rate', str(scanner_config['ratelimit']),
                            '-p', str(scan_port),
                            '-O', 'json',
                            '-q'
                            ], capture_output=True, shell=False)

            json_results_list = results.stdout.decode("utf-8").splitlines()
            json_results_list = list(dict.fromkeys(json_results_list))  

            for result in json_results_list:
                data = json.loads(result)
                data_json = {
                    'ip': data['saddr'],
                    'ts': time.time(),
                    'port': scan_port
                }

                logging.info(str(data_json))

                ack = producer.send(scanner_config['scan_data_pipeline'], data_json)
                
        # Scan complete, update db
        db.update({'last_scan': time.time()}, port_query.port == scan_port)
