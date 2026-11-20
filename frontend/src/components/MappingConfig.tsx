import { useState, useEffect } from 'react';
import { Box, Button, Flex, Grid, Heading, Text, Input, Stack, Link } from '@chakra-ui/react';
import { useWorkflowStore } from '../stores/workflowStore';
import type { FieldMapping } from '../types';

export function MappingConfig() {
  const { transformResult, ingestionConfig, setIngestionConfig, setState } = useWorkflowStore();
  const [availableFields, setAvailableFields] = useState<string[]>([]);
  const [indexAliasError, setIndexAliasError] = useState<string>('');

  useEffect(() => {
    // Extract field names from successful records
    if (transformResult && transformResult.parsedData.length > 0) {
      const firstRecord = transformResult.parsedData[0].jsonData;
      const fields = Object.keys(firstRecord);
      setAvailableFields(fields);

      // Initialize field mappings if empty
      if (ingestionConfig.fieldMappings.length === 0) {
        const initialMappings: FieldMapping[] = fields.map((field) => ({
          sourceField: field,
          targetField: field,
          transform: 'string',
        }));
        setIngestionConfig({ fieldMappings: initialMappings });
      }

      // Set default ID field if not set
      if (!ingestionConfig.idField && fields.length > 0) {
        setIngestionConfig({ idField: fields[0] });
      }
    }
  }, [transformResult, ingestionConfig.fieldMappings.length, ingestionConfig.idField, setIngestionConfig]);

  const handleAddMapping = () => {
    const newMapping: FieldMapping = {
      sourceField: availableFields[0] || '',
      targetField: '',
      transform: 'string',
    };
    setIngestionConfig({
      fieldMappings: [...ingestionConfig.fieldMappings, newMapping],
    });
  };

  const handleRemoveMapping = (index: number) => {
    const updated = ingestionConfig.fieldMappings.filter((_, i) => i !== index);
    setIngestionConfig({ fieldMappings: updated });
  };

  const handleUpdateMapping = (index: number, field: keyof FieldMapping, value: string) => {
    const updated = [...ingestionConfig.fieldMappings];
    updated[index] = { ...updated[index], [field]: value };
    setIngestionConfig({ fieldMappings: updated });
  };

  const handleAddCustomHeader = () => {
    const headerName = prompt('Enter header name (e.g., X-Custom-Header):');
    if (headerName) {
      setIngestionConfig({
        headers: {
          ...ingestionConfig.headers,
          [headerName]: '',
        },
      });
    }
  };

  const handleUpdateHeader = (name: string, value: string) => {
    setIngestionConfig({
      headers: {
        ...ingestionConfig.headers,
        [name]: value,
      },
    });
  };

  const handleRemoveHeader = (name: string) => {
    const updated = { ...ingestionConfig.headers };
    delete updated[name];
    setIngestionConfig({ headers: updated });
  };

  const validateIndexAlias = (alias: string): boolean => {
    if (!alias) {
      setIndexAliasError('Index alias is required for Speedtrain');
      return false;
    }

    // Must contain only letters, numbers, underscores, and dashes
    if (!/^[a-zA-Z0-9_-]+$/.test(alias)) {
      setIndexAliasError('Only letters, numbers, underscores (_), and dashes (-) allowed');
      return false;
    }

    // Cannot start or end with underscore or dash
    if (/^[_-]|[_-]$/.test(alias)) {
      setIndexAliasError('Cannot start or end with underscore or dash');
      return false;
    }

    setIndexAliasError('');
    return true;
  };

  const handleIndexAliasChange = (value: string) => {
    setIngestionConfig({ indexAlias: value });
    if (value) {
      validateIndexAlias(value);
    } else {
      setIndexAliasError('');
    }
  };

  const handleTargetChange = (target: 'enterspeed' | 'speedtrain') => {
    setIngestionConfig({
      target,
      apiUrl: target === 'enterspeed'
        ? 'https://api.enterspeed.com/ingest/v2/{{id}}'
        : 'https://api.speedtrain.ai/v1/indices/{{indexAlias}}/documents/{{id}}',
      headers: target === 'enterspeed'
        ? {
            'Content-Type': 'application/json',
            'X-Enterspeed-Type': 'Entity',
            'X-Enterspeed-System': 'drop',
            'x-api-key': '',
          }
        : {
            'Content-Type': 'application/json',
            'X-Enterspeed-System': 'drop',
            'x-api-key': '',
          },
      batchSize: target === 'speedtrain' ? 3 : 5,
    });
  };

  const handleProceed = () => {
    // Validation
    if (!ingestionConfig.apiUrl) {
      alert('Please enter an API URL');
      return;
    }
    if (!ingestionConfig.idField) {
      alert('Please select an ID field');
      return;
    }
    if (ingestionConfig.target === 'speedtrain') {
      if (!ingestionConfig.indexAlias || !validateIndexAlias(ingestionConfig.indexAlias)) {
        alert('Please provide a valid index alias for Speedtrain');
        return;
      }
    }
    setState('PAYLOAD_PREVIEW');
  };

  if (!transformResult) {
    return (
      <Box px={6} py={6}>
        <Text fontSize="sm" color="gray.600">No data available. Please go back and transform your data first.</Text>
      </Box>
    );
  }

  return (
    <Box px={6} py={6} pb="120px">
      <Box mb={4}>
        <Heading as="h2" size="md" fontWeight="semibold" color="gray.900">Configure Field Mapping</Heading>
        <Text fontSize="sm" color="gray.500" mt={1}>
          Map your data fields to the API payload and configure ingestion settings
        </Text>
      </Box>

      {/* Ingestion Target Selection */}
      <Box bg="white" borderWidth="1px" borderColor="gray.200" borderRadius="md" p={4} mb={4}>
        <Heading as="h3" fontSize="sm" fontWeight="semibold" color="gray.900" mb={3}>Ingestion Target</Heading>
        <Grid templateColumns="repeat(2, 1fr)" gap={3}>
          <Box
            as="button"
            onClick={() => handleTargetChange('enterspeed')}
            p={4}
            borderWidth="2px"
            borderColor={ingestionConfig.target === 'enterspeed' ? 'brand.600' : 'gray.200'}
            bg={ingestionConfig.target === 'enterspeed' ? 'brand.50' : 'transparent'}
            borderRadius="md"
            textAlign="left"
            transition="border-color 0.2s"
            _hover={{
              borderColor: ingestionConfig.target === 'enterspeed' ? 'brand.600' : 'gray.300'
            }}
          >
            <Text fontWeight="medium" fontSize="sm" mb={1}>Enterspeed</Text>
            <Text fontSize="xs" color="gray.500">Ingest to Enterspeed</Text>
          </Box>
          <Box
            as="button"
            onClick={() => handleTargetChange('speedtrain')}
            p={4}
            borderWidth="2px"
            borderColor={ingestionConfig.target === 'speedtrain' ? 'brand.600' : 'gray.200'}
            bg={ingestionConfig.target === 'speedtrain' ? 'brand.50' : 'transparent'}
            borderRadius="md"
            textAlign="left"
            transition="border-color 0.2s"
            _hover={{
              borderColor: ingestionConfig.target === 'speedtrain' ? 'brand.600' : 'gray.300'
            }}
          >
            <Text fontWeight="medium" fontSize="sm" mb={1}>Speedtrain</Text>
            <Text fontSize="xs" color="gray.500">Ingest to Speedtrain</Text>
          </Box>
        </Grid>
      </Box>

      {/* API Configuration */}
      <Box bg="white" borderWidth="1px" borderColor="gray.200" borderRadius="md" p={4} mb={4}>
        <Heading as="h3" fontSize="sm" fontWeight="semibold" color="gray.900" mb={3}>
          {ingestionConfig.target === 'enterspeed' ? 'Enterspeed' : 'Speedtrain'} Configuration
        </Heading>

        <Stack gap={4}>
          {ingestionConfig.target === 'speedtrain' ? (
            <>
              {/* Speedtrain: 1) Index Alias */}
              <Box>
                <Text as="label" display="block" fontSize="sm" fontWeight="medium" mb={2}>
                  Index Alias <Text as="span" color="error.500">*</Text>
                </Text>
                <Input
                  type="text"
                  value={ingestionConfig.indexAlias || ''}
                  onChange={(e) => handleIndexAliasChange(e.target.value)}
                  placeholder="e.g., products"
                  maxWidth="md"
                  fontFamily="mono"
                  fontSize="sm"
                  borderColor={indexAliasError ? 'error.500' : 'gray.200'}
                />
                {indexAliasError && (
                  <Text fontSize="xs" color="error.600" mt={1}>{indexAliasError}</Text>
                )}
                <Text fontSize="xs" color="gray.500" mt={1}>
                  Logical group of documents (e.g., "products", "articles"). Only letters, numbers, dashes, and underscores.
                </Text>
              </Box>

              {/* Speedtrain: 2) Unique ID Field */}
              <Box>
                <Text as="label" display="block" fontSize="sm" fontWeight="medium" mb={2}>
                  Unique ID Field <Text as="span" color="error.500">*</Text>
                </Text>
                <Box maxW="xs">
                  <select
                    value={ingestionConfig.idField}
                    onChange={(e) => setIngestionConfig({ idField: e.target.value })}
                    style={{
                      width: '100%',
                      borderWidth: '1px',
                      borderRadius: '0.375rem',
                      padding: '0.5rem 0.75rem',
                    }}
                  >
                    <option value="">-- Select Field --</option>
                    <option value="__ROW_INDEX__">Row Index (auto-incremented)</option>
                    {availableFields.map((field) => (
                      <option key={field} value={field}>
                        {field}
                      </option>
                    ))}
                  </select>
                </Box>
                <Text fontSize="xs" color="gray.500" mt={1}>
                  Field to use as the document ID in the Speedtrain API
                </Text>
              </Box>

              {/* Speedtrain: 3) API URL */}
              <Box>
                <Text as="label" display="block" fontSize="sm" fontWeight="medium" mb={2}>
                  API URL <Text as="span" color="error.500">*</Text>
                </Text>
                <Input
                  type="text"
                  value={ingestionConfig.apiUrl}
                  onChange={(e) => setIngestionConfig({ apiUrl: e.target.value })}
                  placeholder="https://api.speedtrain.ai/v1/indices/{{indexAlias}}/documents/{{id}}"
                  fontFamily="mono"
                  fontSize="sm"
                  disabled
                />
                <Text fontSize="xs" color="gray.500" mt={1}>
                  Use <Text as="code" bg="gray.100" px={1} py={0.5} borderRadius="sm">{'{{indexAlias}}'}</Text> for index and{' '}
                  <Text as="code" bg="gray.100" px={1} py={0.5} borderRadius="sm">{'{{id}}'}</Text> for document ID
                </Text>
              </Box>

              {/* Speedtrain: 4) API Key */}
              <Box>
                <Text as="label" display="block" fontSize="sm" fontWeight="medium" mb={2}>
                  API Key <Text as="span" color="error.500">*</Text>
                </Text>
                <Input
                  type="password"
                  value={ingestionConfig.headers['x-api-key'] || ''}
                  onChange={(e) => handleUpdateHeader('x-api-key', e.target.value)}
                  placeholder="Enter your API key"
                  borderColor={!ingestionConfig.headers['x-api-key'] ? 'error.300' : 'gray.200'}
                />
                {!ingestionConfig.headers['x-api-key'] && (
                  <Flex fontSize="xs" color="error.600" fontWeight="semibold" mt={1} alignItems="center" gap={1}>
                    <svg width="16" height="16" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                    API Key is required!
                  </Flex>
                )}
                <Text fontSize="xs" color="gray.500" mt={1}>
                  Find your API key under{' '}
                  <Link
                    href="https://app.speedtrain.ai/settings/management-clients"
                    target="_blank"
                    rel="noopener noreferrer"
                    color="brand.600"
                    textDecoration="underline"
                    _hover={{ color: 'brand.700' }}
                  >
                    Settings / Management Clients
                  </Link>
                </Text>
              </Box>
            </>
          ) : (
            <>
              {/* Enterspeed: 1) Unique ID Field */}
              <Box>
                <Text as="label" display="block" fontSize="sm" fontWeight="medium" mb={2}>
                  Unique ID Field <Text as="span" color="error.500">*</Text>
                </Text>
                <Box maxW="xs">
                  <select
                    value={ingestionConfig.idField}
                    onChange={(e) => setIngestionConfig({ idField: e.target.value })}
                    style={{
                      width: '100%',
                      borderWidth: '1px',
                      borderRadius: '0.375rem',
                      padding: '0.5rem 0.75rem',
                    }}
                  >
                    <option value="">-- Select Field --</option>
                    <option value="__ROW_INDEX__">Row Index (auto-incremented)</option>
                    {availableFields.map((field) => (
                      <option key={field} value={field}>
                        {field}
                      </option>
                    ))}
                  </select>
                </Box>
                <Text fontSize="xs" color="gray.500" mt={1}>
                  Field to use as the document ID in the Enterspeed API
                </Text>
              </Box>

              {/* Enterspeed: 2) API URL */}
              <Box>
                <Text as="label" display="block" fontSize="sm" fontWeight="medium" mb={2}>
                  API URL <Text as="span" color="error.500">*</Text>
                </Text>
                <Input
                  type="text"
                  value={ingestionConfig.apiUrl}
                  onChange={(e) => setIngestionConfig({ apiUrl: e.target.value })}
                  placeholder="https://api.enterspeed.com/ingest/v2/{{id}}"
                  fontFamily="mono"
                  fontSize="sm"
                  disabled
                />
                <Text fontSize="xs" color="gray.500" mt={1}>
                  Use <Text as="code" bg="gray.100" px={1} py={0.5} borderRadius="sm">{'{{id}}'}</Text> for document ID
                </Text>
              </Box>

              {/* Enterspeed: 3) API Key */}
              <Box>
                <Text as="label" display="block" fontSize="sm" fontWeight="medium" mb={2}>
                  API Key <Text as="span" color="error.500">*</Text>
                </Text>
                <Input
                  type="password"
                  value={ingestionConfig.headers['x-api-key'] || ''}
                  onChange={(e) => handleUpdateHeader('x-api-key', e.target.value)}
                  placeholder="Enter your API key"
                  borderColor={!ingestionConfig.headers['x-api-key'] ? 'error.300' : 'gray.200'}
                />
                {!ingestionConfig.headers['x-api-key'] && (
                  <Flex fontSize="xs" color="error.600" fontWeight="semibold" mt={1} alignItems="center" gap={1}>
                    <svg width="16" height="16" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                    </svg>
                    API Key is required!
                  </Flex>
                )}
              </Box>

              {/* Enterspeed: 4) Additional Headers */}
              <Box>
                <Text as="label" display="block" fontSize="sm" fontWeight="medium" mb={2}>Additional Headers</Text>
                <Stack gap={2}>
                  {Object.entries(ingestionConfig.headers)
                    .filter(([name]) => name !== 'x-api-key' && name !== 'Content-Type' && name !== 'X-Enterspeed-System')
                    .map(([name, value]) => (
                      <Flex key={name} gap={2}>
                        <Input
                          type="text"
                          value={name}
                          disabled
                          width="33.333%"
                          bg="gray.50"
                          fontSize="sm"
                        />
                        <Input
                          type="text"
                          value={value}
                          onChange={(e) => handleUpdateHeader(name, e.target.value)}
                          placeholder="Header value"
                          flex={1}
                          fontSize="sm"
                        />
                        <Button
                          onClick={() => handleRemoveHeader(name)}
                          px={3}
                          py={2}
                          fontSize="sm"
                          color="error.600"
                          variant="ghost"
                          _hover={{ bg: 'error.50' }}
                        >
                          Remove
                        </Button>
                      </Flex>
                    ))}
                  <Button
                    onClick={handleAddCustomHeader}
                    fontSize="sm"
                    color="brand.600"
                    variant="ghost"
                    _hover={{ color: 'brand.700' }}
                    justifyContent="flex-start"
                  >
                    + Add Custom Header
                  </Button>
                </Stack>
              </Box>
            </>
          )}
        </Stack>
      </Box>

      {/* Field Mappings */}
      <Box bg="white" borderWidth="1px" borderColor="gray.200" borderRadius="md" p={4} mb={4}>
        <Heading as="h3" fontSize="sm" fontWeight="semibold" color="gray.900" mb={2}>Field Mappings</Heading>
        <Text fontSize="xs" color="gray.500" mb={3}>
          Map source fields from your data to target fields in the API payload
        </Text>

        <Box overflowX="auto">
          <Box as="table" width="full" fontSize="sm">
            <Box as="thead" bg="gray.50">
              <Box as="tr">
                <Box as="th" px={4} py={2} textAlign="left" fontWeight="medium">Source Field</Box>
                <Box as="th" px={4} py={2} textAlign="left" fontWeight="medium">Target Field</Box>
                <Box as="th" px={4} py={2} textAlign="left" fontWeight="medium">Transform</Box>
                <Box as="th" px={4} py={2} textAlign="left" fontWeight="medium">Actions</Box>
              </Box>
            </Box>
            <Box as="tbody">
              {ingestionConfig.fieldMappings.map((mapping, index) => (
                <Box as="tr" key={index} borderTopWidth="1px">
                  <Box as="td" px={4} py={2}>
                    <select
                      value={mapping.sourceField}
                      onChange={(e) =>
                        handleUpdateMapping(index, 'sourceField', e.target.value)
                      }
                      style={{
                        width: '100%',
                        borderWidth: '1px',
                        borderRadius: '0.375rem',
                        padding: '0.25rem 0.5rem',
                      }}
                    >
                      {availableFields.map((field) => (
                        <option key={field} value={field}>
                          {field}
                        </option>
                      ))}
                    </select>
                  </Box>
                  <Box as="td" px={4} py={2}>
                    <Input
                      type="text"
                      value={mapping.targetField}
                      onChange={(e) =>
                        handleUpdateMapping(index, 'targetField', e.target.value)
                      }
                      placeholder="API field name"
                      size="sm"
                    />
                  </Box>
                  <Box as="td" px={4} py={2}>
                    <select
                      value={mapping.transform || 'string'}
                      onChange={(e) =>
                        handleUpdateMapping(index, 'transform', e.target.value)
                      }
                      style={{
                        width: '100%',
                        borderWidth: '1px',
                        borderRadius: '0.375rem',
                        padding: '0.25rem 0.5rem',
                      }}
                    >
                      <option value="string">String</option>
                      <option value="number">Number</option>
                      <option value="boolean">Boolean</option>
                      <option value="date">Date</option>
                    </select>
                  </Box>
                  <Box as="td" px={4} py={2}>
                    <Button
                      onClick={() => handleRemoveMapping(index)}
                      color="error.600"
                      variant="ghost"
                      fontSize="sm"
                      _hover={{ color: 'error.700' }}
                    >
                      Remove
                    </Button>
                  </Box>
                </Box>
              ))}
            </Box>
          </Box>
        </Box>

        <Button
          onClick={handleAddMapping}
          mt={4}
          fontSize="sm"
          color="brand.600"
          variant="ghost"
          _hover={{ color: 'brand.700' }}
        >
          + Add Field Mapping
        </Button>

        <Box borderTopWidth="1px" mt={4} pt={4}>
          <Stack gap={3}>
            <Flex as="label" alignItems="center" gap={3} cursor="pointer">
              <input
                type="checkbox"
                checked={ingestionConfig.forceUpdate}
                onChange={(e) => setIngestionConfig({ forceUpdate: e.target.checked })}
                style={{ width: '16px', height: '16px', accentColor: '#3182ce', borderRadius: '0.25rem' }}
              />
              <Box>
                <Text fontSize="sm" fontWeight="medium" color="gray.900">Force Update</Text>
                <Text fontSize="xs" color="gray.500" mt={0.5}>
                  Adds a timestamp field <Text as="code" bg="gray.100" px={1} py={0.5} borderRadius="sm">ts</Text> with current Unix timestamp (in milliseconds) to force {ingestionConfig.target === 'enterspeed' ? 'entity' : 'document'} updates
                </Text>
              </Box>
            </Flex>

            <Flex as="label" alignItems="center" gap={3} cursor="pointer">
              <input
                type="checkbox"
                checked={ingestionConfig.includeSourceFile}
                onChange={(e) => setIngestionConfig({ includeSourceFile: e.target.checked })}
                style={{ width: '16px', height: '16px', accentColor: '#3182ce', borderRadius: '0.25rem' }}
              />
              <Box>
                <Text fontSize="sm" fontWeight="medium" color="gray.900">Include Source Filename</Text>
                <Text fontSize="xs" color="gray.500" mt={0.5}>
                  Adds a <Text as="code" bg="gray.100" px={1} py={0.5} borderRadius="sm">source</Text> field with the uploaded filename to each record
                </Text>
              </Box>
            </Flex>
          </Stack>
        </Box>
      </Box>

      {/* Batch Settings */}
      <Box bg="white" borderWidth="1px" borderColor="gray.200" borderRadius="md" p={4} mb={4}>
        <Heading as="h3" fontSize="sm" fontWeight="semibold" color="gray.900" mb={3}>Batch Settings</Heading>

        <Stack gap={4}>
          <Box>
            <Text as="label" display="block" fontSize="sm" fontWeight="medium" mb={2}>
              Concurrent Requests (Batch Size)
            </Text>
            <Input
              type="number"
              min={1}
              max={20}
              value={ingestionConfig.batchSize}
              onChange={(e) =>
                setIngestionConfig({ batchSize: parseInt(e.target.value) || 5 })
              }
              width="32"
            />
            <Text fontSize="xs" color="gray.500" mt={1}>
              Number of requests to send simultaneously (1-20). Default: 5 (Speedtrain defaults to 3)
            </Text>
          </Box>

          <Box>
            <Text as="label" display="block" fontSize="sm" fontWeight="medium" mb={2}>
              Delay Between Batches (ms)
            </Text>
            <Input
              type="number"
              min={0}
              max={5000}
              step={100}
              value={ingestionConfig.delayBetweenBatches}
              onChange={(e) =>
                setIngestionConfig({
                  delayBetweenBatches: parseInt(e.target.value) || 100,
                })
              }
              width="32"
            />
            <Text fontSize="xs" color="gray.500" mt={1}>
              Delay in milliseconds between batches to avoid rate limits
            </Text>
          </Box>
        </Stack>
      </Box>

      {/* Sticky Actions Footer */}
      <Box position="fixed" bottom={0} left={0} right={0} bg="white" borderTopWidth="1px" borderColor="gray.200" boxShadow="0 -2px 8px rgba(0, 0, 0, 0.04)" zIndex={10}>
        <Box maxWidth="1920px" margin="0 auto">
          <Flex px={6} py={4} justifyContent="space-between">
            <Button
              onClick={() => setState('VALIDATION_REPORT')}
              size="sm"
              variant="outline"
              borderColor="gray.300"
              _hover={{ bg: 'gray.50' }}
            >
              Back to Validation
            </Button>
            <Button
              onClick={handleProceed}
              size="sm"
              colorScheme="brand"
            >
              Preview Payloads →
            </Button>
          </Flex>
        </Box>
      </Box>
    </Box>
  );
}
