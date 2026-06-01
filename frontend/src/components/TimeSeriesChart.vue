<template>
  <div
    class="relative h-[920px] w-full"
    @mousedown.capture="handleAnnotationDragStart"
    @mousemove="handleChartPointerMove"
    @mouseleave="clearHoverGuide"
  >
    <div
      ref="chartEl"
      class="frequency-chart h-full w-full"
      :class="{ 'frequency-segment-hover': hoveredFrequencySegmentId }"
      @wheel.prevent="handleChartWheel"
    ></div>
    <div class="pointer-events-none absolute inset-0 z-[12]">
      <div
        v-for="item in trackLabelOverlayItems"
        :key="item.key"
        class="track-label-overlay"
        :style="item.style"
      >
        {{ item.label }}
      </div>
    </div>
    <div class="pointer-events-none absolute inset-0 z-[12]">
      <div
        v-for="item in espSegmentLabelOverlayItems"
        :key="item.key"
        class="esp-segment-label-overlay"
        :style="item.style"
        :title="item.fullLabel"
      >
        {{ item.label }}
      </div>
    </div>
    <div class="pointer-events-none absolute inset-0 z-[13]">
      <button
        v-for="item in trackHoverOverlayItems"
        :key="item.key"
        type="button"
        class="track-hover-hitbox"
        :style="item.style"
        @mouseenter="showTrackHoverTooltip($event, item)"
        @mousemove="showTrackHoverTooltip($event, item)"
        @mouseleave="clearTrackHoverTooltip"
        @wheel.prevent="handleChartWheel"
      />
    </div>
    <div v-if="trackHoverTooltip" class="track-hover-tooltip" :style="trackHoverTooltip.style">
      <div class="text-xs font-semibold text-slate-100">{{ trackHoverTooltip.title }}</div>
      <div class="mt-1 grid gap-1">
        <div
          v-for="(line, index) in trackHoverTooltip.lines"
          :key="`${line.label}-${index}`"
          class="grid grid-cols-[minmax(0,1fr)_auto] gap-3 text-[11px]"
        >
          <span class="min-w-0 text-slate-400">{{ line.label }}</span>
          <span class="max-w-[260px] text-right font-medium text-slate-100">{{ line.value }}</span>
        </div>
      </div>
    </div>
    <div v-if="hoverGuideOverlay" class="pointer-events-none absolute inset-0 z-[9]">
      <div v-if="hoverGuideOverlay" class="hover-guide-line" :style="hoverGuideOverlay.lineStyle"></div>
      <div v-if="hoverGuideOverlay" class="hover-guide-tooltip" :style="hoverGuideOverlay.tooltipStyle">
        <div class="text-xs font-semibold text-slate-100">{{ hoverGuideOverlay.date }}</div>
        <div
          class="mt-1 grid gap-1"
          :class="hoverGuideOverlay.metrics.length > 8 ? 'grid-cols-2' : 'grid-cols-1'"
        >
          <div
            v-for="metric in hoverGuideOverlay.metrics"
            :key="metric.key"
            class="grid grid-cols-[10px_minmax(0,1fr)_auto] items-center gap-2"
          >
            <span class="h-2 w-2 rounded-full" :style="{ backgroundColor: metric.color }"></span>
            <span class="min-w-0 truncate text-slate-300">{{ metric.label }}</span>
            <span class="font-medium text-slate-100">{{ metric.value }}</span>
          </div>
        </div>
      </div>
    </div>
    <div class="pointer-events-none absolute inset-0 z-[14]">
      <button
        v-for="item in savedAnnotationOverlayItems"
        :key="item.annotation.id"
        type="button"
        class="saved-annotation-hitbox"
        :class="{ 'is-selected': item.annotation.id === props.selectedAnnotationId }"
        :style="item.style"
        :title="item.payload.label"
        @click.stop="handleSavedAnnotationOverlayClick(item.payload)"
        @wheel.prevent="handleChartWheel"
      />
    </div>
    <div v-if="props.interactionMode === 'annotate'" class="pointer-events-none absolute inset-0 z-[9]">
      <button
        v-for="item in frequencySegmentOverlayItems"
        :key="item.segment.id"
        type="button"
        class="frequency-segment-hitbox"
        :class="{ 'is-selected': props.selectedFrequencySegmentIds.includes(item.segment.id) }"
        :style="item.style"
        :title="`${item.segment.startDate} -> ${item.segment.endDate}`"
        @mouseenter="handleFrequencySegmentOverlayEnter(item.segment)"
        @mouseleave="clearFrequencySegmentHover"
        @click.stop="handleFrequencySegmentOverlayClick(item.segment)"
        @dblclick.stop="handleFrequencySegmentOverlayDoubleClick($event, item.segment)"
        @wheel.prevent="handleChartWheel"
      />
      <button
        v-if="frequencySegmentAddOverlayItem"
        type="button"
        class="frequency-segment-add-button"
        :style="frequencySegmentAddOverlayItem.style"
        title="Добавить ещё один промежуток"
        @click.stop="emit('frequency-segment-add-clicked')"
        @wheel.prevent="handleChartWheel"
      >
        +
      </button>
    </div>
    <div
      v-if="canUseTimePanSlider"
      class="time-pan-slider-shell"
      :style="timePanSliderOverlayStyle"
    >
      <div class="time-pan-track">
        <div class="time-pan-thumb" :style="timePanSliderThumbStyle"></div>
      </div>
      <input
        type="range"
        min="0"
        :max="TIME_PAN_SLIDER_MAX"
        step="1"
        :value="timePanSliderValue"
        class="time-pan-slider"
        title="Прокрутить график по времени"
        @input="handleTimePanSliderInput"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Plotly from 'plotly.js-dist-min'
import type {
  FrequencyBreakpoint,
  FrequencyBreakpointClickPayload,
  FrequencySegment,
  FrequencySegmentClickPayload,
  FrequencySegmentDoubleClickPayload,
  HierarchicalEventTracks,
  InteractionMode,
  SavedAnnotation,
  SelectedInterval,
  SeriesKey,
  TimelineAnnotationClickPayload,
  TimeSeriesPoint,
  TrMonitoringPoint,
  TrMonitoringSeriesKey,
  VisibleDateRange,
  VspPeriod
} from '@/types/timeseries'

const props = defineProps<{
  data: TimeSeriesPoint[]
  trMonitoringData: TrMonitoringPoint[]
  vspPeriods: VspPeriod[]
  activeSeries: SeriesKey[]
  selectedInterval: SelectedInterval | null
  eventTracks: HierarchicalEventTracks
  interactionMode: InteractionMode
  savedAnnotations: SavedAnnotation[]
  selectedAnnotationId: string | null
  frequencyBreakpoints: FrequencyBreakpoint[]
  frequencySegments: FrequencySegment[]
  selectedFrequencyBreakpointId: string | null
  selectedFrequencySegmentIds: string[]
  visibleDateRange: VisibleDateRange | null
}>()

const emit = defineEmits<{
  (event: 'interval-selected', value: SelectedInterval | null): void
  (event: 'annotation-clicked', value: TimelineAnnotationClickPayload): void
  (event: 'frequency-breakpoint-clicked', value: FrequencyBreakpointClickPayload): void
  (event: 'frequency-segment-clicked', value: FrequencySegmentClickPayload): void
  (event: 'frequency-segment-add-clicked'): void
  (event: 'frequency-segment-double-clicked', value: FrequencySegmentDoubleClickPayload): void
  (event: 'visible-range-changed', value: VisibleDateRange | null): void
  (event: 'background-clicked'): void
}>()

type PlotlyElement = HTMLDivElement & {
  on?: (eventName: string, handler: (eventData: Record<string, unknown>) => void) => void
}

interface PlotlySelectedPoint {
  x?: string | number | Date
}

interface PlotlySelectedEvent {
  points?: PlotlySelectedPoint[]
  range?: {
    x?: [string | number | Date, string | number | Date]
  }
}

interface SavedAnnotationCustomdata {
  kind: 'annotation'
  annotationId?: string
  source: 'manual' | 'model'
  layer: 'event' | 'rootCause'
  annotationKind: string
  startDate: string
  endDate: string
  durationDays: number
  categoryLabel: string
  actions: string[]
  actionsText: string
}

interface FrequencyBreakpointCustomdata extends FrequencyBreakpoint {
  kind: 'frequencyBreakpoint'
}

interface FrequencySegmentCustomdata extends FrequencySegment {
  kind: 'frequencySegment'
}

interface OpzCustomdata {
  date: string
  operationType: string
  comment: string
}

interface AnnotationLaneAssignment {
  lanes: number[]
  laneCount: number
}

interface TrackLayoutRow {
  axis: 'y5' | 'y6' | 'y7' | 'y8' | 'y9'
  label: string
  labelColor: string
  domain: [number, number]
  range: [number, number]
}

interface TrackLabelOverlayItem {
  key: TrackLayoutRow['axis']
  label: string
  style: Record<string, string>
}

interface EspSegmentLabelOverlayItem {
  key: string
  label: string
  fullLabel: string
  style: Record<string, string>
  leftPx: number
  rightPx: number
}

interface FrequencySegmentOverlayItem {
  segment: FrequencySegment
  style: Record<string, string>
}

interface SavedAnnotationOverlayItem {
  annotation: SavedAnnotation
  payload: TimelineAnnotationClickPayload
  style: Record<string, string>
}

interface TrackHoverLine {
  label: string
  value: string
}

interface TrackHoverOverlayItem {
  key: string
  title: string
  lines: TrackHoverLine[]
  style: Record<string, string>
}

interface TrackHoverTooltip {
  title: string
  lines: TrackHoverLine[]
  style: Record<string, string>
}

interface HoverGuideMetric {
  key: SeriesKey
  label: string
  color: string
  value: string
}

interface HoverGuideOverlay {
  date: string
  lineStyle: Record<string, string>
  tooltipStyle: Record<string, string>
  metrics: HoverGuideMetric[]
}

const TRACK_LABEL_LEFT = 22
const MAIN_CHART_DOMAIN_START = 0.272
const TRACK_PANEL_TOP = 0.21
const TRACK_MAIN_GAP = 0.028
const CHART_MARGIN_LEFT = 205
const CHART_MARGIN_RIGHT = 195
const CHART_MARGIN_TOP = 24
const CHART_MARGIN_BOTTOM = 42
const MS_PER_DAY = 86400000
const MIN_VISIBLE_RANGE_MS = MS_PER_DAY * 2
const X_AXIS_ZOOM_FACTOR = 0.82
const TIME_PAN_SLIDER_MAX = 1000
const FREQUENCY_SEGMENT_HITBOX_HEIGHT = 28
const FREQUENCY_SEGMENT_TRACK_Y = 0.18
const ANNOTATION_LANE_BASE_Y = 1.55
const ANNOTATION_HITBOX_HEIGHT = 30
const ESP_TRACK_CENTER_Y = 0.5
const ESP_TRACK_BAR_WIDTH = 0.64
const ESP_LABEL_HEIGHT = 16

interface PlotlyRelayoutEvent {
  'xaxis.range[0]'?: string
  'xaxis.range[1]'?: string
  'xaxis.range'?: [string, string]
  'xaxis.autorange'?: boolean
}

const chartEl = ref<HTMLDivElement | null>(null)
const handlersAttached = ref(false)
const hoveredFrequencySegmentId = ref<string | null>(null)
const hoverGuideDate = ref<string | null>(null)
const trackHoverTooltip = ref<TrackHoverTooltip | null>(null)
const chartSize = ref({ width: 0, height: 920 })
const localVisibleDateRange = ref<VisibleDateRange | null>(null)
let suppressBackgroundClickUntil = 0
let suppressDeselectUntil = 0
let hoveredFrequencySegment: FrequencySegmentCustomdata | null = null
let chartResizeObserver: ResizeObserver | null = null
let annotationDragStart: { clientX: number; date: string } | null = null

function handleNativeChartClick(event: Event) {
  if (Date.now() < suppressBackgroundClickUntil) {
    return
  }

  const target = event.target as HTMLElement | null
  if (!target) {
    return
  }

  if (target.closest('.modebar') || target.closest('.legend')) {
    return
  }

  if (target.closest('.nsewdrag') || target.closest('.draglayer') || target.closest('.plotbg')) {
    emit('background-clicked')
  }
}

const seriesConfig: Record<
  SeriesKey,
  {
    label: string
    color: string
    axis: string
    width?: number
    dash?: 'solid' | 'dot' | 'dash' | 'dashdot'
    source?: 'tr'
    shape?: 'linear' | 'hv'
    chartType?: 'line' | 'bar'
    barWidthDays?: number
    barOffsetDays?: number
    markerLineColor?: string
    opacity?: number
  }
