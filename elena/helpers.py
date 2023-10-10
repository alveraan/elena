"""
These helper functions are designed to work with the data structure returned
by the parsers from the parsers module.
"""
import re


class EntityHelper:
    def __init__(self) -> None:
        self.re_item_key = re.compile(r'item\[(\d+)\]')

    def get_entitydef_key(self, entity:dict) -> str:
        for key in entity:
            if key.startswith('entityDef '):
                return key
        raise Exception('No entityDef found')

    def get_def_name(self, entity:dict) -> str:
        key = self.get_entitydef_key(entity)
        def_name = key.split(' ')[1].strip()

        return def_name
    
    def get_class(self, entity:dict, entitydef_key:str=None) -> str:
        if entitydef_key is None:
            entitydef_key = self.get_entitydef_key(entity)
        entity_def = entity[entitydef_key]
        for key in entity_def.keys():
            if key == 'class':
                return entity_def[key]

    def get_inherit(self, entity:dict, entitydef_key:str=None) -> str:
        if entitydef_key is None:
            entitydef_key = self.get_entitydef_key(entity)
        entity_def = entity[entitydef_key]
        for key in entity_def.keys():
            if key == 'inherit':
                return entity_def[key]

    def fix_item_arrays_simple(self, txt:str) -> str:
        """
        will try to quickly fix item[] array ordering, but will NOT fix the
        num = x; declarations. Condition: one item[x] declaration per line
        """
        lines = txt.splitlines()
        line_count = len(lines)
        level = 0
        result = ''
        counters = {0: {'num': -1, 'counter': 0, 'buffer': ''}}
        for idx, line in enumerate(lines):
            if level not in counters:
                counters[level] = {'num_idx': -1, 'counter': 0, 'buffer': ''}

            if self.re_item.search(line):
                line = self.re_item.sub(f"item[{counters[level]['counter']}] =", line)
                counters[level]['counter'] += 1

            level_change = line.count('{') - line.count('}')
            level += level_change

            if self.re_num.search(line):
                counters[level]['num_idx'] = idx
                counters[level]['counter'] = 0

            result += line
            if idx < line_count - 1:
                result += '\n'

        return result

    def fix_item_arrays_entity(self, data:dict) -> dict:
        new_data = {}
        num_key = None
        index = 0
        for key, value in data.items():
            if key == 'num' and not isinstance(value, dict):
                num_key = key
            elif self.re_item_key.match(key):
                key = f'item[{index}]'
                index += 1
            
            if isinstance(value, dict):
                new_data[key] = self.fix_item_arrays_entity(value)
            else:
                new_data[key] = value
        
        if num_key:
            new_data[num_key]= index
        
        return new_data
