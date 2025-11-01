import asyncio
import aiohttp
from concurrent.futures import ProcessPoolExecutor

async def fetch_data(url):
    async with aiohttp.client.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()
        
