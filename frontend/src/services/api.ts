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

export async function fetchAutoEpisodeIntervals(wellId: string): Promise<EventInterval[]> {
  const response = await api.get<EventInterval[]>(`/wells/${wellId}/auto-episodes`)
  return response.data
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

export async function fetchGraphDataExportCsv(): Promise<Blob> {
  const response = await api.get<Blob>('/export/graph-data.csv', {
    responseType: 'blob'
  })
  return response.data
}
