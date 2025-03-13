import asyncio
import os
import sys
import signal
import uvicorn
from subprocess import Popen
import logging
import socket
from contextlib import closing

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def is_port_in_use(port: int) -> bool:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        return sock.connect_ex(('localhost', port)) == 0

async def kill_process_on_port(port: int):
    if is_port_in_use(port):
        if sys.platform == 'win32':
            os.system(f'netstat -ano | findstr :{port} > port.tmp')
            with open('port.tmp') as f:
                for line in f:
                    if 'LISTENING' in line:
                        pid = line.split()[-1]
                        os.system(f'taskkill /F /PID {pid}')
            os.remove('port.tmp')
        else:
            os.system(f'lsof -ti:{port} | xargs kill -9 > /dev/null 2>&1')
        logger.info(f"Killed process on port {port}")
        await asyncio.sleep(1)  # Wait for port to be freed

async def start_nodejs():
    logger.info("Starting Node.js server...")
    await kill_process_on_port(5000)
    
    process = Popen(['npm', 'run', 'dev'], cwd=os.path.dirname(os.path.dirname(__file__)))
    try:
        while True:
            await asyncio.sleep(1)
            if process.poll() is not None:
                logger.error("Node.js server stopped unexpectedly")
                return False
    except Exception as e:
        logger.error(f"Error in Node.js server: {e}")
        process.terminate()
        return False
    finally:
        process.terminate()
    
    return True

async def start_fastapi():
    logger.info("Starting FastAPI server...")
    await kill_process_on_port(5001)
    
    try:
        # Change directory to where fastapi_server.py is located
        server_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(server_dir)
        
        # Start the FastAPI server as a subprocess
        process = Popen([
            sys.executable,
            'fastapi_server.py'
        ])
        
        # Wait for the server to be ready
        for _ in range(30):  # 30 second timeout
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get('http://localhost:5001/health') as response:
                        if response.status == 200:
                            logger.info("FastAPI server is ready")
                            return process
            except Exception:
                await asyncio.sleep(1)
                if process.poll() is not None:
                    raise Exception("FastAPI server failed to start")
                
        raise Exception("FastAPI server failed to respond in time")
    except Exception as e:
        logger.error(f"Error in FastAPI server: {e}")
        return None

async def main():
    # Set up signal handlers
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
    
    try:
        # Start both servers
        nodejs_task = asyncio.create_task(start_nodejs())
        fastapi_task = asyncio.create_task(start_fastapi())
        
        # Wait for both servers to complete or fail
        results = await asyncio.gather(nodejs_task, fastapi_task, return_exceptions=True)
        
        # Check if any server failed
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Server error: {result}")
                await shutdown()
                sys.exit(1)
                
    except Exception as e:
        logger.error(f"Error starting servers: {e}")
        await shutdown()
        sys.exit(1)

async def shutdown():
    logger.info("Shutting down servers...")
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("Shutdown complete")

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down servers...")
        sys.exit(0)
