"""
Common validation functions
"""


def require_string(value, value_name):
    """Require that value is a string

    :raises: TypeError

    """
    if not isinstance(value, str):
        raise TypeError(f'{value_name} must be a str or unicode str, but got {value!r}')


def require_callback(callback, callback_name='callback'):
    """Require that callback is callable and is not None

    :raises: TypeError

    """
    if not callable(callback):
        raise TypeError(f'callback {callback_name} must be callable, but got {callback!r}')


def rpc_completion_callback(callback):
    """Verify callback is callable if not None

    :returns: boolean indicating nowait
    :rtype: bool
    :raises: TypeError

    """
    if callback is None:
        # No callback means we will not expect a response
        # i.e. nowait=True
        return True

    if callable(callback):
        # nowait=False
        return False
    else:
        raise TypeError('completion callback must be callable if not None')


def zero_or_greater(name, value):
    """Verify that value is zero or greater. If not, 'name'
    will be used in error message

    :raises: ValueError

    """
    if int(value) < 0:
        errmsg = f'{name} must be >= 0, but got {value}'
        raise ValueError(errmsg)
