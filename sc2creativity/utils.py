import os

__all__ = ('data_dir',)


def data_dir(*names):
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', *names))
