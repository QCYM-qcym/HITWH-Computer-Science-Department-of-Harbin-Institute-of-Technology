import type { components } from './openapi'
export type Schemas = components['schemas']
export type DatasetList = Schemas['DatasetList']
export type RunRequest = Schemas['RunRequest']
export type RunStatus = Schemas['RunStatus']
export type RunAccepted = Schemas['RunAccepted']
export type SeriesPage = Schemas['SeriesPage']
export type SeriesPoint = Schemas['SeriesPoint']
export type Evaluation = Schemas['Evaluation']
export type MinuteDetail = Schemas['MinuteDetail']
export type Query = { start?: string; end?: string; page?: number; page_size?: number }
export type ExportKind = 'scores' | 'metrics' | 'config'
export interface TrafficApi {
  datasets(): Promise<DatasetList>
  submit(request: RunRequest): Promise<RunAccepted>
  status(id: string, signal?: AbortSignal): Promise<RunStatus>
  series(id: string, query: Query): Promise<SeriesPage>
  alarms(id: string, query: Query): Promise<SeriesPage>
  evaluation(id: string): Promise<Evaluation>
  minute(id: string, timestamp: string): Promise<MinuteDetail>
  download(id: string, kind: ExportKind): Promise<Blob>
}
