import { useEffect, useState } from 'react';
import Editor from '@monaco-editor/react';
import { Box, Button, Flex, Heading, Text, Spinner, Stack, Table } from '@chakra-ui/react';
import { useWorkflowStore } from '../stores/workflowStore';
import { FileParser } from '../services/fileParser';
import type { RawPreview as RawPreviewType, ViewMode } from '../types';

export function RawPreview() {
  const { rawFile, setState, setParsingConfig } = useWorkflowStore();
  const [preview, setPreview] = useState<RawPreviewType | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('spreadsheet');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!rawFile) return;

    const loadPreview = async () => {
      try {
        setLoading(true);
        setError(null);

        // Detect file type
        const ext = rawFile.name.toLowerCase().split('.').pop();
        const fileType = ext === 'csv' ? 'csv' : ext === 'json' ? 'json' : 'excel';

        const parsed = await FileParser.parseFile(rawFile, fileType);
        setPreview(parsed);
        setViewMode(parsed.mode);

        // Update parsing config with detected file type
        setParsingConfig({ fileType });
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to parse file');
      } finally {
        setLoading(false);
      }
    };

    loadPreview();
  }, [rawFile, setParsingConfig]);

  const handleViewModeChange = (mode: ViewMode) => {
    setViewMode(mode);
  };

  const handleProceed = () => {
    setState('PARSING_CONFIG');
  };

  if (loading) {
    return (
      <Flex alignItems="center" justifyContent="center" py={16}>
        <Stack alignItems="center" gap={3}>
          <Spinner size="lg" colorPalette="brand" borderWidth="3px" />
          <Text fontSize="sm" color="gray.600">Loading file preview...</Text>
        </Stack>
      </Flex>
    );
  }

  if (error) {
    return (
      <Box px={6} py={6}>
        <Box bg="error.50" borderWidth="1px" borderColor="error.200" borderRadius="md" p={4}>
          <Text fontSize="sm" color="error.600">{error}</Text>
        </Box>
        <Button
          onClick={() => setState('FILE_UPLOAD')}
          mt={4}
          size="sm"
          variant="outline"
          colorScheme="gray"
        >
          Back to Upload
        </Button>
      </Box>
    );
  }

  if (!preview) return null;

  const displayContent =
    viewMode === 'code-editor'
      ? FileParser.convertToCodeView(preview)
      : FileParser.convertToSpreadsheetView(preview);

  return (
    <Box px={6} py={6} pb="80px">
      {/* Header with actions */}
      <Flex alignItems="center" justifyContent="space-between" mb={4}>
        <Box>
          <Heading size="md" color="gray.900">Raw File Preview</Heading>
          <Text fontSize="sm" color="gray.500" mt={1}>
            {preview.fileName} • {(preview.fileSize / 1024).toFixed(2)} KB • {preview.totalRows} rows
            {preview.preview && ' (showing first 1000)'}
          </Text>
        </Box>
        <Flex gap={2}>
          <Button
            onClick={() => handleViewModeChange('spreadsheet')}
            size="sm"
            colorScheme={viewMode === 'spreadsheet' ? 'brand' : 'gray'}
            variant={viewMode === 'spreadsheet' ? 'solid' : 'outline'}
          >
            Spreadsheet View
          </Button>
          <Button
            onClick={() => handleViewModeChange('code-editor')}
            size="sm"
            colorScheme={viewMode === 'code-editor' ? 'brand' : 'gray'}
            variant={viewMode === 'code-editor' ? 'solid' : 'outline'}
          >
            Code Editor
          </Button>
        </Flex>
      </Flex>

      {/* Full-width preview area */}
      <Box borderWidth="1px" borderColor="gray.200" borderRadius="md" overflow="hidden" bg="white">
        {viewMode === 'code-editor' ? (
          <Editor
            height="calc(100vh - 300px)"
            language={preview.fileType === 'json' ? 'json' : 'plaintext'}
            value={displayContent as string}
            options={{
              readOnly: true,
              minimap: { enabled: false },
              scrollBeyondLastLine: false,
              fontSize: 13,
              lineNumbers: 'on',
            }}
            theme="vs-light"
          />
        ) : (
          <Box overflowX="auto" maxHeight="calc(100vh - 300px)">
            <Table.Root size="sm">
              <Table.Header>
                <Table.Row>
                  <Table.ColumnHeader position="sticky" top={0} bg="gray.50">#</Table.ColumnHeader>
                  {(displayContent as any[][])[0]?.map((_, colIdx) => (
                    <Table.ColumnHeader key={colIdx} position="sticky" top={0} bg="gray.50">
                      Col {colIdx + 1}
                    </Table.ColumnHeader>
                  ))}
                </Table.Row>
              </Table.Header>
              <Table.Body>
                {(displayContent as any[][]).map((row, rowIdx) => (
                  <Table.Row key={rowIdx} _hover={{ bg: 'gray.50' }}>
                    <Table.Cell color="gray.500">{rowIdx + 1}</Table.Cell>
                    {row.map((cell, cellIdx) => (
                      <Table.Cell key={cellIdx} maxWidth="xs" overflow="hidden" textOverflow="ellipsis" whiteSpace="nowrap">
                        {String(cell ?? '')}
                      </Table.Cell>
                    ))}
                  </Table.Row>
                ))}
              </Table.Body>
            </Table.Root>
            {preview.preview && (
              <Box px={4} py={3} textAlign="center" fontSize="xs" color="gray.500" borderTopWidth="1px" borderColor="gray.100">
                Showing first 1000 rows of {preview.totalRows}
              </Box>
            )}
          </Box>
        )}
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
          <Flex px={6} py={4} justifyContent="space-between">
            <Button
              onClick={() => setState('FILE_UPLOAD')}
              size="sm"
              variant="outline"
              colorScheme="gray"
            >
              Back
            </Button>
            <Button
              onClick={handleProceed}
              size="sm"
              colorScheme="brand"
            >
              Configure Parsing →
            </Button>
          </Flex>
        </Box>
      </Box>
    </Box>
  );
}
