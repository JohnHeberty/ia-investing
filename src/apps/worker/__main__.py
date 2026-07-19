import asyncio

from apps.worker.main import start_worker

if __name__ == "__main__":
    asyncio.run(start_worker())
