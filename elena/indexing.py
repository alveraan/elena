from math import sqrt


class EntityListItemIndexer:
    """
    Very simple reverse indexer for entities data. The data is assumed to be
    a dictionary of key/value pairs. The key is the entity def name
    (a string) and the value is a dict that contains the key 'entity'. The
    corresponding value for the 'entity' key is the actual entity data as
    returned by EntityParser.
    
    This is a little different than what the parsers in the parsers module
    return, so a coversion might be necessary before using this indexer.
    This indexer was created when the gui started to use a dictionary for
    its list data instead of a list. Note: The older indexer,
    EntityPositionIndexer, still works directly with the structure returned
    by the parsers, but as it hasn't been used by the gui for some time,
    doesn't have as many methods as this indexer.
    
    Stores various dictionaries whose keys are tokens. Each key is associated
    with a set of 0 to n entity def names.

    This basically allows to find out quickly what entities contain a specific
    token.

    The following dictionaries are populated:
    - self._layers: contains all entity layers
    - self._classes: contains all entity classes
    - self._inherits: contains all entity inherits
    - self._spawn_positions: contains all spawn positions in the entire data
                             structure. Useful for distance searches.
    - self._keys: contains all keys in the entire data structure.
    - self._values: contains all values in the entire data structure.
    
    Use the find_*(txt, partial) methods to return a sorted list entity def
    names. Setting partial to True will also return partial results, meaning
    the searched value must contain the given txt. If partial is False, the
    searched value must be exactly the given txt. Partial searches are
    slower, so avoid if you don't really need them.

    Note that all tokens are stored in lowercase form and searches are
    converted to lowercase.
    """
    def __init__(self, entities:dict|None=None) -> None:
        self.intialize_indices()
        if entities is not None:
            self.index(entities)
    
    def intialize_indices(self) -> None:
        """
        Empties all indices
        """
        self._unique_layers = set()
        self._unique_defs = set()
        self._unique_classes = set()
        self._unique_inherits = set()
        self._unique_spawn_positions = set()

        self._entities_without_layers = set()
        self._layers = {}
        self._classes = {}
        self._inherits = {}
        self._spawn_positions = {}
        self._keys = {}
        self._values = {}

    def index(self, items:dict) -> None:
        for def_name, values in items.items():
            if not self._entity_has_layers(values['entity']):
                self._entities_without_layers.add(def_name)
            self._index_entity(values['entity'], def_name)

    def remove(self, def_names:list) -> None:
        for def_name in def_names:
            if def_name in self._unique_defs:
                self._unique_defs.remove(def_name)
            if def_name in self._entities_without_layers:
                self._entities_without_layers.remove(def_name)
            self._remove_from_index(self._layers, def_name)
            self._remove_from_index(self._classes, def_name)
            self._remove_from_index(self._inherits, def_name)
            self._remove_from_index(self._spawn_positions, def_name)
            self._remove_from_index(self._keys, def_name)
            self._remove_from_index(self._values, def_name)

    def _entity_has_layers(self, entity:dict) -> bool:
        if 'layers' in entity:
            value = entity['layers']
            if isinstance(value, list) and len(value) > 0:
                return True
        return False

    def _index_entity(self, entity:dict, def_name:str) -> None:
        for key, value in entity.items():
            value_type = type(value)
            self._add_to_index(self._keys, key, def_name, value_type)
            
            if key == 'layers' and value_type is list:
                for layer in value:
                    self._unique_layers.add(layer)
                    self._add_to_index(self._layers, layer, def_name,
                                       value_type)
            elif value_type == dict:
                if key.startswith('entityDef') and key != 'entityDefs':
                    def_name = key.split(' ')[1]
                    self._unique_defs.add(def_name)
                    self._add_to_index(self._values, def_name, def_name,
                                       value_type)
                elif key == 'spawnPosition':
                    required_keys = set(['x', 'y', 'z'])
                    if set(value.keys()) == required_keys:
                        x = value['x']
                        y = value['y']
                        z = value['z']
                        pos_str = f'{x}x{y}x{z}'
                        self._unique_spawn_positions.add(pos_str)
                        self._add_to_index(self._spawn_positions,
                                           pos_str, def_name,
                                           value_type)
                self._index_entity(value, def_name)
            else:
                if key == 'class':
                    self._unique_classes.add(value)
                    self._add_to_index(self._classes, value, def_name,
                                       value_type)
                elif key == 'inherit':
                    self._unique_inherits.add(value)
                    self._add_to_index(self._inherits, value, def_name,
                                       value_type)
                self._add_to_index(self._values, value, def_name,
                                   value_type)

    def _add_to_index(self, index_dict:dict, value:str|bool|None,
                      def_name:str, value_type:str|bool|int|float) -> None:
        if value is None: value = 'null'
        elif value_type is bool:
            if value: value = 'true'
            else: value = 'false'
        else: value = str(value).lower()

        if value not in index_dict:
            index_dict[value] = set()
        index_dict[value].add(def_name)
    
    def _remove_from_index(self, index_dict:dict, def_name:str) -> None:
        for _, def_names in index_dict.items():
            def_names.discard(def_name)

    def get_unique_defs(self) -> list:
        return list(self._unique_defs)

    def get_unique_layers(self) -> list:
        return list(self._unique_layers)
    
    def get_unique_classes(self) -> list:
        return list(self._unique_classes)
    
    def get_unique_inherits(self) -> list:
        return list(self._unique_inherits)

    def get_unique_spawn_positions(self) -> list:
        return list(self._unique_spawn_positions)

    def get_entities_without_layers(self) -> list:
        return list(self._entities_without_layers)

    def find_key(self, txt:str, partial:bool=False) -> list:
        return self._find_in_index('_keys', txt, partial)

    def find_value(self, txt:str, partial:bool=False) -> list:
        return self._find_in_index('_values', txt, partial)

    def find_def(self, txt:str, partial:bool=False) -> list:
        return self._find_in_index('_defs', txt, partial)
   
    def find_layer(self, txt:str, partial:bool=False) -> list:
        return self._find_in_index('_layers', txt, partial)

    def find_class(self, txt:str, partial:bool=False) -> list:
        return self._find_in_index('_classes', txt, partial)
    
    def find_inherit(self, txt:str, partial:bool=False) -> list:
        return self._find_in_index('_inherits', txt, partial)
    
    def find_surrounding_spawn_positions(self, search_pos_str:str,
                                         max_distance:int|float) -> list:
        search_pos = tuple(map(float, search_pos_str.split('x')))
        neighbors = set()
        for compare_pos_str in self._spawn_positions.keys():
            compare_pos = tuple(map(float, compare_pos_str.split('x')))
            if self.get_distance(search_pos, compare_pos) < max_distance:
                neighbors.update(self._spawn_positions[compare_pos_str])

        return sorted(neighbors)
    
    def get_distance(self, p1:tuple, p2:tuple) -> float:
        x1, y1, z1 = p1
        x2, y2, z2 = p2

        return sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)

    def _find_in_index(self, index:str, txt:str, partial:bool=False) -> list:
        txt = txt.lower()
        search_index = getattr(self, index, None)
        if search_index is None:
            raise ValueError(f"No index named {index} found.")
        
        if partial:
            def_names = set()
            for key in search_index:
                if txt in key:
                    def_names.update(search_index[key])
            return list(def_names)
        else:
            if txt in search_index:
                return list(search_index[txt])
            return []