> = {
  qliq: {
    label: 'Дебит жидкости',
    color: '#020617',
    axis: 'y',
    chartType: 'bar',
    barWidthDays: 0.52,
    barOffsetDays: -0.44,
    markerLineColor: 'rgba(226,232,240,0.62)',
    opacity: 0.9
  },
  buffer_pressure: { label: 'Давление буферное', color: '#fb7185', axis: 'y3', width: 1.35 },
  casing_pressure: { label: 'Давление затрубное', color: '#f59e0b', axis: 'y3', width: 1.35 },
  load: { label: 'Загрузка', color: '#16a34a', axis: 'y2', width: 1.4 },
  water_cut: { label: 'Обводненность', color: '#7dd3fc', axis: 'y2', width: 2.2 },
  intake_pressure: { label: 'Р на приеме насоса', color: '#f87171', axis: 'y3', width: 1.4 },
  esp_frequency: { label: 'Частота вращения двиг.', color: '#2563eb', axis: 'y4', width: 1.4 },
  active_power: { label: 'Активная мощность', color: '#a3e635', axis: 'y14', width: 1.3 },
  bdpv_volume_rate: {
    label: 'БДПВ Объем в пересчете на сутки',
    color: '#38bdf8',
    axis: 'y',
    chartType: 'bar',
    barWidthDays: 0.48,
    barOffsetDays: -0.12,
    markerLineColor: '#0e7490',
    opacity: 0.82
  },
  bdpv_water_flow: {
    label: 'БДПВ Расход воды',
    color: '#0ea5e9',
    axis: 'y',
    chartType: 'bar',
    barWidthDays: 0.3,
    barOffsetDays: 0.08,
    markerLineColor: '#075985',
    opacity: 0.86
  },
  collector_pressure: { label: 'Давление в коллекторе', color: '#facc15', axis: 'y3', width: 1.35 },
  full_power: { label: 'Полная мощность', color: '#14b8a6', axis: 'y14', width: 1.3 },
  qgas: { label: 'Расход газа на сутки', color: '#fdba74', axis: 'y12', width: 2.1 },
  qoil: {
    label: 'Расход нефти',
    color: '#92400e',
    axis: 'y',
    chartType: 'bar',
    barWidthDays: 0.44,
    barOffsetDays: 0.3,
    markerLineColor: '#451a03',
    opacity: 0.82
  },
  gas_factor: { label: 'Газовый фактор', color: '#a78bfa', axis: 'y13', width: 1.4 },
  gas_liquid_factor: { label: 'Газожидкостный фактор', color: '#f472b6', axis: 'y13', width: 1.4 },
  qliq_wfm: { label: 'Дебит жидкости (в.расходомер)', color: '#9ca3af', axis: 'y', width: 2, dash: 'dot' },
  tr_reservoir_pressure: { label: 'ТР: Р пл', color: '#fca5a5', axis: 'y3', width: 1.5, dash: 'dash', source: 'tr', shape: 'hv' },
  tr_dynamic_level: { label: 'ТР: Н д', color: '#c084fc', axis: 'y16', width: 1.45, dash: 'dash', source: 'tr', shape: 'hv' },
  tr_intake_pressure: { label: 'ТР: Р на приёме', color: '#f87171', axis: 'y3', width: 1.45, dash: 'dash', source: 'tr', shape: 'hv' },
  tr_bottomhole_pressure: { label: 'ТР: Рзаб', color: '#fb923c', axis: 'y3', width: 1.45, dash: 'dash', source: 'tr', shape: 'hv' },
  tr_oil_rate: {
    label: 'ТР: Q нефти',
    color: '#92400e',
    axis: 'y',
    source: 'tr',
    chartType: 'bar',
    barWidthDays: 0.22,
    barOffsetDays: 0.48,
    markerLineColor: '#f59e0b',
    opacity: 0.9
  },
  tr_liquid_rate: {
    label: 'ТР: Q жидкости',
    color: '#020617',
    axis: 'y',
    source: 'tr',
    chartType: 'bar',
    barWidthDays: 0.24,
    barOffsetDays: -0.66,
    markerLineColor: 'rgba(226,232,240,0.82)',
    opacity: 0.94
  },
  tr_water_cut: { label: 'ТР: Вода', color: '#7dd3fc', axis: 'y2', width: 1.45, dash: 'dash', source: 'tr', shape: 'hv' },
  tr_pump_pressure: { label: 'ТР: Рнас', color: '#facc15', axis: 'y3', width: 1.45, dash: 'dash', source: 'tr', shape: 'hv' },
  tr_gas_factor: { label: 'ТР: ГФ', color: '#a78bfa', axis: 'y13', width: 1.45, dash: 'dash', source: 'tr', shape: 'hv' },
  tr_productivity: { label: 'ТР: Кпр', color: '#34d399', axis: 'y17', width: 1.45, dash: 'dash', source: 'tr', shape: 'hv' }
}

function getPaletteColor(label: string, palette: string[]): string {
  const hash = label.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)
  return palette[hash % palette.length] ?? palette[0] ?? '#64748b'
}

function getAnnotationColor(label: string): string {
  return getPaletteColor(label || 'episode', ['#38bdf8', '#f97316', '#22c55e', '#eab308', '#ec4899', '#a855f7', '#14b8a6'])
}

function getRootCauseColor(label: string): string {
  return getPaletteColor(label || 'mode', ['#94a3b8', '#60a5fa', '#f59e0b', '#10b981', '#c084fc', '#f472b6', '#2dd4bf'])
}

function getEventTypeLabel(label: string): string {
  return label || 'Без класса'
}

function getRootCauseLabel(label: string): string {
  return label || 'Без класса'
}

function getEspColor(espId: string): string {
  const palette = ['#9ca3af', '#64748b', '#94a3b8', '#475569', '#7c8aa0', '#8b9db2']
  const hash = espId.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)
  return palette[hash % palette.length] ?? '#64748b'
}

function getEspSegmentLabel(espId: string, maxLength: number): string {
  return espId.length > maxLength ? `${espId.slice(0, maxLength)}...` : espId
}

function getEffectiveEspEndDate(endDate: string | null): string {
  if (endDate) {
    return endDate
  }

  const fallbackDates = [
    props.data[props.data.length - 1]?.date,
    props.trMonitoringData[props.trMonitoringData.length - 1]?.date
  ].filter((value): value is string => Boolean(value))

  return fallbackDates.length
    ? fallbackDates.reduce((maxDate, value) => (value > maxDate ? value : maxDate))
    : new Date().toISOString().slice(0, 10)
}

function formatEspInfo(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') {
    return '—'
  }

  return String(value)
}

function calculateDurationDays(startDate: string, endDate: string): number {
  const start = new Date(startDate)
  const end = new Date(endDate)
  return Math.max(1, Math.floor((end.getTime() - start.getTime()) / 86400000) + 1)
}

function suppressBackgroundClick(durationMs = 250) {
  suppressBackgroundClickUntil = Date.now() + durationMs
}

function normalizeSelectedInterval(startValue: string, endValue: string): SelectedInterval {
  const startDate = startValue <= endValue ? startValue : endValue
  const endDate = startValue <= endValue ? endValue : startValue

  return {
    startDate,
    endDate,
    durationDays: calculateDurationDays(startDate, endDate)
  }
}

function normalizePlotlyDateValue(value: string | number | Date | undefined): string | null {
  if (value === undefined) {
    return null
  }

  if (value instanceof Date) {
    return Number.isNaN(value.getTime()) ? null : value.toISOString().slice(0, 10)
  }

  if (typeof value === 'number') {
    const date = new Date(value)
    return Number.isNaN(date.getTime()) ? null : date.toISOString().slice(0, 10)
  }

  const trimmedValue = value.trim()
  if (!trimmedValue) {
    return null
  }

  if (/^\d{4}-\d{2}-\d{2}/.test(trimmedValue)) {
    return trimmedValue.slice(0, 10)
  }

  const numericValue = Number(trimmedValue)
  const date = new Date(Number.isFinite(numericValue) ? numericValue : trimmedValue)
  return Number.isNaN(date.getTime()) ? null : date.toISOString().slice(0, 10)
}

function getSelectedDatesFromPlotlyEvent(eventData: Record<string, unknown>): string[] {
  const selectionData = eventData as PlotlySelectedEvent
  const datesFromPoints = (selectionData.points ?? [])
    .map((point) => normalizePlotlyDateValue(point.x))
    .filter((value): value is string => Boolean(value))

  if (datesFromPoints.length > 0) {
    return [...new Set(datesFromPoints)].sort()
  }

  const range = selectionData.range?.x
  if (!range) {
    return []
  }

  const startDate = normalizePlotlyDateValue(range[0])
  const endDate = normalizePlotlyDateValue(range[1])

  return startDate && endDate ? [startDate, endDate].sort() : []
}

function getInclusiveDateAxisEnd(endDate: string): string {
  return new Date(new Date(endDate).getTime() + MS_PER_DAY).toISOString().slice(0, 10)
}

function toTimestamp(value: string): number {
  return new Date(value).getTime()
}

function buildStableRange(values: Array<number | null>): [number, number] {
  const filteredValues = values.filter((value): value is number => Number.isFinite(value))
  if (filteredValues.length === 0) {
    return [0, 1]
  }

  const min = Math.min(...filteredValues)
  const max = Math.max(...filteredValues)

  if (min === max) {
    const pad = Math.max(Math.abs(min) * 0.1, 1)
    return [min - pad, max + pad]
  }

  const pad = Math.max((max - min) * 0.08, 0.5)
  return [min - pad, max + pad]
}

function getNiceStep(rawStep: number): number {
  const magnitude = 10 ** Math.floor(Math.log10(Math.max(rawStep, 1e-9)))
  const normalized = rawStep / magnitude

  if (normalized <= 1) return 1 * magnitude
  if (normalized <= 2) return 2 * magnitude
  if (normalized <= 2.5) return 2.5 * magnitude
  if (normalized <= 5) return 5 * magnitude
  return 10 * magnitude
}

function buildNiceAxis(values: Array<number | null>, desiredTicks = 5): { range: [number, number]; dtick: number; tick0: number } {
  const filteredValues = values.filter((value): value is number => Number.isFinite(value))
  if (filteredValues.length === 0) {
    return {
      range: [0, 1],
      dtick: 0.2,
      tick0: 0
    }
  }

  let min = Math.min(...filteredValues)
  let max = Math.max(...filteredValues)

  if (min === max) {
    const pad = Math.max(Math.abs(min) * 0.1, 1)
    min -= pad
    max += pad
  }

  const rawStep = (max - min) / Math.max(desiredTicks - 1, 1)
  const dtick = getNiceStep(rawStep)
  const niceMin = Math.floor(min / dtick) * dtick
  const niceMax = Math.ceil(max / dtick) * dtick

  return {
    range: [Number(niceMin.toFixed(6)), Number(niceMax.toFixed(6))],
    dtick: Number(dtick.toFixed(6)),
    tick0: Number(niceMin.toFixed(6))
  }
}

function isTrSeriesKey(key: SeriesKey): key is TrMonitoringSeriesKey {
  return seriesConfig[key].source === 'tr'
}

function getSeriesValues(key: SeriesKey): Array<number | null> {
  if (isTrSeriesKey(key)) {
    return props.trMonitoringData.map((item) => item[key])
  }

  return props.data.map((item) => item[key])
}

function getActiveSeriesValues(keys: SeriesKey[]): Array<number | null> {
  return keys.flatMap((key) => (props.activeSeries.includes(key) ? getSeriesValues(key) : []))
}

function getPrimaryAxisValues(): Array<number | null> {
  return [
    ...getSeriesValues('qliq'),
    ...getSeriesValues('qoil'),
    ...getSeriesValues('qliq_wfm'),
    ...getActiveSeriesValues([
      'tr_liquid_rate',
      'tr_oil_rate',
      'bdpv_volume_rate',
      'bdpv_water_flow'
    ])
  ]
}

function buildAnnotationLaneAssignment(annotations: SavedAnnotation[]): AnnotationLaneAssignment {
  if (annotations.length === 0) {
    return {
      lanes: [],
      laneCount: 0
    }
  }

  const indexedAnnotations = annotations
    .map((annotation, index) => ({
      annotation,
      index,
      startTs: toTimestamp(annotation.startDate),
      endTs: toTimestamp(annotation.endDate)
    }))
    .sort((left, right) => left.startTs - right.startTs || left.endTs - right.endTs)

  const laneEndTimestamps: number[] = []
  const lanes = new Array<number>(annotations.length).fill(0)

  indexedAnnotations.forEach((item) => {
    let laneIndex = laneEndTimestamps.findIndex((laneEndTs) => item.startTs > laneEndTs)

    if (laneIndex === -1) {
      laneIndex = laneEndTimestamps.length
      laneEndTimestamps.push(item.endTs)
    } else {
      laneEndTimestamps[laneIndex] = item.endTs
    }

    lanes[item.index] = laneIndex
  })

  return {
    lanes,
    laneCount: Math.max(1, laneEndTimestamps.length)
  }
}

function getSelectionShapes() {
  const trackLayout = getTrackLayoutRows()
  const markerGuideShapes: Array<Record<string, unknown>> = [
    ...props.eventTracks.opzEvents.map((item) => ({
      type: 'line',
      xref: 'x',
      yref: 'paper',
      x0: item.date,
      x1: item.date,
      y0: trackLayout.mainDomain[0],
      y1: 1,
      line: {
        color: 'rgba(217,119,6,0.48)',
        width: 1.2,
        dash: 'dot'
      },
      layer: 'below'
    })),
    ...props.eventTracks.espWashEvents.map((item) => ({
      type: 'line',
      xref: 'x',
      yref: 'paper',
      x0: item.date,
      x1: item.date,
      y0: trackLayout.mainDomain[0],
      y1: 1,
      line: {
        color: 'rgba(34,211,238,0.42)',
        width: 1.2,
        dash: 'dot'
      },
      layer: 'below'
    })),
    ...props.eventTracks.gtmEvents.map((item) => ({
      type: 'line',
      xref: 'x',
      yref: 'paper',
      x0: item.date,
      x1: item.date,
      y0: trackLayout.mainDomain[0],
      y1: 1,
      line: {
        color: 'rgba(168,85,247,0.4)',
        width: 1.2,
        dash: 'dot'
      },
      layer: 'below'
    })),
    ...props.eventTracks.gdiEvents.map((item) => ({
      type: 'line',
      xref: 'x',
      yref: 'paper',
      x0: item.date,
      x1: item.date,
      y0: trackLayout.mainDomain[0],
      y1: 1,
      line: {
        color: 'rgba(45,212,191,0.36)',
        width: 1.2,
        dash: 'dot'
      },
      layer: 'below'
    }))
  ]
  const shapes: Array<Record<string, unknown>> = markerGuideShapes

  if (!props.selectedInterval) {
    return shapes
  }

  shapes.push({
    type: 'rect',
    xref: 'x',
    yref: 'paper',
    x0: props.selectedInterval.startDate,
    x1: getInclusiveDateAxisEnd(props.selectedInterval.endDate),
    y0: 0,
    y1: 1,
    fillcolor: 'rgba(56,189,248,0.12)',
    line: {
      color: 'rgba(125,211,252,0.58)',
      width: 1.5
    },
    layer: 'below'
  })

  return shapes
}

