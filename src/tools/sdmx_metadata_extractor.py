"""SDMX-ML metadata extractor.

Parses SDMX-ML 2.1 structure messages (a dataflow plus referenced DSD,
codelists, and concept schemes) into a simplified, token-efficient dict
suitable for feeding into an LLM prompt.

Output schema mirrors Google's Data Commons agentic-import extractor
(Apache 2.0 — see
https://github.com/datacommonsorg/data/blob/master/tools/agentic_import/sdmx_metadata_extractor.py)
so downstream tooling built against that schema remains compatible.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, List, Literal, Optional

logger = logging.getLogger(__name__)

DEFAULT_LOCALE = "en"


# ---------------------------------------------------------------------------
# Output schema (dataclasses → JSON)
# ---------------------------------------------------------------------------


@dataclass
class Code:
    id: str
    name: str = ""
    description: str = ""


@dataclass
class CodelistDetails:
    id: str
    name: str = ""
    description: str = ""
    codes: List[Code] = field(default_factory=list)


@dataclass
class RepresentationDetails:
    type: Literal["enumerated", "non-enumerated"]
    codelist: Optional[CodelistDetails] = None


@dataclass
class ConceptDetails:
    id: str
    name: str = ""
    description: str = ""
    concept_scheme_id: Optional[str] = None


@dataclass
class ComponentDetails:
    id: str
    name: str = ""
    description: str = ""
    concept: Optional[ConceptDetails] = None
    representation: Optional[RepresentationDetails] = None


@dataclass
class DataStructureDefinitionDetails:
    id: str
    name: str = ""
    description: str = ""
    dimensions: List[ComponentDetails] = field(default_factory=list)
    attributes: List[ComponentDetails] = field(default_factory=list)
    measures: List[ComponentDetails] = field(default_factory=list)


@dataclass
class ReferencedConceptSchemeDetails:
    id: str
    name: str = ""
    description: str = ""
    concepts: List[ConceptDetails] = field(default_factory=list)


@dataclass
class DataflowArtefactAttributes:
    version: Optional[str] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    is_final: Optional[bool] = None
    is_external_reference: Optional[bool] = None
    service_url: Optional[str] = None
    structure_url: Optional[str] = None


@dataclass
class DataflowStructure:
    id: str
    name: str = ""
    description: str = ""
    some_attributes: Optional[DataflowArtefactAttributes] = None
    data_structure_definition: Optional[DataStructureDefinitionDetails] = None
    referenced_concept_schemes: List[ReferencedConceptSchemeDetails] = field(
        default_factory=list
    )


@dataclass
class MultiDataflowOutput:
    dataflows: List[DataflowStructure] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _i18n(obj: Any) -> str:
    """Resolve an InternationalString (or any value) to a single string."""
    if obj is None:
        return ""
    try:
        from sdmx.model.internationalstring import InternationalString
    except Exception:
        InternationalString = None  # type: ignore

    if InternationalString is not None and isinstance(obj, InternationalString):
        try:
            val = obj.localized_default(DEFAULT_LOCALE)
            return val or ""
        except Exception:
            return str(obj) if obj else ""
    return str(obj) if obj else ""


def _concept_scheme_id(concept: Any) -> Optional[str]:
    if concept is None:
        return None
    try:
        if hasattr(concept, "get_scheme"):
            scheme = concept.get_scheme()
            if scheme is not None:
                return scheme.id
        if hasattr(concept, "scheme") and concept.scheme is not None:
            return concept.scheme.id
    except Exception as e:
        logger.debug("concept-scheme lookup failed for %r: %s", concept, e)
    parent = getattr(concept, "parent", None)
    return getattr(parent, "id", None)


def _concept(concept: Any) -> Optional[ConceptDetails]:
    if concept is None:
        return None
    return ConceptDetails(
        id=getattr(concept, "id", "") or "",
        name=_i18n(getattr(concept, "name", None)),
        description=_i18n(getattr(concept, "description", None)),
        concept_scheme_id=_concept_scheme_id(concept),
    )


def _codelist(codelist: Any) -> Optional[CodelistDetails]:
    if codelist is None:
        return None
    codes: List[Code] = []
    items = getattr(codelist, "items", None) or {}
    for item_id, item in (items.items() if hasattr(items, "items") else ((c.id, c) for c in items)):
        codes.append(
            Code(
                id=item_id,
                name=_i18n(getattr(item, "name", None)),
                description=_i18n(getattr(item, "description", None)),
            )
        )
    return CodelistDetails(
        id=getattr(codelist, "id", "") or "",
        name=_i18n(getattr(codelist, "name", None)),
        description=_i18n(getattr(codelist, "description", None)),
        codes=codes,
    )


def _representation(local_rep: Any) -> Optional[RepresentationDetails]:
    """Resolve a Component's LocalRepresentation to our schema."""
    if local_rep is None:
        return None
    enum = getattr(local_rep, "enumerated", None)
    if enum is not None:
        cl = _codelist(enum)
        return RepresentationDetails(type="enumerated", codelist=cl)
    return RepresentationDetails(type="non-enumerated", codelist=None)


def _component(comp: Any) -> ComponentDetails:
    return ComponentDetails(
        id=getattr(comp, "id", "") or "",
        name=_i18n(getattr(comp, "name", None)),
        description=_i18n(getattr(comp, "description", None)),
        concept=_concept(getattr(comp, "concept_identity", None)),
        representation=_representation(getattr(comp, "local_representation", None)),
    )


