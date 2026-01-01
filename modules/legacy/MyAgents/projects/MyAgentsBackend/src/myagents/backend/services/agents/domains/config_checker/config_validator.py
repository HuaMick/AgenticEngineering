"""Configuration file validator for MyAgents.

This module provides validation functions for the agent-gcptoolkit config file.
It checks file existence, format, required sections, and required fields.
"""

import os
import yaml  # type: ignore[import-untyped]
from pathlib import Path
from typing import Tuple, List


def validate_config_file(config_path: str) -> Tuple[bool, List[str]]:
    """
    Validate that config file exists and is a valid YAML file.

    Args:
        config_path: Absolute path to config file

    Returns:
        Tuple of (is_valid, list_of_errors)
        - is_valid: True if file exists and is valid YAML, False otherwise
        - list_of_errors: List of error messages (empty if valid)

    Example:
        >>> valid, errors = validate_config_file("/path/to/config.yml")
        >>> if not valid:
        ...     for error in errors:
        ...         print(f"Error: {error}")
    """
    errors = []

    # Check if file exists
    if not os.path.exists(config_path):
        errors.append(f"Config file not found at: {config_path}")
        return False, errors

    # Check if it's a file (not a directory)
    if not os.path.isfile(config_path):
        errors.append(f"Config path is not a file: {config_path}")
        return False, errors

    # Check if file is readable
    if not os.access(config_path, os.R_OK):
        errors.append(f"Config file is not readable: {config_path}")
        return False, errors

    # Try to parse as YAML
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        errors.append(f"Config file is not valid YAML: {e}")
        return False, errors
    except Exception as e:
        errors.append(f"Failed to read config file: {e}")
        return False, errors

    # Check if file is empty
    if not config:
        errors.append("Config file is empty")
        return False, errors

    return True, errors


def validate_config_sections(config_path: str) -> Tuple[bool, List[str]]:
    """
    Validate that config file has required sections.

    Required sections:
    - authentication
    - gcp

    Args:
        config_path: Absolute path to config file

    Returns:
        Tuple of (is_valid, list_of_errors)
        - is_valid: True if all required sections exist, False otherwise
        - list_of_errors: List of error messages (empty if valid)

    Example:
        >>> valid, errors = validate_config_sections("/path/to/config.yml")
    """
    errors = []

    # First validate file exists and is valid YAML
    file_valid, file_errors = validate_config_file(config_path)
    if not file_valid:
        return False, file_errors

    # Load config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Check for required sections
    if 'authentication' not in config:
        errors.append("Missing required section: 'authentication'")

    if 'gcp' not in config:
        errors.append("Missing required section: 'gcp'")

    is_valid = len(errors) == 0
    return is_valid, errors


def validate_config_fields(config_path: str) -> Tuple[bool, List[str]]:
    """
    Validate that config file has all required fields.

    Required fields:
    - authentication.type
    - authentication.service_account_path
    - gcp.project_id

    Args:
        config_path: Absolute path to config file

    Returns:
        Tuple of (is_valid, list_of_errors)
        - is_valid: True if all required fields exist and are valid, False otherwise
        - list_of_errors: List of error messages (empty if valid)

    Example:
        >>> valid, errors = validate_config_fields("/path/to/config.yml")
    """
    errors = []

    # First validate sections exist
    sections_valid, sections_errors = validate_config_sections(config_path)
    if not sections_valid:
        return False, sections_errors

    # Load config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Validate authentication section fields
    auth = config.get('authentication', {})

    if 'type' not in auth:
        errors.append("Missing required field: 'authentication.type'")
    elif auth['type'] != 'service_account':
        errors.append(f"Invalid authentication type: '{auth['type']}' (only 'service_account' is supported)")

    if 'service_account_path' not in auth:
        errors.append("Missing required field: 'authentication.service_account_path'")

    # Validate gcp section fields
    gcp = config.get('gcp', {})

    if 'project_id' not in gcp:
        errors.append("Missing required field: 'gcp.project_id'")
    elif not gcp['project_id']:
        errors.append("Field 'gcp.project_id' is empty")

    is_valid = len(errors) == 0
    return is_valid, errors


def validate_service_account(config_path: str) -> Tuple[bool, List[str]]:
    """
    Validate that service account file exists and is readable.

    Args:
        config_path: Absolute path to config file

    Returns:
        Tuple of (is_valid, list_of_errors)
        - is_valid: True if service account file exists and is readable, False otherwise
        - list_of_errors: List of error messages (empty if valid)

    Example:
        >>> valid, errors = validate_service_account("/path/to/config.yml")
    """
    errors = []

    # First validate fields exist
    fields_valid, fields_errors = validate_config_fields(config_path)
    if not fields_valid:
        return False, fields_errors

    # Load config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Get service account path
    service_account_path = config['authentication']['service_account_path']

    # Validate service account file
    if not os.path.exists(service_account_path):
        errors.append(f"Service account file not found at: {service_account_path}")
        return False, errors

    if not os.path.isfile(service_account_path):
        errors.append(f"Service account path is not a file: {service_account_path}")
        return False, errors

    if not os.access(service_account_path, os.R_OK):
        errors.append(f"Service account file is not readable: {service_account_path}")
        return False, errors

    # Try to parse as JSON (service account files are JSON)
    try:
        import json
        with open(service_account_path, 'r') as f:
            sa_data = json.load(f)

        # Basic validation of service account structure
        required_fields = ['type', 'project_id', 'private_key', 'client_email']
        missing_fields = [field for field in required_fields if field not in sa_data]

        if missing_fields:
            errors.append(f"Service account file is missing required fields: {', '.join(missing_fields)}")
            return False, errors

        if sa_data.get('type') != 'service_account':
            sa_type = sa_data.get('type')
            errors.append(f"Service account file has invalid type: '{sa_type}' (expected 'service_account')")
            return False, errors

    except json.JSONDecodeError as e:
        errors.append(f"Service account file is not valid JSON: {e}")
        return False, errors
    except Exception as e:
        errors.append(f"Failed to read service account file: {e}")
        return False, errors

    is_valid = len(errors) == 0
    return is_valid, errors


def validate_config(config_path: str) -> Tuple[bool, List[str]]:
    """
    Run complete validation on config file.

    This is the main entry point for config validation. It runs all validation
    checks in sequence:
    1. File exists and is valid YAML
    2. Required sections exist
    3. Required fields exist and are valid
    4. Service account file exists and is valid

    Args:
        config_path: Absolute path to config file

    Returns:
        Tuple of (is_valid, list_of_errors)
        - is_valid: True if all validations pass, False otherwise
        - list_of_errors: List of all error messages (empty if valid)

    Example:
        >>> valid, errors = validate_config("/path/to/config.yml")
        >>> if valid:
        ...     print("Configuration is valid")
        ... else:
        ...     for error in errors:
        ...         print(f"Error: {error}")
    """
    # Run all validation checks
    # validate_service_account calls all previous checks, so we only need to call it
    return validate_service_account(config_path)
