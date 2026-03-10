# Resource-Based Costing Methodology

DDC-CWICR follows a bottom-up costing methodology where every "Work Item" is decomposed into its constituent "Resources".

## 1. Work Item Decomposition
A work item like "Lightweight Concrete Brick Wall" is not just a single price. It is composed of:
- **Materials**: Bricks, Mortar, Water, Scaffolding ties.
- **Labor**: Mason, Helper.
- **Machinery**: Mortar mixer (if used).

## 2. Unit Rate Calculation
The formula for a direct unit rate is:
`Total Rate = (Material Qty * Unit Price) + (Labor Hours * Hourly Rate) + (Machinery Hours * Hourly Rate)`

## 3. BIM Integration (4D/5D)
The DDC pipeline supports extracting BIM data (volumes, areas) and automatically mapping them to `rate_code` entries using semantic search. This transforms a 3D model into:
- **4D**: Scheduling (using productivity rates).
- **5D**: Costing (using resource-based unit rates).

## 4. Languages and Localization
The database supports 9 languages. Always search using the original technical terms if possible, or use semantic search to map local terms (e.g., "อิฐมวลเบา") to standard items.
