import { useEffect, useState } from 'react';
import Editor from '@monaco-editor/react';
import { Box, Button, Flex, Grid, Heading, Text, Stack, Spinner } from '@chakra-ui/react';
import { useWorkflowStore } from '../stores/workflowStore';
import { TransformationEngine } from '../services/transformationEngine';
import type { TransformResult } from '../types';

export function ValidationReport() {
  const { rawFile, parsingConfig, setState } = useWorkflowStore();
  const [result, setResult] = useState<TransformResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [progress, setProgress] = useState({ current: 0, total: 0 });
  const [showAllSuccessful, setShowAllSuccessful] = useState(false);
  const [showAllFailed, setShowAllFailed] = useState(false);

  useEffect(() => {
    if (!rawFile) return;

    const transform = async () => {
      try {
        setLoading(true);
        const transformResult = await TransformationEngine.transform(
          rawFile,
          parsingConfig,
          (current, total) => setProgress({ current, total })
        );
        setResult(transformResult);

        // Store in workflow state for later use
        useWorkflowStore.setState({ transformResult });
      } catch (error) {
        console.error('Transformation error:', error);
      } finally {
        setLoading(false);
      }
    };

    transform();
  }, [rawFile, parsingConfig]);

  const handleProceed = () => {
    setState('MAPPING_CONFIG');
  };

  if (loading) {
    return (
      <Box px={6} py={16}>
        <Stack alignItems="center" gap={3}>
          <Spinner size="lg" colorPalette="brand" borderWidth="3px" />
          <Text fontSize="sm" color="gray.600">Transforming data to JSON...</Text>
          <Text fontSize="xs" color="gray.500">
            {progress.current} / {progress.total} records processed
          </Text>
        </Stack>
      </Box>
    );
  }

  if (!result) return null;

  const successRate = ((result.successfulRecords / result.totalRecords) * 100).toFixed(1);

  return (
    <Box px={6} py={6} pb="80px">
      <Box mb={4}>
        <Heading size="md" color="gray.900">Transformation Results</Heading>
        <Text fontSize="sm" color="gray.500" mt={1}>Review the parsed data before proceeding</Text>
      </Box>

      {/* Summary Cards - Cleaner, more compact */}
      <Grid templateColumns="repeat(3, 1fr)" gap={3} mb={6}>
        <Box bg="white" borderWidth="1px" borderColor="gray.200" borderRadius="md" p={3}>
          <Text fontSize="2xl" fontWeight="bold" color="success.600">{result.successfulRecords}</Text>
          <Text fontSize="xs" color="gray.600" mt={0.5}>Successfully Parsed</Text>
          <Text fontSize="xs" color="gray.500" mt={1}>{successRate}% success rate</Text>
        </Box>
        <Box bg="white" borderWidth="1px" borderColor="gray.200" borderRadius="md" p={3}>
          <Text fontSize="2xl" fontWeight="bold" color="error.600">{result.failedRecords}</Text>
          <Text fontSize="xs" color="gray.600" mt={0.5}>Failed to Parse</Text>
        </Box>
        <Box bg="white" borderWidth="1px" borderColor="gray.200" borderRadius="md" p={3}>
          <Text fontSize="2xl" fontWeight="bold" color="gray.900">{result.totalRecords}</Text>
          <Text fontSize="xs" color="gray.600" mt={0.5}>Total Records</Text>
        </Box>
      </Grid>

      {/* Successful Samples */}
      {result.successfulRecords > 0 && (
        <Box bg="white" borderWidth="1px" borderColor="gray.200" borderRadius="md" p={4} mb={4}>
          <Flex alignItems="center" justifyContent="space-between" mb={3}>
            <Heading size="sm" color="gray.900">
              Sample Successful Records (JSON)
            </Heading>
            {result.successfulRecords > 10 && (
              <Button
                onClick={() => setShowAllSuccessful(!showAllSuccessful)}
                size="xs"
                variant="ghost"
                colorScheme="brand"
              >
                {showAllSuccessful ? 'Show Samples Only' : `Show All ${result.successfulRecords}`}
              </Button>
            )}
          </Flex>

          <Stack gap={2}>
            {(showAllSuccessful ? result.parsedData : result.sampleRecords).map((record, idx) => (
              <Box key={idx} borderWidth="1px" borderColor="gray.200" borderRadius="md">
                <details open={idx === 0}>
                  <Box
                    as="summary"
                    px={3}
                    py={2}
                    fontSize="sm"
                    cursor="pointer"
                    _hover={{ bg: 'gray.50' }}
                  >
                    Row {record.rowIndex + 1}
                  </Box>
                  <Box borderTopWidth="1px" borderColor="gray.200">
                    <Editor
                      height="180px"
                      language="json"
                      value={JSON.stringify(record.jsonData, null, 2)}
                      options={{
                        readOnly: true,
                        minimap: { enabled: false },
                        scrollBeyondLastLine: false,
                        fontSize: 12,
                      }}
                      theme="vs-light"
                    />
                  </Box>
                </details>
              </Box>
            ))}
          </Stack>
        </Box>
      )}

      {/* Failed Records */}
      {result.failedRecords > 0 && (
        <Box bg="error.50" borderWidth="1px" borderColor="error.200" borderRadius="md" p={4} mb={4}>
          <Flex alignItems="center" justifyContent="space-between" mb={3}>
            <Heading size="sm" color="error.900">Failed Records & Errors</Heading>
            {result.failedRecords > 10 && (
              <Button
                onClick={() => setShowAllFailed(!showAllFailed)}
                size="xs"
                variant="ghost"
                colorScheme="error"
              >
                {showAllFailed ? 'Show Samples Only' : `Show All ${result.failedRecords}`}
              </Button>
            )}
          </Flex>

          <Stack gap={2}>
            {(showAllFailed ? result.validationErrors : result.failedSamples).map((error, idx) => (
              <Box key={idx} bg="white" borderWidth="1px" borderColor="error.300" borderRadius="md" p={3}>
                <Text fontSize="sm" fontWeight="medium" color="error.900" mb={1}>
                  Row {error.rowIndex + 1}: {error.error}
                </Text>
                {error.field && (
                  <Text fontSize="xs" color="error.700" mb={1}>Field: {error.field}</Text>
                )}
                <Text fontSize="xs" color="gray.600">
                  <Text as="span" fontWeight="medium">Raw value: </Text>
                  <Box as="code" bg="gray.100" px={1} borderRadius="sm" display="inline">
                    {JSON.stringify(error.rawValue)}
                  </Box>
                </Text>
                {error.suggestion && (
                  <Text fontSize="xs" color="brand.600" mt={1}>
                    {error.suggestion}
                  </Text>
                )}
              </Box>
            ))}
          </Stack>

          <Text fontSize="xs" color="gray.700" mt={3}>
            These records will be skipped during ingestion. You can fix them in the source file and re-upload.
          </Text>
        </Box>
      )}

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
          <Flex px={6} py={4} justifyContent="space-between">
            <Button
              onClick={() => setState('PARSING_CONFIG')}
              size="sm"
              variant="outline"
              colorScheme="gray"
            >
              Back to Settings
            </Button>
            <Flex gap={2}>
              {result.failedRecords > 0 && (
                <Button
                  onClick={() => {
                    // Export failed records as CSV for user to fix
                    const csv = result.validationErrors
                      .map(e => `${e.rowIndex},${e.error},"${JSON.stringify(e.rawValue)}"`)
                      .join('\n');
                    const blob = new Blob([`Row,Error,Raw Data\n${csv}`], { type: 'text/csv' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'failed-records.csv';
                    a.click();
                  }}
                  size="sm"
                  variant="outline"
                  colorScheme="error"
                >
                  Export Failed Records
                </Button>
              )}
              <Button
                onClick={handleProceed}
                disabled={result.successfulRecords === 0}
                size="sm"
                colorScheme="brand"
              >
                {result.successfulRecords === 0
                  ? 'No Valid Records to Proceed'
                  : `Proceed with ${result.successfulRecords} Records →`}
              </Button>
            </Flex>
          </Flex>
        </Box>
      </Box>
    </Box>
  );
}
