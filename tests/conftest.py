"""
Pytest configuration and shared fixtures for ADK migration tests.
"""

import pytest
import sys
from pathlib import Path
import tempfile
import shutil
from unittest.mock import Mock

# Enable pytest-asyncio
pytest_plugins = ('pytest_asyncio',)

# Base directories
BASE_DIR = Path(__file__).parent.parent.resolve()
TEST_DATA_DIR = BASE_DIR / "test_data"
INPUT_DIR = BASE_DIR / "input"

# Add util/ and tools/ to sys.path for imports
UTIL_DIR = BASE_DIR / "util"
TOOLS_DIR = BASE_DIR / "tools"

if str(UTIL_DIR) not in sys.path:
    sys.path.insert(0, str(UTIL_DIR))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))


@pytest.fixture(scope="session")
def base_dir():
    """Return the base directory of the project."""
    return BASE_DIR


@pytest.fixture(scope="session")
def test_data_dir():
    """Return the test data directory."""
    return TEST_DATA_DIR


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test outputs."""
    temp_path = Path(tempfile.mkdtemp(prefix="adk_test_"))
    yield temp_path
    # Cleanup
    if temp_path.exists():
        shutil.rmtree(temp_path)


@pytest.fixture
def mock_dataset_info():
    """Create a mock DatasetInfo object for testing."""
    from src.state.dataset_info import DatasetInfo

    dataset_path = BASE_DIR / "input" / "test_dataset"
    dataset = DatasetInfo(name="test_dataset", path=dataset_path)
    return dataset


@pytest.fixture
def mock_invocation_context(temp_dir):
    """
    Create a mock ADK InvocationContext for testing agents.

    Provides proper ADK context structure with session.state dictionary.
    """
    ctx = Mock()
    ctx.session = Mock()
    ctx.session.state = {
        "input_dir": str(temp_dir)
    }
    ctx.session.id = "test-session-123"
    ctx.invocation_id = "test-invocation-456"
    ctx.agent = Mock()
    ctx.agent.name = "TestAgent"
    return ctx


@pytest.fixture
def mock_context():
    """
    Create a mock state dictionary for testing (ADK-style).

    ⚠️ DEPRECATED: Use mock_invocation_context for agent tests.
    This fixture is kept for backward compatibility with tool tests.
    """
    return {
        "name": "test_dataset",
        "path": Path("input/test_dataset"),
        "skip_sampling": False,
        "skip_evaluation": False,
        "model": "gemini-2.5-flash"
    }


@pytest.fixture
def sample_pvmap_csv():
    """Return a sample PVMAP CSV content for testing."""
    return """key,property,value
observationAbout,location,dcid:country/USA
observationAbout,variableMeasured,dcid:Count_Person
observationDate,observationDate,2020
value,value,100000
"""


@pytest.fixture
def sample_metadata_csv():
    """Return sample metadata content for testing."""
    return """parameter,value
dataset_name,test_dataset
source,Test Source
date_format,%Y-%m-%d
"""


@pytest.fixture
def sample_sampled_data_csv():
    """Return sample sampled data content for testing."""
    return """location,date,population
USA,2020,100000
USA,2021,100500
USA,2022,101000
"""


# Pytest hooks

def pytest_configure(config):
    """Configure pytest with custom settings."""
    # Add custom markers
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "compatibility: Backward compatibility tests")
    config.addinivalue_line("markers", "performance: Performance tests")
    config.addinivalue_line("markers", "slow: Tests that take a long time")


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers automatically."""
    for item in items:
        # Auto-mark tests based on directory structure
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "compatibility" in str(item.fspath):
            item.add_marker(pytest.mark.compatibility)
        elif "performance" in str(item.fspath):
            item.add_marker(pytest.mark.performance)
        elif "tools" in str(item.fspath) or "agents" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