function buildMainTraces() {
  const x = props.data.map((item) => item.date)
  const baseRange = buildStableRange(getPrimaryAxisValues())

  const visibleSeries = props.activeSeries.map((seriesKey) => {
    const config = seriesConfig[seriesKey]
    const seriesX = isTrSeriesKey(seriesKey)
      ? props.trMonitoringData.map((item) => item.date)
      : props.data.map((item) => item.date)
    const seriesY = isTrSeriesKey(seriesKey)
      ? props.trMonitoringData.map((item) => item[seriesKey])
      : props.data.map((item) => item[seriesKey])

    if (config.chartType === 'bar') {
      return {
        x: seriesX,
        y: seriesY,
        type: 'bar',
        name: config.label,
        yaxis: config.axis,
        width: (config.barWidthDays ?? 0.42) * MS_PER_DAY,
        offset: (config.barOffsetDays ?? 0) * MS_PER_DAY,
        opacity: config.opacity ?? 0.82,
        marker: {
          color: config.color,
          line: {
            color: config.markerLineColor ?? config.color,
            width: 0.75
          }
        },
        hovertemplate: '%{x}<br>%{y:.2f}<extra>' + config.label + '</extra>'
      }
    }

    return {
      x: seriesX,
      y: seriesY,
      type: 'scatter',
      mode: 'lines+markers',
      name: config.label,
      yaxis: config.axis,
      connectgaps: true,
      line: {
        color: config.color,
        width: config.width ?? 2,
        dash: config.dash ?? 'solid',
        shape: config.shape ?? 'linear'
      },
      marker: {
        color: config.color,
        size: 4,
        line: {
          color: '#0f172a',
          width: 0.6
        }
      },
      hovertemplate: '%{x}<br>%{y:.2f}<extra>' + config.label + '</extra>'
    }
  }).filter((trace) => trace.x.length > 0 && trace.y.some((value) => Number.isFinite(value)))

  const espWashTrace =
    props.eventTracks.espWashEvents.length > 0
      ? [
          {
            x: props.eventTracks.espWashEvents.map((item) => item.date),
            y: props.eventTracks.espWashEvents.map(() => baseRange[1] - (baseRange[1] - baseRange[0]) * 0.08),
            type: 'scatter',
            mode: 'markers',
            name: 'Промывка ЭЦН',
            yaxis: 'y',
            marker: {
              symbol: 'triangle-up',
              size: 10,
              color: '#22d3ee',
              line: {
                color: '#0e7490',
                width: 1.2
              }
            },
            customdata: props.eventTracks.espWashEvents.map((item) => ({
              date: item.date,
              operationType: item.operationType,
              comment: item.comment
            })),
            hovertemplate:
              '<b>Промывка ЭЦН</b><br>%{customdata.date}<br>%{customdata.operationType}<br>%{customdata.comment}<extra></extra>'
          }
        ]
      : []

  const selectionHelper = {
    x,
    y: x.map(() => baseRange[0]),
    type: 'scatter',
    mode: 'markers',
    name: 'Выделение',
    yaxis: 'y',
    showlegend: false,
    hoverinfo: 'skip',
    marker: {
      size: 18,
      color: 'rgba(255,255,255,0.01)',
      opacity: 0.01
    }
  }

  return [...visibleSeries, ...espWashTrace, selectionHelper]
}

function buildFrequencySegmentTrace() {
  if (props.frequencySegments.length === 0) {
    return []
  }

  const visibleSegments = props.frequencySegments
    .map((segment) => {
      const bar = getVisibleIntervalBar(segment.startDate, segment.endDate)
      return bar ? { segment, bar } : null
    })
    .filter((item): item is { segment: FrequencySegment; bar: { base: string; durationMs: number } } => Boolean(item))

  if (visibleSegments.length === 0) {
    return []
  }

  return [
    {
      type: 'bar',
      orientation: 'h',
      x: visibleSegments.map((item) => item.bar.durationMs),
      base: visibleSegments.map((item) => item.bar.base),
      y: visibleSegments.map(() => FREQUENCY_SEGMENT_TRACK_Y),
      width: 0.34,
      marker: {
        color: visibleSegments.map((item) =>
          props.selectedFrequencySegmentIds.includes(item.segment.id) ? 'rgba(56,189,248,0.52)' : 'rgba(56,189,248,0.16)'
        ),
        line: {
          color: visibleSegments.map((item) =>
            props.selectedFrequencySegmentIds.includes(item.segment.id) ? 'rgba(248,250,252,0.92)' : 'rgba(125,211,252,0.30)'
          ),
          width: visibleSegments.map((item) => (props.selectedFrequencySegmentIds.includes(item.segment.id) ? 1.6 : 0.8))
        }
      },
      yaxis: 'y8',
      showlegend: false,
      customdata: visibleSegments.map((item): FrequencySegmentCustomdata => ({
        kind: 'frequencySegment',
        ...item.segment
      })),
      hovertemplate:
        '<b>Промежуток частоты</b><br>%{customdata.startDate} -> %{customdata.endDate}<br>' +
        'Длительность: %{customdata.durationDays} сут.<extra></extra>'
    }
  ]
}

function buildFrequencyBreakpointTrace() {
  if (props.frequencyBreakpoints.length === 0) {
    return []
  }

  return [
    {
      type: 'scatter',
      mode: 'markers',
      x: props.frequencyBreakpoints.map((item) => item.date),
      y: props.frequencyBreakpoints.map(() => FREQUENCY_SEGMENT_TRACK_Y),
      yaxis: 'y8',
      showlegend: false,
      marker: {
        symbol: 'line-ns',
        size: props.frequencyBreakpoints.map((item) => (item.id === props.selectedFrequencyBreakpointId ? 26 : 22)),
        color: props.frequencyBreakpoints.map((item) =>
          item.id === props.selectedFrequencyBreakpointId ? '#f8fafc' : item.source === 'manual' ? '#38bdf8' : '#f59e0b'
        ),
        line: {
          color: props.frequencyBreakpoints.map((item) =>
            item.id === props.selectedFrequencyBreakpointId ? '#f8fafc' : item.source === 'manual' ? '#0ea5e9' : '#d97706'
          ),
          width: props.frequencyBreakpoints.map((item) => (item.id === props.selectedFrequencyBreakpointId ? 4 : 3))
        }
      },
      customdata: props.frequencyBreakpoints.map((item): FrequencyBreakpointCustomdata => ({
        kind: 'frequencyBreakpoint',
        ...item
      })),
      hovertemplate:
        '<b>Штрих частоты</b><br>%{customdata.date}<br>%{customdata.reason}<br>' +
        'Частота: %{customdata.fromFrequency} -> %{customdata.toFrequency}<extra></extra>'
    }
  ]
}

function buildSavedAnnotationTrace(trackAxis: 'y8' | 'y9', annotationKind: 'event' | 'rootCause') {
  const trackAnnotations = props.savedAnnotations.filter((item) => item.annotationKind === annotationKind)

  if (trackAnnotations.length === 0) {
    return []
  }

  const laneAssignment = buildAnnotationLaneAssignment(trackAnnotations)
  const visibleAnnotations = trackAnnotations
    .map((annotation, index) => {
      const bar = getVisibleIntervalBar(annotation.startDate, annotation.endDate)
      return bar ? { annotation, index, bar } : null
    })
    .filter(
      (item): item is { annotation: SavedAnnotation; index: number; bar: { base: string; durationMs: number } } =>
        Boolean(item)
    )

  if (visibleAnnotations.length === 0) {
    return []
  }

  return [
    {
      type: 'bar',
      orientation: 'h',
      x: visibleAnnotations.map((item) => item.bar.durationMs),
      base: visibleAnnotations.map((item) => item.bar.base),
      y: visibleAnnotations.map((item) => (laneAssignment.lanes[item.index] ?? 0) + ANNOTATION_LANE_BASE_Y),
      width: 0.58,
      marker: {
        color: visibleAnnotations.map((item) =>
          item.annotation.annotationKind === 'event'
            ? getAnnotationColor(item.annotation.eventType)
            : getRootCauseColor(item.annotation.rootCause)
        ),
        line: {
          color: visibleAnnotations.map((item) =>
            item.annotation.id === props.selectedAnnotationId
              ? '#0f172a'
              : item.annotation.annotationKind === 'event'
                ? getAnnotationColor(item.annotation.eventType)
                : getRootCauseColor(item.annotation.rootCause)
          ),
          width: visibleAnnotations.map((item) => (item.annotation.id === props.selectedAnnotationId ? 2.5 : 1.1))
        },
        opacity: visibleAnnotations.map((item) => (item.annotation.id === props.selectedAnnotationId ? 1 : 0.88))
      },
      yaxis: trackAxis,
      showlegend: false,
      customdata: visibleAnnotations.map((item) => ({
        kind: 'annotation',
        annotationId: item.annotation.id,
        source: 'manual' as const,
        layer: item.annotation.annotationKind,
        annotationKind: item.annotation.annotationKind === 'event' ? 'Эпизод' : 'Режим',
        startDate: item.annotation.startDate,
        endDate: item.annotation.endDate,
        durationDays: item.annotation.durationDays,
        categoryLabel:
          item.annotation.annotationKind === 'event'
            ? getEventTypeLabel(item.annotation.eventType)
            : getRootCauseLabel(item.annotation.rootCause),
        actions: item.annotation.actions ?? [],
        actionsText: item.annotation.actions?.length ? item.annotation.actions.join(', ') : 'не назначены'
      })),
      hovertemplate:
        '<b>%{customdata.annotationKind}</b>: %{customdata.categoryLabel}<br>%{customdata.startDate} -> %{customdata.endDate}<br>' +
        'Мероприятия: %{customdata.actionsText}<br>' +
        'Длительность: %{customdata.durationDays} сут.<extra></extra>'
    }
  ]
}

function buildContextMarkerTrackTraces() {
  const opzTrace =
    props.eventTracks.opzEvents.length > 0
      ? [
          {
            x: props.eventTracks.opzEvents.map((item) => item.date),
            y: props.eventTracks.opzEvents.map(() => 0.72),
            type: 'scatter',
            mode: 'markers',
            name: 'ОПЗ',
            yaxis: 'y7',
            showlegend: false,
            cliponaxis: false,
            marker: {
              symbol: 'diamond',
              size: 9,
              color: '#d97706',
              line: {
                color: '#9a3412',
                width: 1.3
              }
            },
            customdata: props.eventTracks.opzEvents.map((item) => ({
              date: item.date,
              operationType: item.operationType,
              category: item.category ?? '—',
              composition: item.composition ?? '—',
              volume: formatMarkerNumber(item.volume, 1),
              capexOpex: item.capexOpex ?? '—',
              comment: item.comment
            })),
            hovertemplate:
              '<b>ОПЗ</b><br>Дата ОПЗ: %{customdata.date}<br>' +
              'Вид ОПЗ: %{customdata.operationType}<br>' +
              'Категория (БП/КРС): %{customdata.category}<br>' +
              'Состав: %{customdata.composition}<br>' +
              'Объем: %{customdata.volume}<br>' +
              'Capex/Opex: %{customdata.capexOpex}<br>' +
              'Комментарий: %{customdata.comment}<extra></extra>'
          }
        ]
      : []

  const gtmTrace =
    props.eventTracks.gtmEvents.length > 0
      ? [
          {
            x: props.eventTracks.gtmEvents.map((item) => item.date),
            y: props.eventTracks.gtmEvents.map(() => 0.5),
            type: 'scatter',
            mode: 'markers',
            name: 'ГТМ',
            yaxis: 'y7',
            showlegend: false,
            cliponaxis: false,
            marker: {
              symbol: 'square',
              size: 9,
              color: '#a855f7',
              line: {
                color: '#6d28d9',
                width: 1.3
              }
            },
            customdata: props.eventTracks.gtmEvents.map((item) => ({
              date: item.date,
              operationType: item.operationType,
              liquidAfter: formatMarkerNumber(item.liquidAfter, 1),
              comment: item.comment
            })),
            hovertemplate:
              '<b>ГТМ</b><br>Дата запуска скважины: %{customdata.date}<br>' +
              'Имя ГТМ: %{customdata.operationType}<br>' +
              'Дебит жидкости после ГТМ, м3: %{customdata.liquidAfter}<br>' +
              'Комментарий: %{customdata.comment}<extra></extra>'
          }
        ]
      : []

  const gdiTrace =
    props.eventTracks.gdiEvents.length > 0
      ? [
          {
            x: props.eventTracks.gdiEvents.map((item) => item.date),
            y: props.eventTracks.gdiEvents.map(() => 0.28),
            type: 'scatter',
            mode: 'markers',
            name: 'ГДИ',
            yaxis: 'y7',
            showlegend: false,
            cliponaxis: false,
            marker: {
              symbol: 'circle',
              size: 8,
              color: '#2dd4bf',
              line: {
                color: '#0f766e',
                width: 1.3
              }
            },
            customdata: props.eventTracks.gdiEvents.map((item) => ({
              date: item.date,
              operationType: item.operationType,
              acceptedVdpPressure: formatMarkerNumber(item.acceptedVdpPressure, 0),
              productivityVogel: formatMarkerNumber(item.productivityVogel, 1),
              quality: formatMarkerNumber(item.quality, 0),
              comment: item.comment
            })),
            hovertemplate:
              '<b>ГДИ</b><br>Дата окончания: %{customdata.date}<br>' +
              'Вид ГДИ: %{customdata.operationType}<br>' +
              'Рпл принятое ВДП, кгс/см2: %{customdata.acceptedVdpPressure}<br>' +
              'Кпрод Вогель, м3/сут/ ат: %{customdata.productivityVogel}<br>' +
              'Кач-во ГДИ: %{customdata.quality}<br>' +
              'Комментарий: %{customdata.comment}<extra></extra>'
          }
        ]
      : []

  return [...opzTrace, ...gtmTrace, ...gdiTrace]
}

