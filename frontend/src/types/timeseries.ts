export interface TimeSeriesPoint {
  date: string
  qliq: number | null
  buffer_pressure: number | null
  casing_pressure: number | null
  load: number | null
  water_cut: number | null
  intake_pressure: number | null
  esp_frequency: number | null
  active_power: number | null
  bdpv_volume_rate: number | null
  bdpv_water_flow: number | null
  collector_pressure: number | null
  full_power: number | null
  qoil: number | null
  qgas: number | null
  gas_factor: number | null
  gas_liquid_factor: number | null
  qliq_wfm: number | null
  qliq_vfm: number | null
}

export type SeriesKey =
  | 'qliq'
  | 'buffer_pressure'
  | 'casing_pressure'
  | 'load'
  | 'water_cut'
  | 'intake_pressure'
  | 'esp_frequency'
  | 'active_power'
  | 'bdpv_volume_rate'
  | 'bdpv_water_flow'
  | 'collector_pressure'
  | 'full_power'
  | 'qoil'
  | 'qgas'
  | 'gas_factor'
  | 'gas_liquid_factor'
  | 'qliq_wfm'

export interface DateRangeValue {
  start: number | null
  end: number | null
}

export interface SelectedInterval {
  startDate: string
  endDate: string
  durationDays: number
}

export interface VisibleDateRange {
  startDate: string
  endDate: string
}

export type InteractionMode = 'navigate' | 'annotate' | 'modelTuning'

export interface EventInterval {
  id: string
  startDate: string
  endDate: string
  label: string
  color: string
}

export interface DailyCauseBand {
  date: string
  label: string
  color: string
}

export interface OpzEventFlag {
  id: string
  date: string
  operationType: string
  comment: string
}

export interface EspInstallationPeriod {
  id: string
  espId: string
  startDate: string
  endDate: string
}

export interface HierarchicalEventTracks {
  installedEspPeriods: EspInstallationPeriod[]
  dailyCauses: DailyCauseBand[]
  opzEvents: OpzEventFlag[]
  espWashEvents: OpzEventFlag[]
  modelEventIntervals: EventInterval[]
  modelRootCauseIntervals: EventInterval[]
}

export interface AnnotationClassOption {
  label: string
  value: string
}

export type EpisodeType = string
export type RootCause = string

export type ConfidenceLevel = 'low' | 'medium' | 'high'
export type WellGroupId = string

export interface EpisodeFormState {
  episodeType: EpisodeType
  rootCause: RootCause
  confidenceEvent: ConfidenceLevel
  confidenceCause: ConfidenceLevel
  comment: string
}

export type AnnotationKind = 'event' | 'rootCause'

interface AnnotationBase extends SelectedInterval {
  id: string
  wellId: string
  wellGroupId: WellGroupId | null
  annotationKind: AnnotationKind
  comment: string
}

export interface SavedEventAnnotation extends AnnotationBase {
  annotationKind: 'event'
  eventType: EpisodeType
  confidenceEvent: ConfidenceLevel
}

export interface SavedRootCauseAnnotation extends AnnotationBase {
  annotationKind: 'rootCause'
  rootCause: RootCause
  confidenceCause: ConfidenceLevel
}

export type SavedAnnotation = SavedEventAnnotation | SavedRootCauseAnnotation

export interface TimelineAnnotationClickPayload {
  annotationId?: string
  source: 'manual' | 'model'
  layer: 'event' | 'rootCause'
  label: string
  startDate: string
  endDate: string
  durationDays: number
}
