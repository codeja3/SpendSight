import pytest
from src.python.config import load_profile

def test_load_valid_profile(tmp_path):
    # 1. Setup: Create a temporary yaml file simulating our configs.yaml
    yaml_content = """
profiles:
  test_bank:
    skip_rows: 1
    sign_multiplier: -1
    column_mapping:
      Transaction Date: date
      Details: raw_description
      Value: amount
    """
    config_file = tmp_path / "configs.yaml"
    config_file.write_text(yaml_content)

    # 2. Execute: Load the profile
    profile = load_profile("test_bank", str(config_file))

    # 3. Verify: Check that Pydantic properly cast and loaded the values
    assert profile.skip_rows == 1
    assert profile.sign_multiplier == -1
    assert profile.column_mapping["Value"] == "amount"

def test_load_invalid_profile_fails(tmp_path):
    # Setup: A config file that doesn't contain the requested profile
    yaml_content = """
profiles:
  other_bank:
    skip_rows: 0
    sign_multiplier: 1
    column_mapping: {}
    """
    config_file = tmp_path / "configs.yaml"
    config_file.write_text(yaml_content)

    # Verify: The system must fail-fast with a clear error
    with pytest.raises(ValueError, match="Profile 'missing_bank' not found"):
        load_profile("missing_bank", str(config_file))