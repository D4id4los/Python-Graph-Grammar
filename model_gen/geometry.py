"""
This file contains classes and functions to use in geometric
calculations such as vectors and matrices and the usual operations
performed with them.
"""

import math


class Vec:

    def __init__(self, v1=None, v2=None,
                 x1: float=None, y1: float=None,
                 x2: float=None, y2: float=None):
        if v1 is not None and v2 is None:
            self.x = float(v1.attr['x'])
            self.y = float(v1.attr['y'])
        elif v2 is not None and v2 is not None:
            self.x = float(v2.attr['x']) - float(v1.attr['x'])
            self.y = float(v2.attr['y']) - float(v1.attr['y'])
        elif ((x1 is not None and y1 is not None)
              and (x2 is None and y2 is None)):
            self.x = x1
            self.y = y1
        elif ((x1 is not None and y1 is not None)
               and (x2 is not None and y2 is not None)):
            self.x = x2 - x1
            self.y = y2 - y1
        else:
            raise ValueError

    def __add__(self, other):
        x = self.x + other.x
        y = self.y + other.y
        return Vec(x1=x, y1=y)

    def __radd__(self, other):
        return self + other

    def __sub__(self, other):
        x = self.x - other.x
        y = self.y - other.y
        return Vec(x1=x, y1=y)

    def __rsub__(self, other):
        return self - other

    def __mul__(self, other):
        if isinstance(other, Vec):
            return self.x * other.x + self.y * other.y
        elif isinstance(other, int) or isinstance(other, float):
            return Vec(x1=self.x*other, y1=self.y*other)
        else:
            return NotImplemented

    def __rmul__(self, other):
        return self * other

    def __truediv__(self, other):
        if isinstance(other, int) or isinstance(other, float):
            return Vec(x1=self.x/other, y1=self.y/other)
        else:
            return NotImplemented

    def __eq__(self, other):
        return self.x == other.x and self.y == other.y


def norm(vec: Vec):
    return math.sqrt(vec.x*vec.x + vec.y*vec.y)


def perp_left(vec: Vec):
    return Vec(x1=-vec.y, y1=vec.x)


def perp_right(vec: Vec):
    return Vec(x1=vec.y, y1=-vec.x)


def calc_angle(vec1: Vec, vec2: Vec):
    angle = math.acos((vec1 * vec2) / (norm(vec1) * norm(vec2)))
    return angle