function buildVspTrackTrace() {
  if (props.vspPeriods.length === 0) {
    return []
  }

  const visiblePeriods = props.vspPeriods
    .map((period) => {
      const bar = getVisibleIntervalBar(period.startDate, period.endDate, { inclusiveEnd: false })
      return bar ? { period, bar } : null
    })
    .filter((item): item is { period: VspPeriod; bar: { base: string; durationMs: number } } => Boolean(item))

  if (visiblePeriods.length === 0) {
    return []
  }

  return [
    {
      type: 'bar',
      orientation: 'h',
      x: visiblePeriods.map((item) => item.bar.durationMs),
      base: visiblePeriods.map((item) => item.bar.base),
      y: visiblePeriods.map(() => 0.5),
      width: 0.44,
      marker: {
        color: visiblePeriods.map((item) =>
          item.period.status === 'work' ? 'rgba(34,197,94,0.88)' : 'rgba(100,116,139,0.78)'
        ),
        line: {
          color: visiblePeriods.map((item) => (item.period.status === 'work' ? '#16a34a' : '#475569')),
          width: 0.7
        }
      },
      yaxis: 'y5',
      showlegend: false,
      customdata: visiblePeriods.map((item) => ({
        startDate: item.period.startDate,
        endDate: item.period.endDate,
        status: item.period.status === 'work' ? 'В работе' : 'Простой',
        wellState: item.period.wellState,
        wellStateCode: item.period.wellStateCode
      })),
      hovertemplate:
        '<b>ВСП</b><br>%{customdata.startDate} -> %{customdata.endDate}<br>' +
        'Статус: %{customdata.status}<br>' +
        'Состояние: %{customdata.wellState}<br>' +
        'Код: %{customdata.wellStateCode}<extra></extra>'
    }
  ]
}

function buildTrackTraces() {
  const visibleEspPeriods = props.eventTracks.installedEspPeriods
    .map((period) => {
      const effectiveEndDate = getEffectiveEspEndDate(period.endDate)
      const bar = getVisibleIntervalBar(period.startDate, effectiveEndDate)
      return bar ? { period, effectiveEndDate, bar } : null
    })
    .filter(
      (
        item
      ): item is {
        period: (typeof props.eventTracks.installedEspPeriods)[number]
        effectiveEndDate: string
        bar: { base: string; durationMs: number }
      } => Boolean(item)
    )
  const espInstallationTrace =
    visibleEspPeriods.length > 0
      ? [
          {
            type: 'bar',
            orientation: 'h',
            x: visibleEspPeriods.map((item) => item.bar.durationMs),
            base: visibleEspPeriods.map((item) => item.bar.base),
            y: visibleEspPeriods.map(() => ESP_TRACK_CENTER_Y),
            width: ESP_TRACK_BAR_WIDTH,
            marker: {
              color: visibleEspPeriods.map((item) => getEspColor(item.period.espId)),
              line: {
                color: visibleEspPeriods.map(() => 'rgba(226,232,240,0.52)'),
                width: 0.9
              }
            },
            yaxis: 'y6',
            showlegend: false,
            text: visibleEspPeriods.map(() => ''),
            textposition: 'inside',
            insidetextanchor: 'middle',
            textfont: {
              size: 18,
              color: '#f8fafc'
            },
            cliponaxis: true,
            customdata: visibleEspPeriods.map((item) => ({
              espId: item.period.espId,
              startDate: item.period.startDate,
              endDate: item.period.endDate ?? '—',
              failureDate: item.period.failureDate ?? '—',
              liftReason: item.period.liftReason ?? '—',
              espSize: item.period.espSize ?? '—',
              nominalRate: formatEspInfo(item.period.nominalRate),
              nominalHead: formatEspInfo(item.period.nominalHead),
              gasSeparatorType: item.period.gasSeparatorType ?? '—',
              motorPowerKw: formatEspInfo(item.period.motorPowerKw)
            })),
            hovertemplate: visibleEspPeriods.map((item) =>
              item.period.isFountain
                ? '<b>%{customdata.espId}</b><br>Дата монтажа ЭЦН: %{customdata.startDate}<br>Дата демонтажа: %{customdata.endDate}<extra></extra>'
                : '<b>%{customdata.espId}</b><br>Дата монтажа ЭЦН: %{customdata.startDate}<br>Дата демонтажа: %{customdata.endDate}<br>' +
                  'Дата отказа: %{customdata.failureDate}<br>' +
                  'Причина подъема: %{customdata.liftReason}<br>' +
                  'Габарит УЭЦН: %{customdata.espSize}<br>' +
                  'Ном. Произв. м3/сут: %{customdata.nominalRate}<br>' +
                  'Ном.напор (50Гц): %{customdata.nominalHead}<br>' +
                  'Тип Газосепаратора: %{customdata.gasSeparatorType}<br>' +
                  'Мощность, кВт для ПЭД: %{customdata.motorPowerKw}<extra></extra>'
            )
          }
        ]
      : []

  return [
    ...buildFrequencySegmentTrace(),
    ...buildContextMarkerTrackTraces(),
    ...buildVspTrackTrace(),
    ...espInstallationTrace,
    ...buildSavedAnnotationTrace('y8', 'event'),
    ...buildSavedAnnotationTrace('y9', 'rootCause'),
    ...buildFrequencyBreakpointTrace()
  ]
}

function getSavedAnnotationTrackRange(annotationKind: 'event' | 'rootCause'): [number, number] {
  const laneCount = buildAnnotationLaneAssignment(
    props.savedAnnotations.filter((item) => item.annotationKind === annotationKind)
  ).laneCount
  return [0, Math.max(2.45, laneCount + ANNOTATION_LANE_BASE_Y + 0.72)]
}

function getTrackLayoutRows(): { rows: TrackLayoutRow[]; mainDomain: [number, number]; separatorYs: number[] } {
  const eventRange = getSavedAnnotationTrackRange('event')
  const rootCauseRange = getSavedAnnotationTrackRange('rootCause')
  const eventLaneCount = Math.max(1, Math.ceil(eventRange[1] - 1.6))
  const rootCauseLaneCount = Math.max(1, Math.ceil(rootCauseRange[1] - 1.6))

  const rowSpecs = [
    { axis: 'y7' as const, label: 'ГТМ / ОПЗ / ГДИ', labelColor: '#94a3b8', heightUnits: 0.34, range: [0, 1] as [number, number] },
    { axis: 'y5' as const, label: 'ВСП', labelColor: '#94a3b8', heightUnits: 0.34, range: [0, 1] as [number, number] },
    { axis: 'y6' as const, label: 'Установленный ЭЦН', labelColor: '#94a3b8', heightUnits: 0.74, range: [0, 1] as [number, number] },
    { axis: 'y8' as const, label: 'Эпизоды', labelColor: '#94a3b8', heightUnits: Math.max(1.02, 0.68 * eventLaneCount), range: eventRange },
    { axis: 'y9' as const, label: 'Режимы', labelColor: '#94a3b8', heightUnits: Math.max(1.02, 0.68 * rootCauseLaneCount), range: rootCauseRange }
  ]

  const trackPanelHeight = TRACK_PANEL_TOP
  const rowGap = 0.006
  const totalTrackUnits = rowSpecs.reduce((sum, row) => sum + row.heightUnits, 0)
  const availableHeight = trackPanelHeight - rowGap * Math.max(0, rowSpecs.length - 1)

  let cursor = 0
  const rowsBottomToTop = [...rowSpecs].reverse().map((row, index) => {
    const rowHeight = availableHeight * (row.heightUnits / totalTrackUnits)
    const domain: [number, number] = [cursor, cursor + rowHeight]
    cursor += rowHeight

    if (index < rowSpecs.length - 1) {
      cursor += rowGap
    }

    return {
      ...row,
      domain
    }
  })

  const rows = rowsBottomToTop.reverse()
  const separatorYs = rowsBottomToTop
    .slice(1)
    .map((row) => row.domain[1] + rowGap / 2)

  return {
    rows,
    mainDomain: [MAIN_CHART_DOMAIN_START, 1],
    separatorYs
  }
}

function getTrackRowByAxis(
  rows: TrackLayoutRow[],
  axis: TrackLayoutRow['axis']
): TrackLayoutRow {
  const row = rows.find((item) => item.axis === axis)

  if (!row) {
    throw new Error(`Track row not found for axis ${axis}`)
  }

  return row
}

function buildAnnotations() {
  const annotations: Array<Record<string, unknown>> = []

  if (props.data.length === 0) {
    const trackLayout = getTrackLayoutRows()

    annotations.push({
      xref: 'paper',
      yref: 'paper',
      x: 0.5,
      y: (trackLayout.mainDomain[0] + trackLayout.mainDomain[1]) / 2,
      xanchor: 'center',
      yanchor: 'middle',
      text: 'Данные временных рядов не загружены',
      showarrow: false,
      font: { size: 16, color: '#9ca3af' }
    })
  }

  return annotations
}

function getFullVisibleDateRange(): VisibleDateRange | null {
  const dates = [
    props.data[0]?.date,
    props.data[props.data.length - 1]?.date,
    props.trMonitoringData[0]?.date,
    props.trMonitoringData[props.trMonitoringData.length - 1]?.date,
    props.vspPeriods[0]?.startDate,
    props.vspPeriods[props.vspPeriods.length - 1]?.endDate
  ].filter((value): value is string => Boolean(value))

  if (!dates.length) {
    return null
  }

  return {
    startDate: dates.reduce((minDate, value) => (value < minDate ? value : minDate)),
    endDate: dates.reduce((maxDate, value) => (value > maxDate ? value : maxDate))
  }
}

function parseIsoDateMs(value: string | undefined): number | null {
  if (!value) {
    return null
  }

  const timestamp = new Date(value).getTime()
  return Number.isNaN(timestamp) ? null : timestamp
}

function formatIsoDateMs(value: number): string {
  return new Date(value).toISOString().slice(0, 10)
}

function getIntervalCenterDate(startDate: string, endDate: string): string {
  const startMs = parseIsoDateMs(startDate)
  const endMs = parseIsoDateMs(endDate)

  if (startMs === null || endMs === null) {
    return startDate
  }

  return formatIsoDateMs(startMs + (endMs - startMs) / 2)
}

function getFullDateRangeMs(): [number, number] | null {
  const fullRange = getFullVisibleDateRange()
  const startMs = parseIsoDateMs(fullRange?.startDate)
  const endMs = parseIsoDateMs(fullRange?.endDate)

  return startMs !== null && endMs !== null && endMs > startMs ? [startMs, endMs] : null
}

function getCurrentDateRangeMs(): [number, number] | null {
  const fallbackRange = getFullVisibleDateRange()
  const visibleRange = localVisibleDateRange.value ?? props.visibleDateRange ?? fallbackRange
  const startMs = parseIsoDateMs(visibleRange?.startDate)
  const endMs = parseIsoDateMs(visibleRange?.endDate)

  return startMs !== null && endMs !== null && endMs > startMs ? [startMs, endMs] : null
}

function getVisibleIntervalBar(
  startDate: string,
  endDate: string,
  options?: { inclusiveEnd?: boolean }
): { base: string; durationMs: number } | null {
  const currentRange = getCurrentDateRangeMs()
  const startMs = parseIsoDateMs(startDate)
  const endMs = parseIsoDateMs(endDate)

  if (!currentRange || startMs === null || endMs === null) {
    return null
  }

  const inclusiveEnd = options?.inclusiveEnd ?? true
  const intervalEndMs = endMs + (inclusiveEnd ? MS_PER_DAY : 0)
  const visibleStartMs = currentRange[0]
  const visibleEndMs = currentRange[1] + MS_PER_DAY
  const clippedStartMs = Math.max(startMs, visibleStartMs)
  const clippedEndMs = Math.min(intervalEndMs, visibleEndMs)

  if (clippedEndMs <= clippedStartMs) {
    return null
  }

  return {
    base: clippedStartMs === startMs ? startDate : formatIsoDateMs(clippedStartMs),
    durationMs: Math.max(60000, clippedEndMs - clippedStartMs)
  }
}

function getPlotBounds() {
  const plotWidth = Math.max(1, chartSize.value.width - CHART_MARGIN_LEFT - CHART_MARGIN_RIGHT)
  const plotHeight = Math.max(1, chartSize.value.height - CHART_MARGIN_TOP - CHART_MARGIN_BOTTOM)

  return {
    left: CHART_MARGIN_LEFT,
    right: CHART_MARGIN_LEFT + plotWidth,
    top: CHART_MARGIN_TOP,
    bottom: CHART_MARGIN_TOP + plotHeight,
    width: plotWidth,
    height: plotHeight
  }
}

const trackLabelOverlayItems = computed<TrackLabelOverlayItem[]>(() => {
  if (chartSize.value.width <= 0 || chartSize.value.height <= 0) {
    return []
  }

  const trackLayout = getTrackLayoutRows()
  const plotBounds = getPlotBounds()

  return trackLayout.rows.map((row) => {
    const paperY = (row.domain[0] + row.domain[1]) / 2
    const centerY = plotBounds.top + (1 - paperY) * plotBounds.height

    return {
      key: row.axis,
      label: row.label,
      style: {
        left: `${TRACK_LABEL_LEFT}px`,
        top: `${centerY}px`,
        color: row.labelColor
      }
    }
  })
})

