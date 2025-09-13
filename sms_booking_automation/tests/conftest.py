"""
Global pytest configuration and fixtures for SMS booking automation tests.
"""

import os
import sys
import pytest
from dotenv import load_dotenv

# Load environment variables for tests
load_dotenv()

# Override database host for tests (use localhost)
os.environ["POSTGRES_HOST"] = "localhost"

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "app"))
