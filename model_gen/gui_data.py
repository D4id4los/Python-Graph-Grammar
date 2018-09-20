import wx
import abc
from typing import Dict

from model_gen.grammar import Grammar


class GuiData(abc.ABC):
    """
    All Classes used to save/wrap data for use inside the GUI inherit
    from this class.
    """
    def __init__(self, name=''):
        self.name = name

    def to_yaml(self) -> Dict:
        """
        Serialize this object into a list or dict for export into
        a yaml file.

        :return: A dict representing the GuiData object.
        """
        fields = {
            'name': self.name,
            'id': id(self)
        }
        return fields

    @staticmethod
    def from_yaml(data, mapping=None) -> 'GuiData':
        """
        Deserialize a GuiData object from a dict, which could have
        been saved in a yaml file.

        :param data: A dict containing a serialized GuiData object.
        :param mapping: A dictionary of already recreated Objects, if
            this object refers to another object already in the
            mapping, then the object from the mapping is used instead
            of creating a new object.
        :return: A GuiData object containg the state of the
            serialized GuiData object.
        """
        if mapping is None:
            mapping = {}
        if data['id'] in mapping:
            return mapping[data['id']]
        result = GuiData()
        result.name = data['name']
        mapping[data['id']] = result
        return result


class GuiGrammar(GuiData):
    """
    This class is used to save the grammars used in the tree of
    productions.
    """
    def __init__(self, grammar: Grammar, name=''):
        super().__init__(name=name)
        self.grammar = grammar

    def to_yaml(self) -> Dict:
        """
        Serialize this object into a list or dict for export into
        a yaml file.

        :return: A dict representing the GuiGrammar.
        """
        result = super().to_yaml()
        fields = {
            'grammar': self.grammar.to_yaml(),
            'id': id(self)
        }
        result.update(fields)
        return result

    @staticmethod
    def from_yaml(data, mapping=None) -> 'GuiGrammar':
        """
        Deserialize a GuiGrammar object from a dict, which could have
        been saved in a yaml file.

        :param data: A dict containing a serialized GuiGrammar object.
        :param mapping: A dictionary of already recreated Objects, if
            this object refers to another object already in the
            mapping, then the object from the mapping is used instead
            of creating a new object.
        :return: A GuiGrammar object containg the state of the
            serialized GuiGrammar object.
        """
        if mapping is None:
            mapping = {}
        if data['id'] in mapping:
            return mapping[data['id']]
        result = super().from_yaml(data, mapping)
        result.__class__ = GuiGrammar
        result.grammar = Grammar.from_yaml(data, mapping)
        mapping[data['id']] = result
        return result