function getTrackYCenter(axis: TrackLayoutRow['axis'], value: number): number | null {
  if (chartSize.value.width <= 0 || chartSize.value.height <= 0) {
    return null
  }

  const trackLayout = getTrackLayoutRows()
  const row = getTrackRowByAxis(trackLayout.rows, axis)
  const plotBounds = getPlotBounds()
  const rowRangeSpan = row.range[1] - row.range[0]
  const yRatioInRow = rowRangeSpan > 0 ? (value - row.range[0]) / rowRangeSpan : 0.5
  const paperY = row.domain[0] + yRatioInRow * (row.domain[1] - row.domain[0])

  return plotBounds.top + (1 - paperY) * plotBounds.height
}

function getTrackPointOverlayGeometry(
  axis: TrackLayoutRow['axis'],
  date: string,
  value: number,
  size = 28
): Record<string, string> | null {
  const x = getXForDate(date)
  const centerY = getTrackYCenter(axis, value)

  if (x === null || centerY === null) {
    return null
  }

  return {
    left: `${x - size / 2}px`,
    top: `${centerY - size / 2}px`,
    width: `${size}px`,
    height: `${size}px`
  }
}

function getTrackIntervalOverlayGeometry(
  axis: TrackLayoutRow['axis'],
  startDate: string,
  endDate: string,
  value: number,
  height = 32
): Record<string, string> | null {
  const currentRange = getCurrentDateRangeMs()
  const startMs = parseIsoDateMs(startDate)
  const endMs = parseIsoDateMs(endDate)
  const centerY = getTrackYCenter(axis, value)

  if (!currentRange || startMs === null || endMs === null || centerY === null) {
    return null
  }

  const plotBounds = getPlotBounds()
  const visibleStartMs = currentRange[0]
  const visibleEndMs = currentRange[1] + MS_PER_DAY
  const visibleSpanMs = Math.max(MS_PER_DAY, visibleEndMs - visibleStartMs)
  const clippedStartMs = Math.max(startMs, visibleStartMs)
  const clippedEndMs = Math.min(endMs + MS_PER_DAY, visibleEndMs)

  if (clippedEndMs <= clippedStartMs) {
    return null
  }

  const left = plotBounds.left + ((clippedStartMs - visibleStartMs) / visibleSpanMs) * plotBounds.width
  const width = Math.max(12, ((clippedEndMs - clippedStartMs) / visibleSpanMs) * plotBounds.width)

  return {
    left: `${left}px`,
    top: `${centerY - height / 2}px`,
    width: `${width}px`,
    height: `${height}px`
  }
}

const espSegmentLabelOverlayItems = computed<EspSegmentLabelOverlayItem[]>(() => {
  const minLabelWidth = 28
  const barTopY = getTrackYCenter('y6', ESP_TRACK_CENTER_Y + ESP_TRACK_BAR_WIDTH / 2)
  const barBottomY = getTrackYCenter('y6', ESP_TRACK_CENTER_Y - ESP_TRACK_BAR_WIDTH / 2)
  const labelHeight =
    barTopY === null || barBottomY === null
      ? ESP_LABEL_HEIGHT
      : Math.max(ESP_LABEL_HEIGHT, Math.abs(barBottomY - barTopY))

  const rawItems = props.eventTracks.installedEspPeriods
    .map((period): EspSegmentLabelOverlayItem | null => {
      const endDate = getEffectiveEspEndDate(period.endDate)
      const style = getTrackIntervalOverlayGeometry('y6', period.startDate, endDate, ESP_TRACK_CENTER_Y, labelHeight)
      if (!style) {
        return null
      }

      const width = Number.parseFloat(style.width ?? '0')
      const left = Number.parseFloat(style.left ?? '0')
      if (!Number.isFinite(width) || width < minLabelWidth) {
        return null
      }

      const maxLength = Math.max(3, Math.floor((width - 10) / 9))
      const labelStyle: Record<string, string> = {
        ...style,
        height: `${labelHeight}px`
      }

      return {
        key: `esp-label-${period.id}`,
        label: getEspSegmentLabel(period.espId, maxLength),
        fullLabel: period.espId,
        style: labelStyle,
        leftPx: left,
        rightPx: left + width
      }
    })
    .filter((item): item is EspSegmentLabelOverlayItem => Boolean(item))

  return rawItems
    .sort((left, right) => left.leftPx - right.leftPx)
    .reduce<EspSegmentLabelOverlayItem[]>((items, item) => {
      const previousItem = items[items.length - 1]
      if (previousItem && item.leftPx < previousItem.rightPx - 1) {
        return items
      }

      items.push(item)
      return items
    }, [])
})

function getSavedAnnotationPayload(annotation: SavedAnnotation): TimelineAnnotationClickPayload {
  return {
    annotationId: annotation.id,
    source: 'manual',
    layer: annotation.annotationKind,
    label: annotation.annotationKind === 'event' ? getEventTypeLabel(annotation.eventType) : getRootCauseLabel(annotation.rootCause),
    startDate: annotation.startDate,
    endDate: annotation.endDate,
    durationDays: annotation.durationDays,
    actions: annotation.actions ?? []
  }
}

function buildSavedAnnotationOverlayItems(annotationKind: 'event' | 'rootCause'): SavedAnnotationOverlayItem[] {
  const trackAnnotations = props.savedAnnotations.filter((item) => item.annotationKind === annotationKind)
  const axis = annotationKind === 'event' ? 'y8' : 'y9'
  const laneAssignment = buildAnnotationLaneAssignment(trackAnnotations)

  return trackAnnotations
    .map((annotation, index) => {
      const laneY = (laneAssignment.lanes[index] ?? 0) + ANNOTATION_LANE_BASE_Y
      const style = getTrackIntervalOverlayGeometry(
        axis,
        annotation.startDate,
        annotation.endDate,
        laneY,
        ANNOTATION_HITBOX_HEIGHT
      )

      return style
        ? {
            annotation,
            payload: getSavedAnnotationPayload(annotation),
            style
          }
        : null
    })
    .filter((item): item is SavedAnnotationOverlayItem => Boolean(item))
}

const savedAnnotationOverlayItems = computed<SavedAnnotationOverlayItem[]>(() => [
  ...buildSavedAnnotationOverlayItems('event'),
  ...buildSavedAnnotationOverlayItems('rootCause')
])

function handleSavedAnnotationOverlayClick(payload: TimelineAnnotationClickPayload) {
  suppressBackgroundClick(300)
  emit('annotation-clicked', payload)
}

function toTrackLine(label: string, value: string | number | null | undefined): TrackHoverLine {
  return {
    label,
    value: formatEspInfo(value)
  }
}

const trackHoverOverlayItems = computed<TrackHoverOverlayItem[]>(() => {
  const items: TrackHoverOverlayItem[] = []

  props.eventTracks.gtmEvents.forEach((event) => {
    const style = getTrackPointOverlayGeometry('y7', event.date, 0.5, 22)
    if (!style) return

    items.push({
      key: `gtm-${event.id}`,
      title: 'ГТМ',
      style,
      lines: [
        toTrackLine('Дата запуска', event.date),
        toTrackLine('Имя ГТМ', event.operationType),
        toTrackLine('Дебит жидкости после ГТМ, м3', formatMarkerNumber(event.liquidAfter, 1)),
        toTrackLine('Комментарий', event.comment)
      ]
    })
  })

  props.eventTracks.opzEvents.forEach((event) => {
    const style = getTrackPointOverlayGeometry('y7', event.date, 0.72, 22)
    if (!style) return

    items.push({
      key: `opz-${event.id}`,
      title: 'ОПЗ',
      style,
      lines: [
        toTrackLine('Дата ОПЗ', event.date),
        toTrackLine('Вид ОПЗ', event.operationType),
        toTrackLine('Категория (БП/КРС)', event.category),
        toTrackLine('Состав', event.composition),
        toTrackLine('Объем', formatMarkerNumber(event.volume, 1)),
        toTrackLine('Capex/Opex', event.capexOpex),
        toTrackLine('Комментарий', event.comment)
      ]
    })
  })

  props.eventTracks.gdiEvents.forEach((event) => {
    const style = getTrackPointOverlayGeometry('y7', event.date, 0.28, 22)
    if (!style) return

    items.push({
      key: `gdi-${event.id}`,
      title: 'ГДИ',
      style,
      lines: [
        toTrackLine('Дата окончания', event.date),
        toTrackLine('Вид ГДИ', event.operationType),
        toTrackLine('Рпл принятое ВДП, кгс/см2', formatMarkerNumber(event.acceptedVdpPressure, 0)),
        toTrackLine('Кпрод Вогель, м3/сут/ ат', formatMarkerNumber(event.productivityVogel, 1)),
        toTrackLine('Кач-во ГДИ', formatMarkerNumber(event.quality, 0)),
        toTrackLine('Комментарий', event.comment)
      ]
    })
  })

  props.vspPeriods.forEach((period) => {
    const style = getTrackIntervalOverlayGeometry('y5', period.startDate, period.endDate, 0.5, 22)
    if (!style) return

    items.push({
      key: `vsp-${period.id}`,
      title: 'ВСП',
      style,
      lines: [
        toTrackLine('Начало', period.startDate.replace('T', ' ')),
        toTrackLine('Конец', period.endDate.replace('T', ' ')),
        toTrackLine('Тип', period.status === 'work' ? 'В работе' : 'Простой'),
        toTrackLine('Состояние', period.wellState),
        toTrackLine('Код', period.wellStateCode)
      ]
    })
  })

  props.eventTracks.installedEspPeriods.forEach((period) => {
    const endDate = getEffectiveEspEndDate(period.endDate)
    const style = getTrackIntervalOverlayGeometry('y6', period.startDate, endDate, 0.5, 34)
    if (!style) return

    items.push({
      key: `esp-${period.id}`,
      title: period.espId,
      style,
      lines: period.isFountain
        ? [
            toTrackLine('Дата монтажа ЭЦН', period.startDate),
            toTrackLine('Дата демонтажа', period.endDate)
          ]
        : [
            toTrackLine('Дата монтажа ЭЦН', period.startDate),
            toTrackLine('Дата демонтажа', period.endDate),
            toTrackLine('Дата отказа', period.failureDate),
            toTrackLine('Причина подъема', period.liftReason),
            toTrackLine('Габарит УЭЦН', period.espSize),
            toTrackLine('Ном. Произв. м3/сут', period.nominalRate),
            toTrackLine('Ном.напор (50Гц)', period.nominalHead),
            toTrackLine('Тип Газосепаратора', period.gasSeparatorType),
            toTrackLine('Мощность, кВт для ПЭД', period.motorPowerKw)
          ]
    })
  })

  return items
})

function showTrackHoverTooltip(event: MouseEvent, item: TrackHoverOverlayItem) {
  if (!chartEl.value) {
    return
  }

  const rect = chartEl.value.getBoundingClientRect()
  const tooltipWidth = 340
  const left = Math.min(
    chartSize.value.width - tooltipWidth - 12,
    Math.max(12, event.clientX - rect.left + 14)
  )
  const top = Math.min(
    chartSize.value.height - 220,
    Math.max(12, event.clientY - rect.top + 14)
  )

  trackHoverTooltip.value = {
    title: item.title,
    lines: item.lines,
    style: {
      left: `${left}px`,
      top: `${top}px`,
      width: `${tooltipWidth}px`
    }
  }
}

function clearTrackHoverTooltip() {
  trackHoverTooltip.value = null
}

function getPointerDateFromEvent(event: MouseEvent, options?: { clamp?: boolean }): string | null {
  const currentRange = getCurrentDateRangeMs()

  if (!chartEl.value || !currentRange) {
    return null
  }

  const rect = chartEl.value.getBoundingClientRect()
  const plotBounds = getPlotBounds()
  const localX = event.clientX - rect.left

  if (!options?.clamp && (localX < plotBounds.left || localX > plotBounds.right)) {
    return null
  }

  const pointerRatio = Math.min(1, Math.max(0, (localX - plotBounds.left) / plotBounds.width))
  return formatIsoDateMs(currentRange[0] + (currentRange[1] - currentRange[0]) * pointerRatio)
}

function getXForDate(date: string): number | null {
  const currentRange = getCurrentDateRangeMs()
  const dateMs = parseIsoDateMs(date)

  if (!currentRange || dateMs === null) {
    return null
  }

  const plotBounds = getPlotBounds()
  const ratio = (dateMs - currentRange[0]) / Math.max(MS_PER_DAY, currentRange[1] - currentRange[0])

  if (ratio < 0 || ratio > 1) {
    return null
  }

  return plotBounds.left + ratio * plotBounds.width
}

function formatMetricValue(value: number | null | undefined): string {
  if (!Number.isFinite(value)) {
    return '—'
  }

  return Number(value).toFixed(2)
}

function formatMarkerNumber(value: number | null | undefined, fractionDigits: number): string {
  if (!Number.isFinite(value)) {
    return '—'
  }

  return Number(value).toFixed(fractionDigits)
}

function getNearestPointByDate(date: string): TimeSeriesPoint | null {
  const targetMs = parseIsoDateMs(date)

  if (targetMs === null || props.data.length === 0) {
    return null
  }

  return props.data.reduce<TimeSeriesPoint | null>((nearestPoint, point) => {
    if (!nearestPoint) {
      return point
    }

    return Math.abs(parseIsoDateMs(point.date)! - targetMs) < Math.abs(parseIsoDateMs(nearestPoint.date)! - targetMs)
      ? point
      : nearestPoint
  }, null)
}

