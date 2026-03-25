"""
Global DatasetRegistry for sharing dataset state across ADK agent invocations.

This is a workaround for ADK InMemorySessionService limitations where
session state doesn't persist properly across invocations. The registry
provides a thread-safe singleton to store and retrieve DatasetInfo objects
keyed by session_id.
"""

import threading
from typing import Optional, Dict
from src.state.dataset_info import DatasetInfo


class DatasetRegistry:
    """
    Thread-safe singleton registry for DatasetInfo objects.

    Stores dataset information keyed by session_id, allowing
    agents to retrieve dataset info without relying on ADK session state.

    Usage:
        # In pipeline runner:
        DatasetRegistry.register(session_id, dataset_info)

        # In agent:
        dataset_info = DatasetRegistry.get(session_id)

        # Cleanup after pipeline completes:
        DatasetRegistry.remove(session_id)

    Thread Safety:
        All operations are protected by a threading.Lock to ensure
        thread-safe access in concurrent pipeline executions.
    """

    _instance = None
    _lock = threading.Lock()
    _datasets: Dict[str, DatasetInfo] = {}

    def __new__(cls):
        """Singleton pattern - only one instance allowed."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, session_id: str, dataset_info: DatasetInfo) -> None:
        """
        Register a dataset for a session.

        Args:
            session_id: ADK session identifier
            dataset_info: DatasetInfo object to store
        """
        with cls._lock:
            cls._datasets[session_id] = dataset_info

    @classmethod
    def get(cls, session_id: str) -> Optional[DatasetInfo]:
        """
        Retrieve dataset for a session.

        Args:
            session_id: ADK session identifier

        Returns:
            DatasetInfo object if found, None otherwise
        """
        with cls._lock:
            return cls._datasets.get(session_id)

    @classmethod
    def remove(cls, session_id: str) -> None:
        """
        Remove dataset from registry (cleanup).

        Args:
            session_id: ADK session identifier
        """
        with cls._lock:
            cls._datasets.pop(session_id, None)

    @classmethod
    def clear(cls) -> None:
        """Clear all registered datasets (for testing/cleanup)."""
        with cls._lock:
            cls._datasets.clear()

    @classmethod
    def list_sessions(cls) -> list:
        """List all registered session IDs (for debugging)."""
        with cls._lock:
            return list(cls._datasets.keys())
