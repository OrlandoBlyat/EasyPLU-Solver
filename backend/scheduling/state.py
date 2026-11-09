"""Shared process state for verified browser grants and active jobs."""
from threading import Lock

lock = Lock()
verified = {}
running = {}
