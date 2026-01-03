#directive = '/home/joao/pricecast/scraper/directives/coinmarketcap.yaml'
import scraper.producer
import sys
import scraper.db_utils
from bson.json_util import dumps
import scraper.logger
import scraper.utils
import json
import csv

def update(name, part):
    res = scraper.db_utils.get_elements_by_part(name, part)
    json_str = dumps(res)
    data = json.loads(json_str)

    scraper.logger.log(f"Updating {name} {part}")
    scraper.utils.parse_coin_to_csv(data)

    return data 
