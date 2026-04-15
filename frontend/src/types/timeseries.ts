export interface TimeSeriesPoint {
  date: string
  qliq: number | null
  qoil: number | null
  qgas: number | null
  gas_factor: number | null
  gas_liquid_factor: number | null
  qliq_wfm: number | null
  qliq_vfm: number | null
  water_cut: number | null
  intake_pressure: number | null
  esp_frequency: number | null
  load: number | null
}

export type SeriesKey =
  | 'qliq'
  | 'qoil'
  | 'qgas'
  | 'gas_factor'
  | 'gas_liquid_factor'
  | 'qliq_wfm'
  | 'water_cut'
  | 'intake_pressure'
  | 'esp_frequency'
  | 'load'

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

export type EpisodeType =
  | 'decline'
  | 'instability'
  | 'water_cut_growth'
  | 'downtime'
  | 'recovery'
  | 'regime_change'
  | 'post_intervention'
  | 'unknown'

export type RootCause =
  | 'esp_degradation'
  | 'water_breakthrough'
  | 'unstable_operation'
  | 'downtime_vsp'
  | 'opz_effect'
  | 'esp_replacement'
  | 'telemetry_issue'
  | 'unknown'

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
