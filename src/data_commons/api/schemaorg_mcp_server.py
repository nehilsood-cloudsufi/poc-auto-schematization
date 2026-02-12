"""
Schema.org MCP Server for Data Commons vocabulary lookup.

Provides MCP tools for looking up schema.org types, properties, and
validating PVMAP property-type compatibility.

The tool logic functions (lookup_type, lookup_property, etc.) are plain
Python functions that can be imported and called directly in tests.
They are registered with the MCP server separately.

Usage:
    # Run directly
    python -m src.data_commons.api.schemaorg_mcp_server

    # Or managed by SchemaOrgMCPManager
    from src.data_commons.api.schemaorg_mcp_manager import SchemaOrgMCPManager
    manager = SchemaOrgMCPManager(port=3001)
    manager.start()

    # Import functions directly for testing
    from src.data_commons.api.schemaorg_mcp_server import lookup_type
    result = lookup_type("Person")
"""

import sys
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP

# Ensure project root is on path for SchemaOrgVocab import
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

mcp = FastMCP("schema-org-vocab")


# ============================================================================
# Tool logic functions (plain Python, importable and testable)
# ============================================================================


def lookup_type(name: str) -> dict:
    """Look up a schema.org type to verify populationType values and discover valid properties.

    Args:
        name: Type name (e.g., "Person", "Place", "Organization", "Observation")

    Returns:
        Type info with parent types, description, and direct properties.
    """
    from src.data_commons.schema.schemaorg_vocab import SchemaOrgVocab

    vocab = SchemaOrgVocab.instance()
    type_info = vocab.get_type(name)

    if type_info is None:
        dc_equiv = vocab.dc_type_to_schemaorg(name)
        if dc_equiv:
            mapped_info = vocab.get_type(dc_equiv)
            return {
                "found": True,
                "type": dc_equiv,
                "note": f"DC type '{name}' maps to schema.org '{dc_equiv}'",
                "parent": mapped_info.get("parent", []) if mapped_info else [],
                "description": mapped_info.get("description", "") if mapped_info else "",
                "properties": mapped_info.get("properties", [])[:20] if mapped_info else [],
            }
        return {"found": False, "error": f"Type '{name}' not found in schema.org or Data Commons"}

    return {
        "found": True,
        "type": name,
        "parent": type_info.get("parent", []),
        "description": type_info.get("description", ""),
        "properties": type_info.get("properties", [])[:20],
    }


def lookup_property(name: str) -> dict:
    """Look up a schema.org property to verify property names and check domain/range.

    Args:
        name: Property name (e.g., "gender", "measuredProperty", "name")

    Returns:
        Property info with domain types, range types, and description.
    """
    from src.data_commons.schema.schemaorg_vocab import SchemaOrgVocab

    vocab = SchemaOrgVocab.instance()
    prop_info = vocab.get_property(name)

    if prop_info is not None:
        return {
            "found": True,
            "property": name,
            "domain": prop_info.get("domain", []),
            "range": prop_info.get("range", []),
            "description": prop_info.get("description", ""),
        }

    if vocab.is_known_dc_property(name):
        schema_equiv = vocab.dc_property_to_schemaorg(name)
        return {
            "found": True,
            "property": name,
            "dc_only": True,
            "schema_equiv": schema_equiv,
            "note": f"'{name}' is a Data Commons extension (not in base schema.org)",
        }

    return {"found": False, "error": f"Property '{name}' not found"}


def search_vocabulary(query: str, search_in: str = "both") -> dict:
    """Search schema.org vocabulary for types and properties matching a query.

    Args:
        query: Search string (e.g., "education", "health", "person")
        search_in: What to search - "types", "properties", or "both"

    Returns:
        Matching types and/or properties with descriptions.
    """
    from src.data_commons.schema.schemaorg_vocab import SchemaOrgVocab

    vocab = SchemaOrgVocab.instance()
    result = {}

    if search_in in ("types", "both"):
        result["types"] = vocab.search_types(query, limit=10)
    if search_in in ("properties", "both"):
        result["properties"] = vocab.search_properties(query, limit=10)

    total = sum(len(v) for v in result.values())
    return {"matches": total, "results": result}


def validate_mapping(property_name: str, population_type: str) -> dict:
    """Validate whether a property is compatible with a population type.

    Args:
        property_name: Property to check (e.g., "gender", "age")
        population_type: Type to check against (e.g., "Person", "Place")

    Returns:
        Validation result with compatibility info and notes.
    """
    from src.data_commons.schema.schemaorg_vocab import SchemaOrgVocab

    vocab = SchemaOrgVocab.instance()

    result = {
        "property": property_name,
        "population_type": population_type,
        "property_known": vocab.is_known_property(property_name),
        "type_known": vocab.is_known_type(population_type),
        "compatible": False,
        "notes": [],
    }

    if not result["property_known"]:
        result["notes"].append(f"Unknown property: '{property_name}'")
    if not result["type_known"]:
        result["notes"].append(f"Unknown type: '{population_type}'")

    if result["property_known"] and result["type_known"]:
        # DC extensions are assumed compatible
        if vocab.is_known_dc_property(property_name) and not vocab.get_property(property_name):
            result["compatible"] = True
            result["notes"].append("DC extension property (assumed compatible)")
        else:
            check_type = population_type
            schemaorg_equiv = vocab.dc_type_to_schemaorg(population_type)
            if schemaorg_equiv:
                check_type = schemaorg_equiv
            result["compatible"] = vocab.is_valid_property_for_type(property_name, check_type)
            if not result["compatible"]:
                result["notes"].append(
                    f"'{property_name}' not in domain of '{check_type}'"
                )

    return result


def get_type_hierarchy(name: str) -> dict:
    """Get the ancestor chain for a schema.org type.

    Args:
        name: Type name (e.g., "Person", "Observation")

    Returns:
        List of ancestor types from most specific to most general.
    """
    from src.data_commons.schema.schemaorg_vocab import SchemaOrgVocab

    vocab = SchemaOrgVocab.instance()
    hierarchy = vocab.get_type_hierarchy(name)

    if hierarchy is None:
        dc_equiv = vocab.dc_type_to_schemaorg(name)
        if dc_equiv:
            hierarchy = vocab.get_type_hierarchy(dc_equiv)
            if hierarchy is not None:
                return {
                    "found": True,
                    "type": dc_equiv,
                    "note": f"DC type '{name}' maps to '{dc_equiv}'",
                    "hierarchy": [dc_equiv] + hierarchy,
                }
        return {"found": False, "error": f"Type '{name}' not found"}

    return {"found": True, "type": name, "hierarchy": [name] + hierarchy}


# ============================================================================
# Register functions as MCP tools (does NOT replace module-level names)
# ============================================================================

mcp.tool()(lookup_type)
mcp.tool()(lookup_property)
mcp.tool()(search_vocabulary)
mcp.tool()(validate_mapping)
mcp.tool()(get_type_hierarchy)


# Health check endpoint
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    """Health check endpoint."""
    from starlette.responses import JSONResponse
    return JSONResponse({"status": "ok", "server": "schema-org-vocab"})


def main():
    """Run the MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="Schema.org MCP Server")
    parser.add_argument("--port", type=int, default=3001, help="Port to listen on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    args = parser.parse_args()

    mcp.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
