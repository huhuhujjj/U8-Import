import { useState } from 'react';
import { keyframes } from '@emotion/react';
import { Box, Flex, Grid, GridItem, Heading, Text, Link } from '@chakra-ui/react';
import { useWorkflowStore } from '../stores/workflowStore';
import type { FileType } from '../types';
import { DropletIcon } from './DropletIcon';

// Define animation keyframes
const pulseDrop = keyframes`
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.8;
    transform: scale(1.05);
  }
`;

export function FileUpload() {
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { setRawFile, setState, reset } = useWorkflowStore();

  const acceptedTypes = {
    'text/csv': ['.csv'],
    'application/json': ['.json'],
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
    'application/vnd.ms-excel': ['.xls'],
  };

  const detectFileType = (file: File): FileType | null => {
    const ext = file.name.toLowerCase().split('.').pop();
    if (ext === 'csv') return 'csv';
    if (ext === 'json') return 'json';
    if (ext === 'xlsx' || ext === 'xls') return 'excel';
    return null;
  };

  const handleFile = (file: File) => {
    setError(null);

    const fileType = detectFileType(file);
    if (!fileType) {
      setError('Unsupported file type. Please upload CSV, JSON, or Excel files.');
      return;
    }

    // Check file size (warn if > 10MB)
    const sizeMB = file.size / (1024 * 1024);
    if (sizeMB > 10) {
      const proceed = confirm(
        `File size is ${sizeMB.toFixed(2)}MB. Large files may slow down your browser. Continue?`
      );
      if (!proceed) return;
    }

    // Reset all workflow state to ensure clean slate
    reset();

    // Set new file and proceed
    setRawFile(file);
    setState('RAW_PREVIEW');
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  return (
    <Flex px={6} py={16} alignItems="center" justifyContent="center">
      <Box maxWidth="2xl" width="100%">
        <Box textAlign="center" mb={8}>
          <Flex alignItems="center" justifyContent="center" gap={2} mb={2}>
            <DropletIcon size="md" />
            <Heading size="lg" color="gray.900">Drop Your Data</Heading>
          </Flex>
          <Text fontSize="sm" color="gray.600">
            Upload a file to begin ingestion to Enterspeed
          </Text>
          <Link
            href="https://docs.enterspeed.com/ingest#how-to-ingest-data"
            target="_blank"
            rel="noopener noreferrer"
            display="inline-flex"
            alignItems="center"
            gap={1}
            fontSize="xs"
            color="brand.600"
            _hover={{ color: 'brand.700' }}
            mt={2}
          >
            Learn more about Enterspeed Ingest
            <svg width="12" height="12" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </Link>
        </Box>

        <Box
          borderWidth="2px"
          borderStyle="dashed"
          borderColor={isDragging ? 'brand.500' : 'gray.300'}
          borderRadius="md"
          p={12}
          textAlign="center"
          transition="all 0.2s"
          bg={isDragging ? 'brand.50' : 'transparent'}
          _hover={{ borderColor: 'brand.400', bg: 'gray.50' }}
          animation={isDragging ? `${pulseDrop} 0.6s ease-in-out` : undefined}
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
        >
          <Box mb={4}>
            {isDragging ? (
              <Box display="flex" justifyContent="center">
                <DropletIcon size="xl" />
              </Box>
            ) : (
              <Box display="flex" justifyContent="center">
                <svg
                  height="48"
                  width="48"
                  color="gray.400"
                  stroke="currentColor"
                  fill="none"
                  viewBox="0 0 48 48"
                  style={{ color: 'var(--chakra-colors-gray-400)' }}
                >
                  <path
                    d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                    strokeWidth={2}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              </Box>
            )}
          </Box>

          <Text fontSize="md" mb={2} color="gray.700">
            <label
              htmlFor="file-upload"
              style={{
                color: 'var(--chakra-colors-brand-600)',
                cursor: 'pointer',
                fontWeight: '500',
              }}
            >
              Choose a file
            </label>
            {' '}or drag and drop
          </Text>
          <Text fontSize="xs" color="gray.500" mb={3}>
            CSV, JSON, or Excel files supported
          </Text>

          <Flex alignItems="center" justifyContent="center" gap={3} fontSize="xs" color="gray.400">
            <Flex alignItems="center" gap={1}>
              <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              CSV
            </Flex>
            <Flex alignItems="center" gap={1}>
              <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
              </svg>
              JSON
            </Flex>
            <Flex alignItems="center" gap={1}>
              <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              Excel
            </Flex>
          </Flex>

          <input
            id="file-upload"
            type="file"
            style={{ display: 'none' }}
            accept={Object.values(acceptedTypes).flat().join(',')}
            onChange={handleFileInput}
          />
        </Box>

        {error && (
          <Box mt={4} p={3} bg="error.50" borderWidth="1px" borderColor="error.200" borderRadius="md">
            <Flex alignItems="center" gap={2}>
              <svg width="16" height="16" fill="currentColor" viewBox="0 0 20 20" style={{ flexShrink: 0, color: 'var(--chakra-colors-error-500)' }}>
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <Text color="error.700" fontSize="xs" fontWeight="medium">{error}</Text>
            </Flex>
          </Box>
        )}

        <Box mt={6} bg="white" borderWidth="1px" borderColor="gray.200" borderRadius="md" p={4}>
          <Text fontSize="sm" fontWeight="medium" color="gray.900" mb={3}>Supported File Types:</Text>
          <Grid templateColumns="repeat(3, 1fr)" gap={3}>
            <GridItem>
              <Flex alignItems="flex-start" gap={2}>
                <Flex
                  flexShrink={0}
                  width="24px"
                  height="24px"
                  bg="brand.100"
                  borderRadius="md"
                  alignItems="center"
                  justifyContent="center"
                >
                  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: 'var(--chakra-colors-brand-600)' }}>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </Flex>
                <Box>
                  <Text fontSize="xs" fontWeight="medium" color="gray.900">CSV</Text>
                  <Text fontSize="xs" color="gray.500">With/without headers</Text>
                </Box>
              </Flex>
            </GridItem>
            <GridItem>
              <Flex alignItems="flex-start" gap={2}>
                <Flex
                  flexShrink={0}
                  width="24px"
                  height="24px"
                  bg="success.100"
                  borderRadius="md"
                  alignItems="center"
                  justifyContent="center"
                >
                  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: 'var(--chakra-colors-success-600)' }}>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                  </svg>
                </Flex>
                <Box>
                  <Text fontSize="xs" fontWeight="medium" color="gray.900">JSON</Text>
                  <Text fontSize="xs" color="gray.500">Objects or arrays</Text>
                </Box>
              </Flex>
            </GridItem>
            <GridItem>
              <Flex alignItems="flex-start" gap={2}>
                <Flex
                  flexShrink={0}
                  width="24px"
                  height="24px"
                  bg="purple.100"
                  borderRadius="md"
                  alignItems="center"
                  justifyContent="center"
                >
                  <svg width="16" height="16" fill="none" stroke="currentColor" viewBox="0 0 24 24" style={{ color: 'var(--chakra-colors-purple-600)' }}>
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M3 14h18m-9-4v8m-7 0h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                </Flex>
                <Box>
                  <Text fontSize="xs" fontWeight="medium" color="gray.900">Excel</Text>
                  <Text fontSize="xs" color="gray.500">Single/multi sheets</Text>
                </Box>
              </Flex>
            </GridItem>
          </Grid>
        </Box>
      </Box>
    </Flex>
  );
}
