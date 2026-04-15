import axios from 'axios'
import type { TimeSeriesPoint } from '@/types/timeseries'

const backendBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

const api = axios.create({
  baseURL: `${backendBaseUrl}/api`
})

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
