class ModelGenArgumentError(ValueError):
    """
    Raised when a function is called with an illegal argument.
    """


class ModelGenInvalidValueError(ValueError):
    """
    Raised when a function returns or encounters an invalid value.
    """


class ModelGenIncongruentGraphStateError(ValueError):
    """
    Raised when the state of a Graph becomes incongruent. E.g. when
    an Edge connects to a Vertex which does not exist inside the
    Graph.
    """