"""
Pydantic schemas for structured PVMAP generation output.

These schemas enable structured output from the LLM, which is then
deterministically converted to CSV format.
"""

from pydantic import BaseModel, Field
from typing import List


class PropertyValuePair(BaseModel):
    """A single property-value mapping."""

    property: str = Field(
        description="Data Commons property name (e.g., observationAbout, measuredProperty, value, unit)"
    )
    value: str = Field(
        description=(
            "Property value - use {Data} for pass-through string, "
            "{Number} for numeric, or dcid:XXX for Data Commons DCIDs"
        )
    )


class PVMAPRow(BaseModel):
    """A single PVMAP row mapping a key to properties."""

    key: str = Field(
        description=(
            "The key from input data - must match column header or cell value EXACTLY. "
            "Use Column:Value syntax for specific cell mappings."
        )
    )
    mappings: List[PropertyValuePair] = Field(
        description="List of property-value pairs for this key"
    )


class PVMAPOutput(BaseModel):
    """Structured PVMAP generation output."""

    format_detected: str = Field(
        description=(
            "'pre-formatted' if data has variableMeasured/observationAbout columns "
            "with existing DCIDs, otherwise 'raw'"
        )
    )
    pvmap_rows: List[PVMAPRow] = Field(
        description="List of PVMAP row mappings"
    )
    validation_notes: str = Field(
        description=(
            "Brief notes about mapping decisions and any assumptions made. "
            "Include notes about any data columns that were not mapped and why."
        )
    )
    confidence: str = Field(
        description="'high', 'medium', or 'low' based on data clarity and mapping certainty"
    )


# JSON Schema for use with Gemini's structured output
PVMAP_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "format_detected": {
            "type": "string",
            "enum": ["pre-formatted", "raw"],
            "description": "Whether data is pre-formatted with DCIDs or raw"
        },
        "pvmap_rows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Key from input data - must match exactly"
                    },
                    "mappings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "property": {
                                    "type": "string",
                                    "description": "Data Commons property name"
                                },
                                "value": {
                                    "type": "string",
                                    "description": "Property value ({Data}, {Number}, or dcid:XXX)"
                                }
                            },
                            "required": ["property", "value"]
                        }
                    }
                },
                "required": ["key", "mappings"]
            }
        },
        "validation_notes": {
            "type": "string",
            "description": "Notes about mapping decisions"
        },
        "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "description": "Confidence level in the mapping"
        }
    },
    "required": ["format_detected", "pvmap_rows", "validation_notes", "confidence"]
}
