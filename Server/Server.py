"""
Compatibility shim for Render / Cloud deployments.
Resolves 'Server.app.main:app' when Root Directory is set to 'Server'.
"""
import sys
import app
import app.main

sys.modules["Server"] = sys.modules[__name__]
sys.modules["Server.app"] = app
sys.modules["Server.app.main"] = app.main
