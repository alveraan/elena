"""
Defines a data class repesenting a map .entities file.
"""
class EntitiesMap:
    def __init__(self) -> None:
        self.version = -1
        self.hierarchy_version = -1
        self.properties = []
        self.entities = []
    
