import axios from 'axios'
import type {
  EspInstallationPeriod,
  EventInterval,
  MarkupState,
  TimeSeriesPoint,
  TrMonitoringPoint,
  VspPeriod,
  WellContext
} from '@/types/timeseries'

const backendBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

const api = axios.create({
  baseURL: `${backendBaseUrl}/api`
})

interface TrMonitoringApiPoint {
  date: string
  reservoir_pressure: number | null
  dynamic_level: number | null
  intake_pressure: number | null
  bottomhole_pressure: number | null
  oil_rate: number | null
  liquid_rate: number | null
  water_cut: number | null
  pump_pressure: number | null
  gas_factor: number | null
  productivity: number | null
}

export interface ModelParamsState {
  globalParams: Record<string, number>
  overrides: Record<string, Record<string, number>>
}

export interface AutomarkQualityRow {
  field: string
  wells: number
  rows: string
  pct: number
  note: string
}

export interface AutomarkRecomputeResponse {
  overall_before: number
  overall_after: number
  by_category_before: Record<string, number>
  by_category_after: Record<string, number>
  rows: AutomarkQualityRow[]
  preview_intervals: EventInterval[]
}

export interface AutomarkRecomputeRequest {
  scope: {
    type: 'well' | 'field' | 'set'
    field?: string
    well?: string
    preview_well?: string
    wells?: string[]
  }
  overrides: Record<string, number>
}

export interface PeriodSummaryRow {
  field_code: string
  well_id: string
  category: string
  interval_start: string
  interval_end: string
  duration_days: number | null
  stop_qliq: number | null
  qliq_1: number | null
  qliq_2: number | null
  qoil_1: number | null
  qoil_2: number | null
  water_cut_1: number | null
  water_cut_2: number | null
  intake_pressure_1: number | null
  intake_pressure_2: number | null
  frequency_1: number | null
  frequency_2: number | null
  load_1: number | null
  load_2: number | null
  gas_factor_1: number | null
  gas_factor_2: number | null
  bdpv_1: number | null
  bdpv_2: number | null
  delta_qliq: number | null
  delta_qoil: number | null
  accumulated_qliq: number | null
  accumulated_qoil: number | null
}

export interface PeriodSummaryResponse {
  period_start: string
  period_end: string
  window_days: number
  rows: PeriodSummaryRow[]
}

export interface PeriodSummaryParams {
  period?: 'week' | 'month' | 'year' | 'custom'
  date_from?: string
  date_to?: string
  field_code?: string
  well_id?: string
}

export async function fetchWellTimeseries(
  wellId: string,
  params: { date_from?: string; date_to?: string }
): Promise<TimeSeriesPoint[]> {
  const response = await api.get<TimeSeriesPoint[]>(`/wells/${wellId}/timeseries`, { params })
  return response.data
}

export async function fetchWellIds(): Promise<string[]> {
  const response = await api.get<string[]>('/wells')
  return response.data
}

export async function fetchWellContext(wellId: string): Promise<WellContext> {
  const response = await api.get<WellContext>(`/wells/${wellId}/context`)
  return response.data
}

export async function fetchArtificialLiftPeriods(wellId: string): Promise<EspInstallationPeriod[]> {
  const response = await api.get<EspInstallationPeriod[]>(`/wells/${wellId}/artificial-lift`)
  return response.data
}

export async function fetchVspPeriods(wellId: string): Promise<VspPeriod[]> {
  const response = await api.get<VspPeriod[]>(`/wells/${wellId}/vsp-periods`)
  return response.data
}

export async function fetchCandidateAutoEpisodeIntervals(wellId: string): Promise<EventInterval[]> {
  try {
    const response = await api.get<EventInterval[]>(`/wells/${wellId}/episodes`)
    return response.data
  } catch (error) {
    const response = await api.get<EventInterval[]>(`/wells/${wellId}/candidate-auto-episodes`)
    return response.data
  }
}

export async function fetchTrMonitoring(
  wellId: string,
  params: { date_from?: string; date_to?: string }
): Promise<TrMonitoringPoint[]> {
  const response = await api.get<TrMonitoringApiPoint[]>(`/wells/${wellId}/tr-monitoring`, { params })
  return response.data.map((item) => ({
    date: item.date,
    tr_reservoir_pressure: item.reservoir_pressure,
    tr_dynamic_level: item.dynamic_level,
    tr_intake_pressure: item.intake_pressure,
    tr_bottomhole_pressure: item.bottomhole_pressure,
    tr_oil_rate: item.oil_rate,
    tr_liquid_rate: item.liquid_rate,
    tr_water_cut: item.water_cut,
    tr_pump_pressure: item.pump_pressure,
    tr_gas_factor: item.gas_factor,
    tr_productivity: item.productivity
  }))
}

export async function fetchMarkup(): Promise<MarkupState> {
  const response = await api.get<MarkupState>('/markup')
  return response.data
}

export async function saveMarkup(markup: MarkupState): Promise<MarkupState> {
  const response = await api.put<MarkupState>('/markup', markup)
  return response.data
}

export async function fetchModelParamsState(): Promise<ModelParamsState> {
  const response = await api.get<ModelParamsState>('/model-params')
  return response.data
}

export async function saveModelParamsForTarget(targetId: string, params: Record<string, number>): Promise<ModelParamsState> {
  const response = await api.put<ModelParamsState>(`/model-params/${targetId}`, { params })
  return response.data
}

export async function resetModelParamsForTarget(targetId: string): Promise<ModelParamsState> {
  const response = await api.delete<ModelParamsState>(`/model-params/${targetId}`)
  return response.data
}

export async function recomputeAutomarkQuality(payload: AutomarkRecomputeRequest): Promise<AutomarkRecomputeResponse> {
  const response = await api.post<AutomarkRecomputeResponse>('/automark/recompute', payload)
  return response.data
}

export async function fetchPeriodSummary(params: PeriodSummaryParams): Promise<PeriodSummaryResponse> {
  const response = await api.get<PeriodSummaryResponse>('/period-summary', { params })
  return response.data
}

export async function fetchGraphDataExportCsv(params?: { field_code?: string; well_id?: string }): Promise<Blob> {
  const response = await api.get<Blob>('/export/graph-data.csv', {
    params,
    responseType: 'blob'
  })
  return response.data
}

export async function fetchManualGraphDataExportCsv(params?: { field_code?: string }): Promise<Blob> {
  const response = await api.get<Blob>('/export/manual-graph-data.csv', {
    params,
    responseType: 'blob'
  })
  return response.data
}

function buildCsvExportUrl(path: string, params?: Record<string, string | undefined>): string {
  const searchParams = new URLSearchParams()
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value) {
      searchParams.set(key, value)
    }
  })
  const query = searchParams.toString()
  return `${backendBaseUrl}/api${path}${query ? `?${query}` : ''}`
}

export function buildGraphDataExportCsvUrl(params?: { field_code?: string; well_id?: string }): string {
  return buildCsvExportUrl('/export/graph-data.csv', params)
}

export function buildManualGraphDataExportCsvUrl(params?: { field_code?: string }): string {
  return buildCsvExportUrl('/export/manual-graph-data.csv', params)
}
