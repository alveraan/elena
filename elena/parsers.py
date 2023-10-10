"""
There are four PEG parsers in this module:
- MapHeaderParser: parses the header part of map .entities files (Version,
                   HierarchyVersion and optional properties)
- EntityParser: parses a single entity
- DeclParser: parses a single decl
- MapEntitiesParserDeprecated: kept here in caes I decide to work on it again
                               later.

The main class to use, however, is MapEntitiesParser, which handles
everything. It splits the header from the rest and parses it using
MapHeaderParser. It then splits up all the entity declarations and uses
EntityParser to parse each one and uses python's ProcessPoolExecutor to put
the result in a list of dictionaries that each represent an entity.

MapEntitiesParser's parse methods return an EnitiesMap instance (see the
entities module).

Thanks go to Pizzaandy for the inspiration to use parsimonious and parallelism.
"""
import re

from concurrent.futures import ProcessPoolExecutor

from parsimonious.grammar import Grammar
from parsimonious.grammar import NodeVisitor
from parsimonious.nodes import Node

from models import EntitiesMap


class MapEntitiesParser:
    """
    Parses Doom Eternal map .entities data line by line and
    returns an EntitiesMap instance.

    If header data for Version and HierarchyVersion is missing,
    the version and hierarchy_version will be set to -1, while
    the properties will be an empty list.
    """
    def __init__(self, debug:bool=False) -> None:
        self.re_block_comment = re.compile(r'/\*.*?\*/', flags=re.DOTALL)
        self.re_entity_start = re.compile(r'entity\s*{', flags=re.MULTILINE)
        self.header_parser = MapHeaderParser(debug=debug)
        self.entity_parser = EntityParser(debug=debug)
        self.debug = debug

    def parse_file(self, filepath:str) -> EntitiesMap:
        with open(filepath) as f:
            txt = f.read()
        return self.parse(txt)

    def parse(self, txt:str) -> EntitiesMap:
        self.map = EntitiesMap()
        entities_raw = []
        txt = self.re_block_comment.sub(r'', txt)
        segments = self.re_entity_start.split(txt)
        
        for segment in segments:
            if segment.lstrip().startswith('Version'):
                self._parse_header(segment)
            elif segment != '':
                entities_raw.append(f'entity {{{segment}')
        
        with ProcessPoolExecutor() as executor:
            self.map.entities = list(executor.map(self.entity_parser.parse, entities_raw))
        
        return self.map
    
    def _parse_header(self, header:str) -> None:
        version, h_version, props = self.header_parser.parse(header)
        self.map.version = version
        self.map.hierarchy_version = h_version
        self.map.properties = props


class MapHeaderParser:
    """
    Parses the header section of a map .enttiies file.

    It only accepts the header text, so do not pass any entity
    declarations to it.
    """
    GRAMMAR = r"""
        DOCUMENT = VERSION? HIERARCHY_VERSION? PROPERTIES? WS?

        VERSION           = WS? "Version" " "+ INT " "* NL
        HIERARCHY_VERSION = WS? "HierarchyVersion" " "+ INT " "* NL
        PROPERTIES        = WS? "properties" WS? "{" PROP_ASSIGNMENT+ "}"
        PROP_ASSIGNMENT   = WS? STR WS? "=" WS? STR WS?
        
        NL = ~r"\n|\r|\r\n"
        WS  = ~r"\s+"
        STR = '"' ~r"[^\"]*" '"'
        INT = ~r"[-]?\d+"
    """
    def __init__(self, debug:bool=False) -> None:
        self.grammar = Grammar(self.GRAMMAR)
        self.debug = debug

    def parse(self, txt:str) -> tuple:
        tree = self.grammar.parse(txt)
        self.visitor = self.MapHeaderVisitor(debug=self.debug)

        return self.visitor.visit(tree)

    class MapHeaderVisitor(NodeVisitor):
        def __init__(self, debug:bool=False) -> None:
            self.debug = debug
        
        def visit_DOCUMENT(self, _, visited_children:list) -> tuple:
            # VERSION HIERARCHY_VERSION PROPERTIES? WS?
            version, h_version, properties, _ = visited_children
            
            if isinstance(version, Node):
                version = -1
            else:
                version = version[0]
            
            if isinstance(h_version, Node):
                h_version = -1
            else:
                h_version = h_version[0]

            if isinstance(properties, Node):
                properties = []
            
            return version, h_version, properties

        def visit_VERSION(self, _, visited_children:list) -> int:
            #  WS? "Version" " "+ INT " "* NL
            _, _, _, version, _, _ = visited_children
            return version
        
        def visit_HIERARCHY_VERSION(self, _, visited_children:list) -> int:
            # WS? "HierarchyVersion" " "+ INT " "* NL
            _, _, _, hierarchy_version, _, _ = visited_children
            return hierarchy_version
        
        def visit_PROPERTIES(self, _, visited_children:list) -> list:
            # WS? "properties" WS? "{" PROP_ASSIGNMENT+ "}"
            _, _, _, _, props, _ = visited_children
            return props[0]
        
        def visit_PROP_ASSIGNMENT(self, _, visited_children:list) -> dict:
            # WS? STR WS? "=" WS? STR WS?
            _, key, _, _, _, value, _ = visited_children
            prop = {key: value}
            if self.debug:
                print('PROP_ASSIGNMENT::', prop)
            return prop

        def visit_STR(self, _, visited_children:list) -> str:
            # '"' ~r"[^\"]*" '"'
            _, txt, _ = visited_children
            return txt.text

        def visit_INT(self, node:Node, _) -> int:
            return int(node.text)
        
        def generic_visit(self, node:Node, visited_children:list) -> list|Node:
            return visited_children or node


