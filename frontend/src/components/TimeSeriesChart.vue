<template>
  <div ref="chartEl" class="h-[720px] w-full"></div>
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
  annotationId: string
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
  qliq: { label: 'QLIQ', color: '#111111', axis: 'y', width: 2.8 },
  qoil: { label: 'QOIL', color: '#8b5e3c', axis: 'y', width: 2.8 },
  qliq_vfm: { label: 'QLIQ VFM', color: '#111111', axis: 'y', width: 2, dash: 'dot' },
  water_cut: { label: 'Water Cut', color: '#7dd3fc', axis: 'y2', width: 2.2 },
  intake_pressure: { label: 'Intake Pressure', color: '#dc2626', axis: 'y3', width: 1.4 },
  esp_frequency: { label: 'ESP Frequency', color: '#2563eb', axis: 'y4', width: 1.4 },
  load: { label: 'Load', color: '#16a34a', axis: 'y5', width: 1.4 }
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

function getEspColor(espId: string): string {
  const palette = ['#9ca3af', '#64748b', '#94a3b8', '#475569', '#7c8aa0', '#8b9db2']
  const hash = espId.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0)
  return palette[hash % palette.length] ?? '#64748b'
}

function getEspSegmentLabel(startDate: string, endDate: string, espId: string): string {
  const durationDays = calculateDurationDays(startDate, endDate)
  return durationDays >= 24 ? espId : ''
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

function buildStableRange(values: number[]): [number, number] {
  if (values.length === 0) {
    return [0, 1]
  }

  const min = Math.min(...values)
  const max = Math.max(...values)

  if (min === max) {
    const pad = Math.max(Math.abs(min) * 0.1, 1)
    return [min - pad, max + pad]
  }

  const pad = Math.max((max - min) * 0.08, 0.5)
  return [min - pad, max + pad]
}

function getSeriesValues(key: SeriesKey): number[] {
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
  const shapes: Array<Record<string, unknown>> = props.eventTracks.opzEvents.map((item) => ({
    type: 'line',
    xref: 'x',
    yref: 'paper',
    x0: item.date,
    x1: item.date,
    y0: 0.37,
    y1: 1,
    line: {
      color: 'rgba(217,119,6,0.48)',
      width: 1.2,
      dash: 'dot'
    },
    layer: 'below'
  }))

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
    fillcolor: 'rgba(15,118,110,0.14)',
    line: {
      color: 'rgba(15,118,110,0.65)',
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
    ...getSeriesValues('qliq_vfm')
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
            name: 'OPZ',
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
              '<b>OPZ</b><br>%{customdata.date}<br>%{customdata.operationType}<br>%{customdata.comment}<extra></extra>'
          }
        ]
      : []

  const selectionHelper = {
    x,
    y: x.map(() => baseRange[0]),
    type: 'scatter',
    mode: 'markers',
    name: 'Selection Helper',
    yaxis: 'y',
    showlegend: false,
    hoverinfo: 'skip',
    marker: {
      size: 18,
      opacity: 0
    }
  }

  return [...visibleSeries, ...opzTrace, selectionHelper]
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
        annotationKind: item.annotationKind,
        startDate: item.startDate,
        endDate: item.endDate,
        durationDays: item.durationDays,
        categoryLabel: item.annotationKind === 'event' ? item.eventType : item.rootCause
      })),
      hovertemplate:
        '<b>%{customdata.annotationKind}</b>: %{customdata.categoryLabel}<br>%{customdata.startDate} -> %{customdata.endDate}<br>' +
        'Duration: %{customdata.durationDays} days<extra></extra>'
    }
  ]
}

function buildTrackTraces() {
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
                color: props.eventTracks.installedEspPeriods.map(() => 'rgba(255,255,255,0.8)'),
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
              size: 10,
              color: '#f8fafc'
            },
            cliponaxis: false,
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
            width: 0.94,
            marker: {
              color: props.eventTracks.dailyCauses.map((item) => item.color),
              opacity: 0.75
            },
            yaxis: 'y7',
            showlegend: false,
            customdata: props.eventTracks.dailyCauses.map((item) => item.label),
            hovertemplate: '%{base}<br>%{customdata}<extra></extra>'
          }
        ]
      : []

  return [
    ...espInstallationTrace,
    ...dailyCauseTraces,
    ...buildSavedAnnotationTrace('y8', 'event'),
    ...buildSavedAnnotationTrace('y9', 'rootCause')
  ]
}

function getSavedAnnotationTrackRange(annotationKind: 'event' | 'rootCause'): [number, number] {
  const laneCount = buildAnnotationLaneAssignment(
    props.savedAnnotations.filter((item) => item.annotationKind === annotationKind)
  ).laneCount
  return [0, Math.max(2, laneCount + 1.6)]
}

