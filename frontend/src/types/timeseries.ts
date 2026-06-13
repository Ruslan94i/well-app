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

export type TelemetrySeriesKey =
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

export type TrMonitoringSeriesKey =
  | 'tr_reservoir_pressure'
  | 'tr_dynamic_level'
  | 'tr_intake_pressure'
  | 'tr_bottomhole_pressure'
  | 'tr_oil_rate'
  | 'tr_liquid_rate'
  | 'tr_water_cut'
  | 'tr_pump_pressure'
  | 'tr_gas_factor'
  | 'tr_productivity'

export type SeriesKey = TelemetrySeriesKey | TrMonitoringSeriesKey

export interface TrMonitoringPoint {
  date: string
  tr_reservoir_pressure: number | null
  tr_dynamic_level: number | null
  tr_intake_pressure: number | null
  tr_bottomhole_pressure: number | null
  tr_oil_rate: number | null
  tr_liquid_rate: number | null
  tr_water_cut: number | null
  tr_pump_pressure: number | null
  tr_gas_factor: number | null
  tr_productivity: number | null
}

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
  confidence?: number | null
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
  category?: string | null
  composition?: string | null
  volume?: number | null
  capexOpex?: string | null
  comment: string
}

export interface GtmEventFlag {
  id: string
  date: string
  startDate: string
  endDate: string
  operationType: string
  comment: string
  durationDays: number | null
  oilBefore: number | null
  liquidBefore: number | null
  waterCutBefore: number | null
  oilAfter: number | null
  liquidAfter: number | null
  waterCutAfter: number | null
}

export interface GdiEventFlag {
  id: string
  date: string
  startDate: string
  endDate: string
  operationType: string
  acceptedVdpPressure: number | null
  productivityVogel: number | null
  quality: number | null
  comment: string
  executor: string | null
  durationHours: number | null
}

export interface EspInstallationPeriod {
  id: string
  espId: string
  startDate: string
  endDate: string | null
  failureDate?: string | null
  liftReason?: string | null
  espSize?: string | null
  nominalRate?: number | null
  nominalHead?: number | null
  gasSeparatorType?: string | null
  motorPowerKw?: number | null
  isFountain?: boolean
}

export interface VspPeriod {
  id: string
  wellId: string
  startDate: string
  endDate: string
  status: 'work' | 'downtime'
  wellState: string
  wellStateCode: string
}

export interface HierarchicalEventTracks {
  installedEspPeriods: EspInstallationPeriod[]
  dailyCauses: DailyCauseBand[]
  opzEvents: OpzEventFlag[]
  espWashEvents: OpzEventFlag[]
  gtmEvents: GtmEventFlag[]
  gdiEvents: GdiEventFlag[]
  candidateModelEventIntervals: EventInterval[]
}

export interface GtmContextEvent {
  id: string
  wellId: string
  startDate: string
  endDate: string
  operationType: string
  direction: string | null
  durationDays: number | null
  oilBefore: number | null
  liquidBefore: number | null
  waterCutBefore: number | null
  oilAfter: number | null
  liquidAfter: number | null
  waterCutAfter: number | null
  comment: string
}

export interface OpzContextEvent {
  id: string
  wellId: string
  date: string
  operationType: string
  category: string | null
  composition: string | null
  volume: number | null
  capexOpex: string | null
  result: string | null
  deltaOil: number | null
  comment: string
}

export interface GdiContextEvent {
  id: string
  wellId: string
  startDate: string
  endDate: string
  operationType: string
  acceptedVdpPressure: number | null
  productivityVogel: number | null
  quality: number | null
  executor: string | null
  durationHours: number | null
  comment: string
}

export interface WellContext {
  wellId: string
  gtm: GtmContextEvent[]
  opz: OpzContextEvent[]
  gdi: GdiContextEvent[]
}

export interface AnnotationClassOption {
  label: string
  value: string
}

export type FrequencyBreakpointSource = 'auto' | 'manual'

export interface FrequencyBreakpoint {
  id: string
  wellId: string
  date: string
  source: FrequencyBreakpointSource
  reason: string
  fromFrequency: number | null
  toFrequency: number | null
}

export interface FrequencyBreakpointSuppression {
  id: string
  wellId: string
  date: string
}

export interface FrequencySegment extends SelectedInterval {
  id: string
  wellId: string
}

export type EpisodeType = string
export type AnnotationClassificationValue = string | null
export type AnnotationClassification = Record<string, AnnotationClassificationValue>

export interface AnnotationClassificationOption {
  label: string
  value: string
}

export interface AnnotationClassificationLevel {
  key: string
  label: string
  options: AnnotationClassificationOption[]
  allowCustom?: boolean
  placeholder?: string
}

export type ConfidenceLevel = 'low' | 'medium' | 'high'
export type WellGroupId = string

export interface EpisodeFormState {
  episodeType: EpisodeType
  classification: AnnotationClassification
  confidenceEvent: ConfidenceLevel
  eventActions: string[]
  comment: string
}

export type AnnotationKind = 'event'

interface AnnotationBase extends SelectedInterval {
  id: string
  wellId: string
  wellGroupId: WellGroupId | null
  annotationKind: AnnotationKind
  comment: string
  actions: string[]
}

export interface SavedEventAnnotation extends AnnotationBase {
  annotationKind: 'event'
  eventType: EpisodeType
  classification: AnnotationClassification
  confidenceEvent: ConfidenceLevel
}

export type SavedAnnotation = SavedEventAnnotation

export interface MarkupState {
  annotations: SavedAnnotation[]
  episodeClasses: AnnotationClassOption[]
  actionClasses: AnnotationClassOption[]
  classificationLevels: AnnotationClassificationLevel[]
  manualFrequencyBreakpoints: FrequencyBreakpoint[]
  suppressedFrequencyBreakpoints: FrequencyBreakpointSuppression[]
}

export interface TimelineAnnotationClickPayload {
  annotationId?: string
  source: 'manual' | 'model'
  layer: 'event'
  label: string
  startDate: string
  endDate: string
  durationDays: number
  actions: string[]
}

export interface FrequencyBreakpointClickPayload extends FrequencyBreakpoint {}

export interface FrequencySegmentClickPayload extends FrequencySegment {}

export interface FrequencySegmentDoubleClickPayload extends FrequencySegment {
  date: string
}
