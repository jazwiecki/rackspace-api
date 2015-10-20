from __future__ import absolute_import
from rackspace_api.rackspace_api import Connection, RackspaceError, Error
__version__ = '0.1'
__author__ = "Jim Jazwiecki <jim.jazwiecki@gmail.com>"
__all__ = ["Connection", "RackspaceError", "Error"]
__doc__ = """
This is a python library for the Rackspace

all methods raise RackspaceError on an unexpected response, or a problem with input
format
"""
