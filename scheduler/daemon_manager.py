"""
Scheduler Daemon Manager

Manages the scheduler as a background daemon process on Windows.
Handles PID file, process lifecycle, and status checking.

Features:
- Start scheduler in background
- Stop running scheduler
- Check scheduler status
- PID file management
- Process supervision

Usage:
    from scheduler.daemon_manager import SchedulerDaemon
    from utils.config import load_config
    
    config = load_config()
    daemon = SchedulerDaemon(config)
    
    # Start in background
    daemon.start()
    
    # Check status
    if daemon.is_running():
        print("Scheduler is running")
    
    # Stop
    daemon.stop()
"""

import os
import sys
import time
import subprocess
import psutil
from pathlib import Path
from typing import Optional, Dict, Any

from utils.logging_config import get_logger


logger = get_logger(__name__)


class SchedulerDaemon:
    """
    Manages the scheduler as a background daemon process.
    
    Handles process lifecycle, PID files, and status checking.
    """
    
    def __init__(self, config: Dict[str, Any], pid_file: Optional[str] = None):
        """
        Initialize daemon manager.
        
        Args:
            config: Configuration dictionary
            pid_file: Path to PID file (default: scheduler.pid in project root)
        """
        self.config = config
        
        # Determine PID file location
        if pid_file is None:
            project_root = Path(__file__).parent.parent
            self.pid_file = project_root / "scheduler.pid"
        else:
            self.pid_file = Path(pid_file)
        
        # Log file for daemon output
        project_root = Path(__file__).parent.parent
        self.log_dir = project_root / "logs"
        self.log_dir.mkdir(exist_ok=True)
        self.daemon_log = self.log_dir / "scheduler.log"
        
        logger.info(f"Daemon manager initialized (PID file: {self.pid_file})")
    
    
    def start(self, foreground: bool = False) -> bool:
        """
        Start the scheduler daemon.
        
        Args:
            foreground: If True, run in foreground (blocking). 
                       If False, spawn background process.
        
        Returns:
            True if started successfully, False otherwise
        """
        # Check if already running
        if self.is_running():
            pid = self.get_pid()
            logger.warning(f"Scheduler is already running (PID: {pid})")
            return False
        
        if foreground:
            # Run in foreground (blocking)
            logger.info("Starting scheduler in foreground mode...")
            return self._start_foreground()
        else:
            # Run in background
            logger.info("Starting scheduler in background mode...")
            return self._start_background()
    
    
    def _start_foreground(self) -> bool:
        """
        Start scheduler in foreground (blocking).
        
        Returns:
            True if started successfully
        """
        try:
            # Write PID file
            self._write_pid(os.getpid())
            
            # Import and start scheduler
            from scheduler.job_scheduler import PriceTrackerScheduler
            
            scheduler = PriceTrackerScheduler(self.config, blocking=True)
            
            logger.info("Scheduler starting in foreground...")
            logger.info("Press Ctrl+C to stop")
            
            try:
                scheduler.start()
            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
                scheduler.stop()
            finally:
                self._remove_pid()
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to start scheduler: {e}", exc_info=True)
            self._remove_pid()
            return False
    
    
    def _start_background(self) -> bool:
        """
        Start scheduler as background process.
        
        Returns:
            True if started successfully
        """
        try:
            # Get Python executable
            python_exe = sys.executable
            
            # Get project root
            project_root = Path(__file__).parent.parent
            
            # Script to run
            script_path = project_root / "scheduler" / "_daemon_runner.py"
            
            # Create daemon runner script if it doesn't exist
            self._create_daemon_runner()
            
            # Start process in background
            if sys.platform == 'win32':
                # Windows: Use subprocess with DETACHED_PROCESS
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                
                process = subprocess.Popen(
                    [python_exe, str(script_path)],
                    cwd=str(project_root),
                    stdout=open(self.daemon_log, 'a'),
                    stderr=subprocess.STDOUT,
                    creationflags=creation_flags,
                    close_fds=False
                )
            else:
                # Unix-like: Use nohup or similar
                process = subprocess.Popen(
                    [python_exe, str(script_path)],
                    cwd=str(project_root),
                    stdout=open(self.daemon_log, 'a'),
                    stderr=subprocess.STDOUT,
                    start_new_session=True
                )
            
            # Write PID file
            self._write_pid(process.pid)
            
            # Give it a moment to start
            time.sleep(2)
            
            # Verify it's running
            if self.is_running():
                logger.info(f"✓ Scheduler started in background (PID: {process.pid})")
                logger.info(f"  Log file: {self.daemon_log}")
                return True
            else:
                logger.error("✗ Scheduler failed to start")
                return False
        
        except Exception as e:
            logger.error(f"Failed to start background scheduler: {e}", exc_info=True)
            return False
    
    
    def stop(self, timeout: int = 10) -> bool:
        """
        Stop the running scheduler daemon.
        
        Args:
            timeout: Seconds to wait for graceful shutdown
        
        Returns:
            True if stopped successfully, False otherwise
        """
        pid = self.get_pid()
        
        if pid is None:
            logger.warning("No PID file found - scheduler may not be running")
            return False
        
        if not self.is_running():
            logger.warning(f"Process {pid} is not running - cleaning up PID file")
            self._remove_pid()
            return True
        
        try:
            logger.info(f"Stopping scheduler (PID: {pid})...")
            
            # Get process
            process = psutil.Process(pid)
            
            # Try graceful termination first
            process.terminate()
            
            # Wait for process to exit
            try:
                process.wait(timeout=timeout)
                logger.info("✓ Scheduler stopped gracefully")
            except psutil.TimeoutExpired:
                logger.warning(f"Process did not stop in {timeout}s, forcing kill...")
                process.kill()
                process.wait(timeout=5)
                logger.info("✓ Scheduler killed forcefully")
            
            # Remove PID file
            self._remove_pid()
            
            return True
        
        except psutil.NoSuchProcess:
            logger.warning(f"Process {pid} not found - cleaning up PID file")
            self._remove_pid()
            return True
        
        except Exception as e:
            logger.error(f"Error stopping scheduler: {e}", exc_info=True)
            return False
    
    
    def restart(self) -> bool:
        """
        Restart the scheduler.
        
        Returns:
            True if restarted successfully
        """
        logger.info("Restarting scheduler...")
        
        if self.is_running():
            if not self.stop():
                logger.error("Failed to stop scheduler")
                return False
            
            # Wait a moment
            time.sleep(1)
        
        return self.start(foreground=False)
    
    
    def is_running(self) -> bool:
        """
        Check if scheduler is running.
        
        Returns:
            True if running, False otherwise
        """
        pid = self.get_pid()
        
        if pid is None:
            return False
        
        try:
            process = psutil.Process(pid)
            return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
        except psutil.NoSuchProcess:
            return False
    
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get detailed scheduler status.
        
        Returns:
            Dictionary with status information
        """
        pid = self.get_pid()
        running = self.is_running()
        
        status = {
            'running': running,
            'pid': pid,
            'pid_file': str(self.pid_file),
            'log_file': str(self.daemon_log)
        }
        
        if running and pid:
            try:
                process = psutil.Process(pid)
                status.update({
                    'status': process.status(),
                    'cpu_percent': process.cpu_percent(interval=0.1),
                    'memory_mb': process.memory_info().rss / 1024 / 1024,
                    'started_at': datetime.fromtimestamp(process.create_time()).isoformat(),
                    'uptime_seconds': time.time() - process.create_time()
                })
            except Exception as e:
                status['error'] = str(e)
        
        return status
    
    
    def get_pid(self) -> Optional[int]:
        """
        Read PID from PID file.
        
        Returns:
            PID if file exists and is valid, None otherwise
        """
        if not self.pid_file.exists():
            return None
        
        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
            return pid
        except (ValueError, IOError) as e:
            logger.warning(f"Invalid PID file: {e}")
            return None
    
    
    def _write_pid(self, pid: int):
        """
        Write PID to file.
        
        Args:
            pid: Process ID to write
        """
        try:
            with open(self.pid_file, 'w') as f:
                f.write(str(pid))
            logger.debug(f"Wrote PID {pid} to {self.pid_file}")
        except IOError as e:
            logger.error(f"Failed to write PID file: {e}")
    
    
    def _remove_pid(self):
        """Remove PID file."""
        if self.pid_file.exists():
            try:
                self.pid_file.unlink()
                logger.debug(f"Removed PID file: {self.pid_file}")
            except IOError as e:
                logger.warning(f"Failed to remove PID file: {e}")
    
    
    def _create_daemon_runner(self):
        """
        Create the daemon runner script.
        
        This script runs the scheduler in the spawned background process.
        """
        runner_path = Path(__file__).parent / "_daemon_runner.py"
        
        if runner_path.exists():
            return  # Already exists
        
        runner_code = '''"""
