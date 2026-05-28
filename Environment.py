# Environment.py
from abc import ABC
from dataclasses import fields
from pathlib import Path
from typing import final


class EnvironmentSchemaBase(ABC):
	_file_path: Path | None = None

	@final
	def save(self):
		print('save')
		if self._file_path is None:
			raise RuntimeError("No file path associated. Load via EnvironmentLoader first.")

		schema_name = self.__class__.__name__
		import hashlib
		schema_hash = hashlib.md5(schema_name.encode()).hexdigest()[:6]

		path = Path(self._file_path)
		path.parent.mkdir(parents=True, exist_ok=True)

		with open(path, 'w', encoding="utf-8") as f:
			f.write(f"# Environment file for {schema_name}\n")
			f.write(f"# Schema hash: {schema_hash}\n")
			f.write(f"# Generated automatically\n\n")
	
			# noinspection
			for field in fields(self): # type: ignore
				value = getattr(self, field.name)

				if value is None:
					value_str = ""
				elif isinstance(value, bool):
					value_str = str(value).lower()
				else:
					value_str = str(value)

				field_upper = field.name.upper()
				env_key = f"{field_upper}_{schema_hash}"
				f.write(f"{env_key}={value_str}\n")