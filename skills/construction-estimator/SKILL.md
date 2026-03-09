---
name: construction-estimator
description: Professional BOQ and Pricing Engine. Uses DDC-CWICR methodology for resource-based costing (Material/Labor/Machinery split). Use when you need to generate priced tenders, apply profit markups, calculate contingency, or normalize item lists to international standards (OmniClass/Uniclass).
---

# Construction Estimator (DDC-CWICR)

This skill provides a structured workflow for generating professional construction estimates based on the DDC-CWICR open-source database and methodology.

## Core Capabilities

1. **Resource-Based Costing**: Decomposing work items into labor, material, and machinery components.
2. **BOQ Normalization**: Mapping user-provided descriptions to standard DDC work item codes and units.
3. **Markup & Margin Analysis**: Applying professional markups for contingency, overhead, and profit.
4. **Multilingual Support**: Handling technical construction terms in 9 languages (including Thai).

## Usage Instructions

### 1. Data Analysis
When analyzing project drawings or PDFs, categorize work items according to the [DDC Schema](references/schema.md).

### 2. Rate Estimation
Follow the [Resource-Based Costing Methodology](references/methodology.md). For each major work item, estimate the resource split:
- **Material**: Raw cost + wastage.
- **Labor**: Man-hours * hourly rate (including night-shift premiums if applicable).
- **Machinery**: Equipment hours * rental rate.

### 3. Calculations
Use the provided `scripts/estimate_utils.py` to perform consistent calculations for markups.

### 4. Output Formatting
Present BOQs in a clean, hierarchical structure:
- Bill 1: Preliminaries
- Bill 2: Site Preparation / Demolition
- Bill 3+: Specialized Trades (Architectural, M&E, Furniture)

## References
- [DDC 85-Field Schema](references/schema.md)
- [Estimation Methodology](references/methodology.md)
