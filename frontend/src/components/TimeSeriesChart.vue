<template>
  <div ref="chartEl" class="h-[920px] w-full"></div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Plotly from 'plotly.js-dist-min'
import type {
  HierarchicalEventTracks,
  InteractionMode,
  SavedAnnotation,
  SelectedInterval,
  SeriesKey,
  TimelineAnnotationClickPayload,
  TimeSeriesPoint,
  VisibleDateRange
} from '@/types/timeseries'

const props = defineProps<{
  data: TimeSeriesPoint[]
  activeSeries: SeriesKey[]
  selectedInterval: SelectedInterval | null
  eventTracks: HierarchicalEventTracks
  interactionMode: InteractionMode
  savedAnnotations: SavedAnnotation[]
  selectedAnnotationId: string | null
  visibleDateRange: VisibleDateRange | null
}>()

const emit = defineEmits<{
  (event: 'interval-selected', value: SelectedInterval | null): void
  (event: 'annotation-clicked', value: TimelineAnnotationClickPayload): void
  (event: 'visible-range-changed', value: VisibleDateRange | null): void
  (event: 'background-clicked'): void
}>()

type PlotlyElement = HTMLDivElement & {
  on?: (eventName: string, handler: (eventData: Record<string, unknown>) => void) => void
}

interface PlotlySelectedPoint {
  x?: string | number
}

interface SavedAnnotationCustomdata {
  annotationId?: string
  source: 'manual' | 'model'
  layer: 'event' | 'rootCause'
  annotationKind: string
  startDate: string
  endDate: string
  durationDays: number
  categoryLabel: string
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
  axis: 'y6' | 'y7' | 'y8' | 'y9' | 'y10' | 'y11'
  label: string
  labelColor: string
  domain: [number, number]
  range: [number, number]
}

const TRACK_LABEL_COLUMN_X = -0.16
const MAIN_CHART_DOMAIN_START = 0.278
const TRACK_PANEL_TOP = 0.248
const TRACK_MAIN_GAP = 0.03

interface PlotlyRelayoutEvent {
  'xaxis.range[0]'?: string
  'xaxis.range[1]'?: string
  'xaxis.range'?: [string, string]
  'xaxis.autorange'?: boolean
}

const chartEl = ref<HTMLDivElement | null>(null)
const handlersAttached = ref(false)
let suppressBackgroundClickUntil = 0

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
  { label: string; color: string; axis: string; width?: number; dash?: 'solid' | 'dot' }
> = {
  qliq: { label: 'Дебит жидкости', color: '#e5e7eb', axis: 'y', width: 2.8 },
  qoil: { label: 'Дебит нефти', color: '#c4a484', axis: 'y', width: 2.8 },
  qgas: { label: 'Добыча газа', color: '#fdba74', axis: 'y12', width: 2.1 },
  gas_factor: { label: 'Газовый фактор', color: '#a78bfa', axis: 'y13', width: 1.4 },
  gas_liquid_factor: { label: 'Газожидкостный фактор', color: '#f472b6', axis: 'y13', width: 1.4 },
  qliq_wfm: { label: 'Дебит жидкости (в.расходомер)', color: '#9ca3af', axis: 'y', width: 2, dash: 'dot' },
  water_cut: { label: 'Обводненность', color: '#7dd3fc', axis: 'y2', width: 2.2 },
  intake_pressure: { label: 'Давление на приеме', color: '#f87171', axis: 'y3', width: 1.4 },
  esp_frequency: { label: 'Частота ЭЦН', color: '#2563eb', axis: 'y4', width: 1.4 },
  load: { label: 'Загрузка', color: '#16a34a', axis: 'y5', width: 1.4 }
}

function getAnnotationColor(label: string): string {
  const colorMap: Record<string, string> = {
    decline: '#c2410c',
    instability: '#7c3aed',
    water_cut_growth: '#2563eb',
    downtime: '#475569',
    recovery: '#2f855a',
    regime_change: '#0f766e',
    post_intervention: '#be185d',
    unknown: '#64748b'
  }

  return colorMap[label] ?? '#64748b'
}