class EntityPositionIndexer:
    """
    Very simple reverse indexer for entities data returned by a parser in the
    parsers module.

    Stores various dictionaries whose keys are tokens. Each key is associated
    with a set of 0 to n positions (indexes) in the list of entities in the
    data structure (position as returned by enumerate).

    This basically allows to find out quickly what entities contain a specific
    token. The position / path of the tokens inside the individual entities
    is not stored, but this could be possible in the future if the need arises.

    The following dictionaries are populated:
    - self._defs: contains all entityDef identifiers
    - self._layers: contains all entity layers
    - self._classes: contains all entity classes
    - self._inherits: contains all entity inherits
    - self._spawn_positions: contains all spawn positions in the entire data
                             structure. Useful for distance searches.
    - self._keys: contains all keys in the entire data structure.
    - self._values: contains all values in the entire data structure.
    
    Use the find_*(txt, partial) methods to return a sorted list of positions.
    Setting partial to True will also return partial results, meaning the
    searched value must contain the given txt. If partial is False, the
    searched value must be exactly the given txt. Partial searches are
    slower, so avoid if you don't really need them.

    Note that all tokens are stored in lowercase form and searches are converted
    to lowercase.
    """
    def __init__(self, entities:list|None=None) -> None:
        if entities is not None:
            self.index(entities)

    def index(self, entities:list) -> None:
        self._unique_layers = set()
        self._unique_defs = set()
        self._unique_classes = set()
        self._unique_inherits = set()
        self._unique_spawn_positions = set()
        
        self._defs = {}
        self._layers = {}
        self._classes = {}
        self._inherits = {}
        self._spawn_positions = {}
        self._keys = {}
        self._values = {}

        for position, entity in enumerate(entities):
            self._index_entity(entity, position)

    def _index_entity(self, entity:dict, position:int) -> None:
        for key, value in entity.items():
            value_type = type(value)
            self._add_to_index(self._keys, key, position, value_type)
            
            if key == 'layers' and value_type is list:
                for layer in value:
                    self._unique_layers.add(layer)
                    self._add_to_index(self._layers, layer, position,
                                       value_type)
            elif value_type == dict:
                if key.startswith('entityDef') and key != 'entityDefs':
                    def_name = key.split(' ')[1]
                    self._unique_defs.add(def_name)
                    self._add_to_index(self._defs, def_name, position,
                                       value_type)
                    self._add_to_index(self._values, def_name, position,
                                       value_type)
                elif key == 'spawnPosition':
                    required_keys = set(['x', 'y', 'z'])
                    if set(value.keys()) == required_keys:
                        x = value['x']
                        y = value['y']
                        z = value['z']
                        pos_str = f'{x}x{y}x{z}'
                        self._unique_spawn_positions.add(pos_str)
                        self._add_to_index(self._spawn_positions, pos_str,
                                           position, value_type)
                self._index_entity(value, position)
            else:
                if key == 'class':
                    self._unique_classes.add(value)
                    self._add_to_index(self._classes, value, position,
                                       value_type)
                elif key == 'inherit':
                    self._unique_inherits.add(value)
                    self._add_to_index(self._inherits, value, position,
                                       value_type)
                self._add_to_index(self._values, value, position, value_type)

    def _add_to_index(self, index_dict:dict, value:str|bool|None,
                      position:int, value_type:str|bool|int|float) -> None:
        if value is None: value = 'null'
        elif value_type is bool:
            if value: value = 'true'
            else: value = 'false'
        else: value = str(value).lower()

        if value not in index_dict:
            index_dict[value] = set()
        index_dict[value].add(position)

    def get_unique_defs(self) -> list:
        return list(self._unique_defs)

    def get_unique_layers(self) -> list:
        return list(self._unique_layers)
    
    def get_unique_classes(self) -> list:
        return list(self._unique_classes)
    
    def get_unique_inherits(self) -> list:
        return list(self._unique_inherits)

    def get_unique_spawn_positions(self) -> list:
        return list(self._unique_spawn_positions)

    def find_key(self, txt:str, partial:bool=False) -> list:
        return self._find_in_index('_keys', txt, partial)

    def find_value(self, txt:str, partial:bool=False) -> list:
        return self._find_in_index('_values', txt, partial)

    def find_def(self, txt:str, partial:bool=False) -> list:
        return self._find_in_index('_defs', txt, partial)
   
    def find_layer(self, txt:str, partial:bool=False) -> list:
        return self._find_in_index('_layers', txt, partial)

    def find_class(self, txt:str, partial:bool=False) -> list:
        return self._find_in_index('_classes', txt, partial)
    
    def find_inherit(self, txt:str, partial:bool=False) -> list:
        return self._find_in_index('_inherits', txt, partial)
    
    def find_surrounding_spawn_positions(self, search_pos_str:str,
                                         max_distance:int|float) -> list:
        search_pos = tuple(map(float, search_pos_str.split('x')))
        neighbors = set()
        for compare_pos_str in self._spawn_positions.keys():
            compare_pos = tuple(map(float, compare_pos_str.split('x')))
            if self.get_distance(search_pos, compare_pos) < max_distance:
                neighbors.update(self._spawn_positions[compare_pos_str])

        return sorted(neighbors)
    
    def get_distance(self, p1:tuple, p2:tuple) -> float:
        x1, y1, z1 = p1
        x2, y2, z2 = p2

        return sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)

    def _find_in_index(self, index:str, txt:str, partial:bool=False) -> list:
        txt = txt.lower()
        search_index = getattr(self, index, None)
        if not search_index:
            raise ValueError(f"No index named {index} found.")
        
        if partial:
            indices = set()
            for key in search_index:
                if txt in key:
                    indices.update(search_index[key])
            return sorted(indices)
        else:
            if txt in search_index:
                return sorted(search_index[txt])
            return []
