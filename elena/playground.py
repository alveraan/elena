"""
Just a playground to play around with the different classes.
"""
import sys
import re

from parsers import MapEntitiesParser, EntityParser
from helpers import EntityHelper
from indexing import EntityPositionIndexer


if __name__ == '__main__':
    pass # do whatever you want here

    re_mat_coords = re.compile(r'mat\[\d+\]\s*=\s*{(.+?)}', re.DOTALL)
    txt = """
    spawnOrientation = {
    mat = {
        mat[0] = {
        x = -9.53674203e-07;
        y = -1;
        z = -8.00937343e-08;
        }fdsf
        mat[1] = {
        x = 0.998742223;
        y = -9.56490567e-07;
        z = 0.0501395427;
        }
        mat[2] = {
        x = -0.0501395427;
        y = -3.2176203e-08;
        z = 0.998742223;
        }
    }
    """
    txt = re_mat_coords.sub('', txt)
    print(txt)
    