function getRootCauseColor(label: string): string {
  const colorMap: Record<string, string> = {
    esp_degradation: '#b45309',
    water_breakthrough: '#1d4ed8',
    unstable_operation: '#6d28d9',
    downtime_vsp: '#334155',
    opz_effect: '#0f766e',
    esp_replacement: '#0891b2',
    telemetry_issue: '#be123c',
    unknown: '#64748b'
  }

  return colorMap[label] ?? '#64748b'
}

function getEventTypeLabel(label: string): string {
  const labelMap: Record<string, string> = {
    decline: 'снижение',
    instability: 'нестабильность',
    water_cut_growth: 'рост обводненности',
    downtime: 'останов',
    recovery: 'восстановление',
    regime_change: 'смена режима',
    post_intervention: 'после вмешательства',
    unknown: 'неизвестно'
  }

  return labelMap[label] ?? label
}

function getRootCauseLabel(label: string): string {
  const labelMap: Record<string, string> = {
    esp_degradation: 'деградация ЭЦН',
    water_breakthrough: 'прорыв воды',
    unstable_operation: 'нестабильная работа',
    downtime_vsp: 'останов ВСП',
    opz_effect: 'эффект ОПЗ',
    esp_replacement: 'замена ЭЦН',
    telemetry_issue: 'ошибка телеметрии',
    unknown: 'неизвестно'
  }

  return labelMap[label] ?? label
}

function getEspColor(espId: string): string {
  const palette = ['#9ca3af', '#64748b', '#94a3b8', '#475569', '#7c8aa0', '#8b9db2']
  const hash = espId.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)
  return palette[hash % palette.length] ?? '#64748b'
}

function getEspSegmentLabel(startDate: string, endDate: string, espId: string): string {
  const durationDays = calculateDurationDays(startDate, endDate)

  if (durationDays >= 24) {
    return espId
  }

  if (durationDays >= 14) {
    return espId.length > 9 ? `${espId.slice(0, 9)}...` : espId
  }

  return ''
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

function toDurationMs(startDate: string, endDate: string): number {
  return Math.max(86400000, new Date(endDate).getTime() - new Date(startDate).getTime() + 86400000)
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

function getSeriesValues(key: SeriesKey): Array<number | null> {
  return props.data.map((item) => item[key])
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
    x1: props.selectedInterval.endDate,
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
  const baseRange = buildStableRange([
    ...getSeriesValues('qliq'),
    ...getSeriesValues('qoil'),
    ...getSeriesValues('qliq_wfm')
  ])

  const visibleSeries = props.activeSeries.map((seriesKey) => {
    const config = seriesConfig[seriesKey]
    return {
      x,
      y: props.data.map((item) => item[seriesKey]),
      type: 'scatter',
      mode: 'lines',
      name: config.label,
      yaxis: config.axis,
      line: {
        color: config.color,
        width: config.width ?? 2,
        dash: config.dash ?? 'solid'
      },
      hovertemplate: '%{x}<br>%{y:.2f}<extra>' + config.label + '</extra>'
    }
  })

  const opzTrace =
    props.eventTracks.opzEvents.length > 0
      ? [
          {
            x: props.eventTracks.opzEvents.map((item) => item.date),
            y: props.eventTracks.opzEvents.map(() => baseRange[1] - (baseRange[1] - baseRange[0]) * 0.04),
            type: 'scatter',
            mode: 'markers',
            name: 'ОПЗ',
            yaxis: 'y',
            marker: {
              symbol: 'diamond',
              size: 11,
              color: '#d97706',
              line: {
                color: '#9a3412',
                width: 1.2
              }
            },
            customdata: props.eventTracks.opzEvents.map((item) => ({
              date: item.date,
              operationType: item.operationType,
              comment: item.comment
            })),
            hovertemplate:
              '<b>ОПЗ</b><br>%{customdata.date}<br>%{customdata.operationType}<br>%{customdata.comment}<extra></extra>'
          }
        ]
      : []

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
      opacity: 0
    }
  }

  return [...visibleSeries, ...opzTrace, ...espWashTrace, selectionHelper]
}

