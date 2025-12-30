"""Input validation for CLI arguments."""
import re
import sys


def validate_secret_name(name: str) -> None:
    """
    Validate secret name matches GCP requirements.

    GCP Secret Manager allows only: [a-zA-Z0-9_-]

    Args:
        name: Secret name to validate

    Raises:
        SystemExit with code 2 if validation fails
    """
    if not name:
        print("Error: Secret name cannot be empty", file=sys.stderr)
        print("\nSecret names must match: [a-zA-Z0-9_-]", file=sys.stderr)
        sys.exit(2)

    # GCP secret name format: alphanumeric, underscores, hyphens only
    pattern = r'^[a-zA-Z0-9_-]+$'

    if not re.match(pattern, name):
        print(f"Error: Invalid secret name '{name}'", file=sys.stderr)
        print("\nAllowed characters: letters, numbers, underscores (_), hyphens (-)", file=sys.stderr)
        print("Not allowed: dots (.), spaces, special characters (@, $, !, etc.)", file=sys.stderr)
        print("\nExamples of valid names:", file=sys.stderr)
        print("  ✓ MY_SECRET", file=sys.stderr)
        print("  ✓ api-key-prod", file=sys.stderr)
        print("  ✓ DATABASE_PASSWORD_123", file=sys.stderr)
        print("\nExamples of invalid names:", file=sys.stderr)
        print("  ✗ api.key (contains dot)", file=sys.stderr)
        print("  ✗ MY SECRET (contains space)", file=sys.stderr)
        print("  ✗ test@prod (contains @)", file=sys.stderr)
        sys.exit(2)


def validate_secret_value(value: str) -> None:
    """
    Validate secret value is not empty.

    GCP Secret Manager does not allow empty secret payloads.

    Args:
        value: Secret value to validate

    Raises:
        SystemExit with code 2 if validation fails
    """
    if not value or value.strip() == "":
        print("Error: Secret value cannot be empty", file=sys.stderr)
        print("\nGCP Secret Manager does not allow empty secret payloads.", file=sys.stderr)
        print("If you need a placeholder, use a special value like 'UNSET' or 'TODO'.", file=sys.stderr)
        sys.exit(2)
