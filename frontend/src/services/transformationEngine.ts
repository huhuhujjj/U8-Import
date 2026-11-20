import Papa from 'papaparse';
import * as XLSX from 'xlsx';
import { normalizeFieldName } from '../utils/fieldNameNormalizer';
import type {
  ParsingConfig,
  ParsedRecord,
  ValidationError,
  TransformResult,
} from '../types';

export class TransformationEngine {
  static async transform(
    file: File,
    config: ParsingConfig,
    onProgress?: (current: number, total: number) => void
  ): Promise<TransformResult> {
    switch (config.fileType) {
      case 'csv':
        return this.transformCSV(file, config, onProgress);
      case 'json':
        return this.transformJSON(file, config, onProgress);
      case 'excel':
        return this.transformExcel(file, config, onProgress);
      default:
        throw new Error(`Unsupported file type: ${config.fileType}`);
    }
  }

  private static transformCSV(
    file: File,
    config: ParsingConfig,
    onProgress?: (current: number, total: number) => void
  ): Promise<TransformResult> {
    return new Promise((resolve) => {
      Papa.parse(file, {
        complete: (results) => {
          const rawData = results.data as any[][];
          const parsedData: ParsedRecord[] = [];
          const validationErrors: ValidationError[] = [];

          // Skip rows if configured
          const dataToProcess = rawData.slice(config.csv.skipRows);

          // Determine headers
          let originalHeaders: string[];
          let headers: string[];
          let startRow: number;

          if (config.csv.hasHeaders) {
            originalHeaders = dataToProcess[0]?.map((h) => String(h || '').trim());
            // Normalize headers to valid JSON property names
            headers = originalHeaders.map((h) => normalizeFieldName(h));
            startRow = 1;
          } else {
            // Generate column names
            const colCount = dataToProcess[0]?.length || 0;
            headers = Array.from({ length: colCount }, (_, i) => `column_${i + 1}`);
            originalHeaders = headers;
            startRow = 0;
          }

          // Handle duplicate headers by appending numbers
          const usedHeaders = new Set<string>();
          headers = headers.map((header) => {
            let uniqueHeader = header;
            let counter = 1;
            while (usedHeaders.has(uniqueHeader)) {
              uniqueHeader = `${header}_${counter}`;
              counter++;
            }
            usedHeaders.add(uniqueHeader);
            return uniqueHeader;
          });

          // Process each row
          for (let i = startRow; i < dataToProcess.length; i++) {
            const row = dataToProcess[i];
            const rowIndex = i + config.csv.skipRows;

            // Skip completely empty rows (all undefined/null)
            if (!row || row.every((cell) => cell === undefined || cell === null)) continue;

            try {
              // Convert row to JSON object with normalized headers
              const jsonData: Record<string, any> = {};
              headers.forEach((header, idx) => {
                jsonData[header] = row[idx] ?? null;
              });

              // Basic validation - check if row has any data
              const hasData = Object.values(jsonData).some((v) => v !== null && v !== '');
              if (!hasData) {
                validationErrors.push({
                  rowIndex,
                  error: 'Row is empty or has no valid data',
                  rawValue: row,
                });
                continue;
              }

              parsedData.push({
                rowIndex,
                rawData: row,
                jsonData,
                valid: true,
              });
            } catch (error) {
              validationErrors.push({
                rowIndex,
                error: error instanceof Error ? error.message : 'Failed to parse row',
                rawValue: row,
              });
            }

            if (onProgress && i % 100 === 0) {
              onProgress(i, dataToProcess.length);
            }
          }

          onProgress?.(dataToProcess.length, dataToProcess.length);

          resolve({
            success: validationErrors.length === 0,
            totalRecords: dataToProcess.length - startRow,
            successfulRecords: parsedData.length,
            failedRecords: validationErrors.length,
            parsedData,
            validationErrors,
            sampleRecords: parsedData.slice(0, 10),
            failedSamples: validationErrors.slice(0, 10),
            fileName: file.name,
          });
        },
      });
    });
  }

