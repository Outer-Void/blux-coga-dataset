"""JSON Schemas for the dataset's own documents. `python -m dstool schemas --write` publishes them to schemas/."""

from __future__ import annotations

from typing import Any

from dstool.common import SPLITS, DsError

Schema = dict[str, Any]

SHA: Schema = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
SLUG: Schema = {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]{1,62}$"}
VARIANT: Schema = {"type": "string", "pattern": "^[0-9]{2}$"}
RECORD_ID: Schema = {"type": "string", "pattern": "^[a-z]{2}:[a-z0-9][a-z0-9-]{1,62}:[0-9]{2}$"}
DATE: Schema = {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"}
LICENSE: Schema = {
    "type": "object",
    "additionalProperties": False,
    "required": ["spdx", "name"],
    "properties": {
        "spdx": {"type": "string", "minLength": 1},
        "name": {"type": "string", "minLength": 1},
        "file": {"type": "string"},
    },
}
ENGINE: Schema = {
    "type": "object",
    "additionalProperties": False,
    "required": ["name", "package", "version", "commit"],
    "properties": {
        "name": {"type": "string"},
        "package": {"type": "string"},
        "version": {"type": "string"},
        "commit": {"type": "string", "pattern": "^[0-9a-f]{40}$"},
    },
}

CONFIG: Schema = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema",
        "dataset_id",
        "title",
        "version",
        "release_date",
        "summary",
        "license",
        "authors",
        "adapter",
        "engines",
        "id_prefix",
        "categories",
        "canary",
        "quality_threshold",
        "near_duplicate_threshold",
        "card",
    ],
    "properties": {
        "schema": {"const": "blux.dataset-config"},
        "dataset_id": SLUG,
        "title": {"type": "string"},
        "version": {"type": "string", "pattern": r"^[0-9]+\.[0-9]+\.[0-9]+$"},
        "release_date": DATE,
        "summary": {"type": "string"},
        "license": LICENSE,
        "authors": {"type": "array", "minItems": 1, "items": {"type": "string"}},
        "adapter": {"enum": ["coga", "ca"]},
        "engines": {"type": "array", "minItems": 1, "items": ENGINE},
        "id_prefix": {"type": "string", "pattern": "^[a-z]{2}$"},
        "categories": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "title", "description"],
                "properties": {"id": SLUG, "title": {"type": "string"}, "description": {"type": "string"}},
            },
        },
        "canary": {"type": "string", "pattern": "^[0-9a-f-]{36}$"},
        "quality_threshold": {"type": "number", "minimum": 0, "maximum": 1},
        "near_duplicate_threshold": {"type": "number", "exclusiveMinimum": 0, "maximum": 1},
        "card": {
            "type": "object",
            "additionalProperties": False,
            "required": ["pretty_name", "tags", "record_format", "intended_use", "out_of_scope", "limitations"],
            "properties": {
                "pretty_name": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "record_format": {"type": "string"},
                "intended_use": {"type": "array", "items": {"type": "string"}},
                "out_of_scope": {"type": "array", "items": {"type": "string"}},
                "limitations": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}

SEED: Schema = {
    "type": "object",
    "additionalProperties": False,
    "required": ["schema", "family", "category", "split", "origin", "review", "instruction", "input", "variants"],
    "properties": {
        "schema": {"const": "blux.dataset-seed"},
        "family": SLUG,
        "category": SLUG,
        "split": {"enum": list(SPLITS)},
        "origin": {"enum": ["synthetic-authored", "imported"]},
        "review": {
            "type": "object",
            "additionalProperties": False,
            "required": ["status"],
            "properties": {
                "status": {"enum": ["approved", "pending"]},
                "reviewer": {"type": "string", "minLength": 1},
                "note": {"type": "string"},
            },
        },
        "license": LICENSE,
        "source": {"type": "string", "description": "Where an imported seed came from."},
        "tags": {"type": "array", "items": SLUG, "uniqueItems": True},
        "instruction": {"type": "string", "minLength": 1, "maxLength": 4000},
        "input": {"type": "object"},
        "variants": {
            "type": "array",
            "minItems": 1,
            "maxItems": 99,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "params"],
                "properties": {
                    "id": VARIANT,
                    "params": {"type": "object"},
                    "retired": {"type": "boolean"},
                    "note": {"type": "string"},
                },
            },
        },
    },
}

