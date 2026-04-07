<template>
  <main class="flex min-h-screen w-full flex-col gap-3 px-3 py-3 md:px-4 md:py-4 lg:px-5 lg:py-4">
    <section class="panel rounded-2xl p-4">
      <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p class="text-xs uppercase tracking-[0.3em] text-teal-600/80">Well Monitoring</p>
          <h1 class="mt-1 text-2xl font-semibold text-slate-900">Well Time Series Dashboard</h1>
          <p class="mt-1 max-w-3xl text-sm text-slate-600">
            One analytical chart with hierarchical event tracks below it and interval inspection on the right.
          </p>
        </div>

        <div class="rounded-xl border border-slate-200 bg-white px-3 py-2 text-right">
          <div class="text-xs uppercase tracking-[0.25em] text-slate-500">Backend</div>
          <div class="mt-1 text-sm text-slate-700">{{ apiBaseLabel }}</div>
        </div>
      </div>
    </section>

    <section class="grid min-h-0 flex-1 gap-3 xl:grid-cols-[260px_minmax(0,1fr)]">
      <aside class="panel rounded-2xl p-4">
        <div class="space-y-4">
          <div>
            <h2 class="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Controls</h2>
          </div>

          <div>
            <label class="mb-2 block text-sm text-slate-700">Well</label>
            <n-select v-model:value="selectedWell" :options="wellOptions" />
          </div>

          <div>
            <label class="mb-2 block text-sm text-slate-700">Date Range</label>
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

          <div class="border-t border-slate-200 pt-3">
            <div class="mb-3 text-sm font-medium text-slate-700">Visible Series</div>
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

      <section class="grid gap-3 xl:grid-cols-[minmax(0,1fr)_270px]">
        <div class="panel rounded-2xl p-4">
          <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div class="flex items-center gap-2">
              <span class="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Mode</span>
              <div class="inline-flex rounded-lg border border-slate-200 bg-slate-100 p-1">
                <button
                  class="rounded-md px-3 py-1.5 text-sm transition"
                  :class="interactionMode === 'navigate' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'"
                  @click="interactionMode = 'navigate'"
                >
                  Navigate
                </button>
                <button
                  class="rounded-md px-3 py-1.5 text-sm transition"
                  :class="interactionMode === 'annotate' ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-600 hover:text-slate-900'"
                  @click="interactionMode = 'annotate'"
                >
                  Annotate
                </button>
              </div>
            </div>

            <div class="text-xs text-slate-500">
              {{ interactionMode === 'navigate' ? 'Zoom, pan, and inspect' : 'Drag to select an interval' }}
            </div>
          </div>

          <div class="mb-3 flex items-center justify-between gap-4">
            <div>
              <h2 class="text-xl font-semibold text-slate-900">Integrated Chart</h2>
              <p class="mt-1 text-sm text-slate-600">
                Main time series on top, hierarchical event tracks below, with separate navigation and annotation modes.
              </p>
            </div>
            <div class="text-right text-xs uppercase tracking-[0.2em] text-slate-500">
              {{ chartData.length }} points
            </div>
          </div>

          <div
            v-if="errorMessage"
            class="mb-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
          >
            {{ errorMessage }}
          </div>

          <div
            v-if="loading"
            class="flex h-[820px] items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50 text-slate-500"
          >
            Loading data from the backend...
          </div>
          <div v-else class="space-y-4">
            <TimeSeriesChart
              ref="chartRef"
              :data="chartData"
              :active-series="activeSeries"
              :selected-interval="selectedInterval"
              :event-tracks="eventTracks"
              :interaction-mode="interactionMode"
              :saved-annotations="savedEpisodes"
              :selected-annotation-id="editingAnnotationId"
              :visible-date-range="visibleDateRange"
              @interval-selected="handleIntervalSelected"
              @annotation-clicked="handleAnnotationClicked"
              @visible-range-changed="handleVisibleRangeChanged"
              @background-clicked="handleChartBackgroundClicked"
            />
            <div
              v-if="!chartData.length"
              class="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-3 py-2 text-sm text-slate-500"
            >
              No data available for the selected well and date range.
            </div>
          </div>
        </div>

        <aside class="panel rounded-2xl p-4">
          <div class="flex items-start justify-between gap-2">
            <div>
              <h2 class="text-base font-semibold text-slate-900">{{ annotationPanelTitle }}</h2>
              <p class="mt-1 text-sm text-slate-600">
                In Annotate mode, drag with the left mouse button to select a time interval for labeling.
              </p>
            </div>
          </div>

            <div class="mt-4 rounded-xl border border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-600">
            <div class="font-semibold uppercase tracking-[0.2em] text-slate-500">Debug</div>
            <div class="mt-2 space-y-1">
              <div>mode: {{ interactionMode }}</div>
              <div>selected start: {{ selectedInterval?.startDate ?? '-' }}</div>
              <div>selected end: {{ selectedInterval?.endDate ?? '-' }}</div>
              <div>selected duration: {{ selectedInterval?.durationDays ?? '-' }}</div>
              <div>dirty draft: {{ hasUnsavedChanges ? 'yes' : 'no' }}</div>
              <div>draft event type: {{ episodeForm.episodeType }}</div>
              <div>draft root cause: {{ episodeForm.rootCause }}</div>
              <div>total saved annotations: {{ savedEpisodes.length }}</div>
            </div>
          </div>

          <div
            v-if="selectedInterval"
            class="mt-4 space-y-3 rounded-xl border border-teal-200 bg-teal-50/80 p-3"
          >
            <div>
              <div class="text-xs uppercase tracking-[0.2em] text-slate-500">Start Date</div>
              <div class="mt-1 text-sm font-medium text-slate-900">{{ selectedInterval.startDate }}</div>
            </div>
            <div>
              <div class="text-xs uppercase tracking-[0.2em] text-slate-500">End Date</div>
              <div class="mt-1 text-sm font-medium text-slate-900">{{ selectedInterval.endDate }}</div>
            </div>
            <div>
              <div class="text-xs uppercase tracking-[0.2em] text-slate-500">Duration</div>
              <div class="mt-1 text-sm font-medium text-slate-900">{{ selectedInterval.durationDays }} days</div>
            </div>
          </div>

          <div v-if="selectedInterval" class="mt-4 space-y-3 rounded-xl border border-slate-200 bg-white p-3">
            <div>
              <label class="mb-1 block text-xs uppercase tracking-[0.2em] text-slate-500">Event Type</label>
              <div class="flex items-start gap-2">
                <n-select v-model:value="episodeForm.episodeType" size="small" :options="episodeTypeOptions" class="min-w-0 flex-1" />
                <n-button type="primary" size="small" @click="saveEvent">Save Event</n-button>
              </div>
            </div>

            <div>
              <label class="mb-1 block text-xs uppercase tracking-[0.2em] text-slate-500">Root Cause</label>
              <div class="flex items-start gap-2">
                <n-select v-model:value="episodeForm.rootCause" size="small" :options="rootCauseOptions" class="min-w-0 flex-1" />
                <n-button type="primary" secondary size="small" @click="saveRootCause">Save Root Cause</n-button>
              </div>
            </div>

            <div>
              <label class="mb-1 block text-xs uppercase tracking-[0.2em] text-slate-500">Confidence</label>
              <n-slider v-model:value="episodeForm.confidence" :step="0.01" :min="0" :max="1" />
              <div class="mt-1 text-xs text-slate-500">{{ episodeForm.confidence.toFixed(2) }}</div>
            </div>

            <div>
              <label class="mb-1 block text-xs uppercase tracking-[0.2em] text-slate-500">Comment</label>
              <n-input
                v-model:value="episodeForm.comment"
                type="textarea"
                size="small"
                placeholder="Add a short annotation"
                :autosize="{ minRows: 3, maxRows: 5 }"
              />
            </div>

            <div class="flex flex-col gap-2">
              <n-button v-if="isEditMode" type="error" secondary @click="deleteAnnotation">Delete</n-button>
              <n-button secondary @click="clearSelection">Clear selection</n-button>
              <n-button quaternary @click="zoomToSelection">Zoom to selection</n-button>
              <n-button quaternary @click="resetZoom">Reset zoom</n-button>
            </div>
          </div>

          <div
            v-else
            class="mt-4 rounded-xl border border-dashed border-slate-300 bg-slate-50 px-3 py-4 text-sm text-slate-500"
          >
            No interval selected yet. Switch to Annotate mode and drag across the chart to choose a time window.
          </div>

          <div class="mt-4 rounded-xl border border-slate-200 bg-white px-3 py-3">
            <div class="flex items-center justify-between gap-2">
              <div class="text-xs uppercase tracking-[0.2em] text-slate-500">Saved Events</div>
              <div class="text-xs text-slate-400">{{ savedEpisodes.length }}</div>
            </div>
            <div v-if="savedEpisodes.length" class="mt-3 space-y-2">
              <button
                v-for="episode in savedEpisodes"
                :key="episode.id"
                class="w-full rounded-lg border px-2.5 py-2 text-left transition"
                :class="episode.id === editingAnnotationId ? 'border-slate-900 bg-slate-100' : 'border-slate-200 bg-slate-50 hover:bg-slate-100'"
                @click="openAnnotationForEdit(episode.id)"
              >
                <div class="text-xs font-medium text-slate-800">{{ episode.startDate }} -> {{ episode.endDate }}</div>
                <div class="mt-1 text-xs text-slate-500">
                  {{ episode.annotationKind === 'event' ? `Event: ${episode.eventType}` : `Root cause: ${episode.rootCause}` }}
                </div>
              </button>
            </div>
            <div v-else class="mt-2 text-sm text-slate-500">
              Saved interval annotations will appear here.
            </div>
          </div>
        </aside>
      </section>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { NButton, NCheckbox, NCheckboxGroup, NDatePicker, NInput, NSelect, NSlider, useMessage } from 'naive-ui'
