import { useEffect, useState, useRef } from 'react';
import { Box, Button, Flex, Grid, Heading, Text, Stack, Spinner, Table } from '@chakra-ui/react';
import { useWorkflowStore } from '../stores/workflowStore';
import { IngestionEngine } from '../services/ingestionEngine';
import type { IngestionProgress as IngestionProgressType, IngestionRecord } from '../types';

export function IngestionProgress() {
  const { transformResult, ingestionConfig, setState } = useWorkflowStore();
  const [progress, setProgress] = useState<IngestionProgressType | null>(null);
  const [records, setRecords] = useState<IngestionRecord[]>([]);
  const [status, setStatus] = useState<'running' | 'paused' | 'completed' | 'cancelled'>('running');
  const engineRef = useRef<IngestionEngine | null>(null);
  const lastUpdateRef = useRef<number>(0);

  useEffect(() => {
    if (!transformResult || !ingestionConfig) return;

    const engine = new IngestionEngine(
      ingestionConfig,
      transformResult.parsedData,
      (newProgress, newRecords) => {
        const now = Date.now();
        // Throttle updates to every 500ms to reduce browser load
        if (now - lastUpdateRef.current > 500 || newProgress.completed + newProgress.failed === newProgress.total) {
          setProgress(newProgress);
          // Only store failed records to reduce memory usage
          setRecords(newRecords.filter(r => r.status === 'failed'));
          lastUpdateRef.current = now;
        } else {
          // Always update failed records immediately
          const failedRecords = newRecords.filter(r => r.status === 'failed');
          if (failedRecords.length !== records.length) {
            setRecords(failedRecords);
          }
        }

        // Check if completed
        const total = newProgress.completed + newProgress.failed;
        if (total === newProgress.total && newProgress.inProgress === 0) {
          setStatus('completed');
          setProgress(newProgress);
          setRecords(newRecords.filter(r => r.status === 'failed'));
        }
      }
    );

    engineRef.current = engine;

    // Start ingestion
    engine.start();

    return () => {
      if (engineRef.current) {
        engineRef.current.cancel();
      }
    };
  }, [transformResult, ingestionConfig]);

  const handlePause = () => {
    if (engineRef.current) {
      engineRef.current.pause();
      setStatus('paused');
    }
  };

  const handleResume = () => {
    if (engineRef.current) {
      engineRef.current.resume();
      setStatus('running');
    }
  };

  const handleCancel = () => {
    if (engineRef.current) {
      engineRef.current.cancel();
      setStatus('cancelled');
    }
  };

  const handleRetryFailed = async () => {
    if (engineRef.current) {
      setStatus('running');
      await engineRef.current.retryFailed();
    }
  };

  const handleExportFailed = () => {
    const failedRecords = records.filter((r) => r.status === 'failed');
    const csv = failedRecords
      .map((r) => `${r.rowIndex},"${r.error || 'Unknown error'}","${JSON.stringify(r.payload).replace(/"/g, '""')}"`)
      .join('\n');

    const blob = new Blob([`Row,Error,Payload\n${csv}`], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'failed-ingestions.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!progress) {
    return (
      <Box px={6} py={16}>
        <Stack alignItems="center" gap={3}>
          <Spinner size="lg" colorPalette="brand" borderWidth="3px" />
          <Text fontSize="sm" color="gray.600">Initializing ingestion...</Text>
        </Stack>
      </Box>
    );
  }

  const progressPercentage = ((progress.completed + progress.failed) / progress.total) * 100;
  const successRate = progress.completed / (progress.completed + progress.failed || 1) * 100;

  return (
    <Box px={6} py={6} pb="80px">
      <Box mb={4}>
        <Heading size="md" color="gray.900">
          {status === 'completed' ? 'Ingestion Complete' : 'Ingestion in Progress'}
        </Heading>
        <Text fontSize="sm" color="gray.500" mt={1}>
          {status === 'running' && 'Processing your data...'}
          {status === 'paused' && 'Ingestion paused'}
          {status === 'completed' && 'All records have been processed'}
          {status === 'cancelled' && 'Ingestion cancelled'}
        </Text>
      </Box>

      {/* Simplified Stats */}
      <Grid templateColumns="repeat(3, 1fr)" gap={4} mb={4}>
        <Box bg="white" borderWidth="1px" borderColor="gray.200" borderRadius="md" p={4}>
          <Text fontSize="sm" color="gray.600" mb={1}>Processed</Text>
          <Text fontSize="3xl" fontWeight="bold" color="gray.900">
            {progress.completed + progress.failed}
          </Text>
          <Text fontSize="sm" color="gray.500">of {progress.total} ({progressPercentage.toFixed(1)}%)</Text>
        </Box>
        <Box bg="white" borderWidth="1px" borderColor="gray.200" borderRadius="md" p={4}>
          <Text fontSize="sm" color="gray.600" mb={1}>Successful</Text>
          <Text fontSize="3xl" fontWeight="bold" color="success.600">{progress.completed}</Text>
          <Text fontSize="sm" color="gray.500">{successRate.toFixed(1)}% success rate</Text>
        </Box>
        <Box bg="white" borderWidth="1px" borderColor="gray.200" borderRadius="md" p={4}>
          <Text fontSize="sm" color="gray.600" mb={1}>Failed</Text>
          <Text fontSize="3xl" fontWeight="bold" color="error.600">{progress.failed}</Text>
          {progress.failed > 0 && (
            <Text fontSize="sm" color="error.500">See details below</Text>
          )}
        </Box>
      </Grid>

      {/* Control Buttons */}
      {status !== 'completed' && status !== 'cancelled' && (
        <Flex gap={2} mb={4}>
          {status === 'running' ? (
            <Button
              onClick={handlePause}
              colorScheme="warning"
              size="md"
            >
              Pause
            </Button>
          ) : (
            <Button
              onClick={handleResume}
              colorScheme="success"
              size="md"
            >
              Resume
            </Button>
          )}
          <Button
            onClick={handleCancel}
            colorScheme="error"
            size="md"
          >
            Cancel
          </Button>
        </Flex>
      )}

      {/* Failed Records Section - Only shown if there are failures */}
      {progress.failed > 0 && (
        <Box bg="error.50" borderWidth="1px" borderColor="error.200" borderRadius="md" p={4} mb={4}>
          <Flex alignItems="center" justifyContent="space-between" mb={4}>
            <Heading size="sm" color="error.900">
              Failed Records ({progress.failed})
            </Heading>
            <Flex gap={2}>
              <Button
                onClick={handleExportFailed}
                size="sm"
                variant="outline"
                colorScheme="error"
              >
                Export Failed
              </Button>
              {status === 'completed' && (
                <Button
                  onClick={handleRetryFailed}
                  size="sm"
                  colorScheme="error"
                >
                  Retry Failed
                </Button>
              )}
            </Flex>
          </Flex>

          <Box maxHeight="96" overflowY="auto" bg="white" borderRadius="md">
            <Table.Root size="sm">
              <Table.Header position="sticky" top={0} bg="error.100" zIndex={1}>
                <Table.Row>
                  <Table.ColumnHeader width="80px">Row</Table.ColumnHeader>
                  <Table.ColumnHeader>Error Message</Table.ColumnHeader>
                  <Table.ColumnHeader width="100px">Attempts</Table.ColumnHeader>
                </Table.Row>
              </Table.Header>
              <Table.Body>
                {records.map((record) => (
                  <Table.Row key={record.id} borderTopWidth="1px" borderColor="error.200">
                    <Table.Cell fontWeight="medium">{record.rowIndex + 1}</Table.Cell>
                    <Table.Cell color="error.700" fontSize="sm">{record.error || 'Unknown error'}</Table.Cell>
                    <Table.Cell>{record.attempts}</Table.Cell>
                  </Table.Row>
                ))}
              </Table.Body>
            </Table.Root>
          </Box>
        </Box>
      )}

      {/* Success message when no failures */}
      {status === 'completed' && progress.failed === 0 && (
        <Box bg="success.50" borderWidth="1px" borderColor="success.200" borderRadius="md" p={6} textAlign="center">
          <Text fontSize="lg" fontWeight="semibold" color="success.700" mb={1}>
            All {progress.completed} records ingested successfully!
          </Text>
          <Text fontSize="sm" color="success.600">
            No errors encountered during ingestion.
          </Text>
        </Box>
      )}

      {/* Sticky Actions Footer - Only on completion */}
      {status === 'completed' && (
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
                onClick={() => setState('FILE_UPLOAD')}
                size="sm"
                variant="outline"
                colorScheme="gray"
              >
                Start New Ingestion
              </Button>
              <Text fontSize="sm" color="gray.600">
                {progress.failed === 0
                  ? 'All records ingested successfully!'
                  : `${progress.completed} succeeded, ${progress.failed} failed`}
              </Text>
            </Flex>
          </Box>
        </Box>
      )}
    </Box>
  );
}