function getTrStepPointByDate(date: string): TrMonitoringPoint | null {
  const targetMs = parseIsoDateMs(date)

  if (targetMs === null || props.trMonitoringData.length === 0) {
    return null
  }

  let latestPoint: TrMonitoringPoint | null = null
  for (const point of props.trMonitoringData) {
    const pointMs = parseIsoDateMs(point.date)
    if (pointMs === null) {
      continue
    }

    if (pointMs > targetMs) {
      break
    }

    latestPoint = point
  }

  return latestPoint ?? props.trMonitoringData[0] ?? null
}

function buildHoverGuideMetrics(date: string): HoverGuideMetric[] {
  const telemetryPoint = getNearestPointByDate(date)
  const trPoint = getTrStepPointByDate(date)

  return props.activeSeries
    .map((key): HoverGuideMetric => {
      const value = isTrSeriesKey(key)
        ? trPoint?.[key]
        : telemetryPoint?.[key]

      return {
        key,
        label: seriesConfig[key].label,
        color: seriesConfig[key].color,
        value: formatMetricValue(value)
      }
    })
    .filter((metric) => metric.value !== '—')
}

const hoverGuideOverlay = computed<HoverGuideOverlay | null>(() => {
  if (!hoverGuideDate.value || chartSize.value.width <= 0) {
    return null
  }

  const x = getXForDate(hoverGuideDate.value)
  const metrics = buildHoverGuideMetrics(hoverGuideDate.value)

  if (x === null || metrics.length === 0) {
    return null
  }

  const plotBounds = getPlotBounds()
  const tooltipWidth = metrics.length > 8 ? 520 : 300
  const tooltipLeft = Math.min(
    chartSize.value.width - tooltipWidth - 12,
    Math.max(CHART_MARGIN_LEFT + 8, x + 12)
  )

  return {
    date: hoverGuideDate.value,
    lineStyle: {
      left: `${x}px`,
      top: `${plotBounds.top}px`,
      height: `${plotBounds.height}px`
    },
    tooltipStyle: {
      left: `${tooltipLeft}px`,
      top: `${plotBounds.top + 10}px`,
      width: `${tooltipWidth}px`
    },
    metrics
  }
})

function handleChartPointerMove(event: MouseEvent) {
  const target = event.target as HTMLElement | null

  if (target?.closest('.modebar')) {
    return
  }

  hoverGuideDate.value = getPointerDateFromEvent(event)
}

function shouldIgnoreAnnotationDragTarget(target: HTMLElement | null): boolean {
  return Boolean(
    target?.closest(
      '.modebar, .legend, .time-pan-slider-shell, .track-hover-hitbox, .saved-annotation-hitbox, .frequency-segment-hitbox, .frequency-segment-add-button, input, button'
    )
  )
}

function handleAnnotationDragStart(event: MouseEvent) {
  if (props.interactionMode !== 'annotate' || event.button !== 0) {
    return
  }

  const target = event.target as HTMLElement | null
  if (shouldIgnoreAnnotationDragTarget(target)) {
    return
  }

  const date = getPointerDateFromEvent(event)
  if (!date) {
    return
  }

  annotationDragStart = {
    clientX: event.clientX,
    date
  }
  window.addEventListener('mouseup', handleAnnotationDragEnd, { once: true })
}

function handleAnnotationDragEnd(event: MouseEvent) {
  if (!annotationDragStart) {
    return
  }

  const dragStart = annotationDragStart
  annotationDragStart = null
  const endDate = getPointerDateFromEvent(event, { clamp: true })
  const movedEnough = Math.abs(event.clientX - dragStart.clientX) >= 6

  if (!endDate || !movedEnough || props.interactionMode !== 'annotate') {
    return
  }

  suppressBackgroundClick()
  resetPlotlySelectionState()
  emit('interval-selected', normalizeSelectedInterval(dragStart.date, endDate))
}

function clearHoverGuide() {
  hoverGuideDate.value = null
  clearFrequencySegmentHover()
  clearTrackHoverTooltip()
}

function clampDateRangeMs(startMs: number, endMs: number, fullRange: [number, number]): [number, number] {
  const [fullStartMs, fullEndMs] = fullRange
  const fullSpan = fullEndMs - fullStartMs
  const rawStartMs = Math.min(startMs, endMs)
  const rawEndMs = Math.max(startMs, endMs)
  const span = Math.min(Math.max(rawEndMs - rawStartMs, MIN_VISIBLE_RANGE_MS), fullSpan)

  if (span >= fullSpan) {
    return fullRange
  }

  let nextStartMs = rawStartMs
  let nextEndMs = rawStartMs + span

  if (nextStartMs < fullStartMs) {
    nextStartMs = fullStartMs
    nextEndMs = nextStartMs + span
  }

  if (nextEndMs > fullEndMs) {
    nextEndMs = fullEndMs
    nextStartMs = nextEndMs - span
  }

  return [nextStartMs, nextEndMs]
}

function setVisibleDateRange(range: [number, number]) {
  if (!chartEl.value) {
    return
  }

  const nextRange = {
    startDate: formatIsoDateMs(range[0]),
    endDate: formatIsoDateMs(range[1])
  }

  localVisibleDateRange.value = nextRange
  void Plotly.relayout(chartEl.value, {
    'xaxis.range[0]': nextRange.startDate,
    'xaxis.range[1]': nextRange.endDate
  })
  emit('visible-range-changed', nextRange)
}

function resetPlotlySelectionState() {
  if (!chartEl.value) {
    return
  }

  suppressDeselectUntil = Date.now() + 300
  void Plotly.restyle(chartEl.value, { selectedpoints: null })
  void Plotly.relayout(chartEl.value, {
    dragmode: props.interactionMode === 'annotate' ? 'select' : 'zoom',
    selectdirection: props.interactionMode === 'annotate' ? 'h' : undefined
  })
}

function handleChartWheel(event: WheelEvent) {
  const fullRange = getFullDateRangeMs()
  const currentRange = getCurrentDateRangeMs()

  if (!chartEl.value || !fullRange || !currentRange) {
    return
  }

  const [currentStartMs, currentEndMs] = currentRange
  const currentSpan = currentEndMs - currentStartMs
  const fullSpan = fullRange[1] - fullRange[0]
  const nextSpan =
    event.deltaY < 0
      ? Math.max(currentSpan * X_AXIS_ZOOM_FACTOR, MIN_VISIBLE_RANGE_MS)
      : Math.min(currentSpan / X_AXIS_ZOOM_FACTOR, fullSpan)

  if (Math.abs(nextSpan - currentSpan) < MS_PER_DAY / 2) {
    return
  }

  const rect = chartEl.value.getBoundingClientRect()
  const plotLeft = rect.left + CHART_MARGIN_LEFT
  const plotRight = rect.right - CHART_MARGIN_RIGHT
  const plotWidth = Math.max(1, plotRight - plotLeft)
  const pointerRatio = Math.min(1, Math.max(0, (event.clientX - plotLeft) / plotWidth))
  const anchorMs = currentStartMs + currentSpan * pointerRatio
  const nextStartMs = anchorMs - nextSpan * pointerRatio
  const nextEndMs = anchorMs + nextSpan * (1 - pointerRatio)

  setVisibleDateRange(clampDateRangeMs(nextStartMs, nextEndMs, fullRange))
}

const canUseTimePanSlider = computed(() => {
  const fullRange = getFullDateRangeMs()
  const currentRange = getCurrentDateRangeMs()

  return Boolean(fullRange && currentRange && currentRange[1] - currentRange[0] < fullRange[1] - fullRange[0] - MS_PER_DAY / 2)
})

const timePanSliderValue = computed(() => {
  const fullRange = getFullDateRangeMs()
  const currentRange = getCurrentDateRangeMs()

  if (!fullRange || !currentRange) {
    return 0
  }

  const currentSpan = currentRange[1] - currentRange[0]
  const availableSpan = fullRange[1] - fullRange[0] - currentSpan
  if (availableSpan <= 0) {
    return 0
  }

  return Math.round(((currentRange[0] - fullRange[0]) / availableSpan) * TIME_PAN_SLIDER_MAX)
})

const timePanSliderOverlayStyle = computed<Record<string, string>>(() => {
  const trackLayout = getTrackLayoutRows()
  const plotBounds = getPlotBounds()
  const mainBottomY = plotBounds.top + (1 - trackLayout.mainDomain[0]) * plotBounds.height

  return {
    left: `${plotBounds.left}px`,
    top: `${mainBottomY + 30}px`,
    width: `${plotBounds.width}px`
  }
})

const timePanSliderThumbStyle = computed<Record<string, string>>(() => {
  const fullRange = getFullDateRangeMs()
  const currentRange = getCurrentDateRangeMs()

  if (!fullRange || !currentRange) {
    return {
      left: '0%',
      width: '100%'
    }
  }

  const fullSpan = fullRange[1] - fullRange[0]
  if (fullSpan <= 0) {
    return {
      left: '0%',
      width: '100%'
    }
  }

  const left = ((currentRange[0] - fullRange[0]) / fullSpan) * 100
  const width = ((currentRange[1] - currentRange[0]) / fullSpan) * 100

  return {
    left: `${Math.max(0, Math.min(100, left))}%`,
    width: `${Math.max(2.5, Math.min(100, width))}%`
  }
})

function handleTimePanSliderInput(event: Event) {
  const fullRange = getFullDateRangeMs()
  const currentRange = getCurrentDateRangeMs()
  const input = event.target as HTMLInputElement | null

  if (!fullRange || !currentRange || !input) {
    return
  }

  const sliderValue = Number(input.value)
  const currentSpan = currentRange[1] - currentRange[0]
  const availableSpan = fullRange[1] - fullRange[0] - currentSpan
  if (!Number.isFinite(sliderValue) || availableSpan <= 0) {
    return
  }

  const nextStartMs = fullRange[0] + (availableSpan * sliderValue) / TIME_PAN_SLIDER_MAX
  setVisibleDateRange(clampDateRangeMs(nextStartMs, nextStartMs + currentSpan, fullRange))
}

function getPrimaryCustomdata(
  eventData: Record<string, unknown>
):
  | SavedAnnotationCustomdata
  | FrequencyBreakpointCustomdata
  | FrequencySegmentCustomdata
  | undefined {
  const points = (eventData.points as Array<{ customdata?: unknown }> | undefined) ?? []
  return points[0]?.customdata as
    | SavedAnnotationCustomdata
    | FrequencyBreakpointCustomdata
    | FrequencySegmentCustomdata
    | undefined
}

function getEventCustomdataByKind<T extends { kind?: string }>(
  eventData: Record<string, unknown>,
  kind: T['kind']
): T | undefined {
  const points = (eventData.points as Array<{ customdata?: unknown }> | undefined) ?? []

  return points
    .map((point) => point.customdata as T | undefined)
    .find((customdata) => customdata?.kind === kind)
}

function clearFrequencySegmentHover() {
  hoveredFrequencySegment = null
  hoveredFrequencySegmentId.value = null
}

function getPointerIsoDate(event: MouseEvent, segment: FrequencySegment): string | null {
  const currentRange = getCurrentDateRangeMs()

  if (!chartEl.value || !currentRange) {
    return null
  }

  const rect = chartEl.value.getBoundingClientRect()
  const plotLeft = rect.left + CHART_MARGIN_LEFT
  const plotRight = rect.right - CHART_MARGIN_RIGHT
  const plotWidth = Math.max(1, plotRight - plotLeft)
  const pointerRatio = Math.min(1, Math.max(0, (event.clientX - plotLeft) / plotWidth))
  const rawDateMs = currentRange[0] + (currentRange[1] - currentRange[0]) * pointerRatio
  const segmentStartMs = parseIsoDateMs(segment.startDate)
  const segmentEndMs = parseIsoDateMs(segment.endDate)

  if (segmentStartMs === null || segmentEndMs === null) {
    return formatIsoDateMs(rawDateMs)
  }

  return formatIsoDateMs(Math.min(segmentEndMs, Math.max(segmentStartMs, rawDateMs)))
}

function getFrequencySegmentPayload(segment: FrequencySegment): FrequencySegmentClickPayload {
  return {
    id: segment.id,
    wellId: segment.wellId,
    startDate: segment.startDate,
    endDate: segment.endDate,
    durationDays: segment.durationDays
  }
}

function updateChartSize() {
  if (!chartEl.value) {
    return
  }

  const rect = chartEl.value.getBoundingClientRect()
  chartSize.value = {
    width: rect.width,
    height: rect.height
  }
}

function getFrequencySegmentOverlayGeometry(segment: FrequencySegment): Record<string, string> | null {
  const currentRange = getCurrentDateRangeMs()

  if (!currentRange || chartSize.value.width <= 0 || chartSize.value.height <= 0) {
    return null
  }

  const segmentStartMs = parseIsoDateMs(segment.startDate)
  const segmentEndMs = parseIsoDateMs(segment.endDate)

  if (segmentStartMs === null || segmentEndMs === null) {
    return null
  }

  const plotWidth = Math.max(1, chartSize.value.width - CHART_MARGIN_LEFT - CHART_MARGIN_RIGHT)
  const plotHeight = Math.max(1, chartSize.value.height - CHART_MARGIN_TOP - CHART_MARGIN_BOTTOM)
  const visibleStartMs = currentRange[0]
  const visibleEndMs = currentRange[1] + MS_PER_DAY
  const visibleSpanMs = Math.max(MS_PER_DAY, visibleEndMs - visibleStartMs)
  const clippedStartMs = Math.max(segmentStartMs, visibleStartMs)
  const clippedEndMs = Math.min(segmentEndMs + MS_PER_DAY, visibleEndMs)

  if (clippedEndMs <= clippedStartMs) {
    return null
  }

  const trackLayout = getTrackLayoutRows()
  const eventRow = getTrackRowByAxis(trackLayout.rows, 'y8')
  const rowRangeSpan = eventRow.range[1] - eventRow.range[0]
  const yRatioInRow = rowRangeSpan > 0 ? (FREQUENCY_SEGMENT_TRACK_Y - eventRow.range[0]) / rowRangeSpan : 0
  const paperY = eventRow.domain[0] + yRatioInRow * (eventRow.domain[1] - eventRow.domain[0])
  const centerY = CHART_MARGIN_TOP + (1 - paperY) * plotHeight
  const left = CHART_MARGIN_LEFT + ((clippedStartMs - visibleStartMs) / visibleSpanMs) * plotWidth
  const width = Math.max(10, ((clippedEndMs - clippedStartMs) / visibleSpanMs) * plotWidth)

  return {
    left: `${left}px`,
    top: `${centerY - FREQUENCY_SEGMENT_HITBOX_HEIGHT / 2}px`,
    width: `${width}px`,
    height: `${FREQUENCY_SEGMENT_HITBOX_HEIGHT}px`
  }
}

