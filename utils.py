import random
from typing import Iterable


def randomly(objects: Iterable):
    shuffled = random.shuffle(list(objects))
    return shuffled