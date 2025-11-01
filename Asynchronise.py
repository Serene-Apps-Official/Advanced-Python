import asyncio
import aiohttp
from concurrent.futures import ProcessPoolExecutor

URLS = [
    'https://jsonplaceholder.typicode.com/todos/1',
    'https://jsonplaceholder.typicode.com/todos/2',
    'https://jsonplaceholder.typicode.com/todos/3',
    'https://jsonplaceholder.typicode.com/todos/4'
]

async def fetch_data(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

def cpu_intensive_task(number):
    print(f"Running CPU-intensive task for number: {number}")
    return sum(i * i for i in range(number * 10000))

async def main():
    fetch_tasks = []
    for url in URLS:
        fetch_tasks.append(fetch_data(url))
    
    all_data = await asyncio.gather(*fetch_tasks)
    
    print("Fetched data:", all_data)
    
    numbers_for_cpu = []
    for item in all_data:
        if item and 'id' in item:
            numbers_for_cpu.append(item['id'])
    
    with ProcessPoolExecutor() as executor:
        loop = asyncio.get_event_loop()
        
        cpu_tasks = []
        for number in numbers_for_cpu:
            future = loop.run_in_executor(executor, cpu_intensive_task, number)
            cpu_tasks.append(future)
            
        cpu_results = await asyncio.gather(*cpu_tasks)

        for number, result in zip(numbers_for_cpu, cpu_results):
            print(f"CPU result for ID {number}: {result}")


if __name__ == "__main__":
    asyncio.run(main())