Daemon Runner Script

This script is executed when starting the scheduler in background mode.
DO NOT run this directly - use main.py start command.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scheduler.job_scheduler import PriceTrackerScheduler
from utils.config import load_config
from utils.logging_config import get_logger

logger = get_logger(__name__)

if __name__ == "__main__":
    try:
        # Load configuration
        config = load_config()
        
        # Create and start scheduler
        scheduler = PriceTrackerScheduler(config, blocking=True)
        
        logger.info("Daemon runner starting scheduler...")
        scheduler.start()
    
    except Exception as e:
        logger.error(f"Daemon runner failed: {e}", exc_info=True)
        sys.exit(1)
'''
        
        with open(runner_path, 'w') as f:
            f.write(runner_code)
        
        logger.debug(f"Created daemon runner: {runner_path}")


# ============================================================================
# IMPORTS (for type hints and utilities)
# ============================================================================

from datetime import datetime


# ============================================================================
# MAIN (for testing)
# ============================================================================

if __name__ == "__main__":
    """
    Test daemon manager.
    Run: python -m scheduler.daemon_manager
    """
    from utils.config import load_config
    
    print("=" * 70)
    print("Scheduler Daemon Manager Test")
    print("=" * 70)
    
    config = load_config()
    daemon = SchedulerDaemon(config)
    
    print(f"\nPID file: {daemon.pid_file}")
    print(f"Log file: {daemon.daemon_log}")
    
    # Check status
    print("\nCurrent status:")
    status = daemon.get_status()
    for key, value in status.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 70)
    print("✓ Daemon manager test complete")
    print("=" * 70)
