import { useState, useEffect } from 'react';
import Editor from '@monaco-editor/react';
import { Box, Button, Flex, Grid, Heading, Text, Stack } from '@chakra-ui/react';
import { useWorkflowStore } from '../stores/workflowStore';
import type { PayloadSample } from '../types';

export function PayloadPreview() {
  const { transformResult, ingestionConfig, setState } = useWorkflowStore();
  const [samples, setSamples] = useState<PayloadSample[]>([]);
  const [showAll, setShowAll] = useState(false);
  const [testingDryRun, setTestingDryRun] = useState(false);
  const [dryRunResults, setDryRunResults] = useState<{ success: number; failed: number } | null>(null);

  useEffect(() => {
    if (!transformResult || !ingestionConfig) return;

    // Generate payload samples from first 5-10 records
    const sampleCount = Math.min(10, transformResult.parsedData.length);
    const generatedSamples: PayloadSample[] = [];

    for (let i = 0; i < sampleCount; i++) {
      const record = transformResult.parsedData[i];
      const payload = buildPayload(record.jsonData, record.rowIndex);
      const url = buildUrl(record.jsonData, record.rowIndex);

      generatedSamples.push({
        recordIndex: record.rowIndex,
        url,
        headers: ingestionConfig.headers,
        body: payload,
      });
    }

    setSamples(generatedSamples);
  }, [transformResult, ingestionConfig]);

  const buildPayload = (jsonData: Record<string, any>, _rowIndex?: number): Record<string, any> => {
    const payload: Record<string, any> = {};

    ingestionConfig.fieldMappings.forEach((mapping) => {
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
    if (ingestionConfig.forceUpdate) {
      payload.ts = Date.now();
    }

    // Add source filename if enabled
    if (ingestionConfig.includeSourceFile && transformResult?.fileName) {
      payload.source = transformResult.fileName;
    }

    return payload;
  };

  const getIdValue = (jsonData: Record<string, any>, rowIndex: number): string => {
    if (ingestionConfig.idField === '__ROW_INDEX__') {
      return String(rowIndex + 1); // 1-based index
    }
    return String(jsonData[ingestionConfig.idField] || '');
  };

  const buildUrl = (jsonData: Record<string, any>, rowIndex: number): string => {
    const idValue = getIdValue(jsonData, rowIndex);
    let url = ingestionConfig.apiUrl.replace(/\{\{id\}\}/g, idValue);

    // Replace indexAlias for Speedtrain
    if (ingestionConfig.target === 'speedtrain' && ingestionConfig.indexAlias) {
      url = url.replace(/\{\{indexAlias\}\}/g, ingestionConfig.indexAlias);
    }

    return url;
  };

  const handleDryRun = async () => {
    if (!transformResult) return;

    setTestingDryRun(true);
    setDryRunResults(null);

    try {
      // Test first 5 records
      const testRecords = transformResult.parsedData.slice(0, 5);
      let successCount = 0;
      let failedCount = 0;

      for (const record of testRecords) {
        const payload = buildPayload(record.jsonData, record.rowIndex);
        const url = buildUrl(record.jsonData, record.rowIndex);

        try {
          const response = await fetch(url, {
            method: 'POST',
            headers: ingestionConfig.headers,
            body: JSON.stringify(payload),
          });

          if (response.ok) {
            successCount++;
          } else {
            failedCount++;
            console.error(`Dry run failed for record ${record.rowIndex}:`, await response.text());
          }
        } catch (error) {
          failedCount++;
          console.error(`Dry run error for record ${record.rowIndex}:`, error);
        }
      }

      setDryRunResults({ success: successCount, failed: failedCount });
    } catch (error) {
      alert('Dry run failed: ' + (error instanceof Error ? error.message : 'Unknown error'));
    } finally {
      setTestingDryRun(false);
    }
  };

  const handleDownloadPayloads = () => {
    if (!transformResult) return;

    const allPayloads = transformResult.parsedData.map((record) => ({
      rowIndex: record.rowIndex,
      url: buildUrl(record.jsonData, record.rowIndex),
      headers: ingestionConfig.headers,
      payload: buildPayload(record.jsonData, record.rowIndex),
    }));

    const blob = new Blob([JSON.stringify(allPayloads, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'payloads.json';
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleStartIngestion = () => {
    setState('INGESTION_RUNNING');
  };

  if (!transformResult || samples.length === 0) {
    return (
      <Box px={6} py={6}>
        <Text fontSize="sm" color="gray.600">Generating payload previews...</Text>
      </Box>
    );
  }

  const displaySamples = showAll ? samples : samples.slice(0, 5);
  const estimatedTime = Math.ceil(
    (transformResult.successfulRecords / ingestionConfig.batchSize) *
      (ingestionConfig.delayBetweenBatches / 1000)
  );

  return (
    <Box px={6} py={6} pb="80px">
      <Box mb={4}>
        <Heading size="md" color="gray.900">Payload Preview</Heading>
        <Text fontSize="sm" color="gray.500" mt={1}>
          Review the exact requests that will be sent to the API
        </Text>
      </Box>

      {/* Summary Card */}
      <Box bg="brand.50" borderWidth="1px" borderColor="brand.200" borderRadius="md" p={4} mb={4}>
        <Heading size="sm" color="brand.900" mb={2}>Ready to Ingest</Heading>
        <Grid templateColumns="repeat(2, 1fr)" gap={4} fontSize="sm">
          <Box>
            <Text as="span" color="brand.700">Total Records:</Text>{' '}
            <Text as="span" fontWeight="semibold">{transformResult.successfulRecords}</Text>
          </Box>
          <Box>
            <Text as="span" color="brand.700">Batch Size:</Text>{' '}
            <Text as="span" fontWeight="semibold">{ingestionConfig.batchSize} concurrent</Text>
          </Box>
          <Box>
            <Text as="span" color="brand.700">Estimated Time:</Text>{' '}
            <Text as="span" fontWeight="semibold">~{estimatedTime} seconds</Text>
          </Box>
          <Box>
            <Text as="span" color="brand.700">API Endpoint:</Text>{' '}
            <Text as="span" fontWeight="semibold" fontSize="xs">{ingestionConfig.apiUrl}</Text>
          </Box>
        </Grid>
      </Box>

      {/* Dry Run Results */}
      {dryRunResults && (
        <Box
          borderWidth="1px"
          borderRadius="md"
          p={3}
          mb={4}
          bg={dryRunResults.failed > 0 ? 'error.50' : 'success.50'}
          borderColor={dryRunResults.failed > 0 ? 'error.200' : 'success.200'}
        >
          <Heading size="sm" mb={2}>
            {dryRunResults.failed > 0 ? '⚠️ Dry Run Results' : '✅ Dry Run Successful'}
          </Heading>
          <Text fontSize="sm">
            Tested 5 records: {dryRunResults.success} succeeded, {dryRunResults.failed} failed
          </Text>
          {dryRunResults.failed > 0 && (
            <Text fontSize="sm" color="error.700" mt={1}>
              Check the console for error details. You may need to adjust your configuration.
            </Text>
          )}
        </Box>
      )}

      {/* Sample Payloads */}
      <Box bg="white" borderWidth="1px" borderColor="gray.200" borderRadius="md" p={4} mb={4}>
        <Flex alignItems="center" justifyContent="space-between" mb={3}>
          <Heading size="sm" color="gray.900">Sample Requests</Heading>
          {samples.length > 5 && (
            <Button
              onClick={() => setShowAll(!showAll)}
              size="sm"
              variant="ghost"
              colorScheme="brand"
            >
              {showAll ? 'Show First 5 Only' : `Show All ${samples.length}`}
            </Button>
          )}
        </Flex>

        <Stack gap={4}>
          {displaySamples.map((sample, idx) => (
            <Box key={idx} borderWidth="1px" borderRadius="md">
              <details open={idx === 0}>
                <Box
                  as="summary"
                  px={4}
                  py={2}
                  cursor="pointer"
                  _hover={{ bg: 'gray.50' }}
                  fontWeight="medium"
                >
                  Record {sample.recordIndex + 1}
                </Box>
                <Box borderTopWidth="1px" p={4} bg="gray.50">
                  <Stack gap={3}>
                    <Box>
                      <Text fontSize="sm" fontWeight="semibold" mb={1}>URL:</Text>
                      <Box
                        as="code"
                        fontSize="xs"
                        bg="white"
                        px={2}
                        py={1}
                        borderRadius="md"
                        borderWidth="1px"
                        display="block"
                      >
                        POST {sample.url}
                      </Box>
                    </Box>

                    <Box>
                      <Text fontSize="sm" fontWeight="semibold" mb={1}>Headers:</Text>
                      <Editor
                        height="120px"
                        language="json"
                        value={JSON.stringify(sample.headers, null, 2)}
                        options={{
                          readOnly: true,
                          minimap: { enabled: false },
                          scrollBeyondLastLine: false,
                          fontSize: 12,
                          lineNumbers: 'off',
                        }}
                        theme="vs-light"
                      />
                    </Box>

                    <Box>
                      <Text fontSize="sm" fontWeight="semibold" mb={1}>Body:</Text>
                      <Editor
                        height="200px"
                        language="json"
                        value={JSON.stringify(sample.body, null, 2)}
                        options={{
                          readOnly: true,
                          minimap: { enabled: false },
                          scrollBeyondLastLine: false,
                          fontSize: 12,
                          lineNumbers: 'off',
                        }}
                        theme="vs-light"
                      />
                    </Box>
                  </Stack>
                </Box>
              </details>
            </Box>
          ))}
        </Stack>
      </Box>

      {/* Sticky Actions Footer */}
      <Box
        position="fixed"
        bottom={0}
        left={0}
        right={0}
        bg="white"
        borderTopWidth="1px"
        borderColor="gray.200"
        boxShadow="0 -2px 8px rgba(0, 0, 0, 0.04)"
        zIndex={10}
      >
        <Box maxWidth="1920px" margin="0 auto">
          <Flex px={6} py={4} justifyContent="space-between" alignItems="center">
            <Button
              onClick={() => setState('MAPPING_CONFIG')}
              size="sm"
              variant="outline"
              colorScheme="gray"
            >
              Back to Mapping
            </Button>

            <Flex gap={2}>
              <Button
                onClick={handleDownloadPayloads}
                size="sm"
                variant="outline"
                colorScheme="brand"
              >
                Download All Payloads
              </Button>
              <Button
                onClick={handleDryRun}
                disabled={testingDryRun}
                size="sm"
                variant="outline"
                colorScheme="success"
              >
                {testingDryRun ? 'Testing...' : 'Test with 5 Records'}
              </Button>
              <Button
                onClick={handleStartIngestion}
                size="sm"
                colorScheme="brand"
              >
                START INGESTION →
              </Button>
            </Flex>
          </Flex>
        </Box>
      </Box>
    </Box>
  );
}
