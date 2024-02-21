"""Custom exceptions."""


class SetupError(Exception):
    """Exception for when there is an issue with setting up a component."""


class ConfigError(Exception):
    """Exception for when the configuration is invalid."""
