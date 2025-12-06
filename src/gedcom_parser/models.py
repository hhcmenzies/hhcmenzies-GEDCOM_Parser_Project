"""
Data models for structured GEDCOM objects.
Future:
- Individual
- Family
- Event
- Source
- Relationship graphs
"""

class Individual:
    def __init__(self, id, name):
        self.id = id
        self.name = name
