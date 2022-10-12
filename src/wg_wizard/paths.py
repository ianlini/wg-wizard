from pathlib import Path


def get_config_path(config_dir, interface) -> Path:
    return Path(config_dir, f"{interface}.yml")


def get_secret_path(config_dir, interface) -> Path:
    return Path(config_dir, f"{interface}_secret.json")