class EntityParser:
    """
    Parses a _single_ entity declaration into a dictionary

    Note that this parser removes both line and block comments. Line comments
    start with // and end at the end of the line. This will be removed by the
    parser. Block comments start with /*, can span multiple lines, and end with
    */. The parser will remove those, along with everything in between.
    """
    GRAMMAR = r"""
        DOCUMENT = ENTITY

        ENTITY         = "entity{" ENTITY_CONTENT "}"
        ENTITY_CONTENT = LAYERS_BLOCK? ASSIGNMENT* ENTITYDEF_BLOCK

        LAYERS_BLOCK    = "layers{" LAYER+ "}"
        ENTITYDEF_BLOCK = "entityDef" " "+ VAR_NAME "{" ASSIGNMENT* "}"
        
        LAYER      = STR WS?
        ASSIGNMENT = VAR_NAME "=" (OBJECT / LITERAL)
        OBJECT     = "{" ASSIGNMENT+ "}"
        LITERAL    = (NR / INT / STR / NULL / BOOL) ";"
        
        VAR_NAME    = ~r"[\w\[\]]+"

        WS = ~r"\s+"

        STR        = '"' ~r"[^\"]*" '"'
        NR         = ~r"[+\-]?(?:0|[1-9]\d*)(?:\.\d*)?(?:[eE][+\-]?\d+)?"
        INT        = ~r"[-]?\d+"
        BOOL       = "true" / "false"
        NULL       = "NULL"
    """

    def __init__(self, debug:bool=False) -> None:
        self.re_line_comment = re.compile(r'\s*//.*$',
                                          flags=re.MULTILINE)
        self.re_block_comment = re.compile(r'/\*.*?\*/',
                                           flags=re.DOTALL)
        self.re_ws_replace_before = re.compile(r'\s*([;=\{\}])')
        self.re_ws_replace_after = re.compile(r'([;=\{\}])\s*')

        self.grammar = Grammar(self.GRAMMAR)
        self.debug = debug

    def parse(self, txt:str) -> dict:
        txt = self._preprocess(txt)
        tree = self.grammar.parse(txt)
        self.visitor = self.EntityVisitor(debug=self.debug)

        return self.visitor.visit(tree)

    def _preprocess(self, txt:str) -> str:
        txt = txt.strip()
        txt = self.re_line_comment.sub(r'', txt)
        txt = self.re_block_comment.sub(r'', txt)
        txt = self.re_ws_replace_before.sub(r'\1', txt)
        txt = self.re_ws_replace_after.sub(r'\1', txt)
        
        return txt

    class EntityVisitor(NodeVisitor):
        def __init__(self, debug:bool=False) -> None:
            self.map = EntitiesMap()
            self.debug = debug
        
        def visit_DOCUMENT(self, _, visited_children:list) -> list:
            return visited_children
            
        def visit_ENTITY(self, _, visited_children:list) -> dict:
            # "entity{" ENTITY_CONTENT "}"
            _, content, _ = visited_children
            if self.debug:
                print('ENTITY:: content:', content)
            return content
            
        def visit_ENTITY_CONTENT(self, _, visited_children:list) -> dict:
            # LAYERS_BLOCK? ASSIGNMENT* ENTITYDEF_BLOCK
            layers, assigns, entitydef = visited_children

            if isinstance(layers, Node) and layers.text == '':
                layers = []
            else:
                layers = layers[0]
            assigns = dict(assigns) if type(assigns) == list else {}
            content = {'layers': layers, **assigns, **entitydef}
            
            if self.debug:
                print('ENTITY_CONTENT::', content)
            return content
        
        def visit_LAYERS_BLOCK(self, _, visited_children:list) -> list:
            # "layers{" LAYER+ "}"
            _, layers, _ = visited_children
            
            if self.debug:
                print('LAYERS_BLOCK::', layers)
            return layers
        
        def visit_LAYER(self, _, visited_children:list) -> str:
            # STR WS?
            layer, _ = visited_children
            if self.debug:
                print('LAYER::', layer)
            return layer

        def visit_ENTITYDEF_BLOCK(self, _, visited_children:list) -> dict:
            # "entityDef " VAR_NAME "{" ASSIGNMENT+ "}"
            _, _, var_name, _, assigns, _ = visited_children
            assigns = dict(assigns)
            entitydef = {'entityDef %s' % var_name: assigns}

            if self.debug:
                print('EDITIYDEF_BLOCK::', entitydef)
            return entitydef

        def visit_ASSIGNMENT(self, _, visited_children:list) -> tuple:
            # VAR_NAME "=" (OBJECT / LITERAL)
            var, _, obj_lit = visited_children
            if self.debug:
                print('ASSIGNMENT:: var:', var[0], 'obj_lit:', obj_lit[0])
            return var, obj_lit[0]

        def visit_OBJECT(self, _, visited_children:list) -> dict:
            # "{" ASSIGNMENT+ "}"
            _, assigns, _ = visited_children
            if self.debug:
                print('OBJECT:: assings:', dict(assigns))
            return dict(assigns)

        def visit_LITERAL(self, _,
                          visited_children:list) -> float|int|str|None|bool:
            # (NR / INT / STR / NULL / BOOL) ";"
            value, _ = visited_children
            return value[0]

        def visit_VAR_NAME(self, node:Node, _) -> str:
            # ~r"[\w\[\]]+"
            if self.debug:
                print('VAR_NAME:: value:', node.text)
            return node.text

        def visit_STR(self, _, visited_children:list) -> str:
            # '"' ~r"[^\"]*" '"'
            _, txt, _ = visited_children
            return txt.text

        def visit_NR(self, node:Node, _) -> int|float:
            if float(node.text).is_integer():
                return int(float(node.text))
            else:
                return float(node.text)

        def visit_INT(self, node:Node, _) -> int:
            return int(node.text)

        def visit_BOOL(self, node:Node, _) -> bool:
            return node.text == "true"

        def visit_NULL(self, _node, _visited_children) -> None:
            return None
        
        def generic_visit(self, node:Node, visited_children:list) -> list|Node:
            return visited_children or node


