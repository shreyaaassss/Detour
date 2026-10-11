"""The escalation call: when a driver does not answer the app within 60 seconds, an automated phone agent calls them.

The agent only reads out the engine's own script and takes one clear answer, by voice or keypad. Calls are opt-in, go
only to numbers listed in .env, and are capped. Everything here also works with no phone line: the dispatcher's
"simulate the call" buttons drive the same code path.
"""
