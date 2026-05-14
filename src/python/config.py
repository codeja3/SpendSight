import yaml
from pathlib import Path
from pydantic import BaseModel, ValidationError

# Our strict Pydantic model for a bank profile
class BankProfile(BaseModel):
    skip_rows: int
    sign_multiplier: int
    column_mapping: dict[str, str]
    date_format: str = "%Y-%m-%d" # Default to ISO if not specified

def load_profile(profile_name: str, config_path: str = "configs.yaml") -> BankProfile:
    """Loads and validates a specific bank profile from the YAML config."""
    path = Path(config_path)
    
    # Defensive Programming: Fail-fast if the file doesn't exist
    if not path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
    with open(path, 'r', encoding='utf-8') as f:
        try:
            config_data = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Failed to parse YAML file: {e}")

    profiles = config_data.get("profiles", {})
    
    # Defensive Programming: Fail-fast if the specific profile is missing
    if profile_name not in profiles:
        raise ValueError(f"Profile '{profile_name}' not found in {config_path}. Please add it.")
        
    profile_data = profiles[profile_name]
    
    # Pydantic automatically validates the dictionary against our BankProfile schema
    try:
        return BankProfile(**profile_data)
    except ValidationError as e:
        raise ValueError(f"Invalid profile configuration for '{profile_name}': {e}")