const frequencySegmentOverlayItems = computed<FrequencySegmentOverlayItem[]>(() => {
  if (props.interactionMode !== 'annotate') {
    return []
  }

  return props.frequencySegments
    .map((segment) => {
      const style = getFrequencySegmentOverlayGeometry(segment)
      return style ? { segment, style } : null
    })
    .filter((item): item is FrequencySegmentOverlayItem => Boolean(item))
})

const frequencySegmentAddOverlayItem = computed<FrequencySegmentOverlayItem | null>(() => {
  const selectedSegments = props.frequencySegments.filter((segment) => props.selectedFrequencySegmentIds.includes(segment.id))
  const lastSelectedSegment = selectedSegments[selectedSegments.length - 1]

  if (!lastSelectedSegment) {
    return null
  }

  const segmentGeometry = getFrequencySegmentOverlayGeometry(lastSelectedSegment)
  if (!segmentGeometry) {
    return null
  }

  const left = Number.parseFloat(segmentGeometry.left ?? '0')
  const width = Number.parseFloat(segmentGeometry.width ?? '0')
  const top = Number.parseFloat(segmentGeometry.top ?? '0')

  return {
    segment: lastSelectedSegment,
    style: {
      left: `${left + width / 2 - 14}px`,
      top: `${top - 32}px`,
      width: '28px',
      height: '28px'
    }
  }
})

function handleFrequencySegmentOverlayEnter(segment: FrequencySegment) {
  hoveredFrequencySegment = {
    kind: 'frequencySegment',
    ...segment
  }
  hoveredFrequencySegmentId.value = segment.id
}

function handleFrequencySegmentOverlayClick(segment: FrequencySegment) {
  suppressBackgroundClick(300)
  emit('frequency-segment-clicked', getFrequencySegmentPayload(segment))
}

function handleFrequencySegmentOverlayDoubleClick(event: MouseEvent, segment: FrequencySegment) {
  const date = getPointerIsoDate(event, segment)
  if (!date) {
    return
  }

  suppressBackgroundClick(450)
  emit('frequency-segment-double-clicked', {
    ...getFrequencySegmentPayload(segment),
    date
  })
}

function handleNativeChartDoubleClick(event: MouseEvent) {
  if (props.interactionMode !== 'annotate' || !hoveredFrequencySegment) {
    return
  }

  const date = getPointerIsoDate(event, hoveredFrequencySegment)
  if (!date) {
    return
  }

  suppressBackgroundClick(450)
  emit('frequency-segment-double-clicked', {
    id: hoveredFrequencySegment.id,
    wellId: hoveredFrequencySegment.wellId,
    startDate: hoveredFrequencySegment.startDate,
    endDate: hoveredFrequencySegment.endDate,
    durationDays: hoveredFrequencySegment.durationDays,
    date
  })
}

function renderChart() {
  if (!chartEl.value) {
    return
  }

  const hasGasProductionSeries = props.activeSeries.includes('qgas')
  const hasGasFactorSeries =
    props.activeSeries.includes('gas_factor') ||
    props.activeSeries.includes('gas_liquid_factor') ||
    props.activeSeries.includes('tr_gas_factor')
  const hasPowerSeries = props.activeSeries.includes('active_power') || props.activeSeries.includes('full_power')
  const hasDynamicLevelSeries = props.activeSeries.includes('tr_dynamic_level')
  const hasProductivitySeries = props.activeSeries.includes('tr_productivity')
  const firstDate = props.data[0]?.date
  const lastDate = props.data[props.data.length - 1]?.date
  const mainAxisConfig = buildNiceAxis(getPrimaryAxisValues(), 6)
  const gasAxisConfig = buildNiceAxis(getSeriesValues('qgas'), 5)
  const percentAxisConfig = buildNiceAxis([
    ...getSeriesValues('water_cut'),
    ...getSeriesValues('load'),
    ...getActiveSeriesValues(['tr_water_cut'])
  ], 5)
  const pressureAxisConfig = buildNiceAxis([
    ...getSeriesValues('buffer_pressure'),
    ...getSeriesValues('casing_pressure'),
    ...getSeriesValues('intake_pressure'),
    ...getSeriesValues('collector_pressure'),
    ...getActiveSeriesValues([
      'tr_reservoir_pressure',
      'tr_intake_pressure',
      'tr_bottomhole_pressure',
      'tr_pump_pressure'
    ])
  ], 5)
  const frequencyAxisConfig = buildNiceAxis(getSeriesValues('esp_frequency'), 4)
  const powerAxisConfig = buildNiceAxis([
    ...getSeriesValues('active_power'),
    ...getSeriesValues('full_power')
  ], 5)
  const factorAxisConfig = buildNiceAxis([
    ...getSeriesValues('gas_factor'),
    ...getSeriesValues('gas_liquid_factor'),
    ...getActiveSeriesValues(['tr_gas_factor'])
  ], 5)
  const dynamicLevelAxisConfig = buildNiceAxis(getSeriesValues('tr_dynamic_level'), 5)
  const productivityAxisConfig = buildNiceAxis(getSeriesValues('tr_productivity'), 5)
  const trackLayout = getTrackLayoutRows()
  const contextRow = getTrackRowByAxis(trackLayout.rows, 'y7')
  const vspRow = getTrackRowByAxis(trackLayout.rows, 'y5')
  const espRow = getTrackRowByAxis(trackLayout.rows, 'y6')
  const eventRow = getTrackRowByAxis(trackLayout.rows, 'y8')
  const rootCauseRow = getTrackRowByAxis(trackLayout.rows, 'y9')
  const visibleRangeForLayout = localVisibleDateRange.value ?? props.visibleDateRange
  const layoutShapes = [
    ...getSelectionShapes(),
    {
      type: 'line',
      xref: 'paper',
      yref: 'paper',
      x0: 0,
      x1: 0,
      y0: trackLayout.rows[trackLayout.rows.length - 1]?.domain[0] ?? 0,
      y1: trackLayout.rows[0]?.domain[1] ?? 0,
      line: {
        color: 'rgba(71,85,105,0.45)',
        width: 1
      },
      layer: 'below'
    },
    ...trackLayout.separatorYs.map((y) => ({
      type: 'line',
      xref: 'paper',
      yref: 'paper',
      x0: 0,
      x1: 1,
      y0: y,
      y1: y,
      line: {
        color: 'rgba(71,85,105,0.38)',
        width: 1
      },
      layer: 'below'
    }))
  ]

  const layout = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: '#0f172a',
    font: { color: '#e5e7eb', family: 'Segoe UI, sans-serif' },
    margin: { l: CHART_MARGIN_LEFT, r: CHART_MARGIN_RIGHT, t: 24, b: 42 },
    dragmode: props.interactionMode === 'annotate' ? 'select' : 'zoom',
    selectdirection: props.interactionMode === 'annotate' ? 'h' : undefined,
    hovermode: false,
    barmode: 'overlay',
    uirevision: firstDate && lastDate ? `${firstDate}-${lastDate}` : 'empty',
    legend: {
      orientation: 'h',
      yanchor: 'bottom',
      y: 1.02,
      xanchor: 'left',
      x: 0,
      bgcolor: 'rgba(15,23,42,0.82)',
      bordercolor: 'rgba(55,65,81,0.85)',
      borderwidth: 1,
      font: {
        color: '#e5e7eb',
        size: 11
      }
    },
    hoverlabel: {
      bgcolor: '#111827',
      bordercolor: '#374151',
      font: {
        color: '#e5e7eb',
        size: 11
      }
    },
    xaxis: {
      title: 'Дата',
      type: 'date',
      range: visibleRangeForLayout ? [visibleRangeForLayout.startDate, visibleRangeForLayout.endDate] : undefined,
      tickformat: '%Y-%m-%d',
      showgrid: true,
      titlefont: { color: '#cbd5e1', size: 11 },
      tickfont: { color: '#cbd5e1', size: 10 },
      gridcolor: 'rgba(71,85,105,0.28)',
      linecolor: 'rgba(100,116,139,0.6)',
      zeroline: false,
      rangeslider: { visible: false }
    },
    yaxis: {
      title: 'Дебиты / БДПВ',
      domain: trackLayout.mainDomain,
      range: mainAxisConfig.range,
      autorange: false,
      fixedrange: true,
      titlefont: { color: '#e5e7eb', size: 11 },
      tickfont: { color: '#e5e7eb', size: 10 },
      tickmode: 'linear',
      tick0: mainAxisConfig.tick0,
      dtick: mainAxisConfig.dtick,
      gridcolor: 'rgba(71,85,105,0.28)',
      linecolor: 'rgba(100,116,139,0.6)',
      zeroline: false
    },
    yaxis2: {
      title: 'Обводненность / загрузка',
      overlaying: 'y',
      side: 'right',
      position: 0.885,
      range: percentAxisConfig.range,
      autorange: false,
      fixedrange: true,
      titlefont: { color: '#7dd3fc', size: 11 },
      tickfont: { color: '#7dd3fc', size: 10 },
      tickmode: 'linear',
      tick0: percentAxisConfig.tick0,
      dtick: percentAxisConfig.dtick,
      showgrid: false
    },
    yaxis3: {
      title: 'Давления',
      overlaying: 'y',
      side: 'right',
      position: 0.92,
      range: pressureAxisConfig.range,
      autorange: false,
      fixedrange: true,
      titlefont: { color: '#f87171', size: 11 },
      tickfont: { color: '#f87171', size: 10 },
      tickmode: 'linear',
      tick0: pressureAxisConfig.tick0,
      dtick: pressureAxisConfig.dtick,
      showgrid: false
    },
    yaxis4: {
      title: 'Частота ЭЦН',
      overlaying: 'y',
      side: 'right',
      position: 0.955,
      range: frequencyAxisConfig.range,
      autorange: false,
      fixedrange: true,
      titlefont: { color: '#2563eb', size: 11 },
      tickfont: { color: '#2563eb', size: 10 },
      tickmode: 'linear',
      tick0: frequencyAxisConfig.tick0,
      dtick: frequencyAxisConfig.dtick,
      showgrid: false
    },
    yaxis5: {
      domain: vspRow.domain,
      range: vspRow.range,
      fixedrange: true,
      showgrid: false,
      showticklabels: false,
      zeroline: false
    },
    yaxis6: {
      domain: espRow.domain,
      range: espRow.range,
      fixedrange: true,
      showgrid: false,
      showticklabels: false,
      zeroline: false
    },
    yaxis7: {
      domain: contextRow.domain,
      range: contextRow.range,
      fixedrange: true,
      showgrid: false,
      showticklabels: false,
      zeroline: false
    },
    shapes: layoutShapes,
    annotations: buildAnnotations()
  }

  if (hasGasProductionSeries) {
    Object.assign(layout, {
      yaxis12: {
        title: 'Расход газа',
        overlaying: 'y',
        side: 'left',
        anchor: 'free',
        position: 0.05,
        range: gasAxisConfig.range,
        autorange: false,
        fixedrange: true,
        titlefont: { color: '#fdba74', size: 11 },
        tickfont: { color: '#fdba74', size: 10 },
        tickmode: 'linear',
        tick0: gasAxisConfig.tick0,
        dtick: gasAxisConfig.dtick,
        showgrid: false
      }
    })
  }

  if (hasPowerSeries) {
    Object.assign(layout, {
      yaxis14: {
        title: 'Мощность',
        overlaying: 'y',
        side: 'left',
        anchor: 'free',
        position: 0.105,
        range: powerAxisConfig.range,
        autorange: false,
        fixedrange: true,
        titlefont: { color: '#a3e635', size: 11 },
        tickfont: { color: '#a3e635', size: 10 },
        tickmode: 'linear',
        tick0: powerAxisConfig.tick0,
        dtick: powerAxisConfig.dtick,
        showgrid: false
      }
    })
  }

  if (hasGasFactorSeries) {
    Object.assign(layout, {
      yaxis13: {
        title: 'Газовые факторы',
        overlaying: 'y',
        side: 'right',
        position: 0.985,
        range: factorAxisConfig.range,
        autorange: false,
        fixedrange: true,
        titlefont: { color: '#c084fc', size: 11 },
        tickfont: { color: '#c084fc', size: 10 },
        tickmode: 'linear',
        tick0: factorAxisConfig.tick0,
        dtick: factorAxisConfig.dtick,
        showgrid: false
      }
    })
  }

  if (hasDynamicLevelSeries) {
    Object.assign(layout, {
      yaxis16: {
        title: 'ТР: Н д',
        overlaying: 'y',
        side: 'left',
        anchor: 'free',
        position: 0.215,
        range: dynamicLevelAxisConfig.range,
        autorange: false,
        fixedrange: true,
        titlefont: { color: '#c084fc', size: 11 },
        tickfont: { color: '#c084fc', size: 10 },
        tickmode: 'linear',
        tick0: dynamicLevelAxisConfig.tick0,
        dtick: dynamicLevelAxisConfig.dtick,
        showgrid: false
      }
    })
  }

  if (hasProductivitySeries) {
    Object.assign(layout, {
      yaxis17: {
        title: 'ТР: Кпр',
        overlaying: 'y',
        side: 'right',
        position: 0.85,
        range: productivityAxisConfig.range,
        autorange: false,
        fixedrange: true,
        titlefont: { color: '#34d399', size: 11 },
        tickfont: { color: '#34d399', size: 10 },
        tickmode: 'linear',
        tick0: productivityAxisConfig.tick0,
        dtick: productivityAxisConfig.dtick,
        showgrid: false
      }
    })
  }

  if (eventRow) {
    Object.assign(layout, {
      yaxis8: {
        domain: eventRow.domain,
        range: eventRow.range,
        fixedrange: true,
        showgrid: false,
        showticklabels: false,
        zeroline: false
      }
    })
  }

  if (rootCauseRow) {
    Object.assign(layout, {
      yaxis9: {
        domain: rootCauseRow.domain,
        range: rootCauseRow.range,
        fixedrange: true,
        showgrid: false,
        showticklabels: false,
        zeroline: false
      }
    })
  }

  const config = {
    responsive: true,
    displayModeBar: true,
    displaylogo: false,
    doubleClick: props.interactionMode === 'navigate' ? 'reset+autosize' : false,
    modeBarButtonsToRemove: ['lasso2d']
  }

  void Plotly.react(chartEl.value, [...buildMainTraces(), ...buildTrackTraces()], layout, config)
}