QUALITY: Schema = {
    "type": "object",
    "additionalProperties": False,
    "required": ["score", "threshold", "components"],
    "properties": {
        "score": {"type": "number", "minimum": 0, "maximum": 1},
        "threshold": {"type": "number"},
        "components": {"type": "object", "additionalProperties": {"type": ["number", "null"]}},
    },
}


def record_schema(categories: list[str]) -> Schema:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema",
            "schema_version",
            "dataset",
            "dataset_version",
            "record_id",
            "family",
            "variant",
            "category",
            "split",
            "task",
            "input",
            "expected",
            "provenance",
            "quality",
            "hashes",
            "tags",
            "canary",
        ],
        "properties": {
            "schema": {"const": "blux.dataset-record"},
            "schema_version": {"const": 1},
            "dataset": SLUG,
            "dataset_version": {"type": "string"},
            "record_id": RECORD_ID,
            "family": SLUG,
            "variant": VARIANT,
            "category": {"enum": categories},
            "split": {"enum": list(SPLITS)},
            "task": {
                "type": "object",
                "additionalProperties": False,
                "required": ["instruction"],
                "properties": {"instruction": {"type": "string", "minLength": 20, "maxLength": 4000}},
            },
            "input": {"type": "object"},
            "expected": {"type": "object"},
            "provenance": {
                "type": "object",
                "additionalProperties": False,
                "required": ["origin", "authors", "license", "seed", "generator", "engines", "created", "review"],
                "properties": {
                    "origin": {"enum": ["synthetic-authored", "imported"]},
                    "authors": {"type": "array", "items": {"type": "string"}},
                    "license": LICENSE,
                    "seed": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["path", "sha256"],
                        "properties": {"path": {"type": "string"}, "sha256": SHA},
                    },
                    "source": {"type": "string"},
                    "generator": {"type": "object", "required": ["name", "version"]},
                    "engines": {"type": "array", "items": ENGINE},
                    "created": DATE,
                    "review": {
                        "type": "object",
                        "required": ["status"],
                        "properties": {"status": {"const": "approved"}},
                    },
                },
            },
            "quality": QUALITY,
            "hashes": {
                "type": "object",
                "additionalProperties": False,
                "required": ["input_sha256", "expected_sha256", "content_sha256"],
                "properties": {"input_sha256": SHA, "expected_sha256": SHA, "content_sha256": SHA},
            },
            "tags": {"type": "array", "items": SLUG},
            "canary": {"type": ["string", "null"]},
        },
    }


LOCK: Schema = {
    "type": "object",
    "additionalProperties": False,
    "required": ["schema", "dataset", "records"],
    "properties": {
        "schema": {"const": "blux.dataset-split-lock"},
        "dataset": SLUG,
        "records": {
            "type": "object",
            "propertyNames": {"pattern": RECORD_ID["pattern"]},
            "additionalProperties": {
                "type": "object",
                "additionalProperties": False,
                "required": ["split", "content_sha256", "status", "since"],
                "properties": {
                    "split": {"enum": list(SPLITS)},
                    "content_sha256": SHA,
                    "status": {"enum": ["active", "retired"]},
                    "since": {"type": "string"},
                },
            },
        },
    },
}

MANIFEST: Schema = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "schema",
        "dataset",
        "version",
        "release_date",
        "license",
        "generator",
        "engines",
        "canary",
        "splits",
        "categories",
        "files",
        "records_sha256",
        "record_count",
        "protected_splits",
        "training_splits",
        "excluded",
    ],
    "properties": {
        "schema": {"const": "blux.dataset-manifest"},
        "dataset": SLUG,
        "version": {"type": "string"},
        "release_date": DATE,
        "license": LICENSE,
        "generator": {"type": "object"},
        "engines": {"type": "array", "items": ENGINE},
        "canary": {"type": "string"},
        "splits": {"type": "object"},
        "categories": {"type": "object"},
        "files": {"type": "object", "additionalProperties": {"type": "object", "required": ["sha256", "records"]}},
        "records_sha256": SHA,
        "record_count": {"type": "integer", "minimum": 0},
        "protected_splits": {"type": "array"},
        "training_splits": {"type": "array"},
        "excluded": {"type": "array"},
    },
}


def check(schema: Schema, doc: Any, where: str) -> None:
    import jsonschema

    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(doc), key=lambda e: list(map(str, e.path)))
    if errors:
        e = errors[0]
        raise DsError("SCHEMA", f"{where}: /{'/'.join(map(str, e.path))}: {e.message}")
