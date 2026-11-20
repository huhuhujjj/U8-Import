import { create } from 'zustand';
import type { WorkflowData, WorkflowState, ParsingConfig, IngestionConfig } from '../types';

interface WorkflowStore extends WorkflowData {
  setState: (state: WorkflowState) => void;
  setRawFile: (file: File) => void;
  setParsingConfig: (config: Partial<ParsingConfig>) => void;
  setIngestionConfig: (config: Partial<IngestionConfig>) => void;
  reset: () => void;
}

const initialState: WorkflowData = {
  state: 'FILE_UPLOAD',
  rawFile: null,
  rawPreview: null,
  parsingConfig: {
    fileType: 'csv',
    csv: {
      delimiter: ',',
      hasHeaders: true,
      headerRow: 1,
      skipRows: 0,
      encoding: 'utf-8',
    },
    json: {
      rootPath: '',
      flattenNested: false,
      arrayHandling: 'rows',
    },
    excel: {
      sheetName: '',
      hasHeaders: true,
      headerRow: 1,
    },
  },
  transformResult: null,
  ingestionConfig: {
    target: 'enterspeed',
    apiUrl: 'https://api.enterspeed.com/ingest/v2/{{id}}',
    headers: {
      'Content-Type': 'application/json',
      'X-Enterspeed-Type': 'Entity',
      'X-Enterspeed-System': 'drop',
      'x-api-key': '',
    },
    idField: '',
    fieldMappings: [],
    batchSize: 5,
    delayBetweenBatches: 100,
    forceUpdate: false,
    includeSourceFile: false,
    indexAlias: '',
  },
  payloadPreview: null,
  ingestionProgress: null,
  ingestionRecords: [],
};

export const useWorkflowStore = create<WorkflowStore>((set) => ({
  ...initialState,

  setState: (state: WorkflowState) => set({ state }),

  setRawFile: (file: File) => set({ rawFile: file }),

  setParsingConfig: (config: Partial<ParsingConfig>) =>
    set((state) => ({
      parsingConfig: {
        ...state.parsingConfig,
        ...config,
      },
    })),

  setIngestionConfig: (config: Partial<IngestionConfig>) =>
    set((state) => ({
      ingestionConfig: {
        ...state.ingestionConfig,
        ...config,
      },
    })),

  reset: () => set(initialState),
}));
