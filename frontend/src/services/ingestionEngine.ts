import type { IngestionConfig, ParsedRecord, IngestionRecord, IngestionProgress } from '../types';

export class IngestionEngine {
  private records: IngestionRecord[] = [];
  private progress: IngestionProgress = {
    total: 0,
    completed: 0,
    failed: 0,
    inProgress: 0,
    itemsPerSecond: 0,
    estimatedTimeRemaining: 0,
    currentBatch: 0,
    totalBatches: 0,
  };
  private startTime: number = 0;
  private isPaused: boolean = false;
  private isCancelled: boolean = false;
  private config: IngestionConfig;
  private data: ParsedRecord[];
  private onProgress: (progress: IngestionProgress, records: IngestionRecord[]) => void;

  constructor(
    config: IngestionConfig,
    data: ParsedRecord[],
    onProgress: (progress: IngestionProgress, records: IngestionRecord[]) => void
  ) {
    this.config = config;
    this.data = data;
    this.onProgress = onProgress;
    this.progress.total = data.length;
    this.progress.totalBatches = Math.ceil(data.length / config.batchSize);
  }

  async start(): Promise<void> {
    this.startTime = Date.now();
    this.isCancelled = false;
    this.isPaused = false;

    // Initialize ingestion records
    this.records = this.data.map((record, index) => ({
      id: `record-${index}`,
      fileId: 'current-file',
      rowIndex: record.rowIndex,
      url: this.buildUrl(record.jsonData, record.rowIndex),
      payload: this.buildPayload(record.jsonData, record.rowIndex),
      status: 'pending',
      attempts: 0,
      headers: this.config.headers,
    }));

    // Process in batches
    const batches = this.createBatches();

    for (let i = 0; i < batches.length; i++) {
      if (this.isCancelled) break;

      // Wait if paused
      while (this.isPaused && !this.isCancelled) {
        await this.delay(100);
      }

      if (this.isCancelled) break;

      this.progress.currentBatch = i + 1;
      await this.processBatch(batches[i]);

      // Delay between batches
      if (i < batches.length - 1) {
        await this.delay(this.config.delayBetweenBatches);
      }

      this.updateProgress();
    }
  }

  pause(): void {
    this.isPaused = true;
  }

  resume(): void {
    this.isPaused = false;
  }

  cancel(): void {
    this.isCancelled = true;
  }

  async retryFailed(): Promise<void> {
    const failedRecords = this.records.filter((r) => r.status === 'failed');

    if (failedRecords.length === 0) return;

    // Reset failed records to pending
    failedRecords.forEach((record) => {
      record.status = 'retrying';
      record.attempts++;
    });

    this.updateProgress();

    // Process failed records in batches
    const batches = this.createBatches(failedRecords);

    for (const batch of batches) {
      if (this.isCancelled) break;

      await this.processBatch(batch);
      await this.delay(this.config.delayBetweenBatches);
      this.updateProgress();
    }
  }

  private createBatches(recordsToProcess?: IngestionRecord[]): IngestionRecord[][] {
    const records = recordsToProcess || this.records;
    const batches: IngestionRecord[][] = [];

    for (let i = 0; i < records.length; i += this.config.batchSize) {
      batches.push(records.slice(i, i + this.config.batchSize));
    }

    return batches;
  }

  private async processBatch(batch: IngestionRecord[]): Promise<void> {
    this.progress.inProgress = batch.length;
    this.updateProgress();

    const promises = batch.map(async (record) => {
      await this.ingestRecord(record);
      // Decrement in-progress count after each record completes
      this.progress.inProgress = Math.max(0, this.progress.inProgress - 1);
      this.updateProgress();
    });
    await Promise.allSettled(promises);

    this.progress.inProgress = 0;
    this.updateProgress();
  }

  private async ingestRecord(record: IngestionRecord): Promise<void> {
    try {
      const response = await fetch(record.url, {
        method: 'POST',
        headers: record.headers,
        body: JSON.stringify(record.payload),
      });

      if (response.ok) {
        record.status = 'success';
        this.progress.completed++;
      } else {
        const errorText = await response.text();
        record.status = 'failed';
        record.error = `HTTP ${response.status}: ${errorText}`;
        this.progress.failed++;
      }
    } catch (error) {
      record.status = 'failed';
      record.error = error instanceof Error ? error.message : 'Network error';
      this.progress.failed++;
    }
  }

  private buildPayload(jsonData: Record<string, any>, _rowIndex: number): Record<string, any> {
    const payload: Record<string, any> = {};

    this.config.fieldMappings.forEach((mapping) => {
      const sourceValue = jsonData[mapping.sourceField];
      let transformedValue = sourceValue;

      // Apply transformations
      if (mapping.transform === 'number') {
        transformedValue = sourceValue ? parseFloat(sourceValue) : 0;
      } else if (mapping.transform === 'boolean') {
        transformedValue = Boolean(sourceValue);
      } else if (mapping.transform === 'date') {
        transformedValue = sourceValue ? new Date(sourceValue).toISOString() : null;
      } else {
        transformedValue = sourceValue ? String(sourceValue) : '';
      }

      payload[mapping.targetField] = transformedValue;
    });

    // Add timestamp if force update is enabled
    if (this.config.forceUpdate) {
      payload.ts = Date.now();
    }

    return payload;
  }

  private getIdValue(jsonData: Record<string, any>, rowIndex: number): string {
    if (this.config.idField === '__ROW_INDEX__') {
      return String(rowIndex + 1); // 1-based index
    }
    return String(jsonData[this.config.idField] || '');
  }

  private buildUrl(jsonData: Record<string, any>, rowIndex: number): string {
    const idValue = this.getIdValue(jsonData, rowIndex);
    let url = this.config.apiUrl.replace(/\{\{id\}\}/g, idValue);

    if (this.config.target === 'speedtrain' && this.config.indexAlias) {
      url = url.replace(/\{\{indexAlias\}\}/g, this.config.indexAlias);
    }

    return url;
  }

  private updateProgress(): void {
    const elapsedSeconds = (Date.now() - this.startTime) / 1000;
    const completedTotal = this.progress.completed + this.progress.failed;

    if (elapsedSeconds > 0 && completedTotal > 0) {
      this.progress.itemsPerSecond = completedTotal / elapsedSeconds;
      const remaining = this.progress.total - completedTotal;
      this.progress.estimatedTimeRemaining = Math.ceil(
        remaining / this.progress.itemsPerSecond
      );
    }

    this.onProgress(this.progress, this.records);
  }

  private delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}
