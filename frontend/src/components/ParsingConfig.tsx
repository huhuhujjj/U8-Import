import { Box, Button, Flex, Heading, Input, Stack, Text } from '@chakra-ui/react';
import { useWorkflowStore } from '../stores/workflowStore';

export function ParsingConfig() {
  const { parsingConfig, setParsingConfig, setState } = useWorkflowStore();

  const handleApplyParsing = () => {
    setState('TRANSFORMING');
  };

  return (
    <Box px={6} py={6} pb="80px">
      <Box mb={4}>
        <Heading size="md" color="gray.900">Configure Parsing Settings</Heading>
        <Text fontSize="sm" color="gray.500" mt={1}>
          Adjust how your file should be parsed
        </Text>
      </Box>

      <Box bg="white" borderWidth="1px" borderColor="gray.200" borderRadius="md" p={4}>
        <Stack gap={4}>
          {parsingConfig.fileType === 'csv' && (
            <Stack gap={4}>
              <Heading size="md" fontWeight="semibold">CSV Options</Heading>

              <Box>
                <Flex alignItems="center" gap={2}>
                  <input
                    type="checkbox"
                    checked={parsingConfig.csv.hasHeaders}
                    onChange={(e) =>
                      setParsingConfig({
                        csv: { ...parsingConfig.csv, hasHeaders: e.target.checked },
                      })
                    }
                    style={{ borderRadius: '0.25rem' }}
                  />
                  <Text>First row contains headers</Text>
                </Flex>
              </Box>

              <Box>
                <Text fontSize="sm" fontWeight="medium" mb={2}>Delimiter</Text>
                <Box maxWidth="xs">
                  <select
                    value={parsingConfig.csv.delimiter}
                    onChange={(e) =>
                      setParsingConfig({
                        csv: { ...parsingConfig.csv, delimiter: e.target.value as any },
                      })
                    }
                    style={{
                      width: '100%',
                      borderWidth: '1px',
                      borderRadius: '0.375rem',
                      padding: '0.5rem 0.75rem',
                    }}
                  >
                    <option value=",">Comma (,)</option>
                    <option value=";">Semicolon (;)</option>
                    <option value="\t">Tab</option>
                    <option value="auto">Auto-detect</option>
                  </select>
                </Box>
              </Box>

              <Box>
                <Text fontSize="sm" fontWeight="medium" mb={2}>Skip Rows</Text>
                <Input
                  type="number"
                  min={0}
                  value={parsingConfig.csv.skipRows}
                  onChange={(e) =>
                    setParsingConfig({
                      csv: { ...parsingConfig.csv, skipRows: parseInt(e.target.value) || 0 },
                    })
                  }
                  maxWidth="xs"
                />
                <Text fontSize="xs" color="gray.500" mt={1}>Number of rows to skip from the top</Text>
              </Box>

              <Box>
                <Text fontSize="sm" fontWeight="medium" mb={2}>Encoding</Text>
                <Box maxWidth="xs">
                  <select
                    value={parsingConfig.csv.encoding}
                    onChange={(e) =>
                      setParsingConfig({
                        csv: { ...parsingConfig.csv, encoding: e.target.value },
                      })
                    }
                    style={{
                      width: '100%',
                      borderWidth: '1px',
                      borderRadius: '0.375rem',
                      padding: '0.5rem 0.75rem',
                    }}
                  >
                    <option value="utf-8">UTF-8</option>
                    <option value="latin1">Latin-1</option>
                    <option value="windows-1252">Windows-1252</option>
                  </select>
                </Box>
              </Box>
            </Stack>
          )}

          {parsingConfig.fileType === 'json' && (
            <Stack gap={4}>
              <Heading size="md" fontWeight="semibold">JSON Options</Heading>

              <Box>
                <Text fontSize="sm" fontWeight="medium" mb={2}>Root Path (JSONPath)</Text>
                <Input
                  type="text"
                  value={parsingConfig.json.rootPath}
                  onChange={(e) =>
                    setParsingConfig({
                      json: { ...parsingConfig.json, rootPath: e.target.value },
                    })
                  }
                  placeholder="e.g., data.items"
                />
                <Text fontSize="xs" color="gray.500" mt={1}>
                  Path to array in JSON (leave empty if root is array)
                </Text>
              </Box>

              <Box>
                <Flex alignItems="center" gap={2}>
                  <input
                    type="checkbox"
                    checked={parsingConfig.json.flattenNested}
                    onChange={(e) =>
                      setParsingConfig({
                        json: { ...parsingConfig.json, flattenNested: e.target.checked },
                      })
                    }
                    style={{ borderRadius: '0.25rem' }}
                  />
                  <Text>Flatten nested objects</Text>
                </Flex>
                <Text fontSize="xs" color="gray.500" mt={1} ml={6}>
                  Convert nested properties to flat structure (e.g., user.name → user_name)
                </Text>
              </Box>

              <Box>
                <Text fontSize="sm" fontWeight="medium" mb={2}>Array Handling</Text>
                <Box maxWidth="xs">
                  <select
                    value={parsingConfig.json.arrayHandling}
                    onChange={(e) =>
                      setParsingConfig({
                        json: { ...parsingConfig.json, arrayHandling: e.target.value as any },
                      })
                    }
                    style={{
                      width: '100%',
                      borderWidth: '1px',
                      borderRadius: '0.375rem',
                      padding: '0.5rem 0.75rem',
                    }}
                  >
                    <option value="rows">Each array item is a row</option>
                    <option value="single-object">Treat as single object</option>
                  </select>
                </Box>
              </Box>
            </Stack>
          )}

          {parsingConfig.fileType === 'excel' && (
            <Stack gap={4}>
              <Heading size="md" fontWeight="semibold">Excel Options</Heading>

              <Box>
                <Text fontSize="sm" fontWeight="medium" mb={2}>Sheet Name</Text>
                <Input
                  type="text"
                  value={parsingConfig.excel.sheetName}
                  onChange={(e) =>
                    setParsingConfig({
                      excel: { ...parsingConfig.excel, sheetName: e.target.value },
                    })
                  }
                  placeholder="Leave empty for first sheet"
                />
              </Box>

              <Box>
                <Flex alignItems="center" gap={2}>
                  <input
                    type="checkbox"
                    checked={parsingConfig.excel.hasHeaders}
                    onChange={(e) =>
                      setParsingConfig({
                        excel: { ...parsingConfig.excel, hasHeaders: e.target.checked },
                      })
                    }
                    style={{ borderRadius: '0.25rem' }}
                  />
                  <Text>First row contains headers</Text>
                </Flex>
              </Box>

              <Box>
                <Text fontSize="sm" fontWeight="medium" mb={2}>Header Row</Text>
                <Input
                  type="number"
                  min={1}
                  value={parsingConfig.excel.headerRow}
                  onChange={(e) =>
                    setParsingConfig({
                      excel: { ...parsingConfig.excel, headerRow: parseInt(e.target.value) || 1 },
                    })
                  }
                  maxWidth="xs"
                />
                <Text fontSize="xs" color="gray.500" mt={1}>Which row number is the header</Text>
              </Box>
            </Stack>
          )}
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
          <Flex px={6} py={4} justifyContent="space-between">
            <Button
              onClick={() => setState('RAW_PREVIEW')}
              size="sm"
              variant="outline"
              colorScheme="gray"
            >
              Back to Preview
            </Button>
            <Button
              onClick={handleApplyParsing}
              size="sm"
              colorScheme="brand"
            >
              Apply & Transform to JSON →
            </Button>
          </Flex>
        </Box>
      </Box>
    </Box>
  );
}
