"""Anki add-on entry point; pure modules remain importable without Anki."""
try:
    import aqt
except ModuleNotFoundError as error:
    if error.name != 'aqt':
        raise
else:
    from .akb.integration import install
    install(__name__)