function buildSavedAnnotationTrace(trackAxis: 'y8' | 'y9', annotationKind: 'event' | 'rootCause') {
  const trackAnnotations = props.savedAnnotations.filter((item) => item.annotationKind === annotationKind)

  if (trackAnnotations.length === 0) {
    return []
  }

  const laneAssignment = buildAnnotationLaneAssignment(trackAnnotations)

  return [
    {
      type: 'bar',
      orientation: 'h',
      x: trackAnnotations.map((item) => toDurationMs(item.startDate, item.endDate)),
      base: trackAnnotations.map((item) => item.startDate),
      y: laneAssignment.lanes.map((laneIndex) => laneIndex + 1.2),
      width: 0.72,
      marker: {
        color: trackAnnotations.map((item) =>
          item.annotationKind === 'event' ? getAnnotationColor(item.eventType) : getRootCauseColor(item.rootCause)
        ),
        line: {
          color: trackAnnotations.map((item) =>
            item.id === props.selectedAnnotationId
              ? '#0f172a'
              : item.annotationKind === 'event'
                ? getAnnotationColor(item.eventType)
                : getRootCauseColor(item.rootCause)
          ),
          width: trackAnnotations.map((item) => (item.id === props.selectedAnnotationId ? 2.5 : 1.1))
        },
        opacity: trackAnnotations.map((item) => (item.id === props.selectedAnnotationId ? 1 : 0.88))
      },
      yaxis: trackAxis,
      showlegend: false,
      customdata: trackAnnotations.map((item) => ({
        annotationId: item.id,
        source: 'manual' as const,
        layer: item.annotationKind,
        annotationKind: item.annotationKind === 'event' ? 'Событие' : 'Причина',
        startDate: item.startDate,
        endDate: item.endDate,
        durationDays: item.durationDays,
        categoryLabel: item.annotationKind === 'event' ? getEventTypeLabel(item.eventType) : getRootCauseLabel(item.rootCause)
      })),
      hovertemplate:
        '<b>%{customdata.annotationKind}</b>: %{customdata.categoryLabel}<br>%{customdata.startDate} -> %{customdata.endDate}<br>' +
        'Длительность: %{customdata.durationDays} сут.<extra></extra>'
    }
  ]
}

function buildModelTrackTrace(trackAxis: 'y10' | 'y11', trackType: 'event' | 'rootCause') {
  const intervals =
    trackType === 'event' ? props.eventTracks.modelEventIntervals : props.eventTracks.modelRootCauseIntervals

  if (intervals.length === 0) {
    return []
  }

  return [
    {
      type: 'bar',
      orientation: 'h',
      x: intervals.map((item) => toDurationMs(item.startDate, item.endDate)),
      base: intervals.map((item) => item.startDate),
      y: intervals.map(() => 0.5),
      width: 0.58,
      marker: {
        color: intervals.map((item) => item.color),
        opacity: 0.58,
        line: {
          color: intervals.map((item) => item.color),
          width: 1.2,
          dash: 'dot'
        }
      },
      yaxis: trackAxis,
      showlegend: false,
      customdata: intervals.map((item) => ({
        source: 'model' as const,
        layer: trackType,
        annotationKind: trackType === 'event' ? 'Эпизод' : 'Режим',
        label: item.label,
        startDate: item.startDate,
        endDate: item.endDate,
        durationDays: calculateDurationDays(item.startDate, item.endDate),
        categoryLabel: item.label
      })),
      hovertemplate:
        '<b>%{customdata.annotationKind}</b>: %{customdata.label}<br>%{customdata.startDate} -> %{customdata.endDate}<br>' +
        'Длительность: %{customdata.durationDays} сут.<extra></extra>'
    }
  ]
}

