import datetime

url = '/home/joao/pricecast/scraper/logs/log.txt'

def log(message):
    with open(url, 'a') as f:
        f.write(str(datetime.datetime.now()) + ' - ' + message + '\n')

def exclude_log(log):
    pass