  private static async transformJSON(
    file: File,
    config: ParsingConfig,
    onProgress?: (current: number, total: number) => void
  ): Promise<TransformResult> {
    const text = await file.text();
    const data = JSON.parse(text);

    const parsedData: ParsedRecord[] = [];
    const validationErrors: ValidationError[] = [];

    // Extract array from root path if specified
    let arrayData: any[] = [];
    if (config.json.rootPath) {
      const keys = config.json.rootPath.split('.');
      let current = data;
      for (const key of keys) {
        current = current[key];
      }
      arrayData = Array.isArray(current) ? current : [current];
    } else {
      arrayData = Array.isArray(data) ? data : [data];
    }

    // Process each item
    arrayData.forEach((item, index) => {
      try {
        let jsonData = item;

        // Flatten nested objects if configured
        if (config.json.flattenNested && typeof item === 'object') {
          jsonData = this.flattenObject(item);
        }

        // Validate that it's an object
        if (typeof jsonData !== 'object' || jsonData === null) {
          throw new Error('Item is not a valid object');
        }

        // Normalize field names to valid JSON property names
        const normalizedData: Record<string, any> = {};
        const originalKeys = Object.keys(jsonData);
        const normalizedKeys = originalKeys.map((key) => normalizeFieldName(key));

        // Handle duplicate normalized keys
        const usedKeys = new Set<string>();
        const finalKeys = normalizedKeys.map((key) => {
          let uniqueKey = key;
          let counter = 1;
          while (usedKeys.has(uniqueKey)) {
            uniqueKey = `${key}_${counter}`;
            counter++;
          }
          usedKeys.add(uniqueKey);
          return uniqueKey;
        });

        // Build normalized object
        originalKeys.forEach((originalKey, idx) => {
          normalizedData[finalKeys[idx]] = jsonData[originalKey];
        });

        parsedData.push({
          rowIndex: index,
          rawData: item,
          jsonData: normalizedData,
          valid: true,
        });
      } catch (error) {
        validationErrors.push({
          rowIndex: index,
          error: error instanceof Error ? error.message : 'Failed to parse item',
          rawValue: item,
        });
      }

      if (onProgress && index % 100 === 0) {
        onProgress(index, arrayData.length);
      }
    });

    onProgress?.(arrayData.length, arrayData.length);

    return {
      success: validationErrors.length === 0,
      totalRecords: arrayData.length,
      successfulRecords: parsedData.length,
      failedRecords: validationErrors.length,
      parsedData,
      validationErrors,
      sampleRecords: parsedData.slice(0, 10),
      failedSamples: validationErrors.slice(0, 10),
      fileName: file.name,
    };
  }

  private static async transformExcel(
    file: File,
    config: ParsingConfig,
    onProgress?: (current: number, total: number) => void
  ): Promise<TransformResult> {
    const buffer = await file.arrayBuffer();
    const workbook = XLSX.read(buffer, { type: 'array' });

    // Get specified sheet or first sheet
    const sheetName = config.excel.sheetName || workbook.SheetNames[0];
    const sheet = workbook.Sheets[sheetName];

    // Convert to 2D array
    const rawData = XLSX.utils.sheet_to_json(sheet, { header: 1 }) as any[][];

    const parsedData: ParsedRecord[] = [];
    const validationErrors: ValidationError[] = [];

    // Determine headers
    const headerRow = config.excel.headerRow - 1; // Convert to 0-based index
    let originalHeaders: string[];
    let headers: string[];

    if (config.excel.hasHeaders) {
      originalHeaders = rawData[headerRow]?.map((h) => String(h || '').trim());
      // Normalize headers to valid JSON property names
      headers = originalHeaders.map((h) => normalizeFieldName(h));
    } else {
      headers = Array.from({ length: rawData[0]?.length || 0 }, (_, i) => `column_${i + 1}`);
      originalHeaders = headers;
    }

    const startRow = config.excel.hasHeaders ? headerRow + 1 : 0;

    // Handle duplicate headers by appending numbers
    const usedHeaders = new Set<string>();
    headers = headers.map((header) => {
      let uniqueHeader = header;
      let counter = 1;
      while (usedHeaders.has(uniqueHeader)) {
        uniqueHeader = `${header}_${counter}`;
        counter++;
      }
      usedHeaders.add(uniqueHeader);
      return uniqueHeader;
    });

    // Process each row
    for (let i = startRow; i < rawData.length; i++) {
      const row = rawData[i];

      // Skip completely empty rows (all undefined/null)
      if (!row || row.every((cell) => cell === undefined || cell === null)) continue;

      try {
        // Convert row to JSON object with normalized headers
        const jsonData: Record<string, any> = {};
        headers.forEach((header, idx) => {
          jsonData[header] = row[idx] ?? null;
        });

        // Basic validation
        const hasData = Object.values(jsonData).some((v) => v !== null && v !== '');
        if (!hasData) {
          validationErrors.push({
            rowIndex: i,
            error: 'Row is empty or has no valid data',
            rawValue: row,
          });
          continue;
        }

        parsedData.push({
          rowIndex: i,
          rawData: row,
          jsonData,
          valid: true,
        });
      } catch (error) {
        validationErrors.push({
          rowIndex: i,
          error: error instanceof Error ? error.message : 'Failed to parse row',
          rawValue: row,
        });
      }

      if (onProgress && i % 100 === 0) {
        onProgress(i, rawData.length);
      }
    }

    onProgress?.(rawData.length, rawData.length);

    return {
      success: validationErrors.length === 0,
      totalRecords: rawData.length - startRow,
      successfulRecords: parsedData.length,
      failedRecords: validationErrors.length,
      parsedData,
      validationErrors,
      sampleRecords: parsedData.slice(0, 10),
      failedSamples: validationErrors.slice(0, 10),
      fileName: file.name,
    };
  }

  private static flattenObject(obj: any, prefix = ''): Record<string, any> {
    const flattened: Record<string, any> = {};

    Object.keys(obj).forEach((key) => {
      const value = obj[key];
      const newKey = prefix ? `${prefix}_${key}` : key;

      if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
        Object.assign(flattened, this.flattenObject(value, newKey));
      } else {
        flattened[newKey] = value;
      }
    });

    return flattened;
  }
}
