"""
This file contains all functionality related to reading and saving
options for Model Gen.
"""

import yaml
import os
from model_gen.utils import Singleton, get_logger
from model_gen.exceptions import ModelGenInvalidValueError

log = get_logger('model_gen.' + __name__)


class Opts(dict, metaclass=Singleton):
    """
    This class saves all options during the programs execution.
    """
    __slots__ = ()
    """
    By default a class inheriting from dict will duplicate all values
    once inside the dicts storage and once inside the __dict__ 
    variable. Setting the __slots__ variable inhibits this behaviour.
    """
    OPTS_FILE_PATH = 'opts.yml'

    def __init__(self, *args, **kwargs):
        super(Opts, self).__init__(*args, **kwargs)
        try:
            this_dir = os.path.dirname(__file__)
            with open(os.path.join(this_dir, self.OPTS_FILE_PATH), 'r',
                      encoding='utf-8') as stream:
                data = yaml.safe_load(stream)
                if not isinstance(data, dict):
                    log.error(f'The data in {self.OPTS_FILE_PATH} is malformed'
                              f' (is not a dict) and cannot be used.')
                    raise ModelGenInvalidValueError
                self.update(data)
        except IOError as e:
            log.error(f'Error reading Options: Cannot open file '
                      f'{self.OPTS_FILE_PATH} for reading.')
            raise e

    def save(self, file_path=None) -> None:
        """
        Saves all options into a yaml file
        """
        try:
            if file_path is None:
                this_dir = os.path.dirname(__file__)
                file_path = os.path.join(this_dir, self.OPTS_FILE_PATH)
            with open(file_path, 'w', encoding='utf-8') as stream:
                yaml.safe_dump(dict(self), stream)
        except IOError as e:
            log.error(f'Error writing Options: Cannot open file '
                      f'{self.OPTS_FILE_PATH} for writing.')
            raise e




