import random
import logging
import logging.config
import yaml
import os
from typing import Iterable, Sized

logging_configured = False


class Bidict(dict):
    """
    This class implements a bidirectional dict, where the other
    direction can be obtained by bi_dict.inverse.

    This comes from https://stackoverflow.com/a/21894086.
    """
    def __init__(self, *args, **kwargs):
        super(Bidict, self).__init__(*args, **kwargs)
        self.inverse = {}
        for key, value in self.items():
            self.inverse.setdefault(value, []).append(key)

    def __setitem__(self, key, value):
        if key in self:
            self.inverse[self[key]].remove(key)
        super(Bidict, self).__setitem__(key, value)
        self.inverse.setdefault(value, []).append(key)

    def __delitem__(self, key):
        self.inverse.setdefault(self[key], []).remove(key)
        if self[key] in self.inverse and not self.inverse[self[key]]:
            del self.inverse[self[key]]
        super(Bidict, self).__delitem__(key)


class UniqueBidict(dict):
    """
    This class is based on the above Bidict to not use a list in the inverse.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.inverse = {}
        for key, value in self.items():
            self.inverse[value] = key

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.inverse[value] = key

    def __delitem__(self, key):
        self.inverse.pop(self[key])
        super().__delitem__(key)


class Mapping(UniqueBidict):
    """
    Maps the elements of one graph to the elements of another graph.

    This mapping can be empty, if there is no correspondence of elements or
    it can be a bijection.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __eq__(self, other):
        return self.__dict__ == other.__dict__

    # TODO: Check if inserted types match,
    # e.g. Edge -> Edge, but not Vert -> Edge

    def to_yaml(self) -> Iterable:
        """
        Return a dict or list giving a representation of the mapping
        fit for export with yaml.

        In this case this means use object ids rather than objects themselves.

        :return: A representation of a Match in list or dict.
        """
        fields = {'dict': {id(k): id(v) for k, v in self.items()},
                  'id': id(self)}
        return fields

    # noinspection PyDefaultArgument
    @staticmethod
    def from_yaml(data, mapping={}) -> 'Mapping':
        """
        Deserialize a Mapping from a list or dict which was saved in
        a yaml file.

        The mapping argument does not need to be specified, it will
        be filled automatically unless you have a specific requirement.

        :param data: The list or dict containing the Mapping data.
        :param mapping: A dictionary which will be used to recreate
            references between objects.
        """
        if data['id'] in mapping:
            return mapping[data['id']]
        result = Mapping()
        for key, value in data['dict'].items():
            result[mapping[key]] = mapping[value]
        mapping[data['id']] = result
        return result


class Singleton(type):
    """
    This class is a meta class used to make other classes singletons.

    Usage:
    > class MyClass(metaclass=Singleton):
    >     pass
    """
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton,
                                        cls).__call__(*args, **kwargs)
        return cls._instances[cls]


def randomly(objects: Sized and Iterable):
    shuffled = list(objects)
    random.shuffle(shuffled)
    return shuffled


def config_logging():
    this_dir = os.path.dirname(__file__)
    with open(os.path.join(this_dir, 'logging_config.yml'), 'r') as file:
        log_conf_dict = yaml.safe_load(file)
    logging.config.dictConfig(log_conf_dict)


def get_logger(name, handler=None):
    if not logging_configured:
        config_logging()
    logger = logging.getLogger(name)
    if handler is None:
        logger.addHandler(logging.NullHandler())
    else:
        logger.addHandler(handler)
    return logger
