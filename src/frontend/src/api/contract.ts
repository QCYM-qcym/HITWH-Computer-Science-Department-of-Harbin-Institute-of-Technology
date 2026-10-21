import Ajv2020 from 'ajv/dist/2020'
import addFormats from 'ajv-formats'
import schemas from '../types/schemas.json'
import type { Schemas } from '../types'

export class ContractError extends Error {
  constructor() { super('接口响应不符合契约 v1，请检查服务版本。'); this.name = 'ContractError' }
}
export class ApiError extends Error {
  constructor(public code: string, message: string) { super(message); this.name = 'ApiError' }
}
const ajv = new Ajv2020({ strict: false, allErrors: false })
addFormats(ajv)
ajv.addSchema({ $id: 'urn:traffic:v1', components: { schemas } })
export function decode<K extends keyof Schemas>(name: K, body: unknown): Schemas[K] {
  const validator = ajv.getSchema(`urn:traffic:v1#/components/schemas/${name}`)
  if (!validator || !validator(body)) throw new ContractError()
  return body as Schemas[K]
}
export function publicError(error: unknown): string {
  if (error instanceof ApiError || error instanceof ContractError) return error.message
  return '连接失败，请检查服务后重试。'
}
