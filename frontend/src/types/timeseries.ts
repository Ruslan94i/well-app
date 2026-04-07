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

export interface SelectedInterval {
  startDate: string
  endDate: string
  durationDays: number
}

export interface VisibleDateRange {
  startDate: string
  endDate: string
}

export type InteractionMode = 'navigate' | 'annotate'

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

export interface EpisodeFormState {
  episodeType: EpisodeType
  rootCause: RootCause
  confidence: number
  comment: string
}

export type AnnotationKind = 'event' | 'rootCause'

interface AnnotationBase extends SelectedInterval {
  id: string
  annotationKind: AnnotationKind
  confidence: number
  comment: string
}

export interface SavedEventAnnotation extends AnnotationBase {
  annotationKind: 'event'
  eventType: EpisodeType
}

export interface SavedRootCauseAnnotation extends AnnotationBase {
  annotationKind: 'rootCause'
  rootCause: RootCause
}

export type SavedAnnotation = SavedEventAnnotation | SavedRootCauseAnnotation

export interface TimelineAnnotationClickPayload {
  annotationId: string
}
