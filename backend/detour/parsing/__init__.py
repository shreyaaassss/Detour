"""Turn a dispatcher's own words into a structured disruption, safely.

An interpreted report is only ever a *proposal*: it is checked against the scenario (unknown places and
vehicles are rejected, never guessed), previewed, and applied only after the dispatcher confirms.
"""