function buildTrackTraces() {
  const showManualTracks = shouldShowManualTracks()
  const espInstallationTrace =
    props.eventTracks.installedEspPeriods.length > 0
      ? [
          {
            type: 'bar',
            orientation: 'h',
            x: props.eventTracks.installedEspPeriods.map((item) => toDurationMs(item.startDate, item.endDate)),
            base: props.eventTracks.installedEspPeriods.map((item) => item.startDate),
            y: props.eventTracks.installedEspPeriods.map(() => 0.5),
            width: 0.48,
            marker: {
              color: props.eventTracks.installedEspPeriods.map((item) => getEspColor(item.espId)),
              line: {
                color: props.eventTracks.installedEspPeriods.map(() => 'rgba(226,232,240,0.52)'),
                width: 0.9
              }
            },
            yaxis: 'y6',
            showlegend: false,
            text: props.eventTracks.installedEspPeriods.map((item) =>
              getEspSegmentLabel(item.startDate, item.endDate, item.espId)
            ),
            textposition: 'inside',
            insidetextanchor: 'middle',
            textfont: {
              size: 11,
              color: '#f8fafc'
            },
            cliponaxis: true,
            customdata: props.eventTracks.installedEspPeriods.map((item) => ({
              espId: item.espId,
              startDate: item.startDate,
              endDate: item.endDate
            })),
            hovertemplate:
              '<b>%{customdata.espId}</b><br>%{customdata.startDate} -> %{customdata.endDate}<extra></extra>'
          }
        ]
      : []

  const dailyCauseTraces =
    props.eventTracks.dailyCauses.length > 0
      ? [
          {
            type: 'bar',
            orientation: 'h',
            x: props.eventTracks.dailyCauses.map(() => 86400000),
            base: props.eventTracks.dailyCauses.map((item) => item.date),
            y: props.eventTracks.dailyCauses.map(() => 0.5),
            width: 0.82,
            marker: {
              color: props.eventTracks.dailyCauses.map((item) => item.color),
              opacity: 0.62,
              line: {
                color: 'rgba(51,65,85,0.9)',
                width: 0.4
              }
            },
            yaxis: 'y7',
            showlegend: false,
            customdata: props.eventTracks.dailyCauses.map((item) => item.label),
            hovertemplate: '<b>Суточная причина</b><br>%{base}<br>%{customdata}<extra></extra>'
          }
        ]
      : []

  return [
    ...espInstallationTrace,
    ...dailyCauseTraces,
    ...(showManualTracks ? buildSavedAnnotationTrace('y8', 'event') : []),
    ...(showManualTracks ? buildSavedAnnotationTrace('y9', 'rootCause') : []),
    ...buildModelTrackTrace('y10', 'event'),
    ...buildModelTrackTrace('y11', 'rootCause')
  ]
}

function getSavedAnnotationTrackRange(annotationKind: 'event' | 'rootCause'): [number, number] {
  const laneCount = buildAnnotationLaneAssignment(
    props.savedAnnotations.filter((item) => item.annotationKind === annotationKind)
  ).laneCount
  return [0, Math.max(2, laneCount + 1.6)]
}

function shouldShowManualTracks(): boolean {
  return props.interactionMode === 'annotate'
}

