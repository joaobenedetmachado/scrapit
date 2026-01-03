import requests
from bs4 import BeautifulSoup
import yaml
from datetime import datetime
from playwright.async_api import async_playwright
from bson.json_util import dumps
import json
import scraper.db_utils
import schedule
import time
import csv
from datetime import datetime, timedelta
from pathlib import Path
import scraper.producer

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"}

async def grab_elements_by_directive(directive):
    with open(directive, 'r') as file:
        dados = yaml.safe_load(file)
    
    if dados['use'] == 'beautifulsoup':
        return use_bs4(dados)
    if dados['use'] == 'playwright':
        return await use_playwright(dados)
            


            
async def use_playwright(dados):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        elements_output = {}
        await page.goto(dados['site'])

        for key, value in dados['scrape'].items():
            selector = value[0]
            attr = value[1].get('attr')

            await page.wait_for_selector(selector)

            element = page.locator(selector).first

            count = await element.count()
            if count == 0:
                elements_output[key] = None
                continue

            if attr == 'text':
                elements_output[key] = await element.inner_text()
            else:
                elements_output[key] = await element.get_attribute(attr)

        await browser.close()
        elements_output["url"] = dados["site"]
        elements_output["timestamp"] = datetime.now()
        return elements_output
    
def use_bs4(dados):
    response = requests.get(dados['site'], headers=headers)
    response.raise_for_status()  

    soup = BeautifulSoup(response.text, "html.parser")
    elements_output = {}

    for key, value in dados['scrape'].items():
        selector = value[0]
        attr = value[1].get('attr')

        element = soup.select_one(selector)

        if element:
            if attr == 'text':
                elements_output[key] = element.get_text(strip=True)
            else:
                elements_output[key] = element.get(attr)
        else:
            elements_output[key] = None

    elements_output["url"] = dados["site"]
    elements_output["timestamp"] = datetime.now()

    return elements_output

def get_scraped_by_sites_formated(name):
    res = db_utils.get_elements_by_site(name)
    json_str = dumps(res)
    data = json.loads(json_str)
    return data
