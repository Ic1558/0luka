# DDC-CWICR 85-Field Schema

The OpenConstructionEstimate (DDC-CWICR) database uses a structured schema organized into logical groups. Use this schema to normalize BOQ data and map work items to resources.

## 1. Classification
- `classification_omniclass_code`: OmniClass 23 - Products
- `classification_omniclass_name`: OmniClass name
- `classification_uniclass_code`: Uniclass 2015
- `classification_uniclass_name`: Uniclass name
- `classification_masterformat_code`: MasterFormat
- `classification_guis_code`: Global Unit Item System

## 2. Work Item (Rate)
- `rate_code`: Unique identifier for the work item
- `rate_original_name`: Full description of the work item
- `rate_unit`: Measurement unit (e.g., m2, m3, kg, pcs)
- `rate_currency`: Base currency (default: USD/THB)

## 3. Resources (Detailed Breakdown)
- `resource_code`: Unique resource identifier
- `resource_name`: Name of material, labor, or machine
- `resource_type`: (Material / Labor / Machinery / Service)
- `resource_unit`: Unit of resource

## 4. Labor Details
- `labor_hours_workers`: Man-hours per unit
- `labor_productivity_rate`: Units per man-hour
- `labor_cost_per_unit`: Total labor value for the work item

## 5. Material & Machinery
- `material_quantity_per_unit`: Quantity of material needed per unit of work item
- `material_wastage_factor`: Allowance for waste (%)
- `machinery_hours_per_unit`: Machine hours per unit
- `machinery_cost_per_unit`: Total machine value for the work item

## 6. Aggregates
- `total_value_labor`: Total labor value
- `total_value_material`: Total material value
- `total_value_machinery`: Total machinery value
- `total_rate_value`: Combined unit rate (Direct Cost)

## 7. Metadata
- `language_code`: (en, th, etc.)
- `region_code`: Geographical relevance
- `source_database`: DDC-CWICR v1.0
