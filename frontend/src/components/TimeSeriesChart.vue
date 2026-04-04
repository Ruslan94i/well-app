<template>
  <div ref="chartEl" class="h-[540px] w-full"></div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Plotly from 'plotly.js-dist-min'
import type { SeriesKey, TimeSeriesPoint } from '@/types/timeseries'

const props = defineProps<{
  data: TimeSeriesPoint[]
  activeSeries: SeriesKey[]
}>()

const chartEl = ref<HTMLDivElement | null>(null)

const seriesConfig: Record<
  SeriesKey,
  { label: string; color: string; axis: string; width?: number; dash?: 'solid' | 'dot' }
> = {
  qliq: { label: 'QLIQ', color: '#22c55e', axis: 'y', width: 2.8 },
  qoil: { label: 'QOIL', color: '#f59e0b', axis: 'y', width: 2.8 },
  qliq_vfm: { label: 'QLIQ VFM', color: '#38bdf8', axis: 'y', width: 2.2, dash: 'dot' },
  water_cut: { label: 'Water Cut', color: '#ef4444', axis: 'y2', width: 2.4 },
  intake_pressure: { label: 'Intake Pressure', color: '#a78bfa', axis: 'y3', width: 2.2 },
  esp_frequency: { label: 'ESP Frequency', color: '#14b8a6', axis: 'y4', width: 2.2 },
  load: { label: 'Load', color: '#e879f9', axis: 'y5', width: 2.2 }
}

function renderChart() {
  if (!chartEl.value) {
    return
  }

  const x = props.data.map((item) => item.date)
  const traces = props.activeSeries.map((seriesKey) => {
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

  const layout = {
    paper_bgcolor: 'rgba(0,0,0,0)',
    plot_bgcolor: '#07111f',
    font: { color: '#cbd5e1', family: 'Segoe UI, sans-serif' },
    margin: { l: 68, r: 120, t: 32, b: 52 },
    legend: {
      orientation: 'h',
      yanchor: 'bottom',
      y: 1.02,
      xanchor: 'left',
      x: 0
    },
    hovermode: 'x unified',
    xaxis: {
      title: 'Date',
      gridcolor: 'rgba(148,163,184,0.10)',
      linecolor: 'rgba(148,163,184,0.25)',
      zeroline: false
    },
    yaxis: {
      title: 'Rates',
      titlefont: { color: '#f8fafc' },
      tickfont: { color: '#f8fafc' },
      gridcolor: 'rgba(148,163,184,0.12)',
      zeroline: false
    },
    yaxis2: {
      title: 'Water Cut, %',
      overlaying: 'y',
      side: 'right',
      position: 0.88,
      titlefont: { color: '#ef4444' },
      tickfont: { color: '#ef4444' },
      showgrid: false
    },
    yaxis3: {
      title: 'Pressure',
      overlaying: 'y',
      side: 'right',
      position: 0.93,
      titlefont: { color: '#a78bfa' },
      tickfont: { color: '#a78bfa' },
      showgrid: false
    },
    yaxis4: {
      title: 'Hz',
      overlaying: 'y',
      side: 'right',
      position: 0.97,
      titlefont: { color: '#14b8a6' },
      tickfont: { color: '#14b8a6' },
      showgrid: false
    },
    yaxis5: {
      title: 'Load',
      anchor: 'free',
      overlaying: 'y',
      side: 'left',
      position: 0.0,
      titlefont: { color: '#e879f9' },
      tickfont: { color: '#e879f9' },
      showgrid: false
    }
  }

  const config = {
    responsive: true,
    displaylogo: false,
    modeBarButtonsToRemove: ['lasso2d', 'select2d']
  }

  Plotly.react(chartEl.value, traces, layout, config)
}

onMounted(renderChart)

watch(
  () => [props.data, props.activeSeries],
  () => {
    renderChart()
  },
  { deep: true }
)

onBeforeUnmount(() => {
  if (chartEl.value) {
    Plotly.purge(chartEl.value)
  }
})
</script>