import TimeSeriesChart from '@/components/TimeSeriesChart.vue'
import { fetchWellTimeseries } from '@/services/api'
import { generateMockEventTracks } from '@/services/mockEventTracks'
import type {
  AnnotationKind,
  EpisodeFormState,
  EpisodeType,
  InteractionMode,
  RootCause,
  SavedAnnotation,
  SavedEventAnnotation,
  SavedRootCauseAnnotation,
  SelectedInterval,
  SeriesKey,
  TimeSeriesPoint,
  VisibleDateRange
} from '@/types/timeseries'

const message = useMessage()
const apiBaseLabel = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
const chartRef = ref<InstanceType<typeof TimeSeriesChart> | null>(null)

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

const episodeTypeOptions: { label: string; value: EpisodeType }[] = [
  { label: 'decline', value: 'decline' },
  { label: 'instability', value: 'instability' },
  { label: 'water_cut_growth', value: 'water_cut_growth' },
  { label: 'downtime', value: 'downtime' },
  { label: 'recovery', value: 'recovery' },
  { label: 'regime_change', value: 'regime_change' },
  { label: 'post_intervention', value: 'post_intervention' },
  { label: 'unknown', value: 'unknown' }
]

const rootCauseOptions: { label: string; value: RootCause }[] = [
  { label: 'esp_degradation', value: 'esp_degradation' },
  { label: 'water_breakthrough', value: 'water_breakthrough' },
  { label: 'unstable_operation', value: 'unstable_operation' },
  { label: 'downtime_vsp', value: 'downtime_vsp' },
  { label: 'opz_effect', value: 'opz_effect' },
  { label: 'esp_replacement', value: 'esp_replacement' },
  { label: 'telemetry_issue', value: 'telemetry_issue' },
  { label: 'unknown', value: 'unknown' }
]

