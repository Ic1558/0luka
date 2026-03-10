# CAD to Data Conversion Workflows

This document outlines the workflows for converting BIM/CAD files (Revit, IFC, DWG, DGN) into structured data (Excel, CSV, JSON) for use in AI agents and estimation pipelines.

## 1. Supported Formats
- **Revit (.rvt)**: Automated extraction of parameters, families, and quantities.
- **IFC (.ifc)**: Open BIM data extraction.
- **AutoCAD (.dwg)**: Extraction of block attributes, layers, and geometry metadata.
- **MicroStation (.dgn)**: Basic geometry and property extraction.

## 2. Extraction Pipeline (ETL)
The standard ETL pipeline involves:
1. **Extract**: Using `RvtExporter.exe` or `DwgExporter.exe` (CLI tools).
2. **Transform**: Normalizing the extracted Excel/JSON data.
3. **Load**: Importing into a database or directly into a BOQ.

## 3. Revit QTO (Quantity Takeoff)
The pipeline extracts the following metadata:
- **Element IDs**: For tracking and validation.
- **Parameters**: Instance and Type parameters.
- **Quantities**: Length, Area, Volume, and Count.
- **Classification**: Mapping elements to OmniClass/Uniclass.

## 4. Automation via n8n
Workflows can be triggered to:
- Monitor a folder for new CAD files.
- Automatically run the converter.
- Send the structured data to the `construction-estimator` skill for pricing.
