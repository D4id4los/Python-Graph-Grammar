import random
from typing import Sequence

def randomly(seq: Sequence):
    shuffled = random.shuffle(list(seq))
    return shuffled