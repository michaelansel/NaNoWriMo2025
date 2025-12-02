#!/usr/bin/env python3
"""
Shared state management for multi-worker webhook service.

Provides file-based state that works across gunicorn workers using
file locking for atomic operations.

Key components:
- SharedJobState: Manages active jobs across all workers
- FileCancellationEvent: Drop-in replacement for threading.Event that works cross-process

Implementation uses file-based synchronization to coordinate across process boundaries.
"""

import os
import json
import fcntl
import time
import logging
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime

logger = logging.getLogger(__name__)

# Default state file location
DEFAULT_STATE_DIR = Path("/tmp/continuity-webhook")
DEFAULT_STATE_FILE = DEFAULT_STATE_DIR / "active_jobs.json"


def ensure_state_dir():
    """Ensure the state directory exists."""
    DEFAULT_STATE_DIR.mkdir(parents=True, exist_ok=True)


class FileLock:
    """Context manager for file-based locking."""

    def __init__(self, lock_path: Path, timeout: float = 10.0):
        self.lock_path = lock_path
        self.timeout = timeout
        self.lock_file = None

    def __enter__(self):
        ensure_state_dir()
        self.lock_file = open(self.lock_path, 'w')
        start = time.time()
        while True:
            try:
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except BlockingIOError:
                if time.time() - start > self.timeout:
                    raise TimeoutError(f"Could not acquire lock on {self.lock_path} within {self.timeout}s")
                time.sleep(0.01)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.lock_file:
            fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
            self.lock_file.close()


class FileCancellationEvent:
    """
    Cross-process cancellation event using a file.

    Drop-in replacement for threading.Event that works across gunicorn workers.
    Each job gets a unique cancellation file based on workflow_id.
    """

    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        ensure_state_dir()
        self.cancel_file = DEFAULT_STATE_DIR / f"cancel_{workflow_id}"

    def set(self):
        """Signal cancellation by creating the cancel file."""
        try:
            self.cancel_file.touch()
            logger.info(f"Cancellation signaled for workflow {self.workflow_id}")
        except Exception as e:
            logger.error(f"Failed to signal cancellation for {self.workflow_id}: {e}")

    def is_set(self) -> bool:
        """Check if cancellation has been signaled."""
        return self.cancel_file.exists()

    def clear(self):
        """Clear the cancellation signal."""
        try:
            if self.cancel_file.exists():
                self.cancel_file.unlink()
        except Exception as e:
            logger.warning(f"Failed to clear cancellation for {self.workflow_id}: {e}")

    def cleanup(self):
        """Remove the cancel file (call when job completes)."""
        self.clear()


@dataclass
class JobInfo:
    """Information about an active job."""
    workflow_id: str
    pr_number: int
    operation_type: str  # 'continuity' or 'extraction'
    status: str
    start_time: float
    current_path: Optional[str] = None
    total_paths: Optional[int] = None
    processed_paths: int = 0
    worker_pid: int = 0

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'JobInfo':
        return cls(**data)


