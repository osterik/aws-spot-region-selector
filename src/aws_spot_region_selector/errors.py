class SelectorError(Exception):
    """Base exception with a stable process exit code."""

    exit_code = 10


class ConfigError(SelectorError):
    exit_code = 2


class AwsAuthenticationError(SelectorError):
    exit_code = 3


class NoCandidatesError(SelectorError):
    exit_code = 4


class InsufficientDataError(SelectorError):
    exit_code = 5
