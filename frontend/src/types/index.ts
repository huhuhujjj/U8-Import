// Core types for the ingestion workflow

export type WorkflowState =
  | 'FILE_UPLOAD'
  | 'RAW_PREVIEW'
  | 'PARSING_CONFIG'
  | 'TRANSFORMING'
  | 'VALIDATION_REPORT'
  | 'MAPPING_CONFIG'
  | 'PAYLOAD_PREVIEW'
  | 'INGESTION_RUNNING'
  | 'INGESTION_COMPLETE'
  | 'INGESTION_PAUSED';

export type FileType = 'csv' | 'json' | 'excel';
export type ViewMode = 'spreadsheet' | 'code-editor';

// Parsing configuration
export interface ParsingConfig {
  fileType: FileType;
  csv: {
    delimiter: ',' | ';' | '\t' | 'auto';
    hasHeaders: boolean;
    headerRow: number;
    skipRows: number;
    encoding: string;
  };
  json: {
    rootPath: string;
    flattenNested: boolean;
    arrayHandling: 'rows' | 'single-object';
  };
  excel: {
    sheetName: string;
    hasHeaders: boolean;
    headerRow: number;
    range?: string;
  };
}

// Raw file preview
export interface RawPreview {
  mode: ViewMode;
  fileType: FileType;
  fileName: string;
  fileSize: number;
  content: any[][] | string; // 2D array for spreadsheet, string for code
  columns?: string[];
  totalRows: number;
  preview: boolean; // true if showing subset
}

// Transformed records
export interface ParsedRecord {
  rowIndex: number;
  rawData: any;
  jsonData: Record<string, any>;
  valid: boolean;
}

export interface ValidationError {
  rowIndex: number;
  field?: string;
  error: string;
  rawValue: any;
  suggestion?: string;
}

export interface TransformResult {
  success: boolean;
  totalRecords: number;
  successfulRecords: number;
  failedRecords: number;
  parsedData: ParsedRecord[];
  validationErrors: ValidationError[];
  sampleRecords: ParsedRecord[];
  failedSamples: ValidationError[];
  fileName: string; // Source filename for reference
}

// Field mapping configuration
export interface FieldMapping {
  sourceField: string;
  targetField: string;
  transform?: 'string' | 'number' | 'boolean' | 'date';
}

export type IngestionTarget = 'enterspeed' | 'speedtrain';

export interface IngestionConfig {
  target: IngestionTarget; // Which service to ingest to
  apiUrl: string;
  headers: Record<string, string>;
  idField: string; // Field to use for document ID or __ROW_INDEX__
  fieldMappings: FieldMapping[];
  batchSize: number;
  delayBetweenBatches: number;
  forceUpdate: boolean; // Add timestamp to force update
  includeSourceFile: boolean; // Add source filename to payload
  // Speedtrain specific
  indexAlias?: string; // Required for Speedtrain
}

// Payload preview
export interface PayloadSample {
  recordIndex: number;
  url: string;
  headers: Record<string, string>;
  body: Record<string, any>;
}

export interface PayloadPreview {
  sampleCount: number;
  samples: PayloadSample[];
}

// Ingestion progress
export interface IngestionRecord {
  id: string;
  fileId: string;
  rowIndex: number;
  url: string;
  payload: any;
  status: 'pending' | 'success' | 'failed' | 'retrying';
  error?: string;
  attempts: number;
  headers: Record<string, string>;
}

export interface IngestionProgress {
  total: number;
  completed: number;
  failed: number;
  inProgress: number;
  itemsPerSecond: number;
  estimatedTimeRemaining: number;
  currentBatch: number;
  totalBatches: number;
}

// Workflow data
export interface WorkflowData {
  state: WorkflowState;
  rawFile: File | null;
  rawPreview: RawPreview | null;
  parsingConfig: ParsingConfig;
  transformResult: TransformResult | null;
  ingestionConfig: IngestionConfig;
  payloadPreview: PayloadPreview | null;
  ingestionProgress: IngestionProgress | null;
  ingestionRecords: IngestionRecord[];
}