class SharedJobState:
    """
    Manages active job state across all gunicorn workers.

    Uses file-based storage with locking to ensure atomicity.
    """

    def __init__(self, state_file: Path = DEFAULT_STATE_FILE):
        self.state_file = state_file
        self.lock_path = state_file.with_suffix('.lock')
        ensure_state_dir()

    def _read_state(self) -> Dict:
        """Read state from file (must be called within lock)."""
        if not self.state_file.exists():
            return {
                'active_jobs': {},
                'pr_continuity_jobs': {},
                'pr_extraction_jobs': {},
                'job_history': []
            }
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to read state file, starting fresh: {e}")
            return {
                'active_jobs': {},
                'pr_continuity_jobs': {},
                'pr_extraction_jobs': {},
                'job_history': []
            }

    def _write_state(self, state: Dict):
        """Write state to file (must be called within lock)."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to write state file: {e}")
            raise

    def register_job(self, job_info: JobInfo) -> Optional[str]:
        """
        Register a new job. Returns existing workflow_id if one exists for this PR/type.

        Args:
            job_info: Information about the job to register

        Returns:
            workflow_id of existing job if one exists (should be cancelled),
            None if this is a new job
        """
        with FileLock(self.lock_path):
            state = self._read_state()

            # Check for existing job of same type for this PR
            existing_workflow_id = None
            if job_info.operation_type == 'continuity':
                existing_workflow_id = state['pr_continuity_jobs'].get(str(job_info.pr_number))
            elif job_info.operation_type == 'extraction':
                existing_workflow_id = state['pr_extraction_jobs'].get(str(job_info.pr_number))

            # Register the new job
            job_info.worker_pid = os.getpid()
            state['active_jobs'][job_info.workflow_id] = job_info.to_dict()

            # Update PR tracking
            if job_info.operation_type == 'continuity':
                state['pr_continuity_jobs'][str(job_info.pr_number)] = job_info.workflow_id
            elif job_info.operation_type == 'extraction':
                state['pr_extraction_jobs'][str(job_info.pr_number)] = job_info.workflow_id

            self._write_state(state)

            return existing_workflow_id

    def update_job(self, workflow_id: str, **updates):
        """Update job status/progress."""
        with FileLock(self.lock_path):
            state = self._read_state()
            if workflow_id in state['active_jobs']:
                state['active_jobs'][workflow_id].update(updates)
                self._write_state(state)

    def complete_job(self, workflow_id: str, final_status: str = 'completed'):
        """Mark a job as complete and move to history."""
        with FileLock(self.lock_path):
            state = self._read_state()

            if workflow_id in state['active_jobs']:
                job_data = state['active_jobs'].pop(workflow_id)
                job_data['status'] = final_status
                job_data['end_time'] = time.time()

                # Remove from PR tracking
                pr_number = str(job_data.get('pr_number', ''))
                op_type = job_data.get('operation_type', '')

                if op_type == 'continuity' and state['pr_continuity_jobs'].get(pr_number) == workflow_id:
                    del state['pr_continuity_jobs'][pr_number]
                elif op_type == 'extraction' and state['pr_extraction_jobs'].get(pr_number) == workflow_id:
                    del state['pr_extraction_jobs'][pr_number]

                # Add to history (keep last 50)
                state['job_history'].append(job_data)
                state['job_history'] = state['job_history'][-50:]

                self._write_state(state)

        # Cleanup cancellation file
        FileCancellationEvent(workflow_id).cleanup()

    def get_job(self, workflow_id: str) -> Optional[JobInfo]:
        """Get information about a specific job."""
        with FileLock(self.lock_path):
            state = self._read_state()
            job_data = state['active_jobs'].get(workflow_id)
            if job_data:
                return JobInfo.from_dict(job_data)
            return None

    def get_existing_job_for_pr(self, pr_number: int, operation_type: str) -> Optional[str]:
        """Get workflow_id of existing job for this PR, if any."""
        with FileLock(self.lock_path):
            state = self._read_state()
            if operation_type == 'continuity':
                return state['pr_continuity_jobs'].get(str(pr_number))
            elif operation_type == 'extraction':
                return state['pr_extraction_jobs'].get(str(pr_number))
            return None

    def cancel_existing_job(self, pr_number: int, operation_type: str) -> Optional[str]:
        """
        Cancel any existing job for this PR/type.

        Returns the workflow_id of the cancelled job, or None if no job existed.
        """
        existing_workflow_id = self.get_existing_job_for_pr(pr_number, operation_type)
        if existing_workflow_id:
            # Signal cancellation via file
            cancel_event = FileCancellationEvent(existing_workflow_id)
            cancel_event.set()
            logger.info(f"Signaled cancellation for existing {operation_type} job {existing_workflow_id} (PR #{pr_number})")
            return existing_workflow_id
        return None

    def get_all_active_jobs(self) -> Dict[str, JobInfo]:
        """Get all active jobs."""
        with FileLock(self.lock_path):
            state = self._read_state()
            return {
                wid: JobInfo.from_dict(data)
                for wid, data in state['active_jobs'].items()
            }

    def get_job_history(self) -> list:
        """Get recent job history."""
        with FileLock(self.lock_path):
            state = self._read_state()
            return state.get('job_history', [])

    def cleanup_stale_jobs(self, max_age_seconds: int = 3600):
        """Remove jobs that have been running too long (likely orphaned)."""
        now = time.time()
        with FileLock(self.lock_path):
            state = self._read_state()

            stale_jobs = []
            for workflow_id, job_data in list(state['active_jobs'].items()):
                if now - job_data.get('start_time', 0) > max_age_seconds:
                    stale_jobs.append(workflow_id)

            for workflow_id in stale_jobs:
                job_data = state['active_jobs'].pop(workflow_id)
                logger.warning(f"Cleaned up stale job {workflow_id}")

                # Remove from PR tracking
                pr_number = str(job_data.get('pr_number', ''))
                op_type = job_data.get('operation_type', '')
                if op_type == 'continuity' and state['pr_continuity_jobs'].get(pr_number) == workflow_id:
                    del state['pr_continuity_jobs'][pr_number]
                elif op_type == 'extraction' and state['pr_extraction_jobs'].get(pr_number) == workflow_id:
                    del state['pr_extraction_jobs'][pr_number]

                # Cleanup cancellation file
                FileCancellationEvent(workflow_id).cleanup()

            if stale_jobs:
                self._write_state(state)

            return stale_jobs


# Global singleton for easy access
_shared_state = None

def get_shared_state() -> SharedJobState:
    """Get the global shared state instance."""
    global _shared_state
    if _shared_state is None:
        _shared_state = SharedJobState()
    return _shared_state