class MapEntitiesParserDeprecated:
    """
    DO NOT USE

    This parser works, but with one restriction. It replaces
    any amount of whitespace with one space before parsing.
    This will change any whitespace in string literals like
    "my value is    separated   by lots of   spaces",
    which is not ideal.
    """
    GRAMMAR = r"""
        DOCUMENT = VERSION_LINES? PROPERTIES? ENTITY+

        VERSION_LINES = "Version " INT NL "HierarchyVersion " INT NL

        PROPERTIES      = "properties{" PROP_ASSIGNMENT+ "}"
        PROP_ASSIGNMENT = STR "=" STR

        ENTITY         = "entity{" ENTITY_CONTENT "}"
        ENTITY_CONTENT = LAYERS_BLOCK? ASSIGNMENT* ENTITYDEF_BLOCK

        LAYERS_BLOCK    = "layers{" LAYER+ "}"
        ENTITYDEF_BLOCK = "entityDef " VAR_NAME "{" ASSIGNMENT+ "}"
        
        LAYER      = STR " "?
        ASSIGNMENT = VAR_NAME "=" (OBJECT / LITERAL)
        OBJECT     = "{" ASSIGNMENT+ "}"
        LITERAL    = (NR / INT / STR / NULL / BOOL) ";"
        
        VAR_NAME    = ~r"[\w\[\]]+"

        NL = ~r'\n'

        STR        = '"' ~r"[^\"]*" '"'
        NR         = ~r"[+\-]?(?:0|[1-9]\d*)(?:\.\d*)?(?:[eE][+\-]?\d+)?"
        INT        = ~r"[-]?\d+"
        BOOL       = "true" / "false"
        NULL       = "NULL"
    """

    def __init__(self, debug=False):
        self.re_versions_ws = re.compile(r'^\s*(Version|HierarchyVersion) ([0-9])\s*\n')
        self.re_line_comment = re.compile(r'//.+(?=\n|\r|\r\n)')
        self.re_ws_replace_before = re.compile(r'\s*([;=\{\}])')
        self.re_ws_replace_after = re.compile(r'([;=\{\}])\s*')
        self.re_two_or_more_ws = re.compile(r'\s{2,}')

        self.grammar = Grammar(self.GRAMMAR)

        self.debug = debug

    def parse_file(self, filepath):
        with open(filepath) as f:
            txt = f.read()

        return self.parse(txt)

    def preprocess(self, txt):
        txt = self.re_versions_ws.sub(r'\1 \2\n', txt)
        txt = self.re_line_comment.sub('', txt)
        txt = self.re_ws_replace_before.sub(r'\1', txt)
        txt = self.re_ws_replace_after.sub(r'\1', txt)
        txt = self.re_two_or_more_ws.sub(' ', txt)

        return txt

    def parse(self, txt):
        txt = self.preprocess(txt)
        tree = self.grammar.parse(txt)
        self.visitor = self.MapEntitiesVisitor(debug=self.debug)

        return self.visitor.visit(tree)
    
    class MapEntitiesVisitor(NodeVisitor):
        def __init__(self, debug=False):
            self.map = EntitiesMap()
            self.debug = debug
        
        def visit_DOCUMENT(self, node, visited_children):
            return self.map

        def visit_VERSION_LINES(self, node, visited_children):
            # "Version " INT NL "HierarchyVersion " INT NL
            _, version, _, _, hierarchy_version, _ = visited_children
            self.map.version = version
            self.map.hierarchy_version = hierarchy_version
        
        def visit_PROP_ASSIGNMENT(self, node, visited_children):
            # STR "=" STR
            key, _, value = visited_children
            prop = {key: value}
            if self.debug:
                print('PROP_ASSIGNMENT::', prop)
            self.map.properties.append(prop)
            
        def visit_ENTITY(self, node, visited_children):
            # "entity{" ENTITY_CONTENT "}"
            _, content, _ = visited_children
            if self.debug:
                print('ENTITY:: content:', content)
            self.map.entities.append(content)
            
        def visit_ENTITY_CONTENT(self, node, visited_children):
            # LAYERS_BLOCK? ASSIGNMENT* ENTITYDEF_BLOCK
            layers, assigns, entitydef = visited_children

            if isinstance(layers, Node) and layers.text == '':
                layers = []
            else:
                layers = layers[0]
            assigns = dict(assigns) if type(assigns) == list else {}
            content = {'layers': layers, **assigns, **entitydef}
            
            if self.debug:
                print('ENTITY_CONTENT::', content)
            return content
        
        def visit_LAYERS_BLOCK(self, node, visited_children):
            # "layers{" LAYER+ "}"
            _, layers, _ = visited_children
            
            if self.debug:
                print('LAYERS_BLOCK::', layers)
            return layers
        
        def visit_LAYER(self, node, visited_children):
            # STR WS?
            layer, _ = visited_children
            if self.debug:
                print('LAYER::', layer)
            return layer

        def visit_ENTITYDEF_BLOCK(self, node, visited_children):
            # "entityDef " VAR_NAME "{" ASSIGNMENT+ "}"
            _, var_name, _, assigns, _ = visited_children
            assigns = dict(assigns)
            entitydef = {'entityDef %s' % var_name: assigns}

            if self.debug:
                print('EDITIYDEF_BLOCK::', entitydef)
            return entitydef

        def visit_ASSIGNMENT(self, node, visited_children):
            # VAR_NAME "=" (OBJECT / LITERAL)
            var, _, obj_lit = visited_children
            if self.debug:
                print('ASSIGNMENT:: var:', var[0], 'obj_lit:',
                      obj_lit[0])
            return var, obj_lit[0]

        def visit_OBJECT(self, node, visited_children):
            # "{" ASSIGNMENT+ "}"
            _, assigns, _ = visited_children
            if self.debug:
                print('OBJECT:: assings:', dict(assigns))
            return dict(assigns)

        def visit_LITERAL(self, node, visited_children):
            # (NR / INT / STR / NULL / BOOL) ";"
            value, _ = visited_children
            return value[0]

        def visit_VAR_NAME(self, node, visited_children):
            # ~r"[\w\[\]]+"
            if self.debug:
                print('VAR_NAME:: value:', node.text)
            return node.text

        def visit_STR(self, node, visited_children):
            # '"' ~r"[^\"]*" '"'
            _, txt, _ = visited_children
            return txt.text

        def visit_NR(self, node, visited_children):
            if float(node.text).is_integer():
                return int(float(node.text))
            else:
                return float(node.text)

        def visit_INT(self, node, visited_children):
            return int(node.text)

        def visit_BOOL(self, node, visited_children):
            return node.text == "true"

        def visit_NULL(self, node, visited_children):
            return None
        
        def generic_visit(self, node, visited_children):
            return visited_children or node
