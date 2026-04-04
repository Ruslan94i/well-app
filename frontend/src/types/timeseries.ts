export interface TimeSeriesPoint {
  date: string
  qliq: number
  qoil: number
  qliq_vfm: number
  water_cut: number
  intake_pressure: number
  esp_frequency: number
  load: number
}

export type SeriesKey =
  | 'qliq'
  | 'qoil'
  | 'qliq_vfm'
  | 'water_cut'
  | 'intake_pressure'
  | 'esp_frequency'
  | 'load'

export interface DateRangeValue {
  start: number | null
  end: number | null
}

