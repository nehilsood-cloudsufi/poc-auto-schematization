"""Schema.org vocabulary lookup tools for ADK agents."""

from src.data_commons.schema.schemaorg_vocab import SchemaOrgVocab


def lookup_schemaorg_type(type_name: str) -> dict:
    """Verify a populationType exists in schema.org and discover its valid properties.

    WHEN TO CALL: Before using a populationType that is NOT in the
    Schema Examples vocabulary. Standard types (Person, Place, Organization)
    don't need verification.

    Args:
        type_name: The type name to look up (e.g., "Person", "Place", "Organization")

    Returns:
        Dict with success, data (type info with parent, description, properties), and error fields.
    """
    vocab = SchemaOrgVocab.instance()
    type_info = vocab.get_type(type_name)
    if type_info is None:
        # Check DC mapping
        dc_equiv = vocab.dc_type_to_schemaorg(type_name)
        if dc_equiv:
            mapped_info = vocab.get_type(dc_equiv)
            return {
                "success": True,
                "data": mapped_info,
                "note": f"DC type '{type_name}' maps to schema.org '{dc_equiv}'"
            }
        return {"success": False, "data": None, "error": f"Type '{type_name}' not found in schema.org or Data Commons"}
    return {"success": True, "data": type_info, "error": None}


def lookup_schemaorg_property(property_name: str) -> dict:
    """Look up a schema.org property to verify property names and discover domain/range info.

    Args:
        property_name: The property name to look up (e.g., "gender", "measuredProperty")

    Returns:
        Dict with success, data (property info with domain, range, description), and error fields.
    """
    vocab = SchemaOrgVocab.instance()
    prop_info = vocab.get_property(property_name)
    if prop_info is not None:
        return {"success": True, "data": prop_info, "error": None}

    # Check if it's a known DC-only property
    if vocab.is_known_dc_property(property_name):
        schema_equiv = vocab.dc_property_to_schemaorg(property_name)
        return {
            "success": True,
            "data": {"dc_only": True, "schema_equiv": schema_equiv},
            "note": f"'{property_name}' is a Data Commons extension property (not in base schema.org)"
        }

    return {"success": False, "data": None, "error": f"Property '{property_name}' not found in schema.org or Data Commons"}


def search_schemaorg_vocabulary(query: str, search_type: str = "both") -> dict:
    """Search schema.org types and properties by keyword.

    WHEN TO CALL: When you need to find the correct property name for
    a data column and it's not in the VALID ENUM VALUES list. Also use
    when choosing between multiple possible property names.

    Args:
        query: Search string (e.g., "education", "health", "employment")
        search_type: What to search - "types", "properties", or "both" (default: "both")

    Returns:
        Dict with success, data containing matched types and/or properties, and error fields.
    """
    vocab = SchemaOrgVocab.instance()
    result = {}

    if search_type in ("types", "both"):
        result["types"] = vocab.search_types(query, limit=10)
    if search_type in ("properties", "both"):
        result["properties"] = vocab.search_properties(query, limit=10)

    total = sum(len(v) for v in result.values())
    if total == 0:
        return {"success": False, "data": result, "error": f"No matches found for '{query}'"}

    return {"success": True, "data": result, "error": None}


def validate_pvmap_property(property_name: str, population_type: str) -> dict:
    """Check if a property is valid for a given populationType.

    WHEN TO CALL: When you're uncertain whether a dimension property
    applies to your chosen populationType. NOT needed for standard
    combos like (gender, Person) or (measuredProperty, Person).

    Args:
        property_name: The property to validate (e.g., "gender", "age")
        population_type: The populationType to check against (e.g., "Person", "Place")

    Returns:
        Dict with success, data containing validation result, and error fields.
    """
    vocab = SchemaOrgVocab.instance()

    result = {
        "property": property_name,
        "population_type": population_type,
        "property_known": False,
        "type_known": False,
        "compatible": False,
        "notes": []
    }

    # Check property
    if vocab.get_property(property_name) is not None:
        result["property_known"] = True
        result["property_source"] = "schema.org"
    elif vocab.is_known_dc_property(property_name):
        result["property_known"] = True
        result["property_source"] = "dc_extension"
        result["notes"].append(f"'{property_name}' is a Data Commons extension (not in base schema.org)")
    else:
        result["notes"].append(f"Unknown property: '{property_name}'")

    # Check type
    if vocab.get_type(population_type) is not None:
        result["type_known"] = True
        result["type_source"] = "schema.org"
    elif vocab.is_known_dc_type(population_type):
        result["type_known"] = True
        result["type_source"] = "dc_extension"
        schemaorg_equiv = vocab.dc_type_to_schemaorg(population_type)
        if schemaorg_equiv:
            result["notes"].append(f"DC type '{population_type}' maps to schema.org '{schemaorg_equiv}'")
    else:
        result["notes"].append(f"Unknown type: '{population_type}'")

    # Compatibility check (only for schema.org properties)
    if result["property_known"] and result["type_known"]:
        if result.get("property_source") == "dc_extension":
            result["compatible"] = True  # DC extensions assumed compatible with their types
            result["notes"].append("DC extension properties are assumed compatible")
        else:
            # Use schema.org type (resolve DC type if needed)
            check_type = population_type
            if result.get("type_source") == "dc_extension":
                check_type = vocab.dc_type_to_schemaorg(population_type) or population_type

            result["compatible"] = vocab.is_valid_property_for_type(property_name, check_type)
            if not result["compatible"]:
                expected_range = vocab.get_expected_range(property_name)
                result["notes"].append(
                    f"'{property_name}' is not in the domain of '{check_type}'. "
                    f"Expected range: {expected_range}"
                )

    return {"success": True, "data": result, "error": None}
