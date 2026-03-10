---
name: cad2data-pipeline
description: BIM/CAD to Data ETL. Automatically extracts quantities, Element IDs, and metadata from Revit (.rvt), AutoCAD (.dwg), IFC (.ifc), and DGN files. Use when the user has design models and needs structured CSV/Excel/JSON for Quantity Takeoff (QTO) or to provide inputs for the construction-estimator skill.
---

# CAD to Data Pipeline (BIM ETL)

This skill provides the procedural knowledge to automate the extraction of quantities and metadata from various CAD and BIM formats.

## Core Capabilities

1. **Multi-Format Extraction**: Handling Revit (.rvt), IFC, and AutoCAD (.dwg) files using specialized CLI exporters.
2. **Quantity Takeoff (QTO)**: Extracting volumes, areas, and lengths directly from design models without a CAD license.
3. **Data Normalization**: Transforming raw CAD metadata into structured formats compatible with the `construction-estimator` skill.
4. **Automated Validation**: Running multi-format validation checks to ensure data integrity before estimation.

## Usage Instructions

### 1. File Ingestion
Identify the source file format and the target data requirements (e.g., "Extract all wall quantities from this Revit file").

### 2. Execution Workflow
Follow the [Conversion Workflows](references/conversion_workflows.md):
- Use `RvtExporter` or similar CLI tools for extraction.
- Target outputs: Excel or JSON.

### 3. Validation
Perform [Data Validation](references/data_validation.md) on the extracted output:
- Check for missing parameters.
- Verify unit consistency.

### 4. Integration
Pass the validated data to the `construction-estimator` skill to generate a DDC-compliant priced BOQ.

## References
- [Conversion Workflows](references/conversion_workflows.md)
- [Data Validation Standards](references/data_validation.md)
