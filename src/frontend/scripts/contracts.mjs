import { readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { parse } from 'yaml'
import openapiTS, { astToString } from 'openapi-typescript'

const document = parse(await readFile(new URL('../../../docs/design/openapi-v1.yaml', import.meta.url), 'utf8'))
const outputs = {
  'openapi.ts': '// Generated from W0 OpenAPI v1. Do not edit.\n' + astToString(await openapiTS(document)),
  'schemas.json': JSON.stringify(document.components.schemas, null, 2) + '\n',
}
for (const [name, value] of Object.entries(outputs)) {
  const path = new URL('../src/types/' + name, import.meta.url)
  if (process.argv.includes('--check')) {
    if (await readFile(path, 'utf8') !== value) throw new Error('Contract output is stale: ' + name)
  } else await writeFile(path, value)
}
console.log('W0 contract outputs verified: ' + Object.keys(outputs).join(', '))
