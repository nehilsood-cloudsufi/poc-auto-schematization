# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#         https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Data context module for understanding dataset structure.

This module provides:
- DataContext: A dataclass capturing the essence of a dataset for PVMAP generation
- DataContextGenerator: Generates DataContext from pandas DataFrame analysis

The context includes:
- Dataset topology (tidy/long vs wide/pivoted)
- Column classifications (place, time, dimension, value, metadata)
- Dimension domains (unique values per dimension column)
- StatVar pattern inference
- Coverage statistics
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import re

from absl import logging

try:
    import pandas as pd
except ImportError:
    pd = None


# Configuration defaults for data context generation
DATA_CONTEXT_CONFIG = {
    # Dimension detection thresholds
    'cardinality_dimension_threshold': 0.1,   # < 10% unique = likely dimension
    'cardinality_value_threshold': 0.5,       # > 50% unique = likely value
    'cardinality_metadata_threshold': 0.01,   # < 1% unique = likely metadata

    # Semantic keywords for column classification
    'dimension_keywords': [
        'gender', 'sex', 'age', 'race', 'ethnicity', 'industry', 'education',
        'status', 'type', 'category', 'sector', 'occupation', 'class',
        'group', 'level', 'grade', 'disability', 'citizenship', 'veteran'
    ],
    'value_keywords': [
        'count', 'total', 'amount', 'percent', 'rate', 'value', 'number',
        'sum', 'avg', 'average', 'mean', 'median', 'population', 'estimate',
        'quantity', 'measurement', 'observation', 'score', 'index'
    ],
    'metadata_keywords': [
        'source', 'unit', 'note', 'moe', 'annotation', 'method', 'flag',
        'footnote', 'comment', 'description', 'id', 'code', 'name'
    ],
    'place_keywords': [
        'state', 'county', 'city', 'fips', 'geo', 'region', 'country',
        'place', 'district', 'area', 'location', 'territory', 'nation',
        'province', 'municipality', 'zip', 'tract', 'block'
    ],
    'time_keywords': [
        'year', 'date', 'month', 'quarter', 'period', 'time', 'fiscal',
        'annual', 'weekly', 'daily', 'observation_date', 'ref_date'
    ],

    # Total/aggregate detection
    'total_keywords': ['total', 'all', 'overall', 'aggregate', 'combined', 'national', 'entire'],

    # Combination tracking limits
    'max_dimension_columns': 5,           # Limit to prevent cartesian explosion
    'min_combination_coverage': 0.2,      # Target 20% of combinations
}