function attachEventHandlers() {
  const plotlyElement = chartEl.value as PlotlyElement | null

  if (!plotlyElement || handlersAttached.value) {
    return
  }

  plotlyElement.on?.('plotly_selected', (eventData: Record<string, unknown>) => {
    if (props.interactionMode !== 'annotate') {
      return
    }

    suppressBackgroundClick()

    const xValues = getSelectedDatesFromPlotlyEvent(eventData)

    if (xValues.length > 0) {
      const startDate = xValues[0]
      const endDate = xValues[xValues.length - 1]

      if (startDate && endDate) {
        emit('interval-selected', normalizeSelectedInterval(startDate, endDate))
      }
    }
  })

  plotlyElement.on?.('plotly_deselect', () => {
    if (Date.now() < suppressDeselectUntil) {
      return
    }

    if (props.interactionMode === 'annotate') {
      emit('interval-selected', null)
    }
  })

  plotlyElement.on?.('plotly_hover', (eventData: Record<string, unknown>) => {
    const customdata = getEventCustomdataByKind<FrequencySegmentCustomdata>(eventData, 'frequencySegment')

    if (props.interactionMode === 'annotate' && customdata) {
      hoveredFrequencySegment = customdata
      hoveredFrequencySegmentId.value = customdata.id
      return
    }

    clearFrequencySegmentHover()
  })

  plotlyElement.on?.('plotly_unhover', () => {
    clearFrequencySegmentHover()
  })

  plotlyElement.on?.('plotly_click', (eventData: Record<string, unknown>) => {
    suppressBackgroundClick()

    const segmentCustomdata = getEventCustomdataByKind<FrequencySegmentCustomdata>(eventData, 'frequencySegment')
    if (segmentCustomdata) {
      emit('frequency-segment-clicked', {
        id: segmentCustomdata.id,
        wellId: segmentCustomdata.wellId,
        startDate: segmentCustomdata.startDate,
        endDate: segmentCustomdata.endDate,
        durationDays: segmentCustomdata.durationDays
      })
      return
    }

    const breakpointCustomdata = getEventCustomdataByKind<FrequencyBreakpointCustomdata>(eventData, 'frequencyBreakpoint')
    if (breakpointCustomdata) {
      emit('frequency-breakpoint-clicked', {
        id: breakpointCustomdata.id,
        wellId: breakpointCustomdata.wellId,
        date: breakpointCustomdata.date,
        source: breakpointCustomdata.source,
        reason: breakpointCustomdata.reason,
        fromFrequency: breakpointCustomdata.fromFrequency,
        toFrequency: breakpointCustomdata.toFrequency
      })
      return
    }

    const customdata = getEventCustomdataByKind<SavedAnnotationCustomdata>(eventData, 'annotation')

    if (customdata) {
      emit('annotation-clicked', {
        annotationId: customdata.annotationId,
        source: customdata.source,
        layer: customdata.layer,
        label: customdata.categoryLabel,
        startDate: customdata.startDate,
        endDate: customdata.endDate,
        durationDays: customdata.durationDays,
        actions: customdata.actions ?? []
      })
    }
  })

  plotlyElement.on?.('plotly_relayout', (eventData: Record<string, unknown>) => {
    const relayoutData = eventData as PlotlyRelayoutEvent
    const explicitRange = relayoutData['xaxis.range']
    const rangeStart = explicitRange?.[0] ?? relayoutData['xaxis.range[0]']
    const rangeEnd = explicitRange?.[1] ?? relayoutData['xaxis.range[1]']

    if (rangeStart && rangeEnd) {
      const nextRange = {
        startDate: rangeStart,
        endDate: rangeEnd
      }
      localVisibleDateRange.value = nextRange
      emit('visible-range-changed', nextRange)
      return
    }

    if (relayoutData['xaxis.autorange']) {
      const fullRange = getFullVisibleDateRange()
      localVisibleDateRange.value = fullRange
      emit('visible-range-changed', fullRange)
    }
  })

  chartEl.value?.addEventListener('click', handleNativeChartClick)
  chartEl.value?.addEventListener('dblclick', handleNativeChartDoubleClick)

  handlersAttached.value = true
}

function clearSelection() {
  resetPlotlySelectionState()
  emit('interval-selected', null)
}

function zoomToSelection() {
  if (!chartEl.value || !props.selectedInterval) {
    return
  }

  void Plotly.relayout(chartEl.value, {
    'xaxis.range[0]': props.selectedInterval.startDate,
    'xaxis.range[1]': getInclusiveDateAxisEnd(props.selectedInterval.endDate)
  })
}

function resetZoom() {
  if (!chartEl.value) {
    return
  }

  const nextRange = getFullVisibleDateRange()

  if (nextRange) {
    localVisibleDateRange.value = nextRange
    void Plotly.relayout(chartEl.value, {
      'xaxis.range[0]': nextRange.startDate,
      'xaxis.range[1]': nextRange.endDate
    })
    return
  }

  localVisibleDateRange.value = getFullVisibleDateRange()
  void Plotly.relayout(chartEl.value, {
    'xaxis.autorange': true
  })
}

defineExpose({
  clearSelection,
  zoomToSelection,
  resetZoom
})

onMounted(() => {
  renderChart()
  attachEventHandlers()

  updateChartSize()
  if (chartEl.value) {
    chartResizeObserver = new ResizeObserver(updateChartSize)
    chartResizeObserver.observe(chartEl.value)
  }
})

watch(
  () => props.visibleDateRange,
  (visibleRange) => {
    localVisibleDateRange.value = visibleRange
  },
  { deep: true, immediate: true }
)

watch(
  () => [
    props.data,
    props.trMonitoringData,
    props.vspPeriods,
    props.activeSeries,
    props.selectedInterval,
    props.eventTracks,
    props.interactionMode,
    props.savedAnnotations,
    props.selectedAnnotationId,
    props.frequencyBreakpoints,
    props.frequencySegments,
    props.selectedFrequencyBreakpointId,
    props.selectedFrequencySegmentIds,
    props.visibleDateRange
  ],
  () => {
    renderChart()
  },
  { deep: true }
)

onBeforeUnmount(() => {
  chartResizeObserver?.disconnect()
  chartResizeObserver = null
  window.removeEventListener('mouseup', handleAnnotationDragEnd)
  chartEl.value?.removeEventListener('click', handleNativeChartClick)
  chartEl.value?.removeEventListener('dblclick', handleNativeChartDoubleClick)
  if (chartEl.value) {
    Plotly.purge(chartEl.value)
  }
})
</script>

<style scoped>
.frequency-chart {
  position: relative;
}

.frequency-chart :deep(.modebar-container) {
  position: absolute !important;
  top: 8px !important;
  left: 8px !important;
  right: auto !important;
  width: auto !important;
  height: auto !important;
  z-index: 30 !important;
  pointer-events: none;
}

.frequency-chart :deep(.modebar) {
  position: static !important;
  display: flex !important;
  flex-wrap: wrap;
  gap: 2px;
  width: 76px;
  padding: 3px;
  border: 1px solid rgba(71, 85, 105, 0.72);
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.88);
  pointer-events: auto;
  transform: none !important;
}

.frequency-chart :deep(.modebar-group) {
  display: flex !important;
  flex-wrap: wrap;
  gap: 2px;
  padding: 0 !important;
}

.frequency-chart.frequency-segment-hover,
.frequency-chart.frequency-segment-hover :deep(.nsewdrag),
.frequency-chart.frequency-segment-hover :deep(.drag),
.frequency-chart.frequency-segment-hover :deep(.barlayer),
.frequency-chart.frequency-segment-hover :deep(.bars) {
  cursor: pointer !important;
}

.track-label-overlay {
  position: absolute;
  transform: translateY(-50%);
  white-space: nowrap;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  text-shadow: 0 1px 2px rgba(2, 6, 23, 0.88);
}

.esp-segment-label-overlay {
  position: absolute;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  padding: 0 8px;
  color: #f8fafc;
  font-size: 13px;
  font-weight: 700;
  line-height: 1;
  text-align: center;
  text-overflow: ellipsis;
  text-shadow: 0 1px 3px rgba(2, 6, 23, 0.85);
  white-space: nowrap;
}

.hover-guide-line {
  position: absolute;
  width: 1px;
  transform: translateX(-0.5px);
  background: rgba(226, 232, 240, 0.74);
  box-shadow: 0 0 0 1px rgba(14, 165, 233, 0.16);
}

.hover-guide-tooltip {
  position: absolute;
  max-height: 360px;
  overflow: hidden;
  border: 1px solid rgba(100, 116, 139, 0.72);
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.92);
  padding: 8px 10px;
  font-size: 11px;
  box-shadow: 0 12px 28px rgba(2, 6, 23, 0.32);
}

.track-hover-hitbox {
  position: absolute;
  pointer-events: auto;
  cursor: help;
  border: 0;
  background: transparent;
  padding: 0;
}

.track-hover-tooltip {
  position: absolute;
  z-index: 14;
  pointer-events: none;
  max-height: 300px;
  overflow: hidden;
  border: 1px solid rgba(100, 116, 139, 0.78);
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.95);
  padding: 9px 11px;
  font-size: 11px;
  box-shadow: 0 14px 30px rgba(2, 6, 23, 0.38);
}

.saved-annotation-hitbox {
  position: absolute;
  pointer-events: auto;
  cursor: pointer;
  border: 1px solid transparent;
  border-radius: 4px;
  background: transparent;
  padding: 0;
}

.saved-annotation-hitbox:hover,
.saved-annotation-hitbox.is-selected {
  border-color: rgba(248, 250, 252, 0.82);
  background: rgba(248, 250, 252, 0.06);
  box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.32);
}

.frequency-segment-hitbox {
  position: absolute;
  pointer-events: auto;
  cursor: pointer;
  border: 1px solid rgba(125, 211, 252, 0.28);
  border-radius: 4px;
  background: rgba(56, 189, 248, 0.08);
  padding: 0;
  transition:
    background 0.12s ease,
    border-color 0.12s ease,
    box-shadow 0.12s ease;
}

.frequency-segment-hitbox:hover,
.frequency-segment-hitbox.is-selected {
  border-color: rgba(248, 250, 252, 0.86);
  background: rgba(56, 189, 248, 0.32);
  box-shadow: 0 0 0 1px rgba(14, 165, 233, 0.35);
}

.frequency-segment-add-button {
  position: absolute;
  pointer-events: auto;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid rgba(248, 250, 252, 0.92);
  border-radius: 9999px;
  background: #38bdf8;
  color: #0f172a;
  font-size: 20px;
  font-weight: 700;
  line-height: 1;
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.35);
}

.frequency-segment-add-button:hover {
  background: #7dd3fc;
}

.time-pan-slider-shell {
  position: absolute;
  z-index: 16;
  height: 18px;
  pointer-events: auto;
}

.time-pan-track {
  position: absolute;
  left: 0;
  right: 0;
  top: 6px;
  height: 6px;
  overflow: hidden;
  border-radius: 9999px;
  background: rgba(51, 65, 85, 0.78);
  box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.18);
}

.time-pan-thumb {
  position: absolute;
  top: 1px;
  bottom: 1px;
  min-width: 36px;
  border-radius: 9999px;
  background: rgba(226, 232, 240, 0.88);
  box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.25);
}

.time-pan-slider {
  position: absolute;
  inset: 0;
  display: block;
  width: 100%;
  height: 18px;
  cursor: grab;
  background: transparent;
  appearance: none;
  opacity: 0;
}

.time-pan-slider:active {
  cursor: grabbing;
}

.time-pan-slider::-webkit-slider-runnable-track {
  height: 18px;
  background: transparent;
}

.time-pan-slider::-webkit-slider-thumb {
  appearance: none;
  width: 18px;
  height: 18px;
}

.time-pan-slider::-moz-range-track {
  height: 18px;
  background: transparent;
}

.time-pan-slider::-moz-range-thumb {
  width: 18px;
  height: 18px;
  border: 0;
  background: transparent;
}
</style>
