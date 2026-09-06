"""Core domain library for graph-augmented conversational memory.

Import direction is strictly one-way:

    schema  <-  persistence
            <-  llm
            <-  graph
            <-  retrieval  <-  pipeline

Nothing in ``core`` imports from ``evaluation``, ``app`` or ``scripts``. Those
are consumers. Keeping that arrow one-directional is what guarantees the system
the thesis evaluates and the system the app demonstrates are the same system.
"""

__version__ = "0.3.0"