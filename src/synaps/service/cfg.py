from typing import Any, Iterable, Mapping, List

from synaps.service.err import MissingConfigurationField, InvalidConfiguration


class Config:

    def __init__(self, field_path: str, data: Mapping):
        self.field_path = field_path
        self._data = data

    def get(self, key: str, default: Any = None) -> Any:
        value = self._data.get(key, default)
        return self._convert_value(f"{self.field_path}.{key}", value)

    def get_list(self, key: str) -> List:
        value = self._data.get(key)
        if value is None:
            return []
        if isinstance(value, str):
            raise InvalidConfiguration(f"`{self.field_path}.{key}` must be a list, not a string")
        if not isinstance(value, Iterable):
            raise InvalidConfiguration(f"`{self.field_path}.{key}` must be iterable")
        return [self._convert_value(f"{self.field_path}.{key}[{i}]", item) for i, item in enumerate(value)]

    def __getitem__(self, key: str) -> Any:
        if key not in self._data:
            raise MissingConfigurationField(f"{self.field_path}.{key}")
        return self._convert_value(f"{self.field_path}.{key}", self._data[key])

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def _convert_value(self, field_path: str, value: Any) -> Any:
        if isinstance(value, Mapping):
            return Config(field_path, value)
        if isinstance(value, Iterable) and not isinstance(value, str):
            return [self._convert_value(f"{field_path}[{i}]", item) for i, item in enumerate(value)]

        return value

    def __iter__(self):
        raise InvalidConfiguration(f"`{self.field_path}` configuration field must be iterable")

    def __repr__(self):
        return f"Config('{self.field_path}', {self._data})"
