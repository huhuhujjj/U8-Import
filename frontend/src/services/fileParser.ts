import Papa from 'papaparse';
import * as XLSX from 'xlsx';
import type { FileType, RawPreview } from '../types';

export class FileParser {
  static async parseFile(file: File, fileType: FileType): Promise<RawPreview> {
    switch (fileType) {
      case 'csv':
        return this.parseCSV(file);
      case 'json':
        return this.parseJSON(file);
      case 'excel':
        return this.parseExcel(file);
      default:
        throw new Error(`Unsupported file type: ${fileType}`);
    }
  }

  private static parseCSV(file: File): Promise<RawPreview> {
    return new Promise((resolve, reject) => {
      Papa.parse(file, {
        complete: (results) => {
          const data = results.data as any[][];

          resolve({
            mode: 'spreadsheet',
            fileType: 'csv',
            fileName: file.name,
            fileSize: file.size,
            content: data,
            columns: data[0]?.map((_, i) => `Column ${i + 1}`),
            totalRows: data.length,
            preview: data.length > 1000,
          });
        },
        error: (error) => reject(error),
        skipEmptyLines: false,
      });
    });
  }

  private static async parseJSON(file: File): Promise<RawPreview> {
    const text = await file.text();
    const data = JSON.parse(text);

    // Convert to string for code editor view
    const formatted = JSON.stringify(data, null, 2);
    const lines = formatted.split('\n');

    return {
      mode: 'code-editor',
      fileType: 'json',
      fileName: file.name,
      fileSize: file.size,
      content: formatted,
      totalRows: Array.isArray(data) ? data.length : 1,
      preview: lines.length > 1000,
    };
  }

  private static async parseExcel(file: File): Promise<RawPreview> {
    const buffer = await file.arrayBuffer();
    const workbook = XLSX.read(buffer, { type: 'array' });

    // Get first sheet
    const sheetName = workbook.SheetNames[0];
    const sheet = workbook.Sheets[sheetName];

    // Convert to 2D array
    const data = XLSX.utils.sheet_to_json(sheet, { header: 1 }) as any[][];

    return {
      mode: 'spreadsheet',
      fileType: 'excel',
      fileName: file.name,
      fileSize: file.size,
      content: data,
      columns: data[0]?.map((_, i) => `Column ${i + 1}`),
      totalRows: data.length,
      preview: data.length > 1000,
    };
  }

  static convertToCodeView(preview: RawPreview): string {
    if (preview.mode === 'code-editor') {
      return preview.content as string;
    }

    // Convert spreadsheet data to JSON
    const data = preview.content as any[][];
    return JSON.stringify(data, null, 2);
  }

  static convertToSpreadsheetView(preview: RawPreview): any[][] {
    if (preview.mode === 'spreadsheet') {
      return preview.content as any[][];
    }

    // Parse JSON string to array
    try {
      const data = JSON.parse(preview.content as string);

      if (Array.isArray(data) && data.length > 0 && typeof data[0] === 'object') {
        // Convert array of objects to 2D array
        const keys = Object.keys(data[0]);
        const rows = [keys]; // Header row

        data.forEach(item => {
          rows.push(keys.map(key => item[key]));
        });

        return rows;
      } else if (Array.isArray(data)) {
        // Already a 2D array or simple array
        return Array.isArray(data[0]) ? data : [data];
      } else {
        // Single object - convert to single row
        const keys = Object.keys(data);
        return [keys, keys.map(key => data[key])];
      }
    } catch {
      return [['Error parsing content']];
    }
  }
}
