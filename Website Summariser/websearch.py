import asyncio
import aiohttp
from bs4 import BeautifulSoup


async def fetch_page(session, url):
    async with session.get(url) as response:
        return await response.text()
    

async def parse(html,element):
    soup = BeautifulSoup(html, 'html.parser')
    titles = []
    for h in soup.find_all(element):
        titles.append(h.text)

    return titles

async def scrape_multiple_pages(urls, element):
    async with aiohttp.ClientSession() as session:

        tasks = []
        for url in urls:
            task = fetch_page(session, url)
            tasks.append(task)

        html_pages = await asyncio.gather(*tasks)
        
        parsing_tasks = []
        for html in html_pages:
            task = parse(html, element)
            parsing_tasks.append(task)

        results = await asyncio.gather(*parsing_tasks)

        return results


def get_title(url):
    urls = [url]
    results = asyncio.run(scrape_multiple_pages(urls, 'title')) 
    return results

def get_paragraphs(url):
    urls = [url]
    results = asyncio.run(scrape_multiple_pages(urls, 'p')) 
    return results

def get_h1(url):
    urls = [url]
    results = asyncio.run(scrape_multiple_pages(urls, 'h1')) 
    return results

def get_h2(url):
    urls = [url]
    results = asyncio.run(scrape_multiple_pages(urls, 'h2')) 
    return results


def getWebDescript(website):
    title = get_title(website)
    paragraphs = get_paragraphs(website)
    h1 = get_h1(website)
    h2 = get_h1(website)
    web_descript = str(title)+str(paragraphs)+str(h1)+str(h2)
    return web_descript
