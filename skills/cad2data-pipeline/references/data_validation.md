# CAD Data Validation Standards

Ensuring data integrity during the conversion from BIM/CAD to structured data is critical for accurate BOQ generation.

## 1. Validation Checks
- **Schema Compliance**: Verify that all 85 fields (if using DDC schema) are correctly populated.
- **Unit Consistency**: Ensure all measurements are normalized to a single system (e.g., metric).
- **Coordinate Sanity**: Check for zero-length elements or elements far from the origin.
- **Missing Parameters**: Identify elements missing mandatory metadata (e.g., Material or Classification code).

## 2. Reporting
Validation reports should include:
- **Success Rate**: % of elements successfully converted.
- **Error Log**: List of Element IDs that failed validation.
- **Summary Table**: Total quantities extracted vs. expected baseline.

## 3. Feedback Loop
If validation fails, the agent should:
1. Log the specific missing parameters.
2. Request the user to update the source BIM model or provide manual overrides.