@dataclass
class DataContext:
    """
    Complete context about a dataset for PVMAP generation.

    Uses UNIVERSAL TEMPLATE that works across ALL domains:
    Demographics, Economy, Health, Energy, Environment, etc.
    """

    # === DATASET CONTEXT (Domain-Agnostic) ===
    name: str = ""                              # Dataset name
    description: str = ""                       # Brief description
    topology: str = "TIDY_LONG"                 # TIDY_LONG | PIVOTED_WIDE | HYBRID
    population_type: str = "Person"             # DC entity: Person, Electricity, etc.

    # === ANCHORS (Required for all StatVarObservations) ===
    geography: Dict[str, Any] = field(default_factory=dict)    # {column, format, resolution}
    time: Dict[str, Any] = field(default_factory=dict)         # {column, format, notes}

    # === COLUMN CLASSIFICATIONS ===
    column_roles: Dict[str, str] = field(default_factory=dict)  # {column_name: role}

    # === SKELETON DIMENSIONS (Define StatVar uniqueness) ===
    dimension_columns: List[str] = field(default_factory=list)  # Columns that define StatVar
    dimension_domains: Dict[str, List[str]] = field(default_factory=dict)  # {dim: [values]}
    hidden_constraints: List[Dict] = field(default_factory=list)  # [{property, value, reason}]

    # === MEASUREMENT LOGIC ===
    value_columns: List[Dict] = field(default_factory=list)  # [{name, stat_type, method, unit}]
    measurement_type: str = "Count"              # Count, Amount, Rate, etc.

    # === DERIVED FIELDS ===
    statvar_pattern: str = ""                   # {measurement}_{population}_{constraints...}
    total_combinations: int = 0
    sample_combinations: int = 0
    coverage_percent: float = 0.0

    # === RAW DATA STATS ===
    total_rows: int = 0
    total_columns: int = 0

    # === ENRICHED FIELDS (for improved PVMAP generation) ===
    all_columns: List[str] = field(default_factory=list)
    ignored_columns: List[str] = field(default_factory=list)
    aggregate_values: Dict[str, List[str]] = field(default_factory=dict)
    place_resolution_hints: List[Dict[str, str]] = field(default_factory=list)
    is_preformatted_dc: bool = False
    one_shot_example: str = ""

    def to_skeleton_summary(self) -> str:
        """
        Generate enriched markdown summary for LLM prompts.

        9-section format designed to prevent the top PVMAP validation errors:
        1. Topology & Structure (all column headers)
        2. Column Classifications (role table)
        3. Anchor Analysis (geo + time with DCID hints)
        4. Dimension Deep Dive (up to 15 values + aggregate flags)
        5. Measurement & Units
        6. StatVar Pattern (P+M+C formula)
        7. One-Shot PVMAP Example
        8. Pre-Formatted DC Detection
        9. Coverage & generate-all reminder
        """
        lines = []

        # === Section 1: Topology & Structure ===
        lines.append("## 1. TOPOLOGY & STRUCTURE")
        lines.append("")
        lines.append(f"- **Dataset:** {self.name}")
        lines.append(f"- **Format:** {self.topology}")
        lines.append(f"- **Rows:** {self.total_rows}  |  **Columns:** {self.total_columns}")
        lines.append("")
        cols = self.all_columns if self.all_columns else list(self.column_roles.keys())
        if cols:
            lines.append(f"**ALL column headers (exact, case-sensitive):** `{'`, `'.join(cols)}`")
        lines.append("")

        # === Section 2: Column Classifications ===
        lines.append("## 2. COLUMN CLASSIFICATIONS")
        lines.append("")
        if self.column_roles:
            lines.append("| Column | Role |")
            lines.append("|--------|------|")
            for col, role in self.column_roles.items():
                lines.append(f"| `{col}` | {role} |")
        if self.ignored_columns:
            lines.append("")
            lines.append(f"**Ignored columns** (metadata/constant — do NOT map): `{'`, `'.join(self.ignored_columns)}`")
        lines.append("")

        # === Section 3: Anchor Analysis ===
        lines.append("## 3. ANCHOR ANALYSIS")
        lines.append("")
        # Geography
        if self.geography:
            geo_col = self.geography.get('column', 'Unknown')
            geo_fmt = self.geography.get('format', 'Unknown')
            geo_samples = self.geography.get('sample_values', [])
            lines.append(f"**Geography:** Column `{geo_col}` — Format: {geo_fmt}")
            if geo_samples:
                lines.append(f"  Sample values: {', '.join(str(v) for v in geo_samples[:5])}")
            if self.place_resolution_hints:
                lines.append("  **Place → DCID resolution hints:**")
                for hint in self.place_resolution_hints[:5]:
                    lines.append(f"  - `{hint.get('raw_value', '?')}` → `{hint.get('suggested_dcid', '?')}`")
        else:
            lines.append("**Geography:** Not detected (CRITICAL: must identify)")
        lines.append("")

        # Time
        if self.time:
            time_col = self.time.get('column', 'Unknown')
            time_fmt = self.time.get('format', 'Unknown')
            time_samples = self.time.get('sample_values', [])
            lines.append(f"**Time:** Column `{time_col}` — Format: {time_fmt}")
            if time_samples:
                lines.append(f"  Sample values: {', '.join(str(v) for v in time_samples[:5])}")
        else:
            lines.append("**Time:** Not detected")
        lines.append("")

        # === Section 4: Dimension Deep Dive ===
        lines.append("## 4. DIMENSION DEEP DIVE")
        lines.append("")
        if self.dimension_columns:
            for dim in self.dimension_columns:
                values = self.dimension_domains.get(dim, [])
                # Show up to 15 values (enriched from original 5)
                values_preview = values[:15] if len(values) > 15 else values
                values_str = ", ".join(str(v) for v in values_preview)
                if len(values) > 15:
                    values_str += f", ... ({len(values)} total)"
                lines.append(f"- **`{dim}`** ({len(values)} values): [{values_str}]")
                # Flag aggregate values
                agg_vals = self.aggregate_values.get(dim, [])
                if agg_vals:
                    lines.append(f"  ⚠ Aggregate values detected: {', '.join(agg_vals)} — consider dropping constraint or mapping to empty value")
        else:
            lines.append("- No dimension columns detected")

        if self.hidden_constraints:
            lines.append("")
            lines.append("**Hidden Constraints (implicit in all StatVars):**")
            for hc in self.hidden_constraints:
                lines.append(f"- {hc.get('property', 'Unknown')}: {hc.get('value', 'Unknown')} ({hc.get('reason', '')})")
        lines.append("")

        # === Section 5: Measurement & Units ===
        lines.append("## 5. MEASUREMENT & UNITS")
        lines.append("")
        if self.value_columns:
            for vc in self.value_columns:
                vc_name = vc.get('name', 'Unknown')
                vc_type = vc.get('stat_type', self.measurement_type)
                vc_unit = vc.get('unit', '')
                unit_str = f", Unit: {vc_unit}" if vc_unit else ""
                lines.append(f"- Value Column: `{vc_name}` (StatType: {vc_type}{unit_str})")
        else:
            lines.append("- No value columns detected")
        lines.append(f"- **Population Type:** {self.population_type}")
        lines.append(f"- **Measurement Type:** {self.measurement_type}")
        lines.append("")

        # === Section 6: StatVar Pattern ===
        lines.append("## 6. STATVAR PATTERN (P+M+C Formula)")
        lines.append("")
        if self.statvar_pattern:
            lines.append(f"`{self.statvar_pattern}`")
        else:
            lines.append("- Pattern not yet determined")
        lines.append("")

        # === Section 7: One-Shot PVMAP Example ===
        lines.append("## 7. ONE-SHOT PVMAP EXAMPLE")
        lines.append("")
        if self.one_shot_example:
            lines.append("```csv")
            lines.append(self.one_shot_example)
            lines.append("```")
        else:
            lines.append("_No one-shot example available._")
        lines.append("")

        # === Section 8: Pre-Formatted DC Detection ===
        lines.append("## 8. PRE-FORMATTED DATA COMMONS DETECTION")
        lines.append("")
        if self.is_preformatted_dc:
            lines.append("**YES — This data is already in Data Commons format.**")
            lines.append("Use passthrough mapping:")
            lines.append("```csv")
            lines.append("key,property,value")
            lines.append("observationAbout,observationAbout,{Data}")
            lines.append("observationDate,observationDate,{Data}")
            lines.append("variableMeasured,variableMeasured,{Data}")
            lines.append("value,value,{Number}")
            lines.append("```")
        else:
            lines.append("Not pre-formatted. Generate PVMAP from scratch.")
        lines.append("")

        # === Section 9: Coverage ===
        lines.append("## 9. COVERAGE")
        lines.append("")
        lines.append(f"- Total Dimension Combinations: {self.total_combinations}")
        if self.sample_combinations > 0:
            lines.append(f"- Sample Covers: {self.sample_combinations} ({self.coverage_percent:.1f}%)")
        lines.append("")
        lines.append("**IMPORTANT:** Generate PVMAP for ALL dimension combinations, not just those in sample.")

        return "\n".join(lines)

    def to_metadata_dict(self) -> Dict[str, Any]:
        """
        Returns context as a dictionary for programmatic use.
        """
        return {
            'dataset_name': self.name,
            'dataset_description': self.description,
            'topology': self.topology,
            'population_type': self.population_type,
            'geography': self.geography,
            'time': self.time,
            'column_roles': self.column_roles,
            'dimension_columns': self.dimension_columns,
            'dimension_domains': self.dimension_domains,
            'hidden_constraints': self.hidden_constraints,
            'value_columns': self.value_columns,
            'measurement_type': self.measurement_type,
            'statvar_pattern': self.statvar_pattern,
            'total_combinations': self.total_combinations,
            'sample_combinations': self.sample_combinations,
            'coverage_percent': self.coverage_percent,
            'total_rows': self.total_rows,
            'total_columns': self.total_columns,
            'all_columns': self.all_columns,
            'ignored_columns': self.ignored_columns,
            'aggregate_values': self.aggregate_values,
            'place_resolution_hints': self.place_resolution_hints,
            'is_preformatted_dc': self.is_preformatted_dc,
        }

    def to_mcp_query_context(self) -> Dict[str, Any]:
        """
        Generate context for MCP StatVar discovery.
        Uses P+M+C formula (Population + MeasuredProperty + Constraints).
        """
        return {
            'population': self.population_type,
            'measurement': self.measurement_type,
            'constraints': {dim: self.dimension_domains.get(dim, [])
                          for dim in self.dimension_columns},
            'statvar_pattern': self.statvar_pattern,
        }


