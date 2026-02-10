/**
 * Phase 12: Mission Control Redaction Logic
 * Strictly filters sensitive strings before DOM insertion.
 */

const Redactor = {
    patterns: [
        { regex: /\/Users\/[^\/\s]+/g, replacement: "[PATH_REDACTED]" },
        { regex: /(?:\b|'|")([a-zA-Z0-9_\-\.]{20,})(?:\b|'|")/g, replacement: "[TOKEN_REDACTED]" }, // Generic long token-like strings
        { regex: /\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b/g, replacement: "[IP_REDACTED]" }
    ],

    sanitize: function (text) {
        if (typeof text !== 'string') return text;
        let sanitized = text;
        this.patterns.forEach(p => {
            sanitized = sanitized.replace(p.regex, p.replacement);
        });
        return sanitized;
    }
};

if (typeof module !== 'undefined') {
    module.exports = Redactor;
}
