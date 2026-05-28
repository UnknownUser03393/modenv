from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any
import hashlib

from dacite import from_dict, Config

from modenv.Environment import EnvironmentSchemaBase


class MissingEnvironmentFileError(FileNotFoundError): pass


class UnexpectedEnvironmentFileVariableError(Exception): pass


class EnvironmentLoader:
	@staticmethod
	def _get_schema_hash(schema_name: str) -> str:
		"""根据 schema 名称生成短 hash"""
		return hashlib.md5(schema_name.encode()).hexdigest()[:6]

	@staticmethod
	def _to_env_key(field_name: str, schema_name: str) -> str:
		"""将代码中的字段名转为环境变量 key（大写 + hash）"""
		field_upper = field_name.upper()
		schema_hash = EnvironmentLoader._get_schema_hash(schema_name)
		return f"{field_upper}_{schema_hash}"

	@staticmethod
	def _from_env_key(env_key: str, schema_name: str) -> str | None:
		"""将环境变量 key 转回字段名，如果不是当前 schema 的则返回 None"""
		schema_hash = EnvironmentLoader._get_schema_hash(schema_name)
		suffix = f"_{schema_hash}"

		if env_key.endswith(suffix):
			# 去掉后缀，转回原始大小写（这里无法还原大小写，假设都是大写）
			original = env_key[:-len(suffix)]
			return original.lower()  # 转为小写 snake_case
		return None

	@staticmethod
	def _loadEnvironmentBySchema[T: EnvironmentSchemaBase](cls: type[T], data: dict[str, Any]) -> T:
		field_names = {field.name for field in fields(cls)}
		unexpected = sorted(set(data) - field_names)
		if unexpected:
			raise UnexpectedEnvironmentFileVariableError(
				f"Unexpected variables for {cls.__name__}: {', '.join(unexpected)}"
			)
		return from_dict(data_class=cls, data=data, config=Config(cast=[int, bool]))  # type: ignore

	@staticmethod
	def _parseEnvironmentFile(file: str | Path, schema_name: str) -> dict[str, str]:
		"""解析环境文件，将带 hash 的环境变量 key 转回字段名"""
		path = Path(file)
		if not path.exists():
			raise MissingEnvironmentFileError(f"Environment file not found: {path}")

		data: dict[str, str] = {}
		with open(path, encoding="utf-8") as f:
			for raw_line in f:
				line = raw_line.strip()
				if not line or line.startswith("#"):
					continue
				if len(parts := line.split("=", 1)) != 2:
					continue
				env_key = parts[0].strip()
				if not env_key:
					continue

				# 尝试将环境变量 key 转回字段名
				field_name = EnvironmentLoader._from_env_key(env_key, schema_name)
				if field_name:
					data[field_name] = parts[1].strip()
		return data

	@staticmethod
	def _getDefaultValuesFromSchema[T: EnvironmentSchemaBase](cls: type[T]) -> dict[str, Any]:
		"""从 schema 中提取默认值"""
		defaults = {}
		for field in fields(cls):
			if field.default != field.default_factory:
				defaults[field.name] = field.default
			elif field.default_factory is not None:
				defaults[field.name] = field.default_factory()
		return defaults

	@staticmethod
	def _createEnvironmentFileFromSchema[T: EnvironmentSchemaBase](cls: type[T], file: str | Path) -> None:
		path = Path(file)
		path.parent.mkdir(parents=True, exist_ok=True)

		defaults = EnvironmentLoader._getDefaultValuesFromSchema(cls)
		schema_name = cls.__name__
		schema_hash = EnvironmentLoader._get_schema_hash(schema_name)

		with open(path, 'w', encoding="utf-8") as f:
			f.write(f"# Environment file for {schema_name}\n")
			f.write(f"# Schema hash: {schema_hash}\n")
			f.write(f"# Generated automatically\n\n")

			for field in fields(cls):
				value = defaults.get(field.name)

				if value is None:
					value_str = ""
				elif isinstance(value, bool):
					value_str = str(value).lower()
				else:
					value_str = str(value)

				env_key = EnvironmentLoader._to_env_key(field.name, schema_name)
				f.write(f"{env_key}={value_str}\n")

		print(f"Created environment file: {path}")

	@staticmethod
	def loadEnvironmentBySchema[T: EnvironmentSchemaBase](cls: type[T], file: str | Path) -> T:
		schema_name = cls.__name__
		parsed_data = EnvironmentLoader._parseEnvironmentFile(file, schema_name)
		instance = EnvironmentLoader._loadEnvironmentBySchema(cls, parsed_data)
		instance.__dict__['_file_path'] = Path(file)
		return instance

	@staticmethod
	def loadOptionalEnvironmentBySchema[T: EnvironmentSchemaBase](cls: type[T], file: str | Path) -> T | None:
		path = Path(file)
		if not path.exists():
			return None
		return EnvironmentLoader.loadEnvironmentBySchema(cls, path)

	@staticmethod
	def loadOrCreateEnvironmentBySchema[T: EnvironmentSchemaBase](cls: type[T], file: str | Path) -> T:
		"""加载环境文件，如果不存在则根据 schema 创建并写入默认值"""
		path = Path(file)
		if not path.exists():
			EnvironmentLoader._createEnvironmentFileFromSchema(cls, path)
		return EnvironmentLoader.loadEnvironmentBySchema(cls, path)