class DataContextGenerator:
    """
    Generates DataContext using UNIVERSAL analysis that works across ALL domains.
    NOT overfitted to any specific domain like wages or population.
    """

    # Universal population type mapping (domain-agnostic)
    POPULATION_KEYWORDS = {
        # Demographics
        'person': 'Person', 'people': 'Person', 'population': 'Person',
        'individual': 'Person', 'resident': 'Person', 'citizen': 'Person',
        'household': 'Household', 'family': 'Household', 'home': 'Household',
        # Economy
        'business': 'EconomicActivity', 'gdp': 'EconomicActivity',
        'establishment': 'Establishment', 'firm': 'Establishment',
        'worker': 'Worker', 'employee': 'Worker', 'labor': 'Worker',
        'job': 'Job', 'employment': 'Job',
        # Energy
        'electricity': 'Electricity', 'power': 'Electricity', 'energy': 'Electricity',
        'plant': 'PowerPlant', 'generator': 'PowerPlant',
        'fuel': 'Fuel', 'coal': 'Fuel', 'oil': 'Fuel', 'gas': 'Fuel',
        # Environment
        'air': 'Atmosphere', 'pollutant': 'AirPollutant', 'emission': 'Emissions',
        'temperature': 'Atmosphere', 'weather': 'Atmosphere', 'climate': 'Atmosphere',
        'water': 'Water', 'precipitation': 'Precipitation',
        # Health
        'patient': 'Person', 'case': 'MedicalCondition',
        'disease': 'MedicalCondition', 'death': 'MortalityEvent',
        'birth': 'BirthEvent', 'hospital': 'Hospital',
        # Education
        'student': 'Student', 'school': 'School', 'enrollment': 'Student',
        'graduate': 'Student', 'teacher': 'Teacher',
        # Crime/Safety
        'crime': 'CriminalActivity', 'incident': 'CriminalActivity',
        'arrest': 'CriminalActivity', 'vehicle': 'Vehicle',
    }

    # Universal measurement type mapping
    MEASUREMENT_KEYWORDS = {
        'count': 'Count', 'number': 'Count', 'total': 'Count', 'quantity': 'Count',
        'amount': 'Amount', 'value': 'Amount', 'sum': 'Amount',
        'rate': 'Rate', 'percent': 'Percent', 'percentage': 'Percent', 'ratio': 'Ratio',
        'mean': 'Mean', 'average': 'Mean', 'avg': 'Mean', 'median': 'Median',
        'concentration': 'Concentration', 'level': 'Concentration',
        'generation': 'Generation', 'production': 'Generation', 'output': 'Generation',
        'consumption': 'Consumption', 'usage': 'Consumption', 'demand': 'Consumption',
        'price': 'Price', 'cost': 'Price', 'income': 'Income', 'wage': 'Income',
        'index': 'Index', 'score': 'Index',
    }

    def __init__(self, config: Dict = None):
        """Initialize the DataContextGenerator.

        Args:
            config: Optional configuration dictionary to override defaults.
        """
        self._config = {**DATA_CONTEXT_CONFIG, **(config or {})}

    def generate(self, df, metadata: Dict = None, dataset_name: str = "") -> DataContext:
        """Analyze dataset and generate UNIVERSAL context.

        Args:
            df: pandas DataFrame to analyze
            metadata: Optional metadata dictionary (from metadata.csv)
            dataset_name: Optional dataset name

        Returns:
            DataContext with full analysis
        """
        if pd is None:
            raise ImportError("pandas is required for DataContextGenerator")

        if df is None or len(df) == 0:
            return DataContext(name=dataset_name)

        metadata = metadata or {}
        context = DataContext(
            name=dataset_name or metadata.get('datasetname', 'Unknown'),
            total_rows=len(df),
            total_columns=len(df.columns),
        )

        # Step 1: Classify columns
        context.column_roles = self._classify_columns(df)

        # Step 2: Detect topology (tidy vs wide)
        context.topology = self._detect_topology(df, context.column_roles)

        # Step 3: Identify anchors (geography and time)
        context.geography = self._detect_geography(df, context.column_roles)
        context.time = self._detect_time(df, context.column_roles)

        # Step 4: Identify dimension columns and domains
        context.dimension_columns = self._get_dimension_columns(context.column_roles)
        context.dimension_domains = self._build_dimension_domains(df, context.dimension_columns)

        # Step 5: Identify value columns and measurement type
        context.value_columns = self._detect_value_columns(df, context.column_roles)
        context.measurement_type = self._infer_measurement_type(df, context.value_columns, metadata)

        # Step 6: Infer population type
        context.population_type = self._infer_population_type(df, metadata, context)

        # Step 7: Generate StatVar pattern
        context.statvar_pattern = self._generate_statvar_pattern(context)

        # Step 8: Calculate combination statistics
        context.total_combinations = self._calculate_total_combinations(context.dimension_domains)

        # Step 9: Generate description
        context.description = self._generate_description(df, metadata, context)

        # Step 10: Populate enriched fields
        context.all_columns = list(df.columns)
        context.ignored_columns = [
            col for col, role in context.column_roles.items()
            if role == 'metadata'
        ]
        context.aggregate_values = self._detect_aggregate_values(
            df, context.dimension_columns
        )
        context.place_resolution_hints = self._generate_place_resolution_hints(
            context.geography, df
        )
        context.is_preformatted_dc = self._detect_preformatted_dc(df)
        context.one_shot_example = self._generate_one_shot_example(context, df)

        return context

    # === GEO FORMAT → DCID PREFIX LOOKUP ===
    GEO_FORMAT_DCID_MAP = {
        'FIPS_STATE': ('geoId/{val:0>2}', 'geoId/'),
        'FIPS_COUNTY': ('geoId/{val:0>5}', 'geoId/'),
        'FIPS': ('geoId/{val}', 'geoId/'),
        'ISO_2': ('country/{val}', 'country/'),
        'ISO_3': ('country/{val}', 'country/'),
        'DC_DCID': ('{val}', ''),
        'NAME': ('wikidataId/{val}', 'wikidataId/'),
        'NUMERIC_CODE': ('geoId/{val}', 'geoId/'),
    }

    def _detect_aggregate_values(self, df, dimension_columns: List[str]) -> Dict[str, List[str]]:
        """Scan each dimension for values matching total_keywords config.

        Args:
            df: pandas DataFrame
            dimension_columns: List of dimension column names

        Returns:
            Dict mapping dimension name to list of aggregate value strings found
        """
        total_keywords = self._config.get('total_keywords', [])
        aggregate_values = {}

        for col in dimension_columns:
            if col not in df.columns:
                continue
            col_aggs = []
            unique_vals = df[col].dropna().unique()
            for val in unique_vals:
                val_lower = str(val).strip().lower()
                for kw in total_keywords:
                    if val_lower == kw or val_lower.startswith(kw + ' ') or val_lower.endswith(' ' + kw):
                        col_aggs.append(str(val))
                        break
            if col_aggs:
                aggregate_values[col] = col_aggs

        return aggregate_values

    def _generate_place_resolution_hints(
        self, geo_info: Dict[str, Any], df
    ) -> List[Dict[str, str]]:
        """Map detected geo format to DCID pattern with sample values.

        Args:
            geo_info: Geography dict from _detect_geography
            df: pandas DataFrame

        Returns:
            List of 3-5 sample {raw_value, suggested_dcid} dicts
        """
        if not geo_info:
            return []

        geo_col = geo_info.get('column')
        geo_format = geo_info.get('format', 'NAME')

        if not geo_col or geo_col not in df.columns:
            return []

        format_info = self.GEO_FORMAT_DCID_MAP.get(geo_format)
        if not format_info:
            return []

        pattern, prefix = format_info
        sample_values = df[geo_col].dropna().unique()[:5]
        hints = []

        for raw in sample_values:
            raw_str = str(raw).strip()
            if geo_format in ('FIPS_STATE',):
                try:
                    suggested = f"geoId/{int(raw_str):02d}"
                except (ValueError, TypeError):
                    suggested = f"geoId/{raw_str}"
            elif geo_format in ('FIPS_COUNTY',):
                try:
                    suggested = f"geoId/{int(raw_str):05d}"
                except (ValueError, TypeError):
                    suggested = f"geoId/{raw_str}"
            elif geo_format == 'DC_DCID':
                suggested = raw_str
            elif prefix:
                suggested = f"{prefix}{raw_str}"
            else:
                suggested = raw_str

            hints.append({
                'raw_value': raw_str,
                'suggested_dcid': suggested,
            })

        return hints

    def _generate_one_shot_example(self, context: 'DataContext', df) -> str:
        """Generate a deterministic template-based mini PVMAP example.

        Args:
            context: Partially-filled DataContext
            df: pandas DataFrame

        Returns:
            String containing a small PVMAP CSV example (3-8 rows)
        """
        lines = ["key,property,value"]

        # Place anchor
        if context.geography:
            geo_col = context.geography.get('column', '')
            geo_format = context.geography.get('format', 'NAME')
            format_info = self.GEO_FORMAT_DCID_MAP.get(geo_format)
            if format_info:
                _, prefix = format_info
                if geo_format == 'FIPS_STATE':
                    lines.append(f'{geo_col},#Format,observationAbout=geoId/{{Number:0>2}}')
                elif geo_format == 'FIPS_COUNTY':
                    lines.append(f'{geo_col},#Format,observationAbout=geoId/{{Number:0>5}}')
                elif geo_format == 'DC_DCID':
                    lines.append(f'{geo_col},observationAbout,{{Data}}')
                elif prefix:
                    lines.append(f'{geo_col},observationAbout,{prefix}{{Data}}')
                else:
                    lines.append(f'{geo_col},observationAbout,{{Data}}')
            else:
                lines.append(f'{geo_col},observationAbout,{{Data}}')

        # Time anchor
        if context.time:
            time_col = context.time.get('column', '')
            lines.append(f'{time_col},observationDate,{{Data}}')

        # Dimension values (for dims with <=10 values, enumerate)
        for dim in context.dimension_columns:
            values = context.dimension_domains.get(dim, [])
            if 0 < len(values) <= 10:
                for val in values:
                    val_str = str(val)
                    # Use COLUMN:VALUE syntax
                    dim_prop = dim.lower().replace(' ', '')
                    lines.append(f'{dim}:{val_str},{dim_prop},{val_str}')

        # Value column with full StatVar properties
        if context.value_columns:
            vc = context.value_columns[0]
            vc_name = vc.get('name', 'Value')
            pop_type = context.population_type
            meas_type = context.measurement_type.lower()
            lines.append(
                f'{vc_name},value,{{Number}},populationType,{pop_type},'
                f'measuredProperty,{meas_type},statType,measuredValue'
            )

        return "\n".join(lines)

    def _detect_preformatted_dc(self, df) -> bool:
        """Check if data is already in Data Commons format.

        Detection: columns include variableMeasured + observationAbout + value.

        Args:
            df: pandas DataFrame

        Returns:
            True if data appears to be pre-formatted DC data
        """
        col_set = set(c.lower().strip() for c in df.columns)
        required = {'variablemeasured', 'observationabout', 'value'}
        return required.issubset(col_set)

    def _classify_columns(self, df) -> Dict[str, str]:
        """Classify columns into: place, time, dimension, value, metadata.

        Args:
            df: pandas DataFrame

        Returns:
            Dictionary mapping column name to role string
        """
        roles = {}
        n_rows = len(df)

        for col in df.columns:
            col_lower = col.lower()
            series = df[col]

            # Calculate cardinality
            n_unique = series.nunique()
            unique_ratio = n_unique / n_rows if n_rows > 0 else 1.0

            # Check for empty/constant columns
            non_null_count = series.notna().sum()
            if non_null_count == 0 or n_unique <= 1:
                roles[col] = 'metadata'
                continue

            # Semantic keyword matching (highest priority)
            role = self._semantic_classify(col_lower)
            if role:
                roles[col] = role
                continue

            # Cardinality-based classification
            if unique_ratio < self._config['cardinality_metadata_threshold']:
                # Very low cardinality - likely constant/metadata
                roles[col] = 'metadata'
            elif unique_ratio < self._config['cardinality_dimension_threshold']:
                # Low cardinality - likely dimension
                roles[col] = 'dimension'
            elif unique_ratio > self._config['cardinality_value_threshold']:
                # High cardinality - check if numeric
                if self._is_numeric_column(series):
                    roles[col] = 'value'
                else:
                    roles[col] = 'metadata'  # High cardinality text
            else:
                # Medium cardinality - check if numeric
                if self._is_numeric_column(series):
                    roles[col] = 'value'
                else:
                    roles[col] = 'dimension'

        return roles

    def _semantic_classify(self, col_lower: str) -> Optional[str]:
        """Classify column by semantic keyword matching.

        Args:
            col_lower: Lowercase column name

        Returns:
            Role string or None if no match
        """
        # Check place keywords
        for kw in self._config['place_keywords']:
            if kw in col_lower:
                return 'place'

        # Check time keywords
        for kw in self._config['time_keywords']:
            if kw in col_lower:
                return 'time'

        # Check dimension keywords
        for kw in self._config['dimension_keywords']:
            if kw in col_lower:
                return 'dimension'

        # Check value keywords
        for kw in self._config['value_keywords']:
            if kw in col_lower:
                return 'value'

        # Check metadata keywords
        for kw in self._config['metadata_keywords']:
            if kw in col_lower:
                return 'metadata'

        return None

    def _is_numeric_column(self, series) -> bool:
        """Check if a column is primarily numeric.

        Args:
            series: pandas Series

        Returns:
            True if >80% of non-null values are numeric
        """
        numeric_count = 0
        non_null_count = 0

        for val in series.dropna():
            non_null_count += 1
            try:
                # Remove common formatting
                clean = str(val).strip().replace(',', '').replace('%', '').replace('$', '')
                float(clean)
                numeric_count += 1
            except (ValueError, TypeError):
                pass

        if non_null_count == 0:
            return False

        return numeric_count / non_null_count >= 0.8

    def _detect_topology(self, df, column_roles: Dict[str, str]) -> str:
        """Detect if data is TIDY_LONG, PIVOTED_WIDE, or HYBRID.

        Args:
            df: pandas DataFrame
            column_roles: Column classification dictionary

        Returns:
            Topology string: TIDY_LONG, PIVOTED_WIDE, or HYBRID
        """
        value_cols = [col for col, role in column_roles.items() if role == 'value']
        dimension_cols = [col for col, role in column_roles.items() if role == 'dimension']

        # Wide data: multiple value columns, few dimension columns
        # Long/tidy data: one or few value columns, multiple dimension columns
        if len(value_cols) > 5:
            return 'PIVOTED_WIDE'
        elif len(dimension_cols) > len(value_cols):
            return 'TIDY_LONG'
        elif len(value_cols) > 1:
            return 'HYBRID'
        else:
            return 'TIDY_LONG'

    def _detect_geography(self, df, column_roles: Dict[str, str]) -> Dict[str, Any]:
        """Detect geography/place column and format.

        Args:
            df: pandas DataFrame
            column_roles: Column classification dictionary

        Returns:
            Dictionary with column, format, resolution
        """
        place_cols = [col for col, role in column_roles.items() if role == 'place']

        if not place_cols:
            return {}

        # Use first place column
        geo_col = place_cols[0]
        sample_values = df[geo_col].dropna().head(10).tolist()

        # Detect format
        geo_format = self._detect_geo_format(sample_values, geo_col)

        return {
            'column': geo_col,
            'format': geo_format,
            'unique_values': df[geo_col].nunique(),
            'sample_values': sample_values[:5],
        }

    def _detect_geo_format(self, values: List, col_name: str) -> str:
        """Detect geographic format from sample values.

        Args:
            values: Sample values from the column
            col_name: Column name

        Returns:
            Format string (e.g., 'FIPS_STATE', 'ISO_COUNTRY', 'NAME')
        """
        col_lower = col_name.lower()

        # FIPS patterns
        if 'fips' in col_lower:
            if 'state' in col_lower:
                return 'FIPS_STATE'
            elif 'county' in col_lower:
                return 'FIPS_COUNTY'
            return 'FIPS'

        # Check value patterns
        if values:
            first_val = str(values[0]).strip()

            # ISO country codes
            if len(first_val) == 2 and first_val.isalpha():
                return 'ISO_2'
            elif len(first_val) == 3 and first_val.isalpha():
                return 'ISO_3'

            # Numeric codes
            if first_val.isdigit():
                if len(first_val) == 2:
                    return 'FIPS_STATE'
                elif len(first_val) == 5:
                    return 'FIPS_COUNTY'
                return 'NUMERIC_CODE'

            # DC format (geoId/, country/, etc.)
            if first_val.startswith('geoId/') or first_val.startswith('country/'):
                return 'DC_DCID'

        return 'NAME'

    def _detect_time(self, df, column_roles: Dict[str, str]) -> Dict[str, Any]:
        """Detect time/date column and format.

        Args:
            df: pandas DataFrame
            column_roles: Column classification dictionary

        Returns:
            Dictionary with column, format, notes
        """
        time_cols = [col for col, role in column_roles.items() if role == 'time']

        if not time_cols:
            return {}

        time_col = time_cols[0]
        sample_values = df[time_col].dropna().head(10).tolist()

        # Detect format
        time_format = self._detect_time_format(sample_values)

        return {
            'column': time_col,
            'format': time_format,
            'unique_values': df[time_col].nunique(),
            'sample_values': sample_values[:5],
        }

    def _detect_time_format(self, values: List) -> str:
        """Detect time format from sample values.

        Args:
            values: Sample values from the column

        Returns:
            Format string (e.g., 'YYYY', 'YYYY-MM', 'YYYY-MM-DD')
        """
        if not values:
            return 'UNKNOWN'

        first_val = str(values[0]).strip()

        # Year only
        if re.match(r'^\d{4}$', first_val):
            return 'YYYY'

        # Year-Month
        if re.match(r'^\d{4}-\d{2}$', first_val):
            return 'YYYY-MM'

        # Full date
        if re.match(r'^\d{4}-\d{2}-\d{2}$', first_val):
            return 'YYYY-MM-DD'

        # Quarter
        if re.match(r'^\d{4}Q\d$', first_val):
            return 'YYYY-Q'

        # Fiscal year
        if 'FY' in first_val.upper():
            return 'FISCAL_YEAR'

        return 'CUSTOM'

    def _get_dimension_columns(self, column_roles: Dict[str, str]) -> List[str]:
        """Extract dimension column names from roles.

        Args:
            column_roles: Column classification dictionary

        Returns:
            List of dimension column names
        """
        return [col for col, role in column_roles.items() if role == 'dimension']

    def _build_dimension_domains(self, df, dimension_columns: List[str]) -> Dict[str, List[str]]:
        """Build domain (unique values) for each dimension column.

        Args:
            df: pandas DataFrame
            dimension_columns: List of dimension column names

        Returns:
            Dictionary mapping dimension name to list of unique values
        """
        domains = {}

        for col in dimension_columns:
            if col in df.columns:
                unique_vals = df[col].dropna().unique().tolist()
                # Convert to strings and sort
                domains[col] = sorted([str(v) for v in unique_vals])

        return domains

    def _detect_value_columns(self, df, column_roles: Dict[str, str]) -> List[Dict]:
        """Detect value columns and their properties.

        Args:
            df: pandas DataFrame
            column_roles: Column classification dictionary

        Returns:
            List of dictionaries with value column info
        """
        value_cols = []

        for col, role in column_roles.items():
            if role == 'value':
                col_info = {
                    'name': col,
                    'stat_type': self._infer_stat_type(col),
                    'measurement_method': None,
                    'unit': None,
                }
                value_cols.append(col_info)

        return value_cols

    def _infer_stat_type(self, col_name: str) -> str:
        """Infer stat type from column name.

        Args:
            col_name: Column name

        Returns:
            Stat type string
        """
        col_lower = col_name.lower()

        for keyword, stat_type in self.MEASUREMENT_KEYWORDS.items():
            if keyword in col_lower:
                return stat_type

        return 'measuredValue'

    def _infer_measurement_type(self, df, value_columns: List[Dict],
                                 metadata: Dict) -> str:
        """Infer overall measurement type for the dataset.

        Args:
            df: pandas DataFrame
            value_columns: List of value column info dicts
            metadata: Metadata dictionary

        Returns:
            Measurement type string
        """
        # Check metadata first
        if metadata:
            unit = metadata.get('unit', '').lower()
            if 'percent' in unit:
                return 'Percent'
            if 'rate' in unit:
                return 'Rate'

        # Check value column names
        if value_columns:
            col_name = value_columns[0].get('name', '').lower()
            for keyword, mtype in self.MEASUREMENT_KEYWORDS.items():
                if keyword in col_name:
                    return mtype

        return 'Count'

    def _infer_population_type(self, df, metadata: Dict, context: DataContext) -> str:
        """Infer population type using UNIVERSAL keyword mapping.

        Args:
            df: pandas DataFrame
            metadata: Metadata dictionary
            context: Partially filled DataContext

        Returns:
            Population type string
        """
        # Check metadata first
        all_text = ""
        if metadata:
            all_text += metadata.get('datasetname', '') + " "
            all_text += metadata.get('source', '') + " "

        # Add column names
        all_text += " ".join(df.columns)

        all_text_lower = all_text.lower()

        # Check keywords
        for keyword, pop_type in self.POPULATION_KEYWORDS.items():
            if keyword in all_text_lower:
                return pop_type

        return 'Person'  # Default

    def _generate_statvar_pattern(self, context: DataContext) -> str:
        """Generate StatVar naming pattern.

        Uses P+M+C formula: Population + MeasuredProperty + Constraints

        Args:
            context: DataContext with dimension info

        Returns:
            StatVar pattern string
        """
        parts = [context.measurement_type, context.population_type]

        for dim in context.dimension_columns[:3]:  # Limit to 3 dimensions
            parts.append(f"{{{dim}}}")

        return "_".join(parts)

    def _calculate_total_combinations(self, dimension_domains: Dict[str, List[str]]) -> int:
        """Calculate total possible dimension combinations.

        Args:
            dimension_domains: Dictionary of dimension -> values

        Returns:
            Total number of combinations (cartesian product)
        """
        if not dimension_domains:
            return 1

        total = 1
        for domain in dimension_domains.values():
            total *= max(1, len(domain))

        # Cap at a reasonable max to prevent overflow
        return min(total, 1000000)

    def _generate_description(self, df, metadata: Dict, context: DataContext) -> str:
        """Generate a brief description of the dataset.

        Args:
            df: pandas DataFrame
            metadata: Metadata dictionary
            context: DataContext with analysis

        Returns:
            Description string
        """
        if metadata and metadata.get('datasetname'):
            return metadata['datasetname']

        # Generate from context
        parts = []
        if context.measurement_type:
            parts.append(context.measurement_type)
        if context.population_type:
            parts.append(f"of {context.population_type}")
        if context.dimension_columns:
            parts.append(f"by {', '.join(context.dimension_columns[:2])}")

        return " ".join(parts) if parts else "Dataset"


def generate_data_context(df, metadata: Dict = None, dataset_name: str = "") -> DataContext:
    """Convenience function to generate DataContext.

    Args:
        df: pandas DataFrame
        metadata: Optional metadata dictionary
        dataset_name: Optional dataset name

    Returns:
        DataContext instance
    """
    generator = DataContextGenerator()
    return generator.generate(df, metadata, dataset_name)
