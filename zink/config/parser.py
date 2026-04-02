import yaml
from pathlib import Path

class ConfigError(Exception):
    pass

def load_yaml(path:str | Path)-> dict:
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    
    with path.open() as f:
        content = yaml.safe_load(f)

    if content is None:
        return {}
    
    if not isinstance(content,dict):
        raise ConfigError(f"Config must be a YAML mapping, got {type(content).__name__}: {path}")
    
    return content
