import pytest

from devtrack.database import get_connection, init_db


@pytest.fixture
def conn():
    """A fresh in-memory database with the schema created."""
    connection = get_connection(":memory:")
    init_db(connection)
    yield connection
    connection.close()