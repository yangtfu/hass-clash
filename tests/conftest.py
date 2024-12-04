"""Fixtures for testing."""

import pytest
from pytest_socket import enable_socket, disable_socket, socket_allow_hosts

@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations."""
    return

@pytest.hookimpl(trylast=True)
def pytest_runtest_setup():
    enable_socket()
    socket_allow_hosts(["127.0.0.1", "localhost", "::1", "192.168.0.123"], allow_unix_socket=True)