function buildAnnotations() {
  const annotations: Array<Record<string, unknown>> = [
    {
      xref: 'paper',
      yref: 'paper',
      x: 0,
      y: 0.345,
      xanchor: 'left',
      yanchor: 'middle',
      text: '<b>Installed ESP</b>',
      showarrow: false,
      font: { size: 12, color: '#64748b' }
    },
    {
      xref: 'paper',
      yref: 'paper',
      x: 0,
      y: 0.26,
      xanchor: 'left',
      yanchor: 'middle',
      text: '<b>Daily causes</b>',
      showarrow: false,
      font: { size: 12, color: '#64748b' }
    },
    {
      xref: 'paper',
      yref: 'paper',
      x: 0,
      y: 0.165,
      xanchor: 'left',
      yanchor: 'middle',
      text: '<b>Event Type</b>',
      showarrow: false,
      font: { size: 12, color: '#64748b' }
    },
    {
      xref: 'paper',
      yref: 'paper',
      x: 0,
      y: 0.075,
      xanchor: 'left',
      yanchor: 'middle',
      text: '<b>Root Cause</b>',
      showarrow: false,
      font: { size: 12, color: '#64748b' }
    }
  ]

  if (props.data.length === 0) {
    annotations.push({
      xref: 'paper',
      yref: 'paper',
      x: 0.5,
      y: 0.68,
      xanchor: 'center',
      yanchor: 'middle',
      text: 'No time series data loaded',
      showarrow: false,
      font: { size: 16, color: '#64748b' }
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

  const firstDate = props.data[0]?.date
  const lastDate = props.data[props.data.length - 1]?.date

  const layout = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: '#ffffff',
    font: { color: '#334155', family: 'Segoe UI, sans-serif' },
    margin: { l: 78, r: 136, t: 36, b: 58 },
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
      x: 0
    },
    xaxis: {
      title: 'Date',
      type: 'date',
      range: props.visibleDateRange
        ? [props.visibleDateRange.startDate, props.visibleDateRange.endDate]
        : undefined,
      tickformat: '%Y-%m-%d',
      showgrid: true,
      gridcolor: 'rgba(148,163,184,0.18)',
      linecolor: 'rgba(148,163,184,0.45)',
      zeroline: false,
      rangeslider: { visible: false }
    },
    yaxis: {
      title: 'Qliq / Qoil',
      domain: [0.38, 1],
      range: buildStableRange([
        ...getSeriesValues('qliq'),
        ...getSeriesValues('qoil'),
        ...getSeriesValues('qliq_vfm')
      ]),
      autorange: false,
      fixedrange: true,
      titlefont: { color: '#334155', size: 11 },
      tickfont: { color: '#475569', size: 10 },
      tickformat: '.0f',
      nticks: 6,
      gridcolor: 'rgba(148,163,184,0.18)',
      zeroline: false
    },
    yaxis2: {
      title: 'Water cut',
      overlaying: 'y',
      side: 'right',
      position: 0.91,
      range: buildStableRange(getSeriesValues('water_cut')),
      autorange: false,
      fixedrange: true,
      titlefont: { color: '#475569', size: 11 },
      tickfont: { color: '#64748b', size: 10 },
      tickformat: '.0f',
      nticks: 5,
      showgrid: false
    },
    yaxis3: {
      title: 'Intake pressure',
      overlaying: 'y',
      side: 'right',
      position: 0.95,
      range: buildStableRange(getSeriesValues('intake_pressure')),
      autorange: false,
      fixedrange: true,
      titlefont: { color: '#475569', size: 11 },
      tickfont: { color: '#64748b', size: 10 },
      tickformat: '.0f',
      nticks: 5,
      showgrid: false
    },
    yaxis4: {
      title: 'ESP frequency',
      overlaying: 'y',
      side: 'right',
      position: 0.985,
      range: buildStableRange(getSeriesValues('esp_frequency')),
      autorange: false,
      fixedrange: true,
      titlefont: { color: '#475569', size: 11 },
      tickfont: { color: '#64748b', size: 10 },
      tickformat: '.1f',
      nticks: 4,
      showgrid: false
    },
    yaxis5: {
      title: 'Load',
      overlaying: 'y',
      side: 'left',
      anchor: 'free',
      position: 0,
      range: buildStableRange(getSeriesValues('load')),
      autorange: false,
      fixedrange: true,
      titlefont: { color: '#475569', size: 11 },
      tickfont: { color: '#64748b', size: 10 },
      tickformat: '.0f',
      nticks: 5,
      showgrid: false
    },
    yaxis6: {
      domain: [0.305, 0.36],
      range: [0, 1],
      fixedrange: true,
      showgrid: false,
      showticklabels: false,
      zeroline: false
    },
    yaxis7: {
      domain: [0.225, 0.275],
      range: [0, 1],
      fixedrange: true,
      showgrid: false,
      showticklabels: false,
      zeroline: false
    },
    yaxis8: {
      domain: [0.12, 0.195],
      range: getSavedAnnotationTrackRange('event'),
      fixedrange: true,
      showgrid: false,
      showticklabels: false,
      zeroline: false
    },
    yaxis9: {
      domain: [0.03, 0.095],
      range: getSavedAnnotationTrackRange('rootCause'),
      fixedrange: true,
      showgrid: false,
      showticklabels: false,
      zeroline: false
    },
    shapes: getSelectionShapes(),
    annotations: buildAnnotations()
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

    if (customdata?.annotationId) {
      emit('annotation-clicked', { annotationId: customdata.annotationId })
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
