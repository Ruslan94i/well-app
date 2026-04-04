<template>
  <main class="mx-auto flex min-h-screen max-w-7xl flex-col gap-6 px-4 py-6 md:px-6 lg:px-8">
    <section class="panel rounded-3xl p-6">
      <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p class="text-xs uppercase tracking-[0.3em] text-teal-400/80">Well Monitoring</p>
          <h1 class="mt-2 text-3xl font-semibold text-slate-50">Well Time Series Dashboard</h1>
          <p class="mt-2 max-w-2xl text-sm text-slate-400">
            Daily telemetry is loaded from the FastAPI backend and rendered as an interactive Plotly chart.
          </p>
        </div>

        <div class="rounded-2xl border border-slate-800 bg-slate-950/60 px-4 py-3 text-right">
          <div class="text-xs uppercase tracking-[0.25em] text-slate-500">Backend</div>
          <div class="mt-1 text-sm text-slate-200">{{ apiBaseLabel }}</div>
        </div>
      </div>
    </section>

    <section class="grid gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
      <aside class="panel rounded-3xl p-5">
        <div class="space-y-5">
          <div>
            <h2 class="text-sm font-semibold uppercase tracking-[0.2em] text-slate-400">Controls</h2>
          </div>

          <div>
            <label class="mb-2 block text-sm text-slate-300">Well</label>
            <n-select v-model:value="selectedWell" :options="wellOptions" />
          </div>

          <div>
            <label class="mb-2 block text-sm text-slate-300">Date Range</label>
            <n-date-picker
              v-model:value="dateRange"
              type="daterange"
              clearable
              class="w-full"
            />
          </div>

          <n-button type="primary" block :loading="loading" @click="loadData">
            Load Data
          </n-button>

          <div class="border-t border-slate-800 pt-4">
            <div class="mb-3 text-sm font-medium text-slate-300">Visible Series</div>
            <n-checkbox-group v-model:value="activeSeries">
              <div class="grid gap-2">
                <n-checkbox
                  v-for="series in seriesOptions"
                  :key="series.value"
                  :value="series.value"
                  :label="series.label"
                />
              </div>
            </n-checkbox-group>
          </div>
        </div>
      </aside>

      <section class="panel rounded-3xl p-5">
        <div class="mb-4 flex items-center justify-between gap-4">
          <div>
            <h2 class="text-xl font-semibold text-slate-50">Telemetry Chart</h2>
            <p class="mt-1 text-sm text-slate-400">
              Plotly chart backed by GET /api/wells/{well_id}/timeseries with zoom, hover, and legend toggles.
            </p>
          </div>
          <div class="text-right text-xs uppercase tracking-[0.2em] text-slate-500">
            {{ chartData.length }} points
          </div>
        </div>

        <div
          v-if="errorMessage"
          class="mb-4 rounded-2xl border border-red-900/60 bg-red-950/40 px-4 py-3 text-sm text-red-200"
        >
          {{ errorMessage }}
        </div>

        <div
          v-if="loading"
          class="flex h-[540px] items-center justify-center rounded-2xl border border-dashed border-slate-700 bg-slate-950/40 text-slate-400"
        >
          Loading data from the backend...
        </div>
        <div v-else-if="chartData.length">
          <TimeSeriesChart :data="chartData" :active-series="activeSeries" />
        </div>
        <div
          v-else
          class="flex h-[540px] items-center justify-center rounded-2xl border border-dashed border-slate-700 bg-slate-950/40 text-slate-500"
        >
          No data available for the selected well and date range.
        </div>
      </section>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { NButton, NCheckbox, NCheckboxGroup, NDatePicker, NSelect, useMessage } from 'naive-ui'
import TimeSeriesChart from '@/components/TimeSeriesChart.vue'
import { fetchWellTimeseries } from '@/services/api'
import type { SeriesKey, TimeSeriesPoint } from '@/types/timeseries'

const message = useMessage()
const apiBaseLabel = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

const wellOptions = [
  { label: 'WELL-101', value: 'WELL-101' },
  { label: 'WELL-202', value: 'WELL-202' },
  { label: 'WELL-307', value: 'WELL-307' }
]

const seriesOptions: { label: string; value: SeriesKey }[] = [
  { label: 'qliq', value: 'qliq' },
  { label: 'qoil', value: 'qoil' },
  { label: 'qliq_vfm', value: 'qliq_vfm' },
  { label: 'water_cut', value: 'water_cut' },
  { label: 'intake_pressure', value: 'intake_pressure' },
  { label: 'esp_frequency', value: 'esp_frequency' },
  { label: 'load', value: 'load' }
]

const selectedWell = ref('WELL-101')
const dateRange = ref<[number, number] | null>(null)
const activeSeries = ref<SeriesKey[]>(seriesOptions.map((series) => series.value))
const chartData = ref<TimeSeriesPoint[]>([])
const loading = ref(false)
const errorMessage = ref('')

function toIsoDate(timestamp: number | null | undefined): string | undefined {
  if (!timestamp) {
    return undefined
  }

  return new Date(timestamp).toISOString().slice(0, 10)
}

async function loadData() {
  loading.value = true
  errorMessage.value = ''

  try {
    const [start, end] = dateRange.value ?? []
    const data = await fetchWellTimeseries(selectedWell.value, {
      date_from: toIsoDate(start),
      date_to: toIsoDate(end)
    })

    chartData.value = data
  } catch {
    chartData.value = []
    errorMessage.value = 'Failed to load time series data. Make sure the backend is running on http://localhost:8000.'
    message.error(errorMessage.value)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadData()
})
</script>