function createDefaultEpisodeForm(): EpisodeFormState {
  return {
    episodeType: 'unknown',
    rootCause: 'unknown',
    confidence: 0.5,
    comment: ''
  }
}

const selectedWell = ref('WELL-101')
const dateRange = ref<[number, number] | null>(null)
const activeSeries = ref<SeriesKey[]>(seriesOptions.map((series) => series.value))
const chartData = ref<TimeSeriesPoint[]>([])
const selectedInterval = ref<SelectedInterval | null>(null)
const visibleDateRange = ref<VisibleDateRange | null>(null)
const interactionMode = ref<InteractionMode>('navigate')
const episodeForm = ref<EpisodeFormState>(createDefaultEpisodeForm())
const savedEpisodes = ref<SavedAnnotation[]>([])
const editingAnnotationId = ref<string | null>(null)
const editingAnnotationKind = ref<AnnotationKind | null>(null)
const loading = ref(false)
const errorMessage = ref('')

const eventTracks = computed(() => generateMockEventTracks(chartData.value))
const isEditMode = computed(() => editingAnnotationId.value !== null)
const annotationPanelTitle = computed(() => {
  if (editingAnnotationKind.value === 'event') {
    return 'Edit Event annotation'
  }

  if (editingAnnotationKind.value === 'rootCause') {
    return 'Edit Root Cause annotation'
  }

  return 'Create annotation'
})
const hasUnsavedChanges = computed(() => draftHasUnsavedChanges())

