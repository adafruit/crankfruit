"""Standalone Crankfruit. No computer required for play or audio."""
import supervisor
supervisor.runtime.autoreload = False
from crankfruit import main
main()
