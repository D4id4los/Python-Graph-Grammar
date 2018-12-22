"""
This file contains classes and functions to use in geometric
calculations such as vectors and matrices and the usual operations
performed with them.
"""

import math


class Vec:

    def __init__(self, v1=None, v2=None,
                 x1: float=None, y1: float=None,
                 x2: float=None, y2: float=None,
                 vec1: 'Vec'=None, vec2: 'Vec'=None):
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
        elif vec1 is not None and vec2 is None:
            self.x = vec1.x
            self.y = vec1.y
        elif vec1 is not None and vec2 is not None:
            self.x = vec2.x - vec1.x
            self.y = vec2.y - vec1.y
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

    def __repr__(self):
        return f'Vec(x1={self.x},y1={self.y})'


def norm(vec: Vec) -> float:
    return math.sqrt(vec.x*vec.x + vec.y*vec.y)


def normalize(vec: Vec) -> Vec:
    return vec / norm(vec)


def cross(vec1: Vec, vec2: Vec) -> float:
    return vec1.x*vec2.y - vec1.y*vec2.x


def perp_left(vec: Vec) -> Vec:
    return Vec(x1=-vec.y, y1=vec.x)


def perp_right(vec: Vec) -> Vec:
    return Vec(x1=vec.y, y1=-vec.x)


def angle(vec1: Vec, vec2: Vec) -> float:
    angle = math.acos((vec1 * vec2) / (norm(vec1) * norm(vec2)))
    return angle


def rotate(vec: Vec, radians: float, center: Vec=Vec(x1=0, y1=0)) -> Vec:
    temp_vec = vec - center
    result = Vec(x1=0,y1=0)
    result.x = temp_vec.x * math.cos(radians) - temp_vec.y * math.sin(radians)
    result.y = temp_vec.x * math.sin(radians) + temp_vec.y * math.cos(radians)
    result = result + center
    return result
