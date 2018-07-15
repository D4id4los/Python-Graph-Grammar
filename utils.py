import random
from typing import Iterable, Sized


class Bidict(dict):
    """
    This class implements a bidirectional dict, where the other direction can be optained by bi_dict.inverse.

    This comes from https://stackoverflow.com/a/21894086.
    """
    def __init__(self, *args, **kwargs):
        super(Bidict, self).__init__(*args, **kwargs)
        self.inverse = {}
        for key, value in self.items():
            self.inverse.setdefault(value,[]).append(key)

    def __setitem__(self, key, value):
        if key in self:
            self.inverse[self[key]].remove(key)
        super(Bidict, self).__setitem__(key, value)
        self.inverse.setdefault(value,[]).append(key)

    def __delitem__(self, key):
        self.inverse.setdefault(self[key],[]).remove(key)
        if self[key] in self.inverse and not self.inverse[self[key]]:
            del self.inverse[self[key]]
        super(Bidict, self).__delitem__(key)


def randomly(objects: Sized and Iterable):
    if len(objects) == 1:
        return objects
    shuffled = random.shuffle(list(objects))
    return shuffled