def _components(component_list: Any) -> List[ComponentDetails]:
    if component_list is None:
        return []
    comps = getattr(component_list, "components", None)
    if comps is None:
        comps = list(component_list)
    return [_component(c) for c in comps]


def _dsd(dsd: Any) -> Optional[DataStructureDefinitionDetails]:
    if dsd is None:
        return None
    return DataStructureDefinitionDetails(
        id=getattr(dsd, "id", "") or "",
        name=_i18n(getattr(dsd, "name", None)),
        description=_i18n(getattr(dsd, "description", None)),
        dimensions=_components(getattr(dsd, "dimensions", None)),
        attributes=_components(getattr(dsd, "attributes", None)),
        measures=_components(getattr(dsd, "measures", None)),
    )


def _referenced_concept_schemes(
    dsd: Any, message: Any
) -> List[ReferencedConceptSchemeDetails]:
    """Collect ConceptSchemes referenced by any component of the DSD."""
    if dsd is None:
        return []

    scheme_ids: set[str] = set()
    for comp_list in (
        getattr(dsd, "dimensions", None),
        getattr(dsd, "attributes", None),
        getattr(dsd, "measures", None),
    ):
        if comp_list is None:
            continue
        comps = getattr(comp_list, "components", None) or list(comp_list)
        for comp in comps:
            concept = getattr(comp, "concept_identity", None)
            sid = _concept_scheme_id(concept)
            if sid:
                scheme_ids.add(sid)

    out: List[ReferencedConceptSchemeDetails] = []
    cs_map = getattr(message, "concept_scheme", {}) or {}
    for sid in sorted(scheme_ids):
        cs = cs_map.get(sid)
        if cs is None:
            continue
        concepts: List[ConceptDetails] = []
        items = getattr(cs, "items", None) or {}
        iterator = (
            items.items() if hasattr(items, "items") else ((c.id, c) for c in items)
        )
        for cid, c in iterator:
            concepts.append(
                ConceptDetails(
                    id=cid,
                    name=_i18n(getattr(c, "name", None)),
                    description=_i18n(getattr(c, "description", None)),
                    concept_scheme_id=sid,
                )
            )
        out.append(
            ReferencedConceptSchemeDetails(
                id=sid,
                name=_i18n(getattr(cs, "name", None)),
                description=_i18n(getattr(cs, "description", None)),
                concepts=concepts,
            )
        )
    return out


def _dataflow_attributes(df: Any) -> DataflowArtefactAttributes:
    return DataflowArtefactAttributes(
        version=getattr(df, "version", None),
        valid_from=str(getattr(df, "valid_from", "") or "") or None,
        valid_to=str(getattr(df, "valid_to", "") or "") or None,
        is_final=getattr(df, "is_final", None),
        is_external_reference=getattr(df, "is_external_reference", None),
        service_url=str(getattr(df, "service_url", "") or "") or None,
        structure_url=str(getattr(df, "structure_url", "") or "") or None,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_sdmx_metadata(xml_path: Path) -> dict:
    """Parse an SDMX-ML 2.1 structure message and return the extracted JSON.

    The input XML should be a structure message with ``references=all``
    (produced by `tools/sdmx_import/sdmx_cli.py download-metadata` or any
    equivalent SDMX REST call).

    Returns a dict matching :class:`MultiDataflowOutput`.

    Raises:
        FileNotFoundError: xml_path does not exist.
        RuntimeError: sdmx1 cannot parse the file, or no dataflows found.
    """
    xml_path = Path(xml_path)
    if not xml_path.exists():
        raise FileNotFoundError(f"SDMX metadata file not found: {xml_path}")

    try:
        import sdmx
    except ImportError as e:
        raise RuntimeError(
            "sdmx1 is required for SDMX metadata extraction. "
            "Install with: pip install sdmx1"
        ) from e

    try:
        with xml_path.open("rb") as f:
            message = sdmx.read_sdmx(f)
    except Exception as e:
        raise RuntimeError(f"Failed to parse SDMX-ML at {xml_path}: {e}") from e

    dataflows_map = getattr(message, "dataflow", {}) or {}
    if not dataflows_map:
        raise RuntimeError(
            f"No dataflows found in {xml_path}. "
            "Ensure the structure message was downloaded with references=all."
        )

    output = MultiDataflowOutput(dataflows=[])
    for df_id, df in dataflows_map.items():
        dsd = getattr(df, "structure", None)
        output.dataflows.append(
            DataflowStructure(
                id=df_id,
                name=_i18n(getattr(df, "name", None)),
                description=_i18n(getattr(df, "description", None)),
                some_attributes=_dataflow_attributes(df),
                data_structure_definition=_dsd(dsd),
                referenced_concept_schemes=_referenced_concept_schemes(dsd, message),
            )
        )

    return asdict(
        output,
        dict_factory=lambda kv: {k: v for k, v in kv if v not in (None, "", [])},
    )


def write_sdmx_metadata_json(xml_path: Path, json_path: Path) -> dict:
    """Extract SDMX metadata from XML and write to a JSON file. Returns the dict."""
    data = extract_sdmx_metadata(Path(xml_path))
    Path(json_path).write_text(json.dumps(data, indent=2))
    return data


__all__ = [
    "extract_sdmx_metadata",
    "write_sdmx_metadata_json",
    "MultiDataflowOutput",
    "DataflowStructure",
    "DataStructureDefinitionDetails",
    "ComponentDetails",
    "CodelistDetails",
    "ConceptDetails",
    "Code",
]
