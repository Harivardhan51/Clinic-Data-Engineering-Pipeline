from pathlib import Path
import yaml


class ConfigManager:
    """
    Loads and provides access to pipeline configuration.
    """

    def __init__(self, config_path="config/config.yaml"):
        self.config_path = Path(config_path)

        if not self.config_path.exists():
            raise FileNotFoundError(
                f"Configuration file not found: {self.config_path}"
            )

        with open(self.config_path, "r", encoding="utf-8") as file:
            self.config = yaml.safe_load(file)

    def get(self, key, default=None):
        """
        Get a top-level configuration value.
        """
        return self.config.get(key, default)

    def get_nested(self, *keys, default=None):
        """
        Get a nested configuration value.

        Example:
            config.get_nested("database", "host")
        """
        value = self.config

        for key in keys:
            if not isinstance(value, dict):
                return default

            value = value.get(key)

            if value is None:
                return default

        return value

    def get_database_config(self):
        """
        Return PostgreSQL database configuration.
        """
        return self.config["database"]

    def get_paths(self):
        """
        Return path configuration.
        """
        return self.config["paths"]

    def get_tables(self):
        """
        Return table configuration.
        """
        return self.config["tables"]