function getTrackLayoutRows(): { rows: TrackLayoutRow[]; mainDomain: [number, number]; separatorYs: number[] } {
  const eventRange = getSavedAnnotationTrackRange('event')
  const rootCauseRange = getSavedAnnotationTrackRange('rootCause')
  const eventLaneCount = Math.max(1, Math.ceil(eventRange[1] - 1.6))
  const rootCauseLaneCount = Math.max(1, Math.ceil(rootCauseRange[1] - 1.6))

  const rowSpecs = [
    { axis: 'y6' as const, label: 'Установленный ЭЦН', labelColor: '#94a3b8', heightUnits: 0.56, range: [0, 1] as [number, number] },
    { axis: 'y7' as const, label: 'Суточные причины', labelColor: '#94a3b8', heightUnits: 0.3, range: [0, 1] as [number, number] },
    { axis: 'y8' as const, label: 'Эпизоды (пользователь)', labelColor: '#94a3b8', heightUnits: Math.max(1.02, 0.68 * eventLaneCount), range: eventRange },
    { axis: 'y9' as const, label: 'Режимы (пользователь)', labelColor: '#94a3b8', heightUnits: Math.max(1.02, 0.68 * rootCauseLaneCount), range: rootCauseRange },
    { axis: 'y10' as const, label: 'Эпизоды (модель)', labelColor: '#cbd5e1', heightUnits: 0.62, range: [0, 1] as [number, number] },
    { axis: 'y11' as const, label: 'Режимы (модель)', labelColor: '#cbd5e1', heightUnits: 0.62, range: [0, 1] as [number, number] }
  ].filter((row) => shouldShowManualTracks() || (row.axis !== 'y8' && row.axis !== 'y9'))

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
  const trackLayout = getTrackLayoutRows()
  const annotations: Array<Record<string, unknown>> = trackLayout.rows.map((row) => ({
    xref: 'paper',
    yref: 'paper',
    x: TRACK_LABEL_COLUMN_X,
    y: (row.domain[0] + row.domain[1]) / 2,
    xanchor: 'left',
    yanchor: 'middle',
    text: `<b>${row.label}</b>`,
    showarrow: false,
    align: 'left',
    font: { size: 11, color: row.labelColor }
  }))

  if (props.data.length === 0) {
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
  const startDate = props.data[0]?.date
  const endDate = props.data[props.data.length - 1]?.date

  if (!startDate || !endDate) {
    return null
  }

  return { startDate, endDate }
}

function renderChart() {
  if (!chartEl.value) {
    return
  }

  const hasGasProductionSeries = props.activeSeries.includes('qgas')
  const hasGasFactorSeries =
    props.activeSeries.includes('gas_factor') || props.activeSeries.includes('gas_liquid_factor')
  const firstDate = props.data[0]?.date
  const lastDate = props.data[props.data.length - 1]?.date
  const mainAxisConfig = buildNiceAxis([
    ...getSeriesValues('qliq'),
    ...getSeriesValues('qoil'),
    ...getSeriesValues('qliq_wfm')
  ], 6)
  const gasAxisConfig = buildNiceAxis(getSeriesValues('qgas'), 5)
  const waterAxisConfig = buildNiceAxis(getSeriesValues('water_cut'), 5)
  const pressureAxisConfig = buildNiceAxis(getSeriesValues('intake_pressure'), 5)
  const frequencyAxisConfig = buildNiceAxis(getSeriesValues('esp_frequency'), 4)
  const loadAxisConfig = buildNiceAxis(getSeriesValues('load'), 5)
  const factorAxisConfig = buildNiceAxis([
    ...getSeriesValues('gas_factor'),
    ...getSeriesValues('gas_liquid_factor')
  ], 5)
  const trackLayout = getTrackLayoutRows()
  const espRow = getTrackRowByAxis(trackLayout.rows, 'y6')
  const dailyRow = getTrackRowByAxis(trackLayout.rows, 'y7')
  const modelEventRow = getTrackRowByAxis(trackLayout.rows, 'y10')
  const modelRootCauseRow = getTrackRowByAxis(trackLayout.rows, 'y11')
  const eventRow = shouldShowManualTracks() ? getTrackRowByAxis(trackLayout.rows, 'y8') : null
  const rootCauseRow = shouldShowManualTracks() ? getTrackRowByAxis(trackLayout.rows, 'y9') : null
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
    margin: { l: 190, r: 170, t: 24, b: 42 },
    dragmode: props.interactionMode === 'annotate' ? 'select' : 'zoom',
    selectdirection: props.interactionMode === 'annotate' ? 'h' : undefined,
    hovermode: 'x unified',
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
      range: props.visibleDateRange
        ? [props.visibleDateRange.startDate, props.visibleDateRange.endDate]
        : undefined,
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
      title: 'Дебит жидкости / дебит нефти',
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
      title: 'Обводненность',
      overlaying: 'y',
      side: 'right',
      position: 0.885,
      range: waterAxisConfig.range,
      autorange: false,
      fixedrange: true,
      titlefont: { color: '#7dd3fc', size: 11 },
      tickfont: { color: '#7dd3fc', size: 10 },
      tickmode: 'linear',
      tick0: waterAxisConfig.tick0,
      dtick: waterAxisConfig.dtick,
      showgrid: false
    },
    yaxis3: {
      title: 'Давление на приеме',
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
      title: 'Загрузка',
      overlaying: 'y',
      side: 'left',
      anchor: 'free',
      position: 0,
      range: loadAxisConfig.range,
      autorange: false,
      fixedrange: true,
      titlefont: { color: '#16a34a', size: 11 },
      tickfont: { color: '#16a34a', size: 10 },
      tickmode: 'linear',
      tick0: loadAxisConfig.tick0,
      dtick: loadAxisConfig.dtick,
      showgrid: false
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
      domain: dailyRow.domain,
      range: dailyRow.range,
      fixedrange: true,
      showgrid: false,
      showticklabels: false,
      zeroline: false
    },
    yaxis10: {
      domain: modelEventRow.domain,
      range: modelEventRow.range,
      fixedrange: true,
      showgrid: false,
      showticklabels: false,
      zeroline: false
    },
    yaxis11: {
      domain: modelRootCauseRow.domain,
      range: modelRootCauseRow.range,
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
        title: 'Добыча газа',
        overlaying: 'y',
        side: 'left',
        anchor: 'free',
        position: 0.065,
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

    const points = (eventData.points as PlotlySelectedPoint[] | undefined) ?? []
    const xValues = points
      .map((point) => point.x)
      .filter((value): value is string => typeof value === 'string')
      .sort()

    if (xValues.length > 0) {
      const startDate = xValues[0]
      const endDate = xValues[xValues.length - 1]

      if (startDate && endDate) {
        emit('interval-selected', normalizeSelectedInterval(startDate, endDate))
      }
    }
  })

  plotlyElement.on?.('plotly_click', (eventData: Record<string, unknown>) => {
    suppressBackgroundClick()

    const points = (eventData.points as Array<{ customdata?: unknown }> | undefined) ?? []
    const customdata = points[0]?.customdata as SavedAnnotationCustomdata | undefined

    if (customdata?.layer) {
      emit('annotation-clicked', {
        annotationId: customdata.annotationId,
        source: customdata.source,
        layer: customdata.layer,
        label: customdata.categoryLabel,
        startDate: customdata.startDate,
        endDate: customdata.endDate,
        durationDays: customdata.durationDays
      })
    }
  })

  plotlyElement.on?.('plotly_relayout', (eventData: Record<string, unknown>) => {
    const relayoutData = eventData as PlotlyRelayoutEvent
    const explicitRange = relayoutData['xaxis.range']
    const rangeStart = explicitRange?.[0] ?? relayoutData['xaxis.range[0]']
    const rangeEnd = explicitRange?.[1] ?? relayoutData['xaxis.range[1]']

    if (rangeStart && rangeEnd) {
      emit('visible-range-changed', {
        startDate: rangeStart,
        endDate: rangeEnd
      })
      return
    }

    if (relayoutData['xaxis.autorange']) {
      emit('visible-range-changed', getFullVisibleDateRange())
    }
  })

  chartEl.value?.addEventListener('click', handleNativeChartClick)

  handlersAttached.value = true
}

function clearSelection() {
  emit('interval-selected', null)
}

function zoomToSelection() {
  if (!chartEl.value || !props.selectedInterval) {
    return
  }

  void Plotly.relayout(chartEl.value, {
    'xaxis.range[0]': props.selectedInterval.startDate,
    'xaxis.range[1]': props.selectedInterval.endDate
  })
}

function resetZoom() {
  if (!chartEl.value) {
    return
  }

  const firstDate = props.data[0]?.date
  const lastDate = props.data[props.data.length - 1]?.date

  if (firstDate && lastDate) {
    void Plotly.relayout(chartEl.value, {
      'xaxis.range[0]': firstDate,
      'xaxis.range[1]': lastDate
    })
    return
  }

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
})

watch(
  () => [
    props.data,
    props.activeSeries,
    props.selectedInterval,
    props.eventTracks,
    props.interactionMode,
    props.savedAnnotations,
    props.selectedAnnotationId,
    props.visibleDateRange
  ],
  () => {
    renderChart()
  },
  { deep: true }
)

onBeforeUnmount(() => {
  chartEl.value?.removeEventListener('click', handleNativeChartClick)
  if (chartEl.value) {
    Plotly.purge(chartEl.value)
  }
})
</script>
