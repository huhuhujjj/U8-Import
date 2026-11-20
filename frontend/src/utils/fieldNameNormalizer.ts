/**
 * Normalizes field names to be valid JSON property names
 * - Removes special characters except underscores
 * - Converts spaces to underscores
 * - Removes parentheses and other invalid characters
 * - Ensures it doesn't start with a digit
 * - Converts to camelCase or snake_case
 */
export function normalizeFieldName(fieldName: string): string {
  if (!fieldName) return 'field';

  let normalized = fieldName;

  // Remove or replace common problematic characters
  normalized = normalized
    .trim()
    // Replace spaces with underscores
    .replace(/\s+/g, '_')
    // Remove parentheses and their content (e.g., "(DAN)" -> "")
    .replace(/\([^)]*\)/g, '')
    // Remove brackets
    .replace(/[\[\]]/g, '')
    // Remove quotes
    .replace(/['"]/g, '')
    // Remove other special characters except underscores and hyphens
    .replace(/[^a-zA-Z0-9_-]/g, '')
    // Replace hyphens with underscores
    .replace(/-/g, '_')
    // Remove multiple consecutive underscores
    .replace(/_+/g, '_')
    // Remove leading/trailing underscores
    .replace(/^_+|_+$/g, '');

  // Ensure it doesn't start with a digit
  if (normalized && /^\d/.test(normalized)) {
    normalized = 'field_' + normalized;
  }

  // If empty after normalization, use a default
  if (!normalized) {
    normalized = 'field';
  }

  return normalized;
}

/**
 * Normalizes all field names in a data object
 */
export function normalizeDataObject(data: Record<string, any>): Record<string, any> {
  const normalized: Record<string, any> = {};

  Object.entries(data).forEach(([key, value]) => {
    const normalizedKey = normalizeFieldName(key);
    normalized[normalizedKey] = value;
  });

  return normalized;
}

/**
 * Creates a mapping from original field names to normalized names
 */
export function createFieldNameMapping(originalFields: string[]): Map<string, string> {
  const mapping = new Map<string, string>();

  originalFields.forEach((field) => {
    const normalized = normalizeFieldName(field);
    mapping.set(field, normalized);
  });

  // Handle duplicates by appending numbers
  const usedNames = new Set<string>();
  const finalMapping = new Map<string, string>();

  originalFields.forEach((field) => {
    let normalized = mapping.get(field)!;
    let counter = 1;

    while (usedNames.has(normalized)) {
      normalized = `${mapping.get(field)}_${counter}`;
      counter++;
    }

    usedNames.add(normalized);
    finalMapping.set(field, normalized);
  });

  return finalMapping;
}