function toIsoDate(timestamp: number | null | undefined): string | undefined {
  if (!timestamp) {
    return undefined
  }

  return new Date(timestamp).toISOString().slice(0, 10)
}

function loadEpisodeIntoDraft(episode: SavedAnnotation) {
  selectedInterval.value = {
    startDate: episode.startDate,
    endDate: episode.endDate,
    durationDays: episode.durationDays
  }
  episodeForm.value = {
    episodeType: episode.annotationKind === 'event' ? episode.eventType : 'unknown',
    rootCause: episode.annotationKind === 'rootCause' ? episode.rootCause : 'unknown',
    confidence: episode.confidence,
    comment: episode.comment
  }
  editingAnnotationId.value = episode.id
  editingAnnotationKind.value = episode.annotationKind
}

function getFullDateRange(data: TimeSeriesPoint[]): VisibleDateRange | null {
  const startDate = data[0]?.date
  const endDate = data[data.length - 1]?.date

  if (!startDate || !endDate) {
    return null
  }

  return { startDate, endDate }
}

function createAnnotationId(kind: AnnotationKind): string {
  return `${kind}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function toTimestamp(value: string): number {
  return new Date(value).getTime()
}

function shiftIsoDate(value: string, dayDelta: number): string {
  const date = new Date(value)
  date.setDate(date.getDate() + dayDelta)
  return date.toISOString().slice(0, 10)
}

function buildInterval(startDate: string, endDate: string): SelectedInterval {
  const normalizedStart = startDate <= endDate ? startDate : endDate
  const normalizedEnd = startDate <= endDate ? endDate : startDate

  return {
    startDate: normalizedStart,
    endDate: normalizedEnd,
    durationDays: Math.max(1, Math.floor((toTimestamp(normalizedEnd) - toTimestamp(normalizedStart)) / 86400000) + 1)
  }
}

function getAnnotationCategory(annotation: SavedAnnotation): string {
  return annotation.annotationKind === 'event' ? annotation.eventType : annotation.rootCause
}

function annotationsOverlap(left: SelectedInterval, right: SelectedInterval): boolean {
  return toTimestamp(left.startDate) <= toTimestamp(right.endDate) && toTimestamp(right.startDate) <= toTimestamp(left.endDate)
}

function createSplitAnnotation(
  annotation: SavedAnnotation,
  startDate: string,
  endDate: string,
  idOverride?: string
): SavedAnnotation {
  const interval = buildInterval(startDate, endDate)

  if (annotation.annotationKind === 'event') {
    return {
      id: idOverride ?? annotation.id,
      annotationKind: 'event',
      eventType: annotation.eventType,
      confidence: annotation.confidence,
      comment: annotation.comment,
      ...interval
    }
  }

  return {
    id: idOverride ?? annotation.id,
    annotationKind: 'rootCause',
    rootCause: annotation.rootCause,
    confidence: annotation.confidence,
    comment: annotation.comment,
    ...interval
  }
}

function resolveLayerOverlap(
  existingAnnotations: SavedAnnotation[],
  incomingAnnotation: SavedAnnotation
): SavedAnnotation[] {
  const preservedSegments: SavedAnnotation[] = []

  existingAnnotations.forEach((annotation) => {
    if (annotation.annotationKind !== incomingAnnotation.annotationKind || !annotationsOverlap(annotation, incomingAnnotation)) {
      preservedSegments.push(annotation)
      return
    }

    const hasLeftSegment = toTimestamp(annotation.startDate) < toTimestamp(incomingAnnotation.startDate)
    const hasRightSegment = toTimestamp(annotation.endDate) > toTimestamp(incomingAnnotation.endDate)

    if (hasLeftSegment) {
      preservedSegments.push(
        createSplitAnnotation(annotation, annotation.startDate, shiftIsoDate(incomingAnnotation.startDate, -1), annotation.id)
      )
    }

    if (hasRightSegment) {
      preservedSegments.push(
        createSplitAnnotation(
          annotation,
          shiftIsoDate(incomingAnnotation.endDate, 1),
          annotation.endDate,
          hasLeftSegment ? createAnnotationId(annotation.annotationKind) : annotation.id
        )
      )
    }
  })

  return preservedSegments
}

function mergeAdjacentAnnotations(
  annotations: SavedAnnotation[],
  preferredAnnotationId: string
): SavedAnnotation[] {
  const sortedAnnotations = [...annotations].sort(
    (left, right) => toTimestamp(left.startDate) - toTimestamp(right.startDate) || toTimestamp(left.endDate) - toTimestamp(right.endDate)
  )

  return sortedAnnotations.reduce<SavedAnnotation[]>((mergedAnnotations, annotation) => {
    const previous = mergedAnnotations[mergedAnnotations.length - 1]

    if (
      previous &&
      previous.annotationKind === annotation.annotationKind &&
      getAnnotationCategory(previous) === getAnnotationCategory(annotation) &&
      toTimestamp(annotation.startDate) <= toTimestamp(previous.endDate) + 86400000
    ) {
      const preferredAnnotation =
        previous.id === preferredAnnotationId ? previous : annotation.id === preferredAnnotationId ? annotation : previous
      const mergedInterval = buildInterval(previous.startDate, annotation.endDate)
      const mergedAnnotation =
        preferredAnnotation.annotationKind === 'event'
          ? {
              id: preferredAnnotation.id,
              annotationKind: 'event' as const,
              eventType: preferredAnnotation.eventType,
              confidence: preferredAnnotation.confidence,
              comment: preferredAnnotation.comment,
              ...mergedInterval
            }
          : {
              id: preferredAnnotation.id,
              annotationKind: 'rootCause' as const,
              rootCause: preferredAnnotation.rootCause,
              confidence: preferredAnnotation.confidence,
              comment: preferredAnnotation.comment,
              ...mergedInterval
            }

      mergedAnnotations[mergedAnnotations.length - 1] = mergedAnnotation
      return mergedAnnotations
    }

    mergedAnnotations.push(annotation)
    return mergedAnnotations
  }, [])
}

function normalizeAnnotationsForLayer(incomingAnnotation: SavedAnnotation): void {
  const otherLayers = savedEpisodes.value.filter((item) => item.annotationKind !== incomingAnnotation.annotationKind)
  const sameLayer = savedEpisodes.value.filter((item) => item.annotationKind === incomingAnnotation.annotationKind && item.id !== incomingAnnotation.id)
  const trimmedLayer = resolveLayerOverlap(sameLayer, incomingAnnotation)
  const normalizedLayer = mergeAdjacentAnnotations([...trimmedLayer, incomingAnnotation], incomingAnnotation.id)

  savedEpisodes.value = [...otherLayers, ...normalizedLayer].sort(
    (left, right) => toTimestamp(right.startDate) - toTimestamp(left.startDate)
  )
}

function draftHasUnsavedChanges(): boolean {
  if (!selectedInterval.value && !editingAnnotationId.value) {
    return false
  }

  if (!editingAnnotationId.value || !editingAnnotationKind.value) {
    return selectedInterval.value !== null
  }

  const existingAnnotation = savedEpisodes.value.find((item) => item.id === editingAnnotationId.value)
  if (!existingAnnotation) {
    return selectedInterval.value !== null
  }

  const intervalChanged =
    existingAnnotation.startDate !== selectedInterval.value?.startDate ||
    existingAnnotation.endDate !== selectedInterval.value?.endDate ||
    existingAnnotation.durationDays !== selectedInterval.value?.durationDays

  if (existingAnnotation.annotationKind === 'event') {
    return (
      intervalChanged ||
      existingAnnotation.eventType !== episodeForm.value.episodeType ||
      existingAnnotation.confidence !== episodeForm.value.confidence ||
      existingAnnotation.comment !== episodeForm.value.comment
    )
  }

  return (
    intervalChanged ||
    existingAnnotation.rootCause !== episodeForm.value.rootCause ||
    existingAnnotation.confidence !== episodeForm.value.confidence ||
    existingAnnotation.comment !== episodeForm.value.comment
  )
}

async function loadData() {
  loading.value = true
  errorMessage.value = ''
  selectedInterval.value = null
  editingAnnotationId.value = null
  editingAnnotationKind.value = null
  episodeForm.value = createDefaultEpisodeForm()

  try {
    const [start, end] = dateRange.value ?? []
    const data = await fetchWellTimeseries(selectedWell.value, {
      date_from: toIsoDate(start),
      date_to: toIsoDate(end)
    })

    chartData.value = data
    visibleDateRange.value = getFullDateRange(data)
  } catch {
    chartData.value = []
    visibleDateRange.value = null
    errorMessage.value = 'Failed to load time series data. Make sure the backend is running on http://localhost:8000.'
    message.error(errorMessage.value)
  } finally {
    loading.value = false
  }
}

function handleIntervalSelected(value: SelectedInterval | null) {
  selectedInterval.value = value

  if (!value) {
    editingAnnotationId.value = null
    editingAnnotationKind.value = null
    return
  }

  if (!editingAnnotationId.value) {
    episodeForm.value = createDefaultEpisodeForm()
  }
}

function handleAnnotationClicked(payload: { annotationId: string }) {
  const episode = savedEpisodes.value.find((item) => item.id === payload.annotationId)
  if (!episode) {
    return
  }

  loadEpisodeIntoDraft(episode)
}

function handleVisibleRangeChanged(value: VisibleDateRange | null) {
  visibleDateRange.value = value
}

function openAnnotationForEdit(annotationId: string) {
  const episode = savedEpisodes.value.find((item) => item.id === annotationId)
  if (!episode) {
    return
  }

  loadEpisodeIntoDraft(episode)
}

function clearSelection() {
  if (!selectedInterval.value && !editingAnnotationId.value) {
    return
  }

  if (hasUnsavedChanges.value) {
    const confirmed = window.confirm('Clear the current selection and draft annotation?')
    if (!confirmed) {
      return
    }
  }

  chartRef.value?.clearSelection()
  selectedInterval.value = null
  editingAnnotationId.value = null
  editingAnnotationKind.value = null
  episodeForm.value = createDefaultEpisodeForm()
}

function zoomToSelection() {
  chartRef.value?.zoomToSelection()
}

function resetZoom() {
  chartRef.value?.resetZoom()
}

function handleChartBackgroundClicked() {
  clearSelection()
}

function saveEvent() {
  if (!selectedInterval.value) {
    message.error('Select an interval before saving an event.')
    return
  }

  if (!episodeForm.value.episodeType) {
    message.error('Choose an event type.')
    return
  }

  if (editingAnnotationId.value && editingAnnotationKind.value === 'event') {
    const index = savedEpisodes.value.findIndex((item) => item.id === editingAnnotationId.value)
    if (index >= 0) {
      const existingAnnotation = savedEpisodes.value[index]
      if (!existingAnnotation || existingAnnotation.annotationKind !== 'event') {
        return
      }

      const updatedAnnotation: SavedEventAnnotation = {
        ...existingAnnotation,
        ...selectedInterval.value,
        eventType: episodeForm.value.episodeType,
        confidence: episodeForm.value.confidence,
        comment: episodeForm.value.comment
      }
      normalizeAnnotationsForLayer(updatedAnnotation)
      message.success('Event annotation updated.')
      return
    }
  }

  const newAnnotation: SavedEventAnnotation = {
    id: createAnnotationId('event'),
    ...selectedInterval.value,
    annotationKind: 'event',
    eventType: episodeForm.value.episodeType,
    confidence: episodeForm.value.confidence,
    comment: episodeForm.value.comment
  }

  normalizeAnnotationsForLayer(newAnnotation)
  editingAnnotationId.value = newAnnotation.id
  editingAnnotationKind.value = 'event'
  message.success('Event annotation saved.')
}

function saveRootCause() {
  if (!selectedInterval.value) {
    message.error('Select an interval before saving a root cause.')
    return
  }

  if (!episodeForm.value.rootCause) {
    message.error('Choose a root cause.')
    return
  }

  if (editingAnnotationId.value && editingAnnotationKind.value === 'rootCause') {
    const index = savedEpisodes.value.findIndex((item) => item.id === editingAnnotationId.value)
    if (index >= 0) {
      const existingAnnotation = savedEpisodes.value[index]
      if (!existingAnnotation || existingAnnotation.annotationKind !== 'rootCause') {
        return
      }

      const updatedAnnotation: SavedRootCauseAnnotation = {
        ...existingAnnotation,
        ...selectedInterval.value,
        rootCause: episodeForm.value.rootCause,
        confidence: episodeForm.value.confidence,
        comment: episodeForm.value.comment
      }
      normalizeAnnotationsForLayer(updatedAnnotation)
      message.success('Root cause annotation updated.')
      return
    }
  }

  const newAnnotation: SavedRootCauseAnnotation = {
    id: createAnnotationId('rootCause'),
    ...selectedInterval.value,
    annotationKind: 'rootCause',
    rootCause: episodeForm.value.rootCause,
    confidence: episodeForm.value.confidence,
    comment: episodeForm.value.comment
  }

  normalizeAnnotationsForLayer(newAnnotation)
  editingAnnotationId.value = newAnnotation.id
  editingAnnotationKind.value = 'rootCause'
  message.success('Root cause annotation saved.')
}

function deleteAnnotation() {
  if (!editingAnnotationId.value) {
    return
  }

  const confirmed = window.confirm('Delete this annotation?')
  if (!confirmed) {
    return
  }

  savedEpisodes.value = savedEpisodes.value.filter((item) => item.id !== editingAnnotationId.value)
  editingAnnotationId.value = null
  editingAnnotationKind.value = null
  selectedInterval.value = null
  episodeForm.value = createDefaultEpisodeForm()
  message.success('Annotation deleted.')
}

onMounted(() => {
  void loadData()
})
</script>
