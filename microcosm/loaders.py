"""
Configuration loading

A configuration loader is any function that accepts `Metadata` and
returns a `Configuration` object. Configuration might be loaded
from a file, from environment variables, or from an external service.
"""
from imp import new_module
from json import loads
from os import environ

from inflection import underscore

from microcosm.configuration import Configuration


def get_config_filename(metadata):
    """
    Derive a configuration file name from the FOO_SETTINGS
    environment variable.

    """
    envvar = "{}_SETTINGS".format(underscore(metadata.name).upper())
    try:
        return environ[envvar]
    except KeyError:
        return None


def _load_from_file(metadata, load_func):
    """
    Load configuration from a file.

    The file path is derived from an environment variable
    named after the service of the form FOO_SETTINGS.

    """
    config_filename = get_config_filename(metadata)
    if config_filename is None:
        return Configuration()

    with open(config_filename, "r") as file_:
        data = load_func(file_.read())
        return Configuration(data)


def load_from_json_file(metadata):
    """
    Load configuration from a JSON file.

    """
    return _load_from_file(metadata, loads)


def load_from_python_file(metadata):
    """
    Load configuration from a Python file.

    The file path is derived from an environment variable
    named after the service of the form FOO_SETTINGS.

    """
    def load_python_module(data):
        module = new_module("magic")
        exec data in module.__dict__, module.__dict__
        return {
            key: value
            for key, value in module.__dict__.items()
            if not key.startswith("_")
        }
    return _load_from_file(metadata, load_python_module)


def load_from_environ(metadata):
    """
    Load configuration from environment variables.

    Any environment variable prefixed with the metadata's name will be
    used to recursively set dictionary keys, splitting on '_'.

    """
    # We'll match the ennvar name against the metadata's name. The ennvar
    # name must be uppercase and hyphens in names converted to underscores.
    #
    # | envar       | name    | matches? |
    # +-------------+---------+----------+
    # | FOO_BAR     | foo     | yes      |
    # | FOO_BAR     | bar     | no       |
    # | foo_bar     | bar     | no       |
    # | FOO_BAR_BAZ | foo_bar | yes      |
    # | FOO_BAR_BAZ | foo-bar | yes      |
    # +-------------+---------+----------+

    prefix = metadata.name.upper().replace("-", "_").split("_")

    def matches_key(key_parts):
        return len(key_parts) > len(prefix) and key_parts[:len(prefix)] == prefix

    config = Configuration()
    for key, value in environ.items():
        key_parts = key.split("_")
        if not matches_key(key_parts):
            continue

        dct = config
        # for each part before the last
        for key_part in key_parts[len(prefix):-1]:
            # build up the nested dictionary structure
            dct[key_part.lower()] = dict()
            dct = dct[key_part.lower()]
        # set the value for the final part
        try:
            dct[key_parts[-1].lower()] = loads(value)
        except ValueError:
            dct[key_parts[-1].lower()] = value
    return config


def load_each(*loaders):
    """
    Loader factory that combines a series of loaders.

    """
    def _load_each(metadata):
        config = loaders[0](metadata)
        for loader in loaders[1:]:
            next_config = loader(metadata)
            config.merge(next_config)
        return config
    return _load_each
