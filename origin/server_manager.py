import asyncio
import logging
import os
import signal
import sys
from subprocess import Popen
import psutil
import aiohttp
from contextlib import closing
import socket

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def find_process_by_port(port):
    """Find process ID using a specific port"""
    for proc in psutil.process_iter(['pid', 'name', 'connections']):
        try:
            for conn in proc.connections():
                if conn.laddr.port == port:
                    return proc.pid
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None

async def ensure_port_free(port: int):
    """Ensure a port is free by terminating any process using it"""
    logger.info(f"Ensuring port {port} is free...")
    pid = find_process_by_port(port)
    if pid:
        try:
            process = psutil.Process(pid)
            process.terminate()
            try:
                process.wait(timeout=5)
            except psutil.TimeoutExpired:
                process.kill()
            logger.info(f"Terminated process using port {port}")
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            logger.error(f"Error terminating process: {e}")

class ServerManager:
    def __init__(self):
        self.fastapi_process = None
        self.nodejs_process = None
        self.should_stop = False

    async def start_fastapi(self):
        """Start the FastAPI server"""
        logger.info("Starting FastAPI server...")
        await ensure_port_free(5001)
        
        server_dir = os.path.dirname(os.path.abspath(__file__))
        self.fastapi_process = Popen(
            [sys.executable, 'api_server.py'],
            cwd=server_dir
        )
        
        # Wait for FastAPI server to be ready
        for _ in range(30):
            if self.should_stop:
                return False
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get('http://localhost:5001/health') as response:
                        if response.status == 200:
                            logger.info("FastAPI server is ready!")
                            return True
            except Exception:
                if self.fastapi_process.poll() is not None:
                    logger.error("FastAPI process died unexpectedly")
                    return False
                await asyncio.sleep(1)
                
        logger.error("FastAPI server failed to start in time")
        return False

    async def start_nodejs(self):
        """Start the Node.js server"""
        logger.info("Starting Node.js server...")
        await ensure_port_free(5000)
        
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.nodejs_process = Popen(
            ['npm', 'run', 'dev'],
            cwd=project_root
        )
        
        # Wait for Node.js server to be ready
        for _ in range(30):
            if self.should_stop:
                return False
            
            if self.nodejs_process.poll() is not None:
                logger.error("Node.js process died unexpectedly")
                return False
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get('http://localhost:5000/') as response:
                        if response.status in [200, 304]:
                            logger.info("Node.js server is ready!")
                            return True
            except Exception:
                await asyncio.sleep(1)
        
        logger.error("Node.js server failed to start in time")
        return False

    async def cleanup(self):
        """Clean up server processes"""
        logger.info("Cleaning up servers...")
        self.should_stop = True
        
        if self.fastapi_process:
            self.fastapi_process.terminate()
            try:
                self.fastapi_process.wait(timeout=5)
            except:
                self.fastapi_process.kill()
        
        if self.nodejs_process:
            self.nodejs_process.terminate()
            try:
                self.nodejs_process.wait(timeout=5)
            except:
                self.nodejs_process.kill()
        
        # Ensure ports are freed
        await ensure_port_free(5000)
        await ensure_port_free(5001)
        
        logger.info("Cleanup complete")

async def main():
    manager = ServerManager()
    
    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda: asyncio.create_task(manager.cleanup())
        )
    
    try:
        # Start FastAPI first
        if not await manager.start_fastapi():
            logger.error("Failed to start FastAPI server")
            await manager.cleanup()
            sys.exit(1)
        
        # Then start Node.js
        if not await manager.start_nodejs():
            logger.error("Failed to start Node.js server")
            await manager.cleanup()
            sys.exit(1)
        
        # Keep the script running and monitor processes
        while not manager.should_stop:
            if (manager.fastapi_process and manager.fastapi_process.poll() is not None) or \
               (manager.nodejs_process and manager.nodejs_process.poll() is not None):
                logger.error("A server process died unexpectedly")
                break
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        await manager.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down servers...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
