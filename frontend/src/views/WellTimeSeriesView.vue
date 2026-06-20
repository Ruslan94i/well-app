<template>
  <main class="flex min-h-screen w-full flex-col px-2 py-2 md:px-3 md:py-2 lg:px-3 lg:py-2">
    <section class="grid min-h-0 flex-1 gap-2 xl:grid-cols-[226px_minmax(0,1fr)]">
      <aside class="panel rounded-2xl p-3">
        <div class="space-y-4">
          <div>
            <h2 class="text-sm font-semibold uppercase tracking-[0.2em] text-slate-400">Параметры</h2>
          </div>

          <div>
            <label class="mb-2 block text-sm text-slate-300">Месторождение</label>
            <n-select
              v-model:value="navigationGroupId"
              :options="wellGroupOptions"
              clearable
              placeholder="Выберите группу"
            />
          </div>

          <div>
            <label class="mb-2 block text-sm text-slate-300">Скважина</label>
            <n-select v-model:value="selectedWell" :options="filteredWellOptions" />
          </div>

          <div>
            <label class="mb-2 block text-sm text-slate-300">Диапазон дат</label>
            <n-date-picker
              v-model:value="dateRange"
              type="daterange"
              clearable
              class="w-full"
            />
          </div>

          <n-button type="primary" block :loading="loading" @click="loadData">
            Загрузить данные
          </n-button>

          <div class="border-t border-slate-700 pt-3">
            <div class="mb-3 text-sm font-medium text-slate-300">Отображаемые параметры</div>
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

      <div class="space-y-3">
        <div class="panel rounded-2xl px-3 py-2">
          <div class="space-y-3">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div class="flex items-center gap-2">
                <span class="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Вкладка</span>
                <div class="inline-flex rounded-lg border border-slate-700 bg-slate-900/70 p-1">
                  <button
                    class="rounded-md px-3 py-1.5 text-sm transition"
                    :class="isInteractionMode('navigate') ? 'bg-slate-700 text-slate-100 shadow-sm' : 'text-slate-400 hover:text-slate-100'"
                    @click="interactionMode = 'navigate'"
                  >
                    Анализ скважинной динамики
                  </button>
                  <button
                    class="rounded-md px-3 py-1.5 text-sm transition"
                    :class="isInteractionMode('annotate') ? 'bg-slate-700 text-slate-100 shadow-sm' : 'text-slate-400 hover:text-slate-100'"
                    @click="interactionMode = 'annotate'"
                  >
                    Разметка
                  </button>
                  <button
                    class="rounded-md px-3 py-1.5 text-sm transition"
                    :class="isInteractionMode('modelTuning') ? 'bg-slate-700 text-slate-100 shadow-sm' : 'text-slate-400 hover:text-slate-100'"
                    @click="interactionMode = 'modelTuning'"
                  >
                    Настройка модели
                  </button>
                  <button
                    class="rounded-md px-3 py-1.5 text-sm transition"
                    :class="isInteractionMode('periodSummary') ? 'bg-slate-700 text-slate-100 shadow-sm' : 'text-slate-400 hover:text-slate-100'"
                    @click="interactionMode = 'periodSummary'"
                  >
                    Сводка периода
                  </button>
                </div>
              </div>

              <div class="text-xs text-slate-400">{{ interactionModeHint }}</div>
            </div>

            <div>
              <h1 class="text-lg font-semibold text-slate-100">{{ currentTabTitle }}</h1>
              <p class="mt-1 text-sm leading-6 text-slate-400">{{ currentTabDescription }}</p>
            </div>
          </div>
        </div>

      <section v-if="interactionMode === 'navigate' || interactionMode === 'annotate'" class="grid gap-2 xl:grid-cols-[minmax(0,1fr)_304px]">
        <div class="panel rounded-2xl p-2">
          <div
            v-if="errorMessage"
            class="mb-3 rounded-xl border border-red-500/40 bg-red-950/40 px-3 py-2 text-sm text-red-300"
          >
            {{ errorMessage }}
          </div>

          <div
            v-if="loading"
            class="flex h-[920px] items-center justify-center rounded-xl border border-dashed border-slate-700 bg-slate-900/50 text-slate-400"
          >
            Загрузка данных с backend...
          </div>
          <div v-else class="space-y-4">
            <div class="flex flex-wrap justify-end gap-1">
              <n-button
                secondary
                size="small"
                :loading="graphDataExporting"
                @click="downloadGraphDataExport"
              >
                Выгрузить все
              </n-button>
              <n-button
                secondary
                size="small"
                :loading="manualGraphDataExporting"
                @click="downloadManualGraphDataExport"
              >
                Выгрузить ручную
              </n-button>
              <n-button
                secondary
                size="small"
                :loading="wellGraphDataExporting"
                @click="downloadCurrentWellGraphDataExport"
              >
                Выгрузить скважину
              </n-button>
            </div>
            <TimeSeriesChart
              v-if="chartData.length"
              ref="chartRef"
              :data="chartData"
              :tr-monitoring-data="trMonitoringData"
              :vsp-periods="vspPeriods"
              :active-series="activeSeries"
              :selected-interval="selectedInterval"
              :event-tracks="eventTracks"
              :interaction-mode="interactionMode"
              :saved-annotations="currentWellAnnotations"
              :classification-levels="classificationLevels"
              :selected-annotation-id="editingAnnotationId"
              :frequency-breakpoints="currentFrequencyBreakpoints"
              :frequency-segments="frequencySegments"
              :selected-frequency-breakpoint-id="selectedFrequencyBreakpointId"
              :selected-frequency-segment-ids="selectedFrequencySegmentIds"
              :visible-date-range="visibleDateRange"
              @interval-selected="handleIntervalSelected"
              @annotation-clicked="handleAnnotationClicked"
              @frequency-segment-clicked="handleFrequencySegmentClicked"
              @frequency-segment-add-clicked="armAdditiveFrequencySelection"
              @frequency-segment-double-clicked="handleFrequencySegmentDoubleClicked"
              @frequency-breakpoint-clicked="handleFrequencyBreakpointClicked"
              @visible-range-changed="handleVisibleRangeChanged"
              @background-clicked="handleChartBackgroundClicked"
            />
            <div
              v-if="!chartData.length"
              class="flex h-[520px] items-center justify-center rounded-xl border border-dashed border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-400"
            >
              Нет данных для выбранной скважины и диапазона дат.
            </div>
          </div>
        </div>

        <aside class="panel rounded-2xl p-3">
          <template v-if="interactionMode === 'navigate'">
            <div class="flex items-start justify-between gap-2">
              <div>
                <h2 class="text-base font-semibold text-slate-100">Аналитика интервала</h2>
                <p class="mt-1 text-xs leading-5 text-slate-400">
                  Нажмите на эпизод на timeline, чтобы получить инженерное сравнение до, в периоде и после интервала.
                </p>
              </div>
            </div>

            <div
              v-if="selectedCandidateAutoAnnotation && selectedInterval"
              class="mt-3 flex flex-col gap-2 rounded-lg border border-sky-400/35 bg-slate-900/95 p-2 shadow-lg shadow-slate-950/20"
            >
              <div class="flex items-start justify-between gap-2">
                <div>
                  <div class="text-[11px] uppercase tracking-[0.16em] text-sky-300">Авторазметка 10.1</div>
                  <div class="mt-1 text-sm font-semibold text-slate-100">{{ selectedCandidateAutoAnnotation.label }}</div>
                  <div class="mt-0.5 text-[11px] text-slate-400">
                    {{ selectedCandidateAutoAnnotation.startDate }} -> {{ selectedCandidateAutoAnnotation.endDate }}
                  </div>
                </div>
                <div
                  v-if="selectedCandidateAutoConfidenceLabel"
                  class="rounded-md border border-slate-700 bg-slate-950/50 px-2 py-1 text-[11px] text-slate-300"
                >
                  Уверенность: {{ selectedCandidateAutoConfidenceLabel }}
                </div>
              </div>
              <n-button
                type="primary"
                secondary
                :disabled="!canTransferSelectedCandidateAuto"
                @click="transferCandidateAutoToManual"
              >
                Перенос в ручную разметку
              </n-button>
              <div class="rounded-lg border border-slate-700 bg-slate-950/35 p-2">
                <div class="text-[11px] uppercase tracking-[0.16em] text-slate-400">Ошибка авторазметки</div>
                <n-radio-group v-model:value="autoEpisodeErrorType" class="mt-2">
                  <n-radio value="full">Полная ошибка</n-radio>
                  <n-radio value="partial">Частичная ошибка</n-radio>
                </n-radio-group>
                <n-input
                  v-model:value="autoEpisodeErrorComment"
                  class="mt-2"
                  type="textarea"
                  size="small"
                  :autosize="{ minRows: 2, maxRows: 4 }"
                  placeholder="Комментарий к ошибочному эпизоду"
                />
                <n-button
                  class="mt-2"
                  type="warning"
                  secondary
                  block
                  :disabled="!canReviewSelectedCandidateAuto"
                  @click="saveCandidateAutoErrorReview"
                >
                  Ошибка
                </n-button>
              </div>
            </div>

            <div
              v-if="analysisDrillDown"
              class="mt-3 space-y-3"
            >
              <div class="rounded-lg border border-sky-500/40 bg-sky-950/30 px-3 py-2.5">
                <div class="grid grid-cols-[110px_minmax(0,1fr)] items-start gap-x-3 gap-y-1.5 text-sm leading-5">
                  <div class="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-400">Интервал</div>
                  <div class="min-w-0 font-medium text-slate-100">
                    {{ analysisDrillDown.interval.startDate }} — {{ analysisDrillDown.interval.endDate }}
                  </div>

                  <div class="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-400">Длительность</div>
                  <div class="min-w-0 text-slate-200">{{ analysisDrillDown.interval.durationDays }} сут.</div>

                  <div class="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-400">Слой</div>
                  <div class="min-w-0 text-slate-200">{{ analysisDrillDown.layerLabel }}</div>
                </div>
              </div>

                  <div class="rounded-xl border border-slate-700 bg-slate-800/90 px-3 py-3">
                <div class="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">До / в периоде / после</div>
                <div class="mt-3 grid gap-2">
                  <div class="grid grid-cols-[88px_repeat(3,minmax(0,1fr))] gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                    <div></div>
                    <div>До</div>
                    <div>В периоде</div>
                    <div>После</div>
                  </div>
                  <div class="grid grid-cols-[88px_repeat(3,minmax(0,1fr))] gap-2 text-sm">
                    <div class="text-slate-400">Нефть</div>
                    <div class="rounded-lg bg-slate-900/50 px-2 py-2">{{ formatMetric(analysisDrillDown.before.qoil) }}</div>
                    <div class="rounded-lg bg-slate-900/50 px-2 py-2">{{ formatMetric(analysisDrillDown.during.qoil) }}</div>
                    <div class="rounded-lg bg-slate-900/50 px-2 py-2">{{ formatMetric(analysisDrillDown.after.qoil) }}</div>
                  </div>
                  <div class="grid grid-cols-[88px_repeat(3,minmax(0,1fr))] gap-2 text-sm">
                    <div class="text-slate-400">Жидкость</div>
                    <div class="rounded-lg bg-slate-900/50 px-2 py-2">{{ formatMetric(analysisDrillDown.before.qliq) }}</div>
                    <div class="rounded-lg bg-slate-900/50 px-2 py-2">{{ formatMetric(analysisDrillDown.during.qliq) }}</div>
                    <div class="rounded-lg bg-slate-900/50 px-2 py-2">{{ formatMetric(analysisDrillDown.after.qliq) }}</div>
                  </div>
                  <div class="grid grid-cols-[88px_repeat(3,minmax(0,1fr))] gap-2 text-sm">
                    <div class="text-slate-400">Рпр</div>
                    <div class="rounded-lg bg-slate-900/50 px-2 py-2">{{ formatMetric(analysisDrillDown.before.intake_pressure) }}</div>
                    <div class="rounded-lg bg-slate-900/50 px-2 py-2">{{ formatMetric(analysisDrillDown.during.intake_pressure) }}</div>
                    <div class="rounded-lg bg-slate-900/50 px-2 py-2">{{ formatMetric(analysisDrillDown.after.intake_pressure) }}</div>
                  </div>
                  <div class="grid grid-cols-[88px_repeat(3,minmax(0,1fr))] gap-2 text-sm">
                    <div class="text-slate-400">Вода</div>
                    <div class="rounded-lg bg-slate-900/50 px-2 py-2">{{ formatMetric(analysisDrillDown.before.water_cut) }}</div>
                    <div class="rounded-lg bg-slate-900/50 px-2 py-2">{{ formatMetric(analysisDrillDown.during.water_cut) }}</div>
                    <div class="rounded-lg bg-slate-900/50 px-2 py-2">{{ formatMetric(analysisDrillDown.after.water_cut) }}</div>
                  </div>
                </div>
              </div>

              <div class="rounded-xl border border-slate-700 bg-slate-800/90 px-3 py-3">
                <div class="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Совокупный эффект</div>
                <div class="mt-3 grid gap-2">
                  <div class="flex items-center justify-between rounded-lg bg-slate-900/50 px-3 py-2 text-sm">
                    <span class="text-slate-300">{{ analysisDrillDown.oilImpactLabel }}</span>
                    <span class="font-semibold text-slate-100">{{ analysisDrillDown.oilDelta.toFixed(2) }}</span>
                  </div>
                  <div class="flex items-center justify-between rounded-lg bg-slate-900/50 px-3 py-2 text-sm">
                    <span class="text-slate-300">{{ analysisDrillDown.liquidImpactLabel }}</span>
                    <span class="font-semibold text-slate-100">{{ analysisDrillDown.liquidDelta.toFixed(2) }}</span>
                  </div>
                </div>
              </div>

              <div class="rounded-xl border border-slate-700 bg-slate-800/90 px-3 py-3">
                <div class="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Потенциал</div>
                <div class="mt-3 grid gap-2">
                  <div class="flex items-center justify-between rounded-lg bg-slate-900/50 px-3 py-2 text-sm">
                    <span class="text-slate-300">Потенциал по нефти</span>
                    <span class="font-semibold text-slate-100">{{ analysisDrillDown.potentialOil.toFixed(2) }}</span>
                  </div>
                  <div class="flex items-center justify-between rounded-lg bg-slate-900/50 px-3 py-2 text-sm">
                    <span class="text-slate-300">Потенциал по жидкости</span>
                    <span class="font-semibold text-slate-100">{{ analysisDrillDown.potentialLiquid.toFixed(2) }}</span>
                  </div>
                </div>
              </div>

              <div class="rounded-xl border border-slate-700 bg-slate-800/90 px-3 py-3">
                <div class="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Уверенность анализа</div>
                <div class="mt-3 flex items-center justify-between rounded-lg bg-slate-900/50 px-3 py-2 text-sm">
                  <span class="text-slate-300">Уровень</span>
                  <span class="font-semibold text-slate-100">{{ analysisDrillDown.confidence }}</span>
                </div>
                <div class="mt-2 rounded-lg bg-slate-900/50 px-3 py-2 text-sm leading-6 text-slate-300">
                  {{ analysisDrillDown.confidenceExplanation }}
                </div>
              </div>

              <div class="rounded-xl border border-slate-700 bg-slate-800/90 px-3 py-3">
                <div class="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Рекомендуемые мероприятия</div>
                <div class="mt-3 space-y-2">
                  <div
                    v-for="action in analysisDrillDown.actions"
                    :key="action"
                    class="rounded-lg bg-slate-900/50 px-3 py-2 text-sm leading-6 text-slate-300"
                  >
                    {{ action }}
                  </div>
                  <div v-if="!analysisDrillDown.actions.length" class="rounded-lg bg-slate-900/50 px-3 py-2 text-sm text-slate-400">
                    Для выбранного интервала дополнительных мероприятий по простым правилам не выявлено.
                  </div>
                </div>
              </div>

              <n-button type="primary" block @click="exportAnalysis(analysisDrillDown)">Выгрузить анализ</n-button>
            </div>

            <div
              v-else
              class="mt-3 rounded-xl border border-dashed border-slate-700 bg-slate-900/50 px-3 py-4 text-sm text-slate-400"
            >
              Нажмите на сохранённый эпизод на timeline, чтобы открыть аналитическое сравнение.
            </div>
          </template>

          <template v-else>
            <div class="flex items-start justify-between gap-2">
              <div>
                <h2 class="text-base font-semibold text-slate-100">{{ annotationPanelTitle }}</h2>
              </div>
            </div>

            <div
              v-if="interactionMode === 'annotate'"
              class="mt-3 space-y-3 rounded-xl border border-slate-700 bg-slate-900/50 px-3 py-3"
            >
            <div>
              <div class="text-xs uppercase tracking-[0.2em] text-slate-400">Скважина</div>
              <div class="mt-1 text-sm font-medium text-slate-100">{{ selectedWell }}</div>
            </div>
            <div>
              <div class="text-xs uppercase tracking-[0.2em] text-slate-400">Текущая группа</div>
              <div class="mt-1 text-sm font-medium text-slate-100">{{ currentWellGroupLabel }}</div>
            </div>
            <div>
              <label class="mb-1 block text-xs uppercase tracking-[0.2em] text-slate-400">Новая группа</label>
              <n-select
                v-model:value="groupMigrationTarget"
                size="medium"
                :options="groupMigrationOptions"
                placeholder="Выберите группу"
                class="w-full"
              />
            </div>
            <div v-if="groupMigrationTarget === CREATE_NEW_GROUP_OPTION">
              <label class="mb-1 block text-xs uppercase tracking-[0.2em] text-slate-400">Название новой группы</label>
              <n-input
                v-model:value="newGroupName"
                size="medium"
                placeholder="Введите название группы"
              />
            </div>
            <n-button
              block
              secondary
              :type="groupSaveFeedback === 'saved' ? 'success' : 'default'"
              @click="moveWellToGroup"
            >
              {{ groupSaveFeedback === 'saved' ? 'Сохранено' : 'Переместить в другую группу' }}
            </n-button>
          </div>

          <div
            v-if="interactionMode === 'annotate'"
            class="mt-3 space-y-3 rounded-xl border border-slate-700 bg-slate-900/50 px-3 py-3"
          >
            <div class="flex items-center justify-between gap-2">
              <div class="text-xs uppercase tracking-[0.2em] text-slate-400">Штрихи частоты</div>
              <div class="text-xs text-slate-400">{{ currentFrequencyBreakpoints.length }}</div>
            </div>

            <div
              v-if="selectedFrequencySegments.length"
              class="rounded-lg border border-sky-400/30 bg-sky-950/20 px-3 py-2"
            >
              <div class="flex items-center justify-between gap-2">
                <div class="min-w-0">
                  <div class="text-[11px] uppercase tracking-[0.16em] text-slate-400">Выбрано промежутков</div>
                  <div class="mt-1 text-sm font-medium text-slate-100">{{ selectedFrequencySegments.length }}</div>
                </div>
                <n-button
                  circle
                  secondary
                  size="small"
                  :type="additiveFrequencySelectionArmed ? 'primary' : 'default'"
                  title="Добавить ещё один промежуток"
                  @click="armAdditiveFrequencySelection"
                >
                  +
                </n-button>
              </div>
            </div>

            <div v-if="selectedFrequencyBreakpoint" class="rounded-lg border border-amber-400/30 bg-amber-950/20 px-3 py-2">
              <div class="grid grid-cols-[74px_minmax(0,1fr)] gap-x-2 gap-y-1 text-sm">
                <div class="text-[11px] uppercase tracking-[0.16em] text-slate-400">Дата</div>
                <div class="font-medium text-slate-100">{{ selectedFrequencyBreakpoint.date }}</div>
                <div class="text-[11px] uppercase tracking-[0.16em] text-slate-400">Тип</div>
                <div class="text-slate-200">{{ getFrequencyBreakpointSourceLabel(selectedFrequencyBreakpoint.source) }}</div>
                <div class="text-[11px] uppercase tracking-[0.16em] text-slate-400">Причина</div>
                <div class="text-slate-200">{{ selectedFrequencyBreakpoint.reason }}</div>
              </div>
              <n-button class="mt-2" block secondary type="warning" size="small" @click="mergeFrequencySegmentsAtSelectedBreakpoint">
                Объединить промежутки
              </n-button>
            </div>

            <div v-if="selectedInterval" class="grid grid-cols-2 gap-2">
              <n-button
                size="small"
                secondary
                :disabled="!canAddManualFrequencyBreakpoint(selectedInterval.startDate)"
                @click="addManualFrequencyBreakpoint(selectedInterval.startDate)"
              >
                Штрих в начало
              </n-button>
              <n-button
                size="small"
                secondary
                :disabled="!canAddManualFrequencyBreakpoint(selectedInterval.endDate)"
                @click="addManualFrequencyBreakpoint(selectedInterval.endDate)"
              >
                Штрих в конец
              </n-button>
            </div>

            <n-button
              v-if="currentSuppressedFrequencyBreakpoints.length"
              quaternary
              size="small"
              class="w-full"
              @click="restoreAutoFrequencyBreakpoints"
            >
              Вернуть автоштрихи
            </n-button>
          </div>

          <div v-if="selectedInterval" class="mt-3 space-y-4 rounded-xl border border-slate-700 bg-slate-800/90 p-4">
            <div
              v-if="selectedCandidateAutoAnnotation"
              class="sticky top-0 z-10 flex flex-col gap-2 rounded-lg border border-sky-400/35 bg-slate-900/95 p-2 shadow-lg shadow-slate-950/20"
            >
              <div class="flex items-start justify-between gap-2">
                <div>
                  <div class="text-[11px] uppercase tracking-[0.16em] text-sky-300">Авторазметка 10.1</div>
                  <div class="mt-1 text-sm font-semibold text-slate-100">{{ selectedCandidateAutoAnnotation.label }}</div>
                  <div class="mt-0.5 text-[11px] text-slate-400">
                    {{ selectedCandidateAutoAnnotation.startDate }} -> {{ selectedCandidateAutoAnnotation.endDate }}
                  </div>
                </div>
                <div
                  v-if="selectedCandidateAutoConfidenceLabel"
                  class="rounded-md border border-slate-700 bg-slate-950/50 px-2 py-1 text-[11px] text-slate-300"
                >
                  Уверенность: {{ selectedCandidateAutoConfidenceLabel }}
                </div>
              </div>
              <n-button
                type="primary"
                secondary
                :disabled="!canTransferSelectedCandidateAuto"
                @click="transferCandidateAutoToManual"
              >
                Перенос в ручную разметку
              </n-button>
              <div class="rounded-lg border border-slate-700 bg-slate-950/35 p-2">
                <div class="text-[11px] uppercase tracking-[0.16em] text-slate-400">Ошибка авторазметки</div>
                <n-radio-group v-model:value="autoEpisodeErrorType" class="mt-2">
                  <n-radio value="full">Полная ошибка</n-radio>
                  <n-radio value="partial">Частичная ошибка</n-radio>
                </n-radio-group>
                <n-input
                  v-model:value="autoEpisodeErrorComment"
                  class="mt-2"
                  type="textarea"
                  size="small"
                  :autosize="{ minRows: 2, maxRows: 4 }"
                  placeholder="Комментарий к ошибочному эпизоду"
                />
                <n-button
                  class="mt-2"
                  type="warning"
                  secondary
                  block
                  :disabled="!canReviewSelectedCandidateAuto"
                  @click="saveCandidateAutoErrorReview"
                >
                  Ошибка
                </n-button>
              </div>
            </div>

            <div v-if="isEditMode" class="sticky top-0 z-10 flex flex-col gap-2 rounded-lg border border-rose-500/25 bg-slate-900/95 p-2 shadow-lg shadow-slate-950/20">
              <div class="text-[11px] uppercase tracking-[0.16em] text-slate-400">{{ draftEpisodeLabel }}</div>
              <n-button type="error" secondary @click="deleteAnnotation">Удалить выбранный эпизод</n-button>
              <n-button secondary @click="handleClearSelectionClick">Очистить выделение</n-button>
            </div>

            <div v-if="isEditMode && boundarySliderMax > 0" class="space-y-3 rounded-lg border border-slate-700 bg-slate-900/45 px-3 py-3">
              <div class="flex items-center justify-between gap-3">
                <label class="block text-xs uppercase tracking-[0.2em] text-slate-400">Границы интервала</label>
                <div class="text-xs font-medium text-slate-300">{{ selectedInterval.durationDays }} сут.</div>
              </div>
              <n-slider
                v-model:value="annotationBoundarySliderValue"
                range
                :min="0"
                :max="boundarySliderMax"
                :step="1"
                :tooltip="false"
              />
              <div class="grid grid-cols-2 gap-2 text-xs">
                <div class="rounded-md bg-slate-950/40 px-2 py-1.5">
                  <label class="block uppercase tracking-[0.14em] text-slate-500" for="interval-start-input">Начало</label>
                  <input
                    id="interval-start-input"
                    v-model="selectedIntervalStartInput"
                    type="datetime-local"
                    step="60"
                    class="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 font-semibold text-slate-100 outline-none transition focus:border-sky-400"
                  />
                </div>
                <div class="rounded-md bg-slate-950/40 px-2 py-1.5">
                  <label class="block uppercase tracking-[0.14em] text-slate-500" for="interval-end-input">Конец</label>
                  <input
                    id="interval-end-input"
                    v-model="selectedIntervalEndInput"
                    type="datetime-local"
                    step="60"
                    class="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2 py-1 font-semibold text-slate-100 outline-none transition focus:border-sky-400"
                  />
                </div>
              </div>
            </div>

            <div class="space-y-2">
              <label class="block text-xs uppercase tracking-[0.2em] text-slate-400">Разметка эпизода</label>
              <div class="grid gap-1.5">
                <div
                  v-for="level in classificationLevels"
                  :key="level.key"
                  class="rounded-md border border-slate-700 bg-slate-900/45 p-2"
                >
                  <label class="block text-[10px] font-medium uppercase tracking-[0.12em] text-slate-500">
                    {{ level.label }}
                  </label>
                  <div v-if="level.options.length" class="mt-1.5 flex flex-wrap gap-1">
                    <button
                      v-for="option in level.options"
                      :key="`${level.key}-${option.value}`"
                      type="button"
                      class="rounded-md border px-1.5 py-0.5 text-[11px] transition"
                      :class="
                        episodeForm.classification[level.key] === option.value
                          ? 'border-sky-400 bg-sky-500/20 text-sky-100'
                          : 'border-slate-700 bg-slate-950/40 text-slate-300 hover:border-slate-500 hover:bg-slate-800'
                      "
                      @click="setClassificationValue(level.key, option.value)"
                    >
                      {{ option.label }}
                    </button>
                  </div>
                  <div class="mt-2 grid grid-cols-2 gap-1.5">
                    <n-button
                      size="tiny"
                      type="primary"
                      secondary
                      :disabled="!episodeForm.classification[level.key]"
                      @click="saveClassificationLevel(level.key)"
                    >
                      Сохранить
                    </n-button>
                    <n-button
                      size="tiny"
                      type="error"
                      secondary
                      :disabled="!canDeleteClassificationLevel(level.key)"
                      @click="deleteClassificationLevel(level.key)"
                    >
                      Удалить
                    </n-button>
                  </div>
                </div>
              </div>
              <div class="text-xs text-slate-500">{{ draftEpisodeLabel }}</div>
            </div>

            <div class="flex flex-col gap-2">
              <n-button quaternary @click="zoomToSelection">Приблизить к выделению</n-button>
              <n-button quaternary @click="resetZoom">Сбросить масштаб</n-button>
            </div>
          </div>

          <div
            v-else
            class="mt-3 rounded-xl border border-dashed border-slate-700 bg-slate-900/50 px-3 py-4 text-sm text-slate-400"
          >
            Интервал ещё не выбран. Перейдите на вкладку разметки и протяните мышью по графику, чтобы выбрать временное окно.
          </div>

          <div class="mt-3 rounded-xl border border-slate-700 bg-slate-800/90 px-3 py-3">
            <div class="flex items-center justify-between gap-2">
              <div class="text-xs uppercase tracking-[0.2em] text-slate-400">Сохранённые аннотации</div>
              <div class="text-xs text-slate-400">{{ currentWellAnnotations.length }}</div>
            </div>
            <div v-if="currentWellAnnotations.length" class="mt-3 space-y-2">
              <button
                v-for="episode in currentWellAnnotations"
                :key="episode.id"
                class="w-full rounded-lg border px-2.5 py-2 text-left transition"
                :class="episode.id === editingAnnotationId ? 'border-sky-400 bg-slate-700/80' : 'border-slate-700 bg-slate-900/50 hover:bg-slate-800'"
                @click="openAnnotationForEdit(episode.id)"
              >
                <div class="text-xs font-medium text-slate-200">{{ episode.startDate }} -> {{ episode.endDate }}</div>
                <div class="mt-1 text-xs text-slate-400">
                  {{ `Эпизод: ${getAnnotationClassificationLabel(episode)}` }}
                </div>
              </button>
            </div>
            <div v-else class="mt-2 text-sm text-slate-400">
              Здесь будут показаны сохранённые аннотации по интервалам.
            </div>
          </div>
          </template>
        </aside>
      </section>

      <section v-else-if="interactionMode === 'modelTuning'">
        <div class="panel rounded-2xl p-3">
          <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <h2 class="text-lg font-semibold text-slate-100">Настройка модели авторазметки</h2>
              <p class="mt-1 max-w-3xl text-sm leading-6 text-slate-400">
                Правила можно подбирать для одной скважины или группы. Центральный график использует те же параметры,
                что выбраны в анализе и разметке.
              </p>
            </div>
            <div class="grid gap-2 sm:grid-cols-3 lg:min-w-[520px]">
              <n-button secondary @click="resetCurrentModelGroup">Сбросить</n-button>
              <n-button secondary type="primary" @click="saveCurrentModelParams">Сохранить настройки</n-button>
              <n-button type="primary" @click="applyCurrentModelParams">Запустить авторазметку ↗</n-button>
            </div>
          </div>

          <div class="mt-3 grid gap-3 rounded-xl border border-slate-700 bg-slate-900/50 p-3 xl:grid-cols-[minmax(0,1fr)_320px] xl:items-center">
            <div class="flex flex-wrap items-center gap-2">
              <div class="mr-2 text-sm text-slate-300">Группа:</div>
            <button
              v-for="group in modelFieldGroups"
              :key="group.value"
                class="relative rounded-lg border px-3 py-1.5 text-sm font-medium transition"
              :class="
                modelSelectedGroupId === group.value
                  ? 'border-sky-400 bg-slate-700 text-slate-100'
                  : 'border-slate-700 bg-slate-950/60 text-slate-300 hover:bg-slate-800'
              "
              @click="modelSelectedGroupId = group.value"
              >
                {{ group.label }}
                <span
                  v-if="hasModelGroupOverrides(group.value)"
                  class="absolute -right-1 -top-1 h-2.5 w-2.5 rounded-full bg-orange-400 shadow shadow-orange-950"
                />
              </button>
            </div>
            <div class="grid gap-2 sm:grid-cols-2">
              <button
                class="rounded-lg border px-3 py-2 text-left text-sm transition"
                :class="modelRunScope === 'well' ? 'border-sky-400 bg-slate-700 text-slate-100' : 'border-slate-700 bg-slate-950/60 text-slate-300 hover:bg-slate-800'"
                @click="modelRunScope = 'well'"
              >
                <div class="text-xs uppercase tracking-[0.16em] text-slate-400">Одна скважина</div>
                <div class="mt-1 font-semibold">{{ selectedWell }}</div>
              </button>
              <button
                class="rounded-lg border px-3 py-2 text-left text-sm transition"
                :class="modelRunScope === 'group' ? 'border-sky-400 bg-slate-700 text-slate-100' : 'border-slate-700 bg-slate-950/60 text-slate-300 hover:bg-slate-800'"
                @click="modelRunScope = 'group'"
              >
                <div class="text-xs uppercase tracking-[0.16em] text-slate-400">Группа скважин</div>
                <div class="mt-1 font-semibold">{{ getModelGroupLabel(modelSelectedGroupId) }}</div>
              </button>
            </div>
          </div>

          <div class="mt-3 grid gap-3 2xl:grid-cols-[360px_minmax(0,1fr)_310px]">
            <aside class="flex max-h-[calc(100vh-258px)] min-h-0 flex-col gap-3 rounded-xl border border-slate-700 bg-slate-900/40 p-3">
              <div class="text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Категории</div>
              <div class="grid gap-1.5">
                <button
                  v-for="category in modelRuleCategories"
                  :key="category.key"
                  class="flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-xs transition"
                  :class="
                    modelSelectedCategoryKey === category.key && modelPanelTab === 'rules'
                      ? 'border-sky-400 bg-slate-700/80 text-slate-100'
                      : 'border-slate-700 bg-slate-950/50 text-slate-300 hover:bg-slate-800'
                  "
                  @click="selectModelRuleCategory(category.key)"
                >
                  <span class="h-3 w-3 rounded-sm" :style="{ backgroundColor: category.color }" />
                  <span>{{ category.label }}</span>
                  <span
                    v-if="hasModelCategoryOverrides(category)"
                    class="ml-auto h-2.5 w-2.5 rounded-full bg-sky-400 shadow shadow-sky-950"
                    title="Есть переопределения в категории"
                  />
                </button>
              </div>

              <div class="min-h-0 flex-1 overflow-hidden rounded-xl border border-slate-700 bg-slate-800/90">
                <div class="border-b border-slate-700 px-3 py-3">
                  <div class="flex items-start justify-between gap-3">
                  <div>
                      <h3 class="text-sm font-semibold text-slate-100">{{ activeModelRuleCategory.label }}</h3>
                      <p class="mt-1 text-xs leading-5 text-slate-400">{{ activeModelRuleCategory.description }}</p>
                  </div>
                    <div class="shrink-0 rounded-lg border border-slate-700 bg-slate-950/60 px-2.5 py-2 text-right">
                      <div class="text-[10px] uppercase tracking-[0.16em] text-slate-400">Совпадение</div>
                      <div class="mt-1 text-xs font-semibold text-slate-100">
                      {{ modelQualityBeforePct }}% → {{ modelQualityAfterPct }}%
                      </div>
                    </div>
                  </div>

                  <pre class="mt-3 max-h-24 overflow-auto rounded-lg border border-slate-700 bg-slate-950/80 px-3 py-2 text-[11px] leading-5 text-slate-300">{{ activeModelRuleCategory.pseudocode }}</pre>
                </div>

                <div class="max-h-[420px] overflow-y-auto px-3 py-2">
                  <div
                    v-for="parameter in activeModelRuleParameters"
                    :key="parameter.key"
                    class="grid gap-2 border-b border-slate-800 py-2.5 last:border-b-0"
                  >
                    <div class="flex items-start justify-between gap-3">
                      <div class="min-w-0">
                        <div class="text-xs font-medium leading-5 text-slate-200">
                          <span v-if="parameter.important" class="mr-1 text-sky-300">★</span>{{ parameter.label }}
                        </div>
                        <div class="text-[11px] text-slate-500">{{ parameter.key }}</div>
                        <div class="mt-0.5 text-[11px] text-slate-500">
                          <span v-if="hasModelParamOverride(parameter.key)">
                            Глобально: {{ formatModelParamValue(parameter, getModelParamInheritedValue(parameter.key)) }}
                          </span>
                          <span v-else>
                            Диапазон: {{ parameter.min }}–{{ parameter.max }}{{ parameter.unit ? ` ${parameter.unit}` : '' }}
                          </span>
                        </div>
                      </div>
                      <div class="shrink-0 text-right">
                        <div class="text-xs font-semibold text-slate-100">
                          {{ formatModelParamValue(parameter, getModelParamValue(parameter.key)) }}
                        </div>
                        <button
                          v-if="hasModelParamOverride(parameter.key)"
                          class="mt-1 text-[11px] text-sky-300 hover:text-sky-100"
                          @click="resetModelParamValue(parameter.key)"
                        >
                          Сбросить
                        </button>
                      </div>
                    </div>
                    <n-slider
                      :value="getModelParamValue(parameter.key)"
                      :min="parameter.min"
                      :max="parameter.max"
                      :step="parameter.step"
                      @update:value="setModelParamValue(parameter.key, Number($event))"
                    />
                  </div>
                </div>
              </div>
            </aside>

            <section class="min-w-0">
              <div class="rounded-xl border border-slate-700 bg-slate-800/90 p-2">
                <div
                  v-if="loading"
                  class="flex h-[760px] items-center justify-center rounded-xl border border-dashed border-slate-700 bg-slate-900/50 text-slate-400"
                >
                  Загрузка данных с backend...
                </div>
                <TimeSeriesChart
                  v-else
                  ref="modelChartRef"
                  :data="chartData"
                  :tr-monitoring-data="trMonitoringData"
                  :vsp-periods="vspPeriods"
                  :active-series="activeSeries"
                  :selected-interval="null"
                  :event-tracks="eventTracks"
                  interaction-mode="navigate"
                  :saved-annotations="currentWellAnnotations"
                  :classification-levels="classificationLevels"
                  :selected-annotation-id="null"
                  :frequency-breakpoints="currentFrequencyBreakpoints"
                  :frequency-segments="frequencySegments"
                  :selected-frequency-breakpoint-id="null"
                  :selected-frequency-segment-ids="[]"
                  :visible-date-range="visibleDateRange"
                  @visible-range-changed="handleVisibleRangeChanged"
                />
              </div>
            </section>

            <aside class="space-y-3 rounded-xl border border-slate-700 bg-slate-900/40 p-3">
              <div>
                <h3 class="text-base font-semibold text-slate-100">Результаты адаптации</h3>
                <p class="mt-1 text-xs leading-5 text-slate-400">Оценка качества до сохранения и после применения правил.</p>
              </div>
              <div class="grid gap-2">
                <div class="rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2">
                  <div class="text-xs uppercase tracking-[0.16em] text-slate-400">До изменений</div>
                  <div class="mt-1 text-2xl font-semibold text-slate-100">{{ modelQualityBeforePct }}%</div>
                </div>
                <div class="rounded-lg border border-sky-500/40 bg-sky-950/30 px-3 py-2">
                  <div class="text-xs uppercase tracking-[0.16em] text-slate-400">После изменений</div>
                  <div class="mt-1 text-2xl font-semibold text-sky-100">{{ modelQualityAfterPct }}%</div>
                </div>
                <div class="rounded-lg border border-slate-700 bg-slate-950/60 px-3 py-2">
                  <div class="text-xs uppercase tracking-[0.16em] text-slate-400">Область применения</div>
                  <div class="mt-1 text-sm font-semibold text-slate-100">{{ modelRunScopeLabel }}</div>
                  <div class="mt-2 text-xs text-slate-400">
                    {{ modelChangedRows.length }} параметров изменено для {{ modelRunScopeLabel }}
                  </div>
                </div>
              </div>

              <div class="rounded-lg border border-slate-700 bg-slate-950/50 p-2">
                <div class="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Качество по группам</div>
                <div class="space-y-2">
                  <div
                    v-for="row in compactModelQualityRows"
                    :key="row.field"
                    class="rounded-lg bg-slate-900/70 px-2.5 py-2"
                  >
                    <div class="flex items-center justify-between">
                      <div class="text-sm font-semibold text-slate-100">{{ row.field }}</div>
                      <div class="text-xs text-slate-400">{{ row.rows }} строк</div>
                    </div>
                    <div class="mt-3 h-2 rounded-full bg-slate-950">
                      <div class="h-2 rounded-full bg-sky-400" :style="{ width: `${row.pct}%` }" />
                    </div>
                    <div class="mt-2 flex items-center justify-between text-xs text-slate-400">
                      <span>{{ row.wells }} скв.</span>
                      <span class="font-semibold text-slate-200">{{ row.pct }}%</span>
                    </div>
                    <div class="mt-2 text-xs leading-5 text-slate-500">{{ row.note }}</div>
                  </div>
                </div>
              </div>

              <div class="grid gap-2">
                <n-button secondary @click="showModelChanges">Что изменилось ↗</n-button>
                <n-button secondary type="primary" @click="saveCurrentModelParams">Сохранить настройки</n-button>
                <n-button type="primary" @click="applyCurrentModelParams">Применить и пересчитать ↗</n-button>
              </div>
            </aside>
          </div>
        </div>
      </section>
      <section v-else>
        <div class="panel rounded-2xl p-3">
          <div class="flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <h2 class="text-lg font-semibold text-slate-100">Сводка авторазметки за период</h2>
              <p class="mt-1 max-w-4xl text-sm leading-6 text-slate-400">
                Категория попадает в таблицу, если её автоинтервал пересекает выбранный период. Для остановок и ГДИ показываются длительность, остановочный дебит и накопленные потери; для остальных категорий считается накопленный dQ по интервалу классификатора.
              </p>
            </div>
            <div class="flex flex-wrap items-end gap-2">
              <div>
                <label class="mb-1 block text-xs uppercase tracking-[0.18em] text-slate-400">Месторождение</label>
                <n-select
                  v-model:value="periodSummaryFieldCode"
                  class="w-44"
                  :options="periodSummaryFieldOptions"
                />
              </div>
              <div>
                <label class="mb-1 block text-xs uppercase tracking-[0.18em] text-slate-400">Скважина</label>
                <n-select
                  v-model:value="periodSummaryWellId"
                  class="w-48"
                  :options="periodSummaryWellOptions"
                />
              </div>
              <div>
                <label class="mb-1 block text-xs uppercase tracking-[0.18em] text-slate-400">Период</label>
                <n-select
                  v-model:value="periodSummaryPreset"
                  class="w-40"
                  :options="periodSummaryPeriodOptions"
                />
              </div>
              <div v-if="periodSummaryPreset === 'custom'">
                <label class="mb-1 block text-xs uppercase tracking-[0.18em] text-slate-400">Свой период</label>
                <n-date-picker
                  v-model:value="periodSummaryDateRange"
                  type="daterange"
                  clearable
                  class="w-64"
                />
              </div>
              <n-button type="primary" :loading="periodSummaryLoading" @click="loadPeriodSummary">
                Обновить
              </n-button>
            </div>
          </div>

          <div class="mt-3 grid gap-3 rounded-xl border border-slate-700 bg-slate-900/50 p-3 xl:grid-cols-6">
            <div class="rounded-lg bg-slate-950/50 px-3 py-2">
              <div class="text-xs uppercase tracking-[0.18em] text-slate-500">Область</div>
              <div class="mt-1 text-sm font-semibold text-slate-100">{{ periodSummaryScopeLabel }}</div>
            </div>
            <div class="rounded-lg bg-slate-950/50 px-3 py-2">
              <div class="text-xs uppercase tracking-[0.18em] text-slate-500">Начало</div>
              <div class="mt-1 text-sm font-semibold text-slate-100">{{ formatPeriodDate(periodSummaryMeta.period_start) }}</div>
            </div>
            <div class="rounded-lg bg-slate-950/50 px-3 py-2">
              <div class="text-xs uppercase tracking-[0.18em] text-slate-500">Конец</div>
              <div class="mt-1 text-sm font-semibold text-slate-100">{{ formatPeriodDate(periodSummaryMeta.period_end) }}</div>
            </div>
            <div class="rounded-lg bg-slate-950/50 px-3 py-2">
              <div class="text-xs uppercase tracking-[0.18em] text-slate-500">Окно средних</div>
              <div class="mt-1 text-sm font-semibold text-slate-100">{{ periodSummaryMeta.window_days }} сут.</div>
            </div>
            <div class="rounded-lg bg-slate-950/50 px-3 py-2">
              <div class="text-xs uppercase tracking-[0.18em] text-slate-500">Строк</div>
              <div class="mt-1 text-sm font-semibold text-slate-100">{{ filteredPeriodSummaryRows.length }} / {{ periodSummaryRows.length }}</div>
            </div>
          </div>

          <div class="mt-2 rounded-xl border border-slate-700 bg-slate-900/40 px-3 py-2 text-xs leading-5 text-slate-400">
            Сейчас показаны только категории, которые пересекают выбранный календарный интервал. Если по области «Все»
            отображается мало скважин, расширьте период до месяца, года или задайте свой диапазон.
          </div>

          <div
            v-if="periodSummaryError"
            class="mt-3 rounded-xl border border-red-500/40 bg-red-950/40 px-3 py-2 text-sm text-red-300"
          >
            {{ periodSummaryError }}
          </div>

          <div class="mt-3 rounded-xl border border-slate-700 bg-slate-900/45 p-3">
            <div class="mb-2 text-xs font-semibold uppercase tracking-[0.22em] text-slate-400">Фильтры по колонкам</div>
            <div class="grid gap-2 md:grid-cols-3 xl:grid-cols-6">
              <n-input
                v-for="column in periodSummaryFilterColumns"
                :key="column.key"
                v-model:value="periodSummaryFilters[column.key]"
                clearable
                size="small"
                :placeholder="column.title"
              />
            </div>
          </div>

          <div class="mt-3 overflow-hidden rounded-xl border border-slate-700 bg-slate-950/35">
            <n-data-table
              :loading="periodSummaryLoading"
              :columns="periodSummaryColumns"
              :data="filteredPeriodSummaryRows"
              :pagination="{ pageSize: 25 }"
              :single-line="false"
              size="small"
              max-height="620"
            />
          </div>
        </div>
      </section>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { NButton, NCheckbox, NCheckboxGroup, NDataTable, NDatePicker, NInput, NRadio, NRadioGroup, NSelect, NSlider, useMessage } from 'naive-ui'
import type { DataTableColumns, SelectOption } from 'naive-ui'
import TimeSeriesChart from '@/components/TimeSeriesChart.vue'
import {
  fetchArtificialLiftPeriods,
  fetchCandidateAutoEpisodeIntervals,
  buildGraphDataExportCsvUrl,
  buildManualGraphDataExportCsvUrl,
  fetchMarkup,
  fetchModelParamsState,
  fetchPeriodSummary,
  fetchTrMonitoring,
  fetchVspPeriods,
  fetchWellContext,
  fetchWellIds,
  fetchWellTimeseries,
  resetModelParamsForTarget,
  saveModelParamsForTarget,
  saveMarkup
} from '@/services/api'
import type { PeriodSummaryRow } from '@/services/api'
import { generateMockEventTracks as generateOldMockEventTracks } from '@/services/mockEventTracks'
import { generateMockEventTracks as generateMockEventTracksV2 } from '@/services/mockEventTracksV2'
import { generateMockTimeseries } from '@/services/mockTimeseries'
import type {
  AnnotationClassOption,
  AnnotationClassification,
  AnnotationClassificationLevel,
  AutoEpisodeErrorType,
  AutoEpisodeReview,
  AnnotationKind,
  ConfidenceLevel,
  EpisodeFormState,
  EpisodeType,
  EspInstallationPeriod,
  EventInterval,
  FrequencyBreakpoint,
  FrequencyBreakpointClickPayload,
  FrequencyBreakpointSuppression,
  FrequencySegment,
  FrequencySegmentClickPayload,
  FrequencySegmentDoubleClickPayload,
  HierarchicalEventTracks,
  InteractionMode,
  MarkupState,
  OpzEventFlag,
  SavedAnnotation,
  SavedEventAnnotation,
  SelectedInterval,
  SeriesKey,
  TimelineAnnotationClickPayload,
  TimeSeriesPoint,
  TrMonitoringPoint,
  VspPeriod,
  VisibleDateRange,
  WellContext,
  WellGroupId
} from '@/types/timeseries'

const message = useMessage()
const chartRef = ref<InstanceType<typeof TimeSeriesChart> | null>(null)
const modelChartRef = ref<InstanceType<typeof TimeSeriesChart> | null>(null)
let groupSaveFeedbackTimeout: ReturnType<typeof setTimeout> | null = null
let markupSaveTimeout: ReturnType<typeof setTimeout> | null = null
let lastMarkupSaveErrorAt = 0
const CREATE_NEW_GROUP_OPTION = '__create_new_group__'
const DEFAULT_FIELD_CODE = 'Ic'
const DEFAULT_WELL_ID = 'Ic_805'
const FREQUENCY_CHANGE_THRESHOLD = 0.1
const MARKUP_STORAGE_KEYS = {
  annotations: 'wellInsight.markup.annotations.v1',
  episodeClasses: 'wellInsight.markup.episodeClasses.v1',
  actionClasses: 'wellInsight.markup.actionClasses.v1',
  manualFrequencyBreakpoints: 'wellInsight.markup.manualFrequencyBreakpoints.v1',
  suppressedFrequencyBreakpoints: 'wellInsight.markup.suppressedFrequencyBreakpoints.v1',
  autoEpisodeReviews: 'wellInsight.markup.autoEpisodeReviews.v1'
}
const UI_STATE_STORAGE_KEY = 'wellInsight.uiState.v1'
const ANNOTATION_SNAP_THRESHOLD_MS = 30 * 60 * 1000

const defaultWellOptions: { label: string; value: string }[] = []
const wellOptions = ref(defaultWellOptions)

const knownFieldCodes = ['Au', 'Az', 'Da', 'Ic', 'Mc', 'Vt', 'Ya']
const getFieldGroupId = (fieldCode: string): WellGroupId => `field-${fieldCode.toLowerCase()}`
const formatFieldGroupLabel = (fieldCode: string): string =>
  fieldCode === 'other' ? 'Без группы' : fieldCode
const getWellFieldCodeFromId = (wellId: string): string => {
  const [fieldCode] = wellId.split('_')
  return fieldCode?.trim() || 'other'
}
const baseWellGroupOptions: { label: string; value: WellGroupId }[] = knownFieldCodes.map((fieldCode) => ({
  label: formatFieldGroupLabel(fieldCode),
  value: getFieldGroupId(fieldCode)
}))

const seriesOptions: { label: string; value: SeriesKey }[] = [
  { label: 'Дебит жидкости', value: 'qliq' },
  { label: 'Давление буферное', value: 'buffer_pressure' },
  { label: 'Давление затрубное', value: 'casing_pressure' },
  { label: 'Загрузка', value: 'load' },
  { label: 'Обводненность_АГЗУ', value: 'water_cut' },
  { label: 'Обводненность ХАЛ', value: 'water_cut_hal' },
  { label: 'Обв_алгоритм', value: 'water_cut_algorithm' },
  { label: 'Р на приеме насоса', value: 'intake_pressure' },
  { label: 'Частота вращения двиг.', value: 'esp_frequency' },
  { label: 'Активная мощность', value: 'active_power' },
  { label: 'БДПВ Объем в пересчете на сутки', value: 'bdpv_volume_rate' },
  { label: 'БДПВ Расход воды', value: 'bdpv_water_flow' },
  { label: 'Давление в коллекторе', value: 'collector_pressure' },
  { label: 'Полная мощность', value: 'full_power' },
  { label: 'Расход газа на сутки', value: 'qgas' },
  { label: 'Расход нефти', value: 'qoil' },
  { label: 'Газовый фактор', value: 'gas_factor' },
  { label: 'Газожидкостный фактор', value: 'gas_liquid_factor' },
  { label: 'Дебит жидкости (в.расходомер)', value: 'qliq_wfm' },
  { label: 'ТР: Р пл', value: 'tr_reservoir_pressure' },
  { label: 'ТР: Н д', value: 'tr_dynamic_level' },
  { label: 'ТР: Р на приёме', value: 'tr_intake_pressure' },
  { label: 'ТР: Рзаб', value: 'tr_bottomhole_pressure' },
  { label: 'ТР: Q нефти', value: 'tr_oil_rate' },
  { label: 'ТР: Q жидкости', value: 'tr_liquid_rate' },
  { label: 'ТР: Вода', value: 'tr_water_cut' },
  { label: 'ТР: Рнас', value: 'tr_pump_pressure' },
  { label: 'ТР: ГФ', value: 'tr_gas_factor' },
  { label: 'ТР: Кпр', value: 'tr_productivity' }
]

const DEFAULT_CLASSIFICATION_LEVELS: AnnotationClassificationLevel[] = [
  {
    key: 'well_state',
    label: 'Уровень 1. Работа / остановка',
    options: [
      { label: 'Работа', value: 'work' },
      { label: 'Остановка', value: 'stop' }
    ]
  },
  {
    key: 'gdi',
    label: 'Уровень 2. ГДИ',
    allowCustom: true,
    options: [
      { label: 'ГДИ', value: 'gdi' }
    ]
  },
  {
    key: 'esp_uvch',
    label: 'Уровень 3. Изменение частоты',
    allowCustom: true,
    placeholder: 'Введите категорию',
    options: [
      { label: 'УВЧ', value: 'uvch' },
      { label: 'УМЧ', value: 'umch' }
    ]
  },
  {
    key: 'esp_rptch',
    label: 'Уровень 4. РПТЧ',
    allowCustom: true,
    placeholder: 'Введите категорию',
    options: [
      { label: 'РПТЧ', value: 'rptch' }
    ]
  },
  {
    key: 'esp_periodic',
    label: 'Уровень 5. Периодическая работа',
    allowCustom: true,
    placeholder: 'Введите категорию',
    options: [
      { label: 'Периодическая работа', value: 'periodic_operation' }
    ]
  },
  {
    key: 'nur',
    label: 'Уровень 6. НУР',
    options: [
      { label: 'НУР', value: 'nur_yes' }
    ]
  },
  {
    key: 'reservoir_pressure_trend',
    label: 'Уровень 7. Рпл',
    options: [
      { label: 'Рост Рпл', value: 'Pres_growth' },
      { label: 'Снижение Рпл', value: 'Pres_decline' }
    ]
  },
  {
    key: 'water_cut_trend',
    label: 'Уровень 8. Обводненность',
    options: [
      { label: 'Рост обводненности', value: 'WCT_growth' },
      { label: 'Снижение обводненности', value: 'WCT_decline' }
    ]
  },
  {
    key: 'productivity_trend',
    label: 'Уровень 9. Кпрод',
    options: [
      { label: 'Рост Кпрод', value: 'Kprod_growth' },
      { label: 'Снижение Кпрод', value: 'Kprod_decline' }
    ]
  },
  {
    key: 'complicated_fund',
    label: 'Уровень 10. Осложненный фонд',
    options: [
      { label: 'Осложненный фонд', value: 'slozhn_fond' }
    ]
  },
  {
    key: 'sppv',
    label: 'Уровень 11. СППВ',
    options: [
      { label: 'СППВ', value: 'sppv' }
    ]
  },
  {
    key: 'esp_degradation',
    label: 'Уровень 12. Деградация ЭЦН',
    allowCustom: true,
    options: [
      { label: 'Деградация ЭЦН', value: 'degr_yes' }
    ]
  },
  {
    key: 'vgf',
    label: 'Уровень 13. ВГФ',
    options: [
      { label: 'ВГФ', value: 'vgf_yes' }
    ]
  },
  {
    key: 'gas_factor_trend',
    label: 'Уровень 14. Изменение ГФ',
    options: [
      { label: 'Снижение ГФ', value: 'GF_decline' },
      { label: 'Рост ГФ', value: 'GF_growth' }
    ]
  },
  {
    key: 'deoptimization',
    label: 'Уровень 15. Деоптимизация',
    options: [
      { label: 'Деоптимизация', value: 'deoptimization' }
    ]
  }
]

function createDefaultClassification(levels: AnnotationClassificationLevel[] = DEFAULT_CLASSIFICATION_LEVELS): AnnotationClassification {
  return Object.fromEntries(levels.map((level) => [level.key, null]))
}

function createDefaultEpisodeForm(): EpisodeFormState {
  return {
    episodeType: '',
    classification: createDefaultClassification(),
    confidenceEvent: 'medium',
    eventActions: [],
    comment: ''
  }
}

const confidenceOptions: { label: string; value: ConfidenceLevel }[] = [
  { label: 'Низкая', value: 'low' },
  { label: 'Средняя', value: 'medium' },
  { label: 'Высокая', value: 'high' }
]

const modelFeatureGroups = [
  {
    key: 'base-signals',
    label: 'Базовые сигналы',
    features: [
      { value: 'base_qliq', label: 'Дебит жидкости' },
      { value: 'base_qoil', label: 'Дебит нефти' },
      { value: 'base_water_cut', label: 'Обводненность' },
      { value: 'base_intake_pressure', label: 'Давление на приеме' },
      { value: 'base_esp_frequency', label: 'Частота ЭЦН' },
      { value: 'base_load', label: 'Загрузка' }
    ]
  },
  {
    key: 'parameter-dynamics',
    label: 'Динамика параметров',
    features: [
      { value: 'dyn_growth', label: 'Рост' },
      { value: 'dyn_decline', label: 'Снижение' },
      { value: 'dyn_sharp_change', label: 'Резкое изменение' }
    ]
  },
  {
    key: 'behavior-patterns',
    label: 'Поведение',
    features: [
      { value: 'behavior_instability', label: 'Нестабильность' },
      { value: 'behavior_trend', label: 'Тренд' },
      { value: 'behavior_plateau', label: 'Плато' }
    ]
  },
  {
    key: 'control-actions',
    label: 'Управляющие воздействия',
    features: [
      { value: 'control_freq_change', label: 'Изменение частоты ЭЦН' },
      { value: 'control_esp_change', label: 'Смена ЭЦН' },
      { value: 'control_opz', label: 'ОПЗ' }
    ]
  },
  {
    key: 'combined-patterns',
    label: 'Комбинированные паттерны',
    features: [
      { value: 'combo_rate_drop_water_growth', label: 'Падение дебита + рост обводненности' },
      { value: 'combo_rate_drop_without_freq_change', label: 'Падение дебита без изменения частоты' },
      { value: 'combo_pressure_growth_rate_drop', label: 'Рост давления + падение дебита' },
      { value: 'combo_rate_growth_after_opz', label: 'Рост дебита после ОПЗ' }
    ]
  }
] as const

interface ModelParams {
  nur_gate_stop_h: number
  nur_min_drop_bar: number
  nur_max_d: number
  nur_max_gap_to_post: number
  uvch_stop_suppress_d: number
  uvch_rise_hz: number
  rptch_interday_std: number
  rptch_osc_hz: number
  rptch_density: number
  snizh_seg_win_d: number
  snizh_seg_drop_bar: number
  snizh_win_d: number
  snizh_win_drop: number
  stop_freq_hz: number
  stop_min_dur_min: number
  long_stop_h: number
  per_window_d: number
  per_start_n: number
  per_keep_n: number
}

type ModelParamKey = keyof ModelParams
type ModelPanelTab = 'rules' | 'quality'
type ModelRunScope = 'well' | 'group'

interface ModelParamDefinition {
  key: ModelParamKey
  label: string
  min: number
  max: number
  step: number
  unit: string
  defaultValue: number
  important?: boolean
}

interface ModelRuleCategory {
  key: string
  label: string
  color: string
  description: string
  pseudocode: string
  paramKeys: ModelParamKey[]
}

interface ModelQualityRow {
  field: string
  wells: number
  rows: string
  pct: number
  note: string
}

type PeriodSummaryPreset = 'week' | 'month' | 'year' | 'custom'
type PeriodSummaryColumnKey = keyof PeriodSummaryRow

interface PeriodSummaryColumnDefinition {
  key: PeriodSummaryColumnKey
  title: string
}

interface PersistedUiState {
  selectedWell?: string
  interactionMode?: InteractionMode
}

type GroupedSelectOption = SelectOption | {
  type: 'group'
  key: string
  label: string
  children: SelectOption[]
}

interface AnalysisWindowMetrics {
  qliq: number | null
  qoil: number | null
  intake_pressure: number | null
  water_cut: number | null
}

interface AnalysisDrillDown {
  interval: TimelineAnnotationClickPayload
  layerLabel: string
  before: AnalysisWindowMetrics
  during: AnalysisWindowMetrics
  after: AnalysisWindowMetrics
  liquidDelta: number
  oilDelta: number
  liquidImpactLabel: string
  oilImpactLabel: string
  potentialLiquid: number
  potentialOil: number
  actions: string[]
  confidence: 'Низкая' | 'Средняя' | 'Высокая'
  confidenceExplanation: string
}

const MODEL_PARAMS_STORAGE_PREFIX = 'model-params-'

const DEFAULT_MODEL_PARAMS: ModelParams = {
  nur_gate_stop_h: 12,
  nur_min_drop_bar: 2,
  nur_max_d: 30,
  nur_max_gap_to_post: 30,
  uvch_stop_suppress_d: 2,
  uvch_rise_hz: 0.3,
  rptch_interday_std: 1.0,
  rptch_osc_hz: 1.5,
  rptch_density: 0.2,
  snizh_seg_win_d: 45,
  snizh_seg_drop_bar: 4,
  snizh_win_d: 14,
  snizh_win_drop: 3,
  stop_freq_hz: 5,
  stop_min_dur_min: 30,
  long_stop_h: 12,
  per_window_d: 14,
  per_start_n: 8,
  per_keep_n: 3
}

const modelFieldGroups: { label: string; value: string }[] = [
  { label: 'Все скважины', value: 'all' },
  { label: 'Ic', value: 'Ic' },
  { label: 'Vt', value: 'Vt' },
  { label: 'Ya', value: 'Ya' },
  { label: 'Au', value: 'Au' },
  { label: 'Mc', value: 'Mc' },
  { label: 'Az', value: 'Az' }
]

const modelParamDefinitions: ModelParamDefinition[] = [
  { key: 'nur_gate_stop_h', label: 'Остановка перед НУР', min: 0.5, max: 24, step: 0.5, unit: 'ч', defaultValue: 12, important: true },
  { key: 'nur_min_drop_bar', label: 'Мин. падение давления для НУР', min: 0.5, max: 10, step: 0.5, unit: 'бар', defaultValue: 2 },
  { key: 'nur_max_d', label: 'Макс. длительность НУР', min: 5, max: 60, step: 1, unit: 'сут', defaultValue: 30 },
  { key: 'nur_max_gap_to_post', label: 'Макс. зазор до пост-режима', min: 5, max: 60, step: 1, unit: 'сут', defaultValue: 30 },
  { key: 'uvch_stop_suppress_d', label: 'Подавление УВЧ после остановки', min: 0, max: 7, step: 1, unit: 'сут', defaultValue: 2, important: true },
  { key: 'uvch_rise_hz', label: 'Рост частоты для УВЧ', min: 0.1, max: 2, step: 0.1, unit: 'Гц', defaultValue: 0.3 },
  { key: 'rptch_interday_std', label: 'Межсуточный std частоты', min: 0.3, max: 3, step: 0.1, unit: 'Гц', defaultValue: 1, important: true },
  { key: 'rptch_osc_hz', label: 'Амплитуда осцилляций РПТЧ', min: 0.5, max: 5, step: 0.5, unit: 'Гц', defaultValue: 1.5 },
  { key: 'rptch_density', label: 'Плотность РПТЧ', min: 0.05, max: 0.5, step: 0.05, unit: '', defaultValue: 0.2 },
  { key: 'snizh_seg_win_d', label: 'Окно сегмента снижения', min: 20, max: 90, step: 5, unit: 'сут', defaultValue: 45, important: true },
  { key: 'snizh_seg_drop_bar', label: 'Падение сегмента', min: 1, max: 15, step: 0.5, unit: 'бар', defaultValue: 4 },
  { key: 'snizh_win_d', label: 'Окно локального снижения', min: 7, max: 30, step: 1, unit: 'сут', defaultValue: 14 },
  { key: 'snizh_win_drop', label: 'Падение локального окна', min: 1, max: 10, step: 0.5, unit: 'бар', defaultValue: 3 },
  { key: 'stop_freq_hz', label: 'Порог остановки по частоте', min: 0.5, max: 15, step: 0.5, unit: 'Гц', defaultValue: 5 },
  { key: 'stop_min_dur_min', label: 'Минимальная длительность остановки', min: 5, max: 120, step: 5, unit: 'мин', defaultValue: 30 },
  { key: 'long_stop_h', label: 'Длинная остановка', min: 2, max: 48, step: 1, unit: 'ч', defaultValue: 12 },
  { key: 'per_window_d', label: 'Окно периодической работы', min: 7, max: 30, step: 1, unit: 'сут', defaultValue: 14 },
  { key: 'per_start_n', label: 'Порог старта периодики', min: 3, max: 15, step: 1, unit: '', defaultValue: 8 },
  { key: 'per_keep_n', label: 'Порог удержания периодики', min: 1, max: 8, step: 1, unit: '', defaultValue: 3 }
]

const modelParamDefinitionByKey = Object.fromEntries(modelParamDefinitions.map((item) => [item.key, item])) as Record<
  ModelParamKey,
  ModelParamDefinition
>

const modelRuleCategories: ModelRuleCategory[] = [
  {
    key: 'stop',
    label: 'Работа / Остановка',
    color: '#E24B4A',
    description: 'Базовое разделение временного ряда на работу и остановку по частоте ЭЦН.',
    pseudocode: 'Остановка = freq_hz < stop_freq_hz\nесли длительность >= stop_min_dur_min\nlong_stop = duration_h >= long_stop_h',
    paramKeys: ['stop_freq_hz', 'stop_min_dur_min', 'long_stop_h']
  },
  {
    key: 'uvch',
    label: 'УВЧ',
    color: '#7F77DD',
    description: 'Фиксация устойчивого повышения частоты без признаков РПТЧ.',
    pseudocode: 'УВЧ = рост частоты >= uvch_rise_hz\nостановки подавляют УВЧ на uvch_stop_suppress_d сут',
    paramKeys: ['uvch_stop_suppress_d', 'uvch_rise_hz']
  },
  {
    key: 'rptch',
    label: 'РПТЧ',
    color: '#D85A30',
    description: 'Выделение частотного регулирования по плотности и вариативности изменения частоты.',
    pseudocode: 'rptch_raw = std(freq_hz) >= rptch_interday_std\nили oscillation >= rptch_osc_hz\nесли плотность >= rptch_density',
    paramKeys: ['rptch_interday_std', 'rptch_osc_hz', 'rptch_density']
  },
  {
    key: 'nur',
    label: 'НУР',
    color: '#639922',
    description: 'Нестабильный установившийся режим по вариативности скорости давления.',
    pseudocode: 'НУР после остановки >= nur_gate_stop_h\nи падение Рпр >= nur_min_drop_bar\nдлительность <= nur_max_d',
    paramKeys: ['nur_gate_stop_h', 'nur_min_drop_bar', 'nur_max_d', 'nur_max_gap_to_post']
  },
  {
    key: 'periodic',
    label: 'Периодическая работа',
    color: '#378ADD',
    description: 'Повторяющиеся остановки и пуски в заданном диапазоне периодов.',
    pseudocode: 'в окне per_window_d\nstart если остановок >= per_start_n\nkeep если остановок >= per_keep_n',
    paramKeys: ['per_window_d', 'per_start_n', 'per_keep_n']
  },
  {
    key: 'snizh',
    label: 'Снижение давления',
    color: '#185FA5',
    description: 'Снижение давления на сегментном и локальном окнах.',
    pseudocode: 'сегмент: окно snizh_seg_win_d, падение snizh_seg_drop_bar\nлокально: окно snizh_win_d, падение snizh_win_drop',
    paramKeys: ['snizh_seg_win_d', 'snizh_seg_drop_bar', 'snizh_win_d', 'snizh_win_drop']
  }
]

const modelQualityRows: ModelQualityRow[] = [
  { field: 'Ic', wells: 8, rows: '29.8K', pct: 51, note: 'иерархическая разметка' },
  { field: 'Vt', wells: 7, rows: '27.7K', pct: 32, note: 'иерархическая разметка' },
  { field: 'Ya', wells: 19, rows: '103.7K', pct: 100, note: 'только Работа/Остановка' },
  { field: 'Au', wells: 5, rows: '29.9K', pct: 100, note: 'только Работа/Остановка' },
  { field: 'Mc', wells: 6, rows: '29.5K', pct: 100, note: 'только Работа/Остановка' },
  { field: 'Az', wells: 7, rows: '28.0K', pct: 100, note: 'только Работа/Остановка' }
]

const periodSummaryPeriodOptions: { label: string; value: PeriodSummaryPreset }[] = [
  { label: 'Неделя', value: 'week' },
  { label: 'Месяц', value: 'month' },
  { label: 'Год', value: 'year' },
  { label: 'Свой период', value: 'custom' }
]

const periodSummaryColumnDefinitions: PeriodSummaryColumnDefinition[] = [
  { key: 'field_code', title: 'Месторождение' },
  { key: 'well_id', title: 'Скважина' },
  { key: 'category', title: 'Категория' },
  { key: 'interval_start', title: 'Начало интервала' },
  { key: 'interval_end', title: 'Конец интервала' },
  { key: 'duration_days', title: 'Длит., сут' },
  { key: 'stop_qliq', title: 'Остановочный Qж' },
  { key: 'qliq_1', title: 'Qж1' },
  { key: 'qliq_2', title: 'Qж2' },
  { key: 'qoil_1', title: 'Qнефти1' },
  { key: 'qoil_2', title: 'Qнефти2' },
  { key: 'water_cut_1', title: 'Обводненность1' },
  { key: 'water_cut_2', title: 'Обводненность2' },
  { key: 'intake_pressure_1', title: 'Рпр1' },
  { key: 'intake_pressure_2', title: 'Рпр2' },
  { key: 'frequency_1', title: 'F1' },
  { key: 'frequency_2', title: 'F2' },
  { key: 'load_1', title: 'Загрузка1' },
  { key: 'load_2', title: 'Загрузка2' },
  { key: 'gas_factor_1', title: 'ГФ1' },
  { key: 'gas_factor_2', title: 'ГФ2' },
  { key: 'bdpv_1', title: 'БДПВ1' },
  { key: 'bdpv_2', title: 'БДПВ2' },
  { key: 'delta_qliq', title: 'dQж' },
  { key: 'delta_qoil', title: 'dQн' },
  { key: 'accumulated_qliq', title: 'Накопл. dQж' },
  { key: 'accumulated_qoil', title: 'Накопл. dQн' }
]

const defaultPeriodSummaryFilters = Object.fromEntries(
  periodSummaryColumnDefinitions.map((column) => [column.key, ''])
) as Record<PeriodSummaryColumnKey, string>

function getEpisodeTypeLabel(value: EpisodeType): string {
  return episodeTypeOptions.value.find((option) => option.value === value)?.label ?? value
}

function getClassificationOptionLabel(level: AnnotationClassificationLevel, value: string | null | undefined): string | null {
  if (!value) {
    return null
  }

  return level.options.find((option) => option.value === value)?.label ?? value
}

function setClassificationValue(levelKey: string, value: string | null): void {
  const normalizedValue = typeof value === 'string' && value.trim() ? value.trim() : null
  episodeForm.value.classification = {
    ...episodeForm.value.classification,
    [levelKey]: normalizedValue
  }
}

function ensureClassificationOption(levelKey: string): void {
  const rawValue = episodeForm.value.classification[levelKey]
  const value = typeof rawValue === 'string' ? rawValue.trim() : ''
  if (!value) {
    setClassificationValue(levelKey, null)
    return
  }

  const levelIndex = classificationLevels.value.findIndex((level) => level.key === levelKey)
  if (levelIndex < 0) {
    return
  }

  const level = classificationLevels.value[levelIndex]
  if (!level) {
    return
  }
  const existingOption = level.options.find((option) =>
    [option.value, option.label].some((candidate) => candidate.toLocaleLowerCase('ru') === value.toLocaleLowerCase('ru'))
  )

  if (existingOption) {
    setClassificationValue(levelKey, existingOption.value)
    return
  }

  const nextOption = { label: value, value }
  const nextLevel: AnnotationClassificationLevel = {
    ...level,
    options: [...level.options, nextOption].sort((left, right) => left.label.localeCompare(right.label, 'ru'))
  }
  classificationLevels.value = classificationLevels.value.map((item, index) => (index === levelIndex ? nextLevel : item))
  setClassificationValue(levelKey, nextOption.value)
}

function ensureDraftClassificationOptions(): void {
  classificationLevels.value.forEach((level) => ensureClassificationOption(level.key))
}

function buildClassificationLabel(
  classification: AnnotationClassification,
  levels: AnnotationClassificationLevel[] = classificationLevels.value
): string {
  const parts = levels
    .map((level) => {
      const valueLabel = getClassificationOptionLabel(level, classification[level.key])
      return valueLabel ? `${level.label}: ${valueLabel}` : null
    })
    .filter((value): value is string => Boolean(value))

  return parts.length > 0 ? parts.join('; ') : 'Без классификации'
}

function buildDraftEpisodeLabel(): string {
  return buildClassificationLabel(episodeForm.value.classification)
}

function getAnnotationClassificationLabel(annotation: SavedAnnotation): string {
  return buildClassificationLabel(annotation.classification)
}

function getWellGroupLabel(value: WellGroupId | null | undefined): string {
  if (!value) {
    return 'Не назначена'
  }

  return wellGroupOptions.value.find((option) => option.value === value)?.label ?? value
}

function normalizeModelParams(value: unknown): Partial<ModelParams> {
  if (!value || typeof value !== 'object') {
    return {}
  }

  const source = value as Record<string, unknown>
  const normalized: Partial<ModelParams> = {}
  modelParamDefinitions.forEach((definition) => {
    const rawValue = source[definition.key]
    if (typeof rawValue !== 'number' || Number.isNaN(rawValue)) {
      return
    }

    normalized[definition.key] = Math.min(definition.max, Math.max(definition.min, rawValue)) as never
  })

  return normalized
}

function toModelParamsPayload(params: Partial<ModelParams>): Record<string, number> {
  return Object.fromEntries(Object.entries(params).filter((entry): entry is [string, number] => typeof entry[1] === 'number'))
}

async function loadModelParamsFromBackend(): Promise<void> {
  try {
    const state = await fetchModelParamsState()
    modelParamsByGroup.value = Object.fromEntries(
      Object.entries(state.overrides).map(([key, value]) => [key, normalizeModelParams(value)])
    )
  } catch {
    message.warning('Не удалось загрузить настройки модели с backend.')
  }
}

function getCurrentModelTargetId(): string {
  return modelRunScope.value === 'well' ? selectedWell.value : modelSelectedGroupId.value
}

function getModelTargetFieldId(targetId: string): string | null {
  if (!targetId || targetId === 'all') {
    return null
  }

  return targetId.includes('_') ? getWellFieldCodeFromId(targetId) : targetId
}

function getInheritedModelParams(targetId: string): ModelParams {
  const allOverrides = modelParamsByGroup.value.all ?? {}
  const fieldId = getModelTargetFieldId(targetId)
  const fieldOverrides = targetId !== fieldId && fieldId ? (modelParamsByGroup.value[fieldId] ?? {}) : {}

  return {
    ...DEFAULT_MODEL_PARAMS,
    ...allOverrides,
    ...fieldOverrides
  }
}

function getResolvedModelParams(targetId: string): ModelParams {
  return {
    ...getInheritedModelParams(targetId),
    ...(modelParamsByGroup.value[targetId] ?? {})
  }
}

function getCurrentModelOverrides(): Partial<ModelParams> {
  return modelParamsByGroup.value[getCurrentModelTargetId()] ?? {}
}

function getModelParamValue(key: ModelParamKey): number {
  return currentModelParams.value[key]
}

function hasModelParamOverride(key: ModelParamKey): boolean {
  return Object.prototype.hasOwnProperty.call(getCurrentModelOverrides(), key)
}

function getModelParamInheritedValue(key: ModelParamKey): number {
  return getInheritedModelParams(getCurrentModelTargetId())[key]
}

function setModelParamValue(key: ModelParamKey, value: number): void {
  const definition = modelParamDefinitionByKey[key]
  const roundedValue = Number(value.toFixed(definition.step < 1 ? 2 : 0))
  const nextValue = Math.min(definition.max, Math.max(definition.min, roundedValue))
  const targetId = getCurrentModelTargetId()
  const currentOverrides = modelParamsByGroup.value[targetId] ?? {}
  const inheritedValue = getInheritedModelParams(targetId)[key]
  const nextOverrides = { ...currentOverrides }

  if (nextValue === inheritedValue) {
    delete nextOverrides[key]
  } else {
    nextOverrides[key] = nextValue as never
  }

  modelParamsByGroup.value = {
    ...modelParamsByGroup.value,
    [targetId]: nextOverrides
  }
}

function resetModelParamValue(key: ModelParamKey): void {
  const targetId = getCurrentModelTargetId()
  const nextOverrides = { ...(modelParamsByGroup.value[targetId] ?? {}) }
  delete nextOverrides[key]
  modelParamsByGroup.value = {
    ...modelParamsByGroup.value,
    [targetId]: nextOverrides
  }
}

function formatModelParamValue(parameter: ModelParamDefinition, value: number): string {
  const formattedValue = parameter.step < 1 ? value.toFixed(1) : String(value)
  return parameter.unit ? `${formattedValue} ${parameter.unit}` : formattedValue
}

function getModelGroupLabel(groupId: string): string {
  return modelFieldGroups.find((group) => group.value === groupId)?.label ?? groupId
}

function hasModelGroupOverrides(groupId: string): boolean {
  return Object.keys(modelParamsByGroup.value[groupId] ?? {}).length > 0
}

function hasModelCategoryOverrides(category: ModelRuleCategory): boolean {
  const overrides = getCurrentModelOverrides()
  return category.paramKeys.some((key) => Object.prototype.hasOwnProperty.call(overrides, key))
}

function selectModelRuleCategory(categoryKey: string): void {
  modelSelectedCategoryKey.value = categoryKey
  modelPanelTab.value = 'rules'
}

function showModelChanges(): void {
  const count = modelChangedRows.value.length
  message.info(count > 0 ? `Изменённых параметров: ${count}. Список показан справа.` : 'Изменений относительно базовых значений нет.')
}

function isInteractionModeValue(value: unknown): value is InteractionMode {
  return value === 'navigate' || value === 'annotate' || value === 'modelTuning' || value === 'periodSummary'
}

function loadPersistedUiState(): PersistedUiState {
  try {
    const rawValue = localStorage.getItem(UI_STATE_STORAGE_KEY)
    if (!rawValue) {
      return {}
    }

    const parsedValue = JSON.parse(rawValue) as PersistedUiState
    return {
      selectedWell: typeof parsedValue.selectedWell === 'string' ? parsedValue.selectedWell : undefined,
      interactionMode: isInteractionModeValue(parsedValue.interactionMode) ? parsedValue.interactionMode : undefined
    }
  } catch {
    return {}
  }
}

function persistUiState(): void {
  try {
    localStorage.setItem(
      UI_STATE_STORAGE_KEY,
      JSON.stringify({
        selectedWell: selectedWell.value,
        interactionMode: interactionMode.value
      })
    )
  } catch {
    // Пользовательская разметка важнее UI-предпочтений: ошибку localStorage здесь можно игнорировать.
  }
}

const persistedUiState = loadPersistedUiState()
const selectedWell = ref(persistedUiState.selectedWell || DEFAULT_WELL_ID)
const navigationGroupId = ref<WellGroupId | null>(getFieldGroupId(getWellFieldCodeFromId(selectedWell.value || DEFAULT_FIELD_CODE)))
const dateRange = ref<[number, number] | null>(null)
const defaultActiveSeries: SeriesKey[] = [
  'qliq',
  'load',
  'water_cut_algorithm',
  'water_cut_hal',
  'intake_pressure',
  'esp_frequency',
  'active_power'
]
const activeSeries = ref<SeriesKey[]>(defaultActiveSeries)
const chartData = ref<TimeSeriesPoint[]>([])
const trMonitoringData = ref<TrMonitoringPoint[]>([])
const vspPeriods = ref<VspPeriod[]>([])
const artificialLiftPeriods = ref<EspInstallationPeriod[]>([])
const candidateAutoEpisodeIntervals = ref<EventInterval[]>([])
const selectedInterval = ref<SelectedInterval | null>(null)
const selectedAnalysisInterval = ref<TimelineAnnotationClickPayload | null>(null)
const selectedCandidateAutoAnnotation = ref<TimelineAnnotationClickPayload | null>(null)
const visibleDateRange = ref<VisibleDateRange | null>(null)
const interactionMode = ref<InteractionMode>(persistedUiState.interactionMode ?? 'navigate')
const episodeForm = ref<EpisodeFormState>(createDefaultEpisodeForm())
const modelSelectedGroupId = ref<string>(getWellFieldCodeFromId(selectedWell.value || DEFAULT_FIELD_CODE))
const modelSelectedCategoryKey = ref('stop')
const modelPanelTab = ref<ModelPanelTab>('rules')
const modelRunScope = ref<ModelRunScope>('well')
const copySettingsFromGroupId = ref<WellGroupId | null>(null)
const selectedModelFeatures = ref<string[]>([
  'base_qliq',
  'base_qoil',
  'base_water_cut',
  'dyn_decline',
  'behavior_instability',
  'behavior_trend',
  'control_freq_change',
  'control_esp_change',
  'control_opz',
  'combo_rate_drop_water_growth',
  'combo_rate_drop_without_freq_change',
  'combo_pressure_growth_rate_drop',
  'combo_rate_growth_after_opz'
])
const modelParamsByGroup = ref<Record<string, Partial<ModelParams>>>({})
const modelQualityByGroup = ref<Record<string, number>>({})
const wellGroupOptions = ref(baseWellGroupOptions)
const wellGroupAssignments = ref<Record<string, WellGroupId | null>>({})
const savedAnnotations = ref<SavedAnnotation[]>([])
const autoEpisodeReviews = ref<AutoEpisodeReview[]>([])
const episodeTypeOptions = ref<AnnotationClassOption[]>([])
const actionOptions = ref<AnnotationClassOption[]>([])
const classificationLevels = ref<AnnotationClassificationLevel[]>([...DEFAULT_CLASSIFICATION_LEVELS])
const manualFrequencyBreakpoints = ref<FrequencyBreakpoint[]>([])
const suppressedFrequencyBreakpoints = ref<FrequencyBreakpointSuppression[]>([])
const editingAnnotationId = ref<string | null>(null)
const editingAnnotationKind = ref<AnnotationKind | null>(null)
const autoEpisodeErrorType = ref<AutoEpisodeErrorType>('full')
const autoEpisodeErrorComment = ref('')
const selectedFrequencyBreakpointId = ref<string | null>(null)
const selectedFrequencySegmentIds = ref<string[]>([])
const additiveFrequencySelectionArmed = ref(false)
const eventActionSelectOpen = ref(false)
const groupSaveFeedback = ref<'idle' | 'saved'>('idle')
const groupMigrationTarget = ref<WellGroupId | typeof CREATE_NEW_GROUP_OPTION | null>(null)
const newGroupName = ref('')
const newEpisodeClassName = ref('')
const newEventActionName = ref('')
const loading = ref(false)
const initialDataLoaded = ref(false)
const graphDataExporting = ref(false)
const manualGraphDataExporting = ref(false)
const wellGraphDataExporting = ref(false)
const periodSummaryPreset = ref<PeriodSummaryPreset>('week')
const periodSummaryFieldCode = ref<string>('all')
const periodSummaryWellId = ref<string>('all')
const periodSummaryDateRange = ref<[number, number] | null>(null)
const periodSummaryRows = ref<PeriodSummaryRow[]>([])
const periodSummaryLoading = ref(false)
const periodSummaryError = ref('')
const periodSummaryMeta = ref({
  period_start: '',
  period_end: '',
  window_days: 0
})
const periodSummaryFilters = ref<Record<PeriodSummaryColumnKey, string>>({ ...defaultPeriodSummaryFilters })
const errorMessage = ref('')
const wellContext = ref<WellContext | null>(null)
const markupLoaded = ref(false)
const markupSaveState = ref<'idle' | 'saving' | 'saved' | 'error'>('idle')
const useMockTelemetry = import.meta.env.VITE_USE_MOCK_TELEMETRY === 'true'
const useMockEvents = import.meta.env.VITE_USE_MOCK_EVENTS === 'true'
const minTrChartStartDate = '2024-11-01'

function buildContextTracks(context: WellContext | null): Pick<HierarchicalEventTracks, 'opzEvents' | 'gtmEvents' | 'gdiEvents'> {
  if (!context || context.wellId !== selectedWell.value) {
    return {
      opzEvents: [],
      gtmEvents: [],
      gdiEvents: []
    }
  }

  return {
    opzEvents: context.opz.map((item): OpzEventFlag => ({
      id: item.id,
      date: item.date,
      operationType: item.operationType,
      category: item.category,
      composition: item.composition,
      volume: item.volume,
      capexOpex: item.capexOpex,
      comment: item.comment
    })),
    gtmEvents: context.gtm.map((item) => ({
      id: item.id,
      date: item.startDate,
      startDate: item.startDate,
      endDate: item.endDate,
      operationType: item.operationType,
      comment: item.comment,
      durationDays: item.durationDays,
      oilBefore: item.oilBefore,
      liquidBefore: item.liquidBefore,
      waterCutBefore: item.waterCutBefore,
      oilAfter: item.oilAfter,
      liquidAfter: item.liquidAfter,
      waterCutAfter: item.waterCutAfter
    })),
    gdiEvents: context.gdi.map((item) => ({
      id: item.id,
      date: item.endDate,
      startDate: item.startDate,
      endDate: item.endDate,
      operationType: item.operationType,
      acceptedVdpPressure: item.acceptedVdpPressure,
      productivityVogel: item.productivityVogel,
      quality: item.quality,
      comment: item.comment,
      executor: item.executor,
      durationHours: item.durationHours
    }))
  }
}

const eventTracks = computed(() => {
  const tracks = useMockEvents ? generateOldMockEventTracks(chartData.value) : generateMockEventTracksV2(chartData.value)
  const contextTracks = buildContextTracks(wellContext.value)
  const hasCurrentContext = wellContext.value?.wellId === selectedWell.value

  return {
    ...tracks,
    installedEspPeriods: artificialLiftPeriods.value,
    opzEvents: hasCurrentContext ? contextTracks.opzEvents : tracks.opzEvents,
    espWashEvents: hasCurrentContext ? [] : tracks.espWashEvents,
    gtmEvents: contextTracks.gtmEvents,
    gdiEvents: contextTracks.gdiEvents,
    dailyCauses: [],
    candidateModelEventIntervals: candidateAutoEpisodeIntervals.value
  }
})
const groupMigrationOptions = computed(() => [
  ...wellGroupOptions.value,
  { label: 'Создать новую группу...', value: CREATE_NEW_GROUP_OPTION }
])
const filteredWellOptions = computed(() => {
  if (!navigationGroupId.value) {
    return wellOptions.value
  }

  return wellOptions.value.filter((option) => wellGroupAssignments.value[option.value] === navigationGroupId.value)
})
const currentWellGroupId = computed<WellGroupId | null>(() => wellGroupAssignments.value[selectedWell.value] ?? null)
const currentWellGroupLabel = computed(() => getWellGroupLabel(currentWellGroupId.value))
const currentModelTargetId = computed(() => getCurrentModelTargetId())
const currentModelParams = computed(() => getResolvedModelParams(currentModelTargetId.value))
const activeModelRuleCategory = computed<ModelRuleCategory>(
  () => modelRuleCategories.find((category) => category.key === modelSelectedCategoryKey.value) ?? modelRuleCategories[0]!
)
const activeModelRuleParameters = computed(() =>
  activeModelRuleCategory.value.paramKeys.map((key) => modelParamDefinitionByKey[key])
)
const modelChangedRows = computed(() =>
  modelParamDefinitions
    .filter((parameter) => hasModelParamOverride(parameter.key))
    .map((parameter) => ({
      key: parameter.key,
      label: parameter.label,
      defaultValue: formatModelParamValue(parameter, getModelParamInheritedValue(parameter.key)),
      currentValue: formatModelParamValue(parameter, currentModelParams.value[parameter.key])
    }))
)
const modelQualityBeforePct = computed(() => {
  const row = modelQualityRows.find((item) => item.field.toLowerCase() === modelSelectedGroupId.value.toLowerCase())
  const baseline =
    modelSelectedGroupId.value === 'all'
      ? Math.round(modelQualityRows.reduce((sum, item) => sum + item.pct, 0) / modelQualityRows.length)
      : row?.pct ?? 45

  return modelRunScope.value === 'well' ? Math.max(0, baseline - 4) : baseline
})
const modelQualityAfterPct = computed(() => {
  const changedCount = modelChangedRows.value.length
  const categoryBoost = activeModelRuleParameters.value.length > 0 ? 2 : 0
  const scopeBoost = modelRunScope.value === 'well' ? 1 : 0
  return Math.max(0, Math.min(100, modelQualityBeforePct.value + Math.min(12, changedCount + categoryBoost + scopeBoost)))
})
const compactModelQualityRows = computed(() =>
  modelSelectedGroupId.value === 'all'
    ? modelQualityRows
    : modelQualityRows.filter((row) => row.field === modelSelectedGroupId.value)
)
const modelRunScopeLabel = computed(() =>
  modelRunScope.value === 'well'
    ? `Скважина ${selectedWell.value}`
    : `Группа ${getModelGroupLabel(modelSelectedGroupId.value)}`
)
const periodSummaryFieldOptions = computed<SelectOption[]>(() => {
  const fieldCodes = Array.from(new Set(wellOptions.value.map((option) => getWellFieldCodeFromId(option.value)))).sort((left, right) =>
    left.localeCompare(right, 'ru')
  )
  return [
    { label: 'Все месторождения', value: 'all' },
    ...fieldCodes.map((fieldCode) => ({ label: formatFieldGroupLabel(fieldCode), value: fieldCode }))
  ]
})
const periodSummaryWellOptions = computed<SelectOption[]>(() => {
  const wells = periodSummaryFieldCode.value === 'all'
    ? wellOptions.value
    : wellOptions.value.filter((option) => getWellFieldCodeFromId(option.value) === periodSummaryFieldCode.value)
  return [
    { label: 'Все скважины', value: 'all' },
    ...wells
  ]
})
const periodSummaryScopeLabel = computed(() => {
  if (periodSummaryWellId.value !== 'all') {
    return periodSummaryWellId.value
  }

  if (periodSummaryFieldCode.value !== 'all') {
    return periodSummaryFieldCode.value
  }

  return 'Все'
})
const periodSummaryFilterColumns = computed(() => periodSummaryColumnDefinitions)
const filteredPeriodSummaryRows = computed(() =>
  periodSummaryRows.value.filter((row) =>
    periodSummaryColumnDefinitions.every((column) => {
      const filterValue = periodSummaryFilters.value[column.key]?.trim().toLocaleLowerCase('ru')
      if (!filterValue) {
        return true
      }

      return formatPeriodSummaryCell(row[column.key]).toLocaleLowerCase('ru').includes(filterValue)
    })
  )
)
const periodSummaryColumns = computed<DataTableColumns<PeriodSummaryRow>>(() =>
  periodSummaryColumnDefinitions.map((column) => ({
    key: column.key,
    title: column.title,
    minWidth: column.key === 'category' ? 170 : column.key === 'well_id' ? 110 : 96,
    sorter: (leftRow, rightRow) => comparePeriodSummaryValues(leftRow[column.key], rightRow[column.key]),
    render: (row) => formatPeriodSummaryCell(row[column.key])
  }))
)
const interactionModeHint = computed(() => {
  if (interactionMode.value === 'navigate') {
    return 'Масштабирование, панорамирование и анализ'
  }

  if (interactionMode.value === 'annotate') {
    return 'Протяните мышью для выбора интервала'
  }

  if (interactionMode.value === 'periodSummary') {
    return 'Сводка категорий авторазметки за выбранный период'
  }

  return 'Настройка правил авторазметки по группе'
})
const currentTabTitle = computed(() => {
  if (interactionMode.value === 'navigate') {
    return 'Анализ скважинной динамики'
  }

  if (interactionMode.value === 'annotate') {
    return 'Разметка'
  }

  if (interactionMode.value === 'periodSummary') {
    return 'Сводка периода'
  }

  return 'Настройка модели'
})
const currentTabDescription = computed(() => {
  if (interactionMode.value === 'navigate') {
    return 'Анализ работы скважины во времени: сверху — телеметрия, снизу — сохранённые эпизоды'
  }

  if (interactionMode.value === 'annotate') {
    return 'Разметка интервалов: выделяйте начало и конец, затем сохраняйте пользовательский эпизод'
  }

  if (interactionMode.value === 'periodSummary') {
    return 'Периодическая таблица по категориям авторазметки и изменению ключевых показателей'
  }

  return 'Настройка правил авторазметки: параметры наследуются из группы «Все» и могут переопределяться по месторождению'
})
const analysisDrillDown = computed<AnalysisDrillDown | null>(() => {
  if (interactionMode.value !== 'navigate' || !selectedAnalysisInterval.value) {
    return null
  }

  const interval = selectedAnalysisInterval.value
  const windowSize = 7
  const beforeStart = getShiftedDate(interval.startDate, -windowSize)
  const beforeEnd = getShiftedDate(interval.startDate, -1)
  const afterStart = getShiftedDate(interval.endDate, 1)
  const afterEnd = getShiftedDate(interval.endDate, windowSize)

  const beforePoints = getPointsForRange(beforeStart, beforeEnd)
  const duringPoints = getPointsForRange(interval.startDate, interval.endDate)
  const afterPoints = getPointsForRange(afterStart, afterEnd)

  const before = getWindowMetrics(beforePoints)
  const during = getWindowMetrics(duringPoints)
  const after = getWindowMetrics(afterPoints)

  const baselineQliq = before.qliq ?? during.qliq ?? after.qliq ?? 0
  const baselineQoil = before.qoil ?? during.qoil ?? after.qoil ?? 0
  const targetQliq = Math.max(baselineQliq, after.qliq ?? baselineQliq)
  const targetQoil = Math.max(baselineQoil, after.qoil ?? baselineQoil)
  const durationDays = interval.durationDays
  const liquidDelta = Number(((during.qliq ?? 0) - baselineQliq).toFixed(2))
  const oilDelta = Number(((during.qoil ?? 0) - baselineQoil).toFixed(2))
  const cumulativeLiquid = Number(Math.abs(liquidDelta * durationDays).toFixed(2))
  const cumulativeOil = Number(Math.abs(oilDelta * durationDays).toFixed(2))
  const rawPotentialLiquid = Math.max(0, (targetQliq - (during.qliq ?? 0)) * durationDays)
  const rawPotentialOil = Math.max(0, (targetQoil - (during.qoil ?? 0)) * durationDays)
  const constrainedPotential = applyPotentialConstraint(rawPotentialOil, rawPotentialLiquid)
  const confidence = buildAnalysisConfidence(interval, before, during, after)

  return {
    interval,
    layerLabel: 'Эпизод',
    before,
    during,
    after,
    liquidDelta: cumulativeLiquid,
    oilDelta: cumulativeOil,
    liquidImpactLabel: liquidDelta < 0 ? 'Потеря жидкости за период' : 'Прирост жидкости за период',
    oilImpactLabel: oilDelta < 0 ? 'Потеря нефти за период' : 'Прирост нефти за период',
    potentialLiquid: constrainedPotential.liquid,
    potentialOil: constrainedPotential.oil,
    actions: interval.actions.length > 0 ? interval.actions : buildSuggestedActions(interval, before, during, after),
    confidence: confidence.level,
    confidenceExplanation: confidence.explanation
  }
})

function isInteractionMode(mode: InteractionMode): boolean {
  return interactionMode.value === mode
}

const currentWellAnnotations = computed(() => savedAnnotations.value.filter((item) => item.wellId === selectedWell.value))
const currentWellAutoEpisodeReviews = computed(() => autoEpisodeReviews.value.filter((item) => item.wellId === selectedWell.value))
const selectedCandidateAutoLevel = computed(() => {
  const levelKey = selectedCandidateAutoAnnotation.value?.classificationLevelKey
  return levelKey ? classificationLevels.value.find((level) => level.key === levelKey) ?? null : null
})
const selectedCandidateAutoConfidenceLabel = computed(() => {
  const confidence = selectedCandidateAutoAnnotation.value?.confidence
  if (confidence === null || confidence === undefined || confidence === '') {
    return ''
  }
  if (typeof confidence === 'string') {
    return confidence
  }
  if (confidence >= 0.67) {
    return 'высокая'
  }
  if (confidence >= 0.34) {
    return 'средняя'
  }
  return 'низкая'
})
const canTransferSelectedCandidateAuto = computed(() =>
  Boolean(
    selectedInterval.value &&
      selectedCandidateAutoAnnotation.value?.classificationLevelKey &&
      selectedCandidateAutoAnnotation.value?.classificationValue
  )
)
const canReviewSelectedCandidateAuto = computed(() =>
  Boolean(selectedCandidateAutoAnnotation.value?.autoEpisodeId && selectedInterval.value)
)
function getActionOptionsForDraft(): GroupedSelectOption[] {
  const selectedCategory = buildDraftEpisodeLabel()
  const usedActionValues = new Set<string>()

  if (selectedCategory) {
    savedAnnotations.value.forEach((annotation) => {
      if (getAnnotationCategory(annotation) !== selectedCategory) {
        return
      }

      getAnnotationActions(annotation).forEach((action) => {
        if (action.trim()) {
          usedActionValues.add(action)
        }
      })
    })
  }

  const optionsByValue = new Map<string, SelectOption>(actionOptions.value.map((option) => [option.value, option]))
  usedActionValues.forEach((value) => {
    if (!optionsByValue.has(value)) {
      optionsByValue.set(value, { label: value, value })
    }
  })

  const suggestedOptions = [...usedActionValues]
    .sort((left, right) => left.localeCompare(right, 'ru'))
    .map((value) => optionsByValue.get(value))
    .filter((option): option is SelectOption => Boolean(option))
  const otherOptions = actionOptions.value.filter((option) => !usedActionValues.has(option.value))

  if (suggestedOptions.length === 0) {
    return otherOptions
  }

  const groupedOptions: GroupedSelectOption[] = [
    {
      type: 'group',
      key: 'event-suggested-actions',
      label: 'Ранее для этой причины',
      children: suggestedOptions
    }
  ]

  if (otherOptions.length > 0) {
    groupedOptions.push({
      type: 'group',
      key: 'event-all-actions',
      label: 'Все мероприятия',
      children: otherOptions
    })
  }

  return groupedOptions
}
const eventActionOptionsForDraft = computed(() => getActionOptionsForDraft())
const draftEpisodeLabel = computed(() => buildDraftEpisodeLabel())
const currentManualFrequencyBreakpoints = computed(() =>
  manualFrequencyBreakpoints.value.filter((item) => item.wellId === selectedWell.value)
)
const currentSuppressedFrequencyBreakpoints = computed(() =>
  suppressedFrequencyBreakpoints.value.filter((item) => item.wellId === selectedWell.value)
)
const autoFrequencyBreakpoints = computed(() => buildAutoFrequencyBreakpoints(chartData.value, selectedWell.value))
const currentFrequencyBreakpoints = computed(() =>
  mergeFrequencyBreakpoints(
    autoFrequencyBreakpoints.value,
    currentManualFrequencyBreakpoints.value,
    currentSuppressedFrequencyBreakpoints.value
  )
)
const frequencySegments = computed(() => buildFrequencySegments(chartData.value, selectedWell.value, currentFrequencyBreakpoints.value))
const selectedFrequencySegments = computed(() => {
  const selectedIds = new Set(selectedFrequencySegmentIds.value)
  return frequencySegments.value.filter((segment) => selectedIds.has(segment.id))
})
const selectedFrequencyBreakpoint = computed<FrequencyBreakpoint | null>(() => {
  if (!selectedFrequencyBreakpointId.value) {
    return null
  }

  return currentFrequencyBreakpoints.value.find((item) => item.id === selectedFrequencyBreakpointId.value) ?? null
})
const isEditMode = computed(() => editingAnnotationId.value !== null)
const annotationPanelTitle = computed(() => {
  if (editingAnnotationKind.value === 'event') {
    return 'Редактирование эпизода'
  }

  return 'Создание аннотации'
})
const hasUnsavedChanges = computed(() => draftHasUnsavedChanges())
const DAY_MS = 86400000

const annotationBoundaryBounds = computed<VisibleDateRange | null>(() => {
  const dates = [
    chartData.value[0]?.date,
    chartData.value[chartData.value.length - 1]?.date,
    trMonitoringData.value[0]?.date,
    trMonitoringData.value[trMonitoringData.value.length - 1]?.date,
    visibleDateRange.value?.startDate,
    visibleDateRange.value?.endDate,
    selectedInterval.value?.startDate,
    selectedInterval.value?.endDate
  ].filter((value): value is string => Boolean(value))

  if (!dates.length) {
    return null
  }

  return {
    startDate: dates.reduce((minDate, value) => (value < minDate ? value : minDate)),
    endDate: dates.reduce((maxDate, value) => (value > maxDate ? value : maxDate))
  }
})

const boundarySliderMax = computed(() => {
  const bounds = annotationBoundaryBounds.value
  if (!bounds) {
    return 0
  }

  return Math.max(0, Math.floor((toTimestamp(bounds.endDate) - toTimestamp(bounds.startDate)) / DAY_MS))
})

const annotationBoundarySliderValue = computed<number[]>({
  get() {
    const bounds = annotationBoundaryBounds.value
    if (!bounds || !selectedInterval.value) {
      return [0, 0]
    }

    const startOffset = Math.floor((toTimestamp(selectedInterval.value.startDate) - toTimestamp(bounds.startDate)) / DAY_MS)
    const endOffset = Math.floor((toTimestamp(selectedInterval.value.endDate) - toTimestamp(bounds.startDate)) / DAY_MS)
    return [
      Math.max(0, Math.min(boundarySliderMax.value, startOffset)),
      Math.max(0, Math.min(boundarySliderMax.value, endOffset))
    ]
  },
  set(value) {
    const bounds = annotationBoundaryBounds.value
    if (!bounds || !selectedInterval.value || value.length < 2) {
      return
    }

    const [rawStart, rawEnd] = value
    const startOffset = Math.max(0, Math.min(boundarySliderMax.value, Math.floor(rawStart ?? 0)))
    const endOffset = Math.max(0, Math.min(boundarySliderMax.value, Math.floor(rawEnd ?? startOffset)))
    selectedInterval.value = buildInterval(
      shiftIsoDate(bounds.startDate, Math.min(startOffset, endOffset)),
      shiftIsoDate(bounds.startDate, Math.max(startOffset, endOffset))
    )
    clearFrequencySegmentSelection()
  }
})

function toDateTimeLocalValue(value: string | null | undefined): string {
  const normalizedValue = normalizeAnnotationDateTime(value)
  if (!normalizedValue) {
    return ''
  }

  return normalizedValue.slice(0, 16)
}

const selectedIntervalStartInput = computed<string>({
  get() {
    return toDateTimeLocalValue(selectedInterval.value?.startDate)
  },
  set(value) {
    if (!selectedInterval.value) {
      return
    }

    const nextStart = normalizeAnnotationDateTime(value)
    if (!nextStart) {
      return
    }

    selectedInterval.value = buildInterval(nextStart, selectedInterval.value.endDate)
    clearFrequencySegmentSelection()
  }
})

const selectedIntervalEndInput = computed<string>({
  get() {
    return toDateTimeLocalValue(selectedInterval.value?.endDate)
  },
  set(value) {
    if (!selectedInterval.value) {
      return
    }

    const nextEnd = normalizeAnnotationDateTime(value)
    if (!nextEnd) {
      return
    }

    selectedInterval.value = buildInterval(selectedInterval.value.startDate, nextEnd)
    clearFrequencySegmentSelection()
  }
})

function toIsoDate(timestamp: number | null | undefined): string | undefined {
  if (!timestamp) {
    return undefined
  }

  return new Date(timestamp).toISOString().slice(0, 10)
}

function toIsoDateKey(value: string | null | undefined): string {
  return value ? value.slice(0, 10) : ''
}

function normalizeAnnotationDateTime(value: unknown): string | null {
  const rawValue = String(value ?? '').trim()
  if (!rawValue) {
    return null
  }

  const normalizedValue = rawValue.includes('T') ? rawValue : rawValue.replace(' ', 'T')
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(normalizedValue)) {
    return normalizedValue.slice(0, 19)
  }

  if (/^\d{4}-\d{2}-\d{2}$/.test(normalizedValue)) {
    return normalizedValue
  }

  const timestamp = new Date(normalizedValue).getTime()
  return Number.isNaN(timestamp) ? null : new Date(timestamp).toISOString().slice(0, 19)
}

function loadEpisodeIntoDraft(episode: SavedAnnotation) {
  clearCandidateAutoSelection()
  selectedInterval.value = {
    startDate: episode.startDate,
    endDate: episode.endDate,
    durationDays: episode.durationDays
  }
  episodeForm.value = {
    episodeType: episode.eventType,
    classification: { ...createDefaultClassification(classificationLevels.value), ...episode.classification },
    confidenceEvent: episode.confidenceEvent,
    eventActions: episode.actions ?? [],
    comment: episode.comment
  }
  editingAnnotationId.value = episode.id
  editingAnnotationKind.value = episode.annotationKind
  selectedFrequencyBreakpointId.value = null
  clearFrequencySegmentSelection()
}

function clearCandidateAutoSelection(): void {
  selectedCandidateAutoAnnotation.value = null
  autoEpisodeErrorType.value = 'full'
  autoEpisodeErrorComment.value = ''
}

function loadCandidateAutoIntoDraft(payload: TimelineAnnotationClickPayload): void {
  selectedCandidateAutoAnnotation.value = payload
  selectedInterval.value = buildInterval(payload.startDate, payload.endDate)
  editingAnnotationId.value = null
  editingAnnotationKind.value = null
  selectedFrequencyBreakpointId.value = null
  clearFrequencySegmentSelection()

  const nextForm = createDefaultEpisodeForm()
  if (payload.classificationLevelKey && payload.classificationValue) {
    nextForm.classification[payload.classificationLevelKey] = payload.classificationValue
    nextForm.episodeType = resolveCandidateAutoEventType(payload)
  } else {
    nextForm.episodeType = payload.label
  }
  episodeForm.value = nextForm

  const review = currentWellAutoEpisodeReviews.value.find(
    (item) =>
      item.autoEpisodeId === payload.autoEpisodeId &&
      item.startDate === payload.startDate &&
      item.endDate === payload.endDate &&
      item.label === payload.label &&
      (item.sourceVersion ?? '') === (payload.sourceVersion ?? '')
  )
  autoEpisodeErrorType.value = review?.errorType ?? 'full'
  autoEpisodeErrorComment.value = review?.comment ?? ''
}

function subtractMonthsIsoDate(date: string, months: number): string {
  const nextDate = new Date(`${toIsoDateKey(date)}T00:00:00`)
  nextDate.setMonth(nextDate.getMonth() - months)

  return nextDate.toISOString().slice(0, 10)
}

function getFullDateRange(data: TimeSeriesPoint[], trData: TrMonitoringPoint[] = []): VisibleDateRange | null {
  const startDate = toIsoDateKey(data[0]?.date)
  const endDates = [
    toIsoDateKey(data[data.length - 1]?.date),
    toIsoDateKey(trData[trData.length - 1]?.date)
  ].filter((value): value is string => Boolean(value))

  if (!startDate || !endDates.length) {
    return null
  }

  const twoMonthsBeforeTelemetry = subtractMonthsIsoDate(startDate, 2)
  const chartStartDate = twoMonthsBeforeTelemetry < minTrChartStartDate ? minTrChartStartDate : twoMonthsBeforeTelemetry
  const endDate = endDates.reduce((maxDate, value) => (value > maxDate ? value : maxDate))

  return { startDate: chartStartDate, endDate }
}

function createAnnotationId(kind: AnnotationKind): string {
  return `${kind}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function createFrequencyBreakpointId(source: FrequencyBreakpoint['source'], wellId: string, date?: string): string {
  const suffix = date ? date.replace(/-/g, '') : `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  return `frequency-${source}-${wellId}-${suffix}`
}

function toTimestamp(value: string): number {
  const normalizedValue = normalizeAnnotationDateTime(value)
  const match = normalizedValue?.match(
    /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2})(?::(\d{2})(?::(\d{2}))?)?)?$/
  )

  if (match) {
    return Date.UTC(
      Number(match[1]),
      Number(match[2]) - 1,
      Number(match[3]),
      Number(match[4] ?? 0),
      Number(match[5] ?? 0),
      Number(match[6] ?? 0)
    )
  }

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
  const durationMs = Math.max(0, toTimestamp(normalizedEnd) - toTimestamp(normalizedStart))

  return {
    startDate: normalizedStart,
    endDate: normalizedEnd,
    durationDays: Number(Math.max(durationMs / 86400000, 1 / 1440).toFixed(3))
  }
}

function snapDateToClosestBoundary(date: string, candidates: string[]): string {
  const timestamp = toTimestamp(date)
  if (!Number.isFinite(timestamp)) {
    return date
  }

  let closestDate = date
  let closestDistance = ANNOTATION_SNAP_THRESHOLD_MS + 1

  candidates.forEach((candidate) => {
    const candidateTimestamp = toTimestamp(candidate)
    if (!Number.isFinite(candidateTimestamp)) {
      return
    }

    const distance = Math.abs(candidateTimestamp - timestamp)
    if (distance <= ANNOTATION_SNAP_THRESHOLD_MS && distance < closestDistance) {
      closestDate = candidate
      closestDistance = distance
    }
  })

  return closestDate
}

function snapIntervalToAnnotationBoundaries(interval: SelectedInterval): SelectedInterval {
  const annotations = currentWellAnnotations.value.filter((annotation) => annotation.id !== editingAnnotationId.value)
  if (annotations.length === 0) {
    return interval
  }

  const boundaryCandidates = annotations.flatMap((annotation) => [
    annotation.startDate,
    annotation.endDate
  ])

  return buildInterval(
    snapDateToClosestBoundary(interval.startDate, boundaryCandidates),
    snapDateToClosestBoundary(interval.endDate, boundaryCandidates)
  )
}

function normalizeFrequencyValue(value: number | null | undefined): number | null {
  return Number.isFinite(value) ? Number(value) : null
}

function isPositiveFrequency(value: number | null): boolean {
  return value !== null && value > 0
}

function formatFrequencyValue(value: number | null): string {
  return value === null ? 'нет данных' : `${Number(value.toFixed(2))}`
}

function upsertAutoBreakpoint(
  breakpointsByDate: Map<string, FrequencyBreakpoint>,
  breakpoint: FrequencyBreakpoint
): void {
  const existingBreakpoint = breakpointsByDate.get(breakpoint.date)

  if (!existingBreakpoint) {
    breakpointsByDate.set(breakpoint.date, breakpoint)
    return
  }

  breakpointsByDate.set(breakpoint.date, {
    ...existingBreakpoint,
    reason: `${existingBreakpoint.reason}; ${breakpoint.reason}`,
    fromFrequency: existingBreakpoint.fromFrequency ?? breakpoint.fromFrequency,
    toFrequency: existingBreakpoint.toFrequency ?? breakpoint.toFrequency
  })
}

function buildAutoFrequencyBreakpoints(data: TimeSeriesPoint[], wellId: string): FrequencyBreakpoint[] {
  const breakpointsByDate = new Map<string, FrequencyBreakpoint>()
  let previousPoint: { date: string; frequency: number } | null = null

  data.forEach((point) => {
    const frequency = normalizeFrequencyValue(point.esp_frequency)

    if (frequency === null) {
      return
    }

    if (previousPoint) {
      const previousFrequency = previousPoint.frequency
      const previousIsPositive = isPositiveFrequency(previousFrequency)
      const currentIsPositive = isPositiveFrequency(frequency)
      let breakpointDate = ''
      let reason = ''

      if (!previousIsPositive && currentIsPositive) {
        breakpointDate = point.date
        reason = `Переход частоты ЭЦН от 0 до ${formatFrequencyValue(frequency)}`
      } else if (previousIsPositive && !currentIsPositive) {
        breakpointDate = previousPoint.date
        reason = `Переход частоты ЭЦН от ${formatFrequencyValue(previousFrequency)} до 0`
      } else if (previousIsPositive && currentIsPositive) {
        if (frequency > previousFrequency) {
          const increaseRatio = (frequency - previousFrequency) / previousFrequency
          if (increaseRatio >= FREQUENCY_CHANGE_THRESHOLD) {
            breakpointDate = point.date
            reason = `Рост частоты ЭЦН на ${Math.round(increaseRatio * 100)}%`
          }
        } else if (frequency < previousFrequency) {
          const previousWasHigherRatio = (previousFrequency - frequency) / frequency
          if (previousWasHigherRatio >= FREQUENCY_CHANGE_THRESHOLD) {
            breakpointDate = previousPoint.date
            reason = `Снижение частоты ЭЦН: предыдущая частота выше на ${Math.round(previousWasHigherRatio * 100)}%`
          }
        }
      }

      if (breakpointDate && reason) {
        upsertAutoBreakpoint(breakpointsByDate, {
          id: createFrequencyBreakpointId('auto', wellId, breakpointDate),
          wellId,
          date: breakpointDate,
          source: 'auto',
          reason,
          fromFrequency: previousFrequency,
          toFrequency: frequency
        })
      }
    }

    previousPoint = {
      date: point.date,
      frequency
    }
  })

  return [...breakpointsByDate.values()].sort((left, right) => left.date.localeCompare(right.date))
}

function mergeFrequencyBreakpoints(
  autoBreakpoints: FrequencyBreakpoint[],
  manualBreakpoints: FrequencyBreakpoint[],
  suppressedBreakpoints: FrequencyBreakpointSuppression[]
): FrequencyBreakpoint[] {
  const suppressedDates = new Set(suppressedBreakpoints.map((item) => item.date))
  const breakpointsByDate = new Map<string, FrequencyBreakpoint>()

  autoBreakpoints.forEach((breakpoint) => {
    if (!suppressedDates.has(breakpoint.date)) {
      breakpointsByDate.set(breakpoint.date, breakpoint)
    }
  })

  manualBreakpoints.forEach((breakpoint) => {
    breakpointsByDate.set(breakpoint.date, breakpoint)
  })

  return [...breakpointsByDate.values()].sort((left, right) => left.date.localeCompare(right.date))
}

function buildFrequencySegments(
  data: TimeSeriesPoint[],
  wellId: string,
  breakpoints: FrequencyBreakpoint[]
): FrequencySegment[] {
  const fullRange = getFullDateRange(data)

  if (!fullRange) {
    return []
  }

  const boundaryDates = [
    fullRange.startDate,
    ...breakpoints.map((breakpoint) => breakpoint.date).filter((date) => date > fullRange.startDate && date <= fullRange.endDate)
  ]
  const uniqueBoundaryDates = [...new Set(boundaryDates)].sort()

  return uniqueBoundaryDates
    .map((startDate, index) => {
      const nextBoundaryDate = uniqueBoundaryDates[index + 1]
      const endDate = nextBoundaryDate ? shiftIsoDate(nextBoundaryDate, -1) : fullRange.endDate

      if (endDate < startDate) {
        return null
      }

      const interval = buildInterval(startDate, endDate)
      return {
        id: `frequency-segment-${wellId}-${interval.startDate}-${interval.endDate}`,
        wellId,
        ...interval
      }
    })
    .filter((segment): segment is FrequencySegment => Boolean(segment))
}

function readStoredValue<T>(key: string, fallbackValue: T): T {
  try {
    const rawValue = localStorage.getItem(key)
    return rawValue ? (JSON.parse(rawValue) as T) : fallbackValue
  } catch {
    return fallbackValue
  }
}

function normalizeClassOptions(options: unknown): AnnotationClassOption[] {
  if (!Array.isArray(options)) {
    return []
  }

  const seenValues = new Set<string>()

  return options
    .map((option) => ({
      label: String((option as AnnotationClassOption).label ?? '').trim(),
      value: String((option as AnnotationClassOption).value ?? (option as AnnotationClassOption).label ?? '').trim()
    }))
    .filter((option) => {
      const normalizedValue = option.value.toLocaleLowerCase('ru')

      if (!option.label || !option.value || seenValues.has(normalizedValue)) {
        return false
      }

      seenValues.add(normalizedValue)
      return true
    })
}

function normalizeClassificationOptionValue(levelKey: string, value: string): string {
  const legacyValues: Record<string, Record<string, string>> = {
    esp_degradation: { yes: 'degr_yes' },
    nur: { yes: 'nur_yes' },
    reservoir_pressure_trend: { growth: 'Pres_growth', decline: 'Pres_decline' },
    water_cut_trend: { growth: 'WCT_growth', decline: 'WCT_decline' },
    productivity_trend: { growth: 'Kprod_growth', decline: 'Kprod_decline' }
  }

  return legacyValues[levelKey]?.[value] ?? value
}

function normalizeClassificationLevels(levels: unknown): AnnotationClassificationLevel[] {
  if (!Array.isArray(levels)) {
    return [...DEFAULT_CLASSIFICATION_LEVELS]
  }

  const seenKeys = new Set<string>()
  const normalizedLevels = levels
    .map((level): AnnotationClassificationLevel | null => {
      const rawLevel = level as Partial<AnnotationClassificationLevel>
      const key = String(rawLevel.key ?? '').trim()
      const label = String(rawLevel.label ?? key).trim()
      const migratedOptionValues = new Set<string>()
      const options = normalizeClassOptions(rawLevel.options)
        .map((option) => ({
          ...option,
          value: normalizeClassificationOptionValue(key, option.value)
        }))
        .filter((option) => {
          const normalizedValue = option.value.toLocaleLowerCase('ru')
          if (migratedOptionValues.has(normalizedValue)) {
            return false
          }
          migratedOptionValues.add(normalizedValue)
          return true
        })

      return key && label
        ? {
            key,
            label,
            options,
            allowCustom: Boolean(rawLevel.allowCustom),
            placeholder: typeof rawLevel.placeholder === 'string' ? rawLevel.placeholder : undefined
          }
        : null
    })
    .filter((level): level is AnnotationClassificationLevel => {
      if (!level || seenKeys.has(level.key)) {
        return false
      }

      seenKeys.add(level.key)
      return true
    })

  DEFAULT_CLASSIFICATION_LEVELS.forEach((defaultLevel) => {
    if (!seenKeys.has(defaultLevel.key)) {
      normalizedLevels.push(defaultLevel)
    }
  })

  if (normalizedLevels.length === 0) {
    return [...DEFAULT_CLASSIFICATION_LEVELS]
  }

  const normalizedByKey = new Map(normalizedLevels.map((level) => [level.key, level]))
  const orderedLevels = DEFAULT_CLASSIFICATION_LEVELS.map((defaultLevel) => {
    const storedLevel = normalizedByKey.get(defaultLevel.key)
    if (!storedLevel) {
      return defaultLevel
    }

    return {
      ...storedLevel,
      label: defaultLevel.label,
      allowCustom: defaultLevel.allowCustom,
      placeholder: defaultLevel.placeholder
    }
  })

  const defaultKeys = new Set(DEFAULT_CLASSIFICATION_LEVELS.map((level) => level.key))
  const deprecatedKeys = new Set(['esp_mode'])
  normalizedLevels.forEach((level) => {
    if (!defaultKeys.has(level.key) && !deprecatedKeys.has(level.key)) {
      orderedLevels.push(level)
    }
  })

  return orderedLevels
}

function normalizeAnnotationClassification(
  annotation: Record<string, unknown>,
  levels: AnnotationClassificationLevel[],
  rawEventType: string
): AnnotationClassification {
  const classification = createDefaultClassification(levels)
  const rawClassification = annotation.classification

  if (rawClassification && typeof rawClassification === 'object' && !Array.isArray(rawClassification)) {
    Object.entries(rawClassification as Record<string, unknown>).forEach(([key, value]) => {
      classification[key] = typeof value === 'string' && value.trim() ? value.trim() : null
    })
  }

  if (classification.esp_degradation === 'yes') {
    classification.esp_degradation = 'degr_yes'
  }
  if (classification.esp_mode === 'uvch' && !classification.esp_uvch) {
    classification.esp_uvch = 'uvch'
  }
  if (classification.esp_mode === 'rptch' && !classification.esp_rptch) {
    classification.esp_rptch = 'rptch'
  }
  if (classification.esp_mode === 'periodic_operation' && !classification.esp_periodic) {
    classification.esp_periodic = 'periodic_operation'
  }
  classification.esp_mode = null
  if (classification.nur === 'yes') {
    classification.nur = 'nur_yes'
  }
  if (classification.reservoir_pressure_trend === 'growth') {
    classification.reservoir_pressure_trend = 'Pres_growth'
  }
  if (classification.reservoir_pressure_trend === 'decline') {
    classification.reservoir_pressure_trend = 'Pres_decline'
  }
  if (classification.water_cut_trend === 'growth') {
    classification.water_cut_trend = 'WCT_growth'
  }
  if (classification.water_cut_trend === 'decline') {
    classification.water_cut_trend = 'WCT_decline'
  }
  if (classification.productivity_trend === 'growth') {
    classification.productivity_trend = 'Kprod_growth'
  }
  if (classification.productivity_trend === 'decline') {
    classification.productivity_trend = 'Kprod_decline'
  }

  const normalizedEventType = rawEventType.toLocaleLowerCase('ru')
  if (!classification.well_state && typeof annotation.workState === 'string') {
    classification.well_state = annotation.workState === 'stop' ? 'stop' : 'work'
  }
  if (!classification.well_state && normalizedEventType.includes('останов')) {
    classification.well_state = 'stop'
  }
  if (!classification.nur && typeof annotation.hasNur === 'boolean') {
    classification.nur = annotation.hasNur ? 'nur_yes' : null
  }
  if (!classification.nur && normalizedEventType.includes('нур')) {
    classification.nur = 'nur_yes'
  }
  if (!classification.vgf && normalizedEventType.includes('вгф')) {
    classification.vgf = 'vgf_yes'
  }
  if (!classification.gas_factor_trend && normalizedEventType.includes('снижение гф')) {
    classification.gas_factor_trend = 'GF_decline'
  }
  if (!classification.gas_factor_trend && normalizedEventType.includes('рост гф')) {
    classification.gas_factor_trend = 'GF_growth'
  }
  if (
    !classification.deoptimization &&
    (
      normalizedEventType.includes('деоптимизац') ||
      normalizedEventType.includes('ограничение эцн') ||
      normalizedEventType.includes('ограничение инфраструктур')
    )
  ) {
    classification.deoptimization = 'deoptimization'
  }
  if (!classification.reservoir_pressure_trend && typeof annotation.hasReservoirPressureDecline === 'boolean') {
    classification.reservoir_pressure_trend = annotation.hasReservoirPressureDecline ? 'Pres_decline' : null
  }
  if (!classification.reservoir_pressure_trend && normalizedEventType.includes('снижение рпл')) {
    classification.reservoir_pressure_trend = 'Pres_decline'
  }
  if (!classification.reservoir_pressure_trend && normalizedEventType.includes('рост рпл')) {
    classification.reservoir_pressure_trend = 'Pres_growth'
  }

  return classification
}

function normalizeSavedAnnotations(
  annotations: unknown,
  levels: AnnotationClassificationLevel[] = classificationLevels.value
): SavedAnnotation[] {
  if (!Array.isArray(annotations)) {
    return []
  }

  return annotations
    .map((rawAnnotation): SavedAnnotation | null => {
      const annotation = rawAnnotation as Record<string, unknown>

      if (annotation.annotationKind !== 'event') {
        return null
      }

      const startDate = normalizeAnnotationDateTime(annotation.startDate)
      const endDate = normalizeAnnotationDateTime(annotation.endDate)
      if (!startDate || !endDate) {
        return null
      }

      const interval = buildInterval(startDate, endDate)
      const confidenceEvent: ConfidenceLevel =
        annotation.confidenceEvent === 'low' || annotation.confidenceEvent === 'high' ? annotation.confidenceEvent : 'medium'
      const rawEventType = String(annotation.eventType ?? '').trim()
      const classification = normalizeAnnotationClassification(annotation, levels, rawEventType)
      const eventType = rawEventType || buildClassificationLabel(classification, levels)

      return {
        id: String(annotation.id || createAnnotationId('event')),
        wellId: String(annotation.wellId ?? selectedWell.value),
        wellGroupId: typeof annotation.wellGroupId === 'string' ? annotation.wellGroupId : null,
        annotationKind: 'event',
        eventType,
        classification,
        confidenceEvent,
        comment: String(annotation.comment ?? ''),
        actions: Array.isArray(annotation.actions)
          ? annotation.actions.filter((item): item is string => typeof item === 'string')
          : [],
        ...interval
      }
    })
    .filter((annotation): annotation is SavedAnnotation => Boolean(annotation))
}

function normalizeFrequencyBreakpoints(breakpoints: unknown): FrequencyBreakpoint[] {
  if (!Array.isArray(breakpoints)) {
    return []
  }

  const seenDatesByWell = new Set<string>()

  return (breakpoints as FrequencyBreakpoint[])
    .map((breakpoint): FrequencyBreakpoint => {
      const source: FrequencyBreakpoint['source'] = breakpoint.source === 'auto' ? 'auto' : 'manual'
      const wellId = String(breakpoint.wellId ?? '').trim()
      const date = String(breakpoint.date ?? '').slice(0, 10)

      return {
        id: String(breakpoint.id || createFrequencyBreakpointId(source, wellId, date)),
        wellId,
        date,
        source,
        reason: String(breakpoint.reason ?? ''),
        fromFrequency: normalizeFrequencyValue(breakpoint.fromFrequency),
        toFrequency: normalizeFrequencyValue(breakpoint.toFrequency)
      }
    })
    .filter((breakpoint) => {
      const key = `${breakpoint.wellId}:${breakpoint.date}`

      if (!breakpoint.wellId || !/^\d{4}-\d{2}-\d{2}$/.test(breakpoint.date) || seenDatesByWell.has(key)) {
        return false
      }

      seenDatesByWell.add(key)
      return true
    })
    .sort((left, right) => left.wellId.localeCompare(right.wellId, 'ru') || left.date.localeCompare(right.date))
}

function normalizeFrequencyBreakpointSuppressions(suppressions: unknown): FrequencyBreakpointSuppression[] {
  if (!Array.isArray(suppressions)) {
    return []
  }

  const seenDatesByWell = new Set<string>()

  return (suppressions as FrequencyBreakpointSuppression[])
    .map((suppression) => ({
      id: String(suppression.id || createFrequencyBreakpointId('auto', suppression.wellId, suppression.date)),
      wellId: String(suppression.wellId ?? '').trim(),
      date: String(suppression.date ?? '').slice(0, 10)
    }))
    .filter((suppression) => {
      const key = `${suppression.wellId}:${suppression.date}`

      if (!suppression.wellId || !/^\d{4}-\d{2}-\d{2}$/.test(suppression.date) || seenDatesByWell.has(key)) {
        return false
      }

      seenDatesByWell.add(key)
      return true
    })
    .sort((left, right) => left.wellId.localeCompare(right.wellId, 'ru') || left.date.localeCompare(right.date))
}

function normalizeAutoEpisodeReviews(reviews: unknown): AutoEpisodeReview[] {
  if (!Array.isArray(reviews)) {
    return []
  }

  const seenReviews = new Set<string>()

  return (reviews as AutoEpisodeReview[])
    .map((review) => {
      const errorType: AutoEpisodeErrorType = review.errorType === 'partial' ? 'partial' : 'full'
      return {
        id: String(review.id || `auto-review-${review.wellId}-${review.autoEpisodeId}`),
        wellId: String(review.wellId ?? '').trim(),
        autoEpisodeId: String(review.autoEpisodeId ?? '').trim(),
        startDate: normalizeAnnotationDateTime(String(review.startDate ?? '')) ?? '',
        endDate: normalizeAnnotationDateTime(String(review.endDate ?? '')) ?? '',
        label: String(review.label ?? '').trim(),
        errorType,
        comment: String(review.comment ?? ''),
        sourceVersion: review.sourceVersion ? String(review.sourceVersion) : undefined,
        classificationLevelKey: review.classificationLevelKey ? String(review.classificationLevelKey) : undefined,
        classificationValue: review.classificationValue ? String(review.classificationValue) : undefined
      }
    })
    .filter((review) => {
      const key = `${review.wellId}:${review.autoEpisodeId}:${review.startDate}:${review.endDate}:${review.label}`
      if (!review.wellId || !review.autoEpisodeId || !review.startDate || !review.endDate || !review.label || seenReviews.has(key)) {
        return false
      }
      seenReviews.add(key)
      return true
    })
    .sort(
      (left, right) =>
        left.wellId.localeCompare(right.wellId, 'ru') ||
        toTimestamp(right.startDate) - toTimestamp(left.startDate)
    )
}

function normalizeMarkupState(markup: Partial<MarkupState> | null | undefined): MarkupState {
  const nextClassificationLevels = normalizeClassificationLevels(markup?.classificationLevels)

  return {
    annotations: normalizeSavedAnnotations(markup?.annotations, nextClassificationLevels),
    episodeClasses: normalizeClassOptions(markup?.episodeClasses),
    actionClasses: normalizeClassOptions(markup?.actionClasses),
    classificationLevels: nextClassificationLevels,
    manualFrequencyBreakpoints: normalizeFrequencyBreakpoints(markup?.manualFrequencyBreakpoints),
    suppressedFrequencyBreakpoints: normalizeFrequencyBreakpointSuppressions(markup?.suppressedFrequencyBreakpoints),
    autoEpisodeReviews: normalizeAutoEpisodeReviews(markup?.autoEpisodeReviews)
  }
}

function buildCurrentMarkupState(): MarkupState {
  return {
    annotations: savedAnnotations.value,
    episodeClasses: episodeTypeOptions.value,
    actionClasses: actionOptions.value,
    classificationLevels: classificationLevels.value,
    manualFrequencyBreakpoints: manualFrequencyBreakpoints.value,
    suppressedFrequencyBreakpoints: suppressedFrequencyBreakpoints.value,
    autoEpisodeReviews: autoEpisodeReviews.value
  }
}

function applyMarkupState(markup: MarkupState): void {
  savedAnnotations.value = markup.annotations
  episodeTypeOptions.value = markup.episodeClasses
  actionOptions.value = markup.actionClasses
  classificationLevels.value = markup.classificationLevels
  manualFrequencyBreakpoints.value = markup.manualFrequencyBreakpoints
  suppressedFrequencyBreakpoints.value = markup.suppressedFrequencyBreakpoints
  autoEpisodeReviews.value = markup.autoEpisodeReviews
}

function hasMarkupStateData(markup: MarkupState): boolean {
  return (
    markup.annotations.length > 0 ||
    markup.episodeClasses.length > 0 ||
    markup.actionClasses.length > 0 ||
    markup.manualFrequencyBreakpoints.length > 0 ||
    markup.suppressedFrequencyBreakpoints.length > 0 ||
    markup.autoEpisodeReviews.length > 0
  )
}

function readLegacyMarkupState(): MarkupState | null {
  const legacyMarkup = normalizeMarkupState({
    annotations: readStoredValue<SavedAnnotation[]>(MARKUP_STORAGE_KEYS.annotations, []),
    episodeClasses: readStoredValue<AnnotationClassOption[]>(MARKUP_STORAGE_KEYS.episodeClasses, []),
    actionClasses: readStoredValue<AnnotationClassOption[]>(MARKUP_STORAGE_KEYS.actionClasses, []),
    manualFrequencyBreakpoints: readStoredValue<FrequencyBreakpoint[]>(MARKUP_STORAGE_KEYS.manualFrequencyBreakpoints, []),
    suppressedFrequencyBreakpoints: readStoredValue<FrequencyBreakpointSuppression[]>(MARKUP_STORAGE_KEYS.suppressedFrequencyBreakpoints, []),
    autoEpisodeReviews: readStoredValue<AutoEpisodeReview[]>(MARKUP_STORAGE_KEYS.autoEpisodeReviews, [])
  })

  return hasMarkupStateData(legacyMarkup) ? legacyMarkup : null
}

function clearLegacyMarkupState(): void {
  Object.values(MARKUP_STORAGE_KEYS).forEach((key) => localStorage.removeItem(key))
}

async function persistMarkupNow(): Promise<boolean> {
  if (!markupLoaded.value) {
    return true
  }

  if (markupSaveTimeout) {
    clearTimeout(markupSaveTimeout)
    markupSaveTimeout = null
  }

  markupSaveState.value = 'saving'

  try {
    await saveMarkup(buildCurrentMarkupState())
    markupSaveState.value = 'saved'
    return true
  } catch {
    markupSaveState.value = 'error'

    if (Date.now() - lastMarkupSaveErrorAt > 5000) {
      message.error('Не удалось сохранить разметку на backend.')
      lastMarkupSaveErrorAt = Date.now()
    }

    return false
  }
}

function scheduleMarkupSave(): void {
  if (!markupLoaded.value) {
    return
  }

  if (markupSaveTimeout) {
    clearTimeout(markupSaveTimeout)
  }

  markupSaveTimeout = setTimeout(() => {
    markupSaveTimeout = null
    void persistMarkupNow()
  }, 500)
}

async function restorePersistentMarkup(): Promise<void> {
  const legacyMarkup = readLegacyMarkupState()

  try {
    const backendMarkup = normalizeMarkupState(await fetchMarkup())

    if (hasMarkupStateData(backendMarkup)) {
      applyMarkupState(backendMarkup)
      clearLegacyMarkupState()
      return
    }

    if (legacyMarkup) {
      applyMarkupState(legacyMarkup)
      await saveMarkup(buildCurrentMarkupState())
      clearLegacyMarkupState()
      message.success('Разметка перенесена из браузера в backend.')
      return
    }

    applyMarkupState(backendMarkup)
  } catch {
    if (legacyMarkup) {
      applyMarkupState(legacyMarkup)
      message.warning('Backend для разметки недоступен. Показана старая локальная копия из браузера.')
      return
    }

    message.warning('Не удалось загрузить разметку с backend.')
  } finally {
    markupLoaded.value = true
  }
}

function addAnnotationClass(): string | null {
  const className = newEpisodeClassName.value.trim()

  if (!className) {
    message.error('Введите название класса эпизода.')
    return null
  }

  const options = episodeTypeOptions
  const existingOption = options.value.find(
    (option) => option.value.toLocaleLowerCase('ru') === className.toLocaleLowerCase('ru')
  )

  if (existingOption) {
    episodeForm.value.episodeType = existingOption.value
    newEpisodeClassName.value = ''
    return existingOption.value
  }

  const option = { label: className, value: className }
  options.value = [...options.value, option].sort((left, right) => left.label.localeCompare(right.label, 'ru'))

  episodeForm.value.episodeType = option.value
  newEpisodeClassName.value = ''

  message.success('Класс эпизода добавлен.')
  return option.value
}

function addEpisodeClass(): void {
  addAnnotationClass()
}

function normalizeSelectedActions(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
}

function handleEventActionsUpdated(value: unknown): void {
  episodeForm.value.eventActions = normalizeSelectedActions(value)
  eventActionSelectOpen.value = false
}

function addActionClass(): string | null {
  const actionInput = newEventActionName
  const actionName = actionInput.value.trim()

  if (!actionName) {
    message.error('Введите название мероприятия.')
    return null
  }

  const existingOption = actionOptions.value.find(
    (option) => option.value.toLocaleLowerCase('ru') === actionName.toLocaleLowerCase('ru')
  )

  if (existingOption) {
    const currentActions = episodeForm.value.eventActions
    if (!currentActions.includes(existingOption.value)) {
      episodeForm.value.eventActions = [...currentActions, existingOption.value]
    }
    actionInput.value = ''
    return existingOption.value
  }

  const option = { label: actionName, value: actionName }
  actionOptions.value = [...actionOptions.value, option].sort((left, right) => left.label.localeCompare(right.label, 'ru'))
  episodeForm.value.eventActions = [...episodeForm.value.eventActions, option.value]
  actionInput.value = ''
  message.success('Мероприятие добавлено.')
  return option.value
}

function addEventActionClass(): void {
  addActionClass()
}

function resolveDraftClass(): string | null {
  const eventType = buildDraftEpisodeLabel()
  episodeForm.value.episodeType = eventType
  return eventType
}

function buildSingleLevelClassification(levelKey: string): AnnotationClassification {
  return {
    ...createDefaultClassification(classificationLevels.value),
    [levelKey]: episodeForm.value.classification[levelKey] ?? null
  }
}

function resolveSingleLevelEventType(levelKey: string): string | null {
  ensureClassificationOption(levelKey)
  const level = classificationLevels.value.find((item) => item.key === levelKey)
  if (!level) {
    return null
  }

  const valueLabel = getClassificationOptionLabel(level, episodeForm.value.classification[levelKey])
  return valueLabel ? `${level.label}: ${valueLabel}` : null
}

function resolveCandidateAutoEventType(payload: TimelineAnnotationClickPayload): string {
  const levelKey = payload.classificationLevelKey
  const value = payload.classificationValue
  const level = levelKey ? classificationLevels.value.find((item) => item.key === levelKey) : null
  const valueLabel = level ? getClassificationOptionLabel(level, value) : null
  return level && valueLabel ? `${level.label}: ${valueLabel}` : payload.label
}

function createAutoEpisodeReviewId(payload: TimelineAnnotationClickPayload): string {
  const autoEpisodeId = payload.autoEpisodeId ?? `${payload.label}-${payload.startDate}-${payload.endDate}`
  return `auto-review-${selectedWell.value}-${autoEpisodeId}`.replace(/[^A-Za-z0-9_-]+/g, '-')
}

function getCandidateAutoReviewSignature(
  item: Pick<AutoEpisodeReview, 'autoEpisodeId' | 'startDate' | 'endDate' | 'label' | 'sourceVersion'>
): string {
  return `${item.sourceVersion ?? ''}|${item.autoEpisodeId}|${item.startDate}|${item.endDate}|${item.label}`
}

function pruneStaleAutoEpisodeReviews(wellId: string, intervals: EventInterval[]): boolean {
  const validSignatures = new Set(
    intervals.map((interval) =>
      getCandidateAutoReviewSignature({
        autoEpisodeId: interval.id,
        startDate: interval.startDate,
        endDate: interval.endDate,
        label: interval.label,
        sourceVersion: interval.sourceVersion ?? undefined
      })
    )
  )
  const previousLength = autoEpisodeReviews.value.length
  autoEpisodeReviews.value = autoEpisodeReviews.value.filter((review) => {
    if (review.wellId !== wellId) {
      return true
    }
    return validSignatures.has(getCandidateAutoReviewSignature(review))
  })
  return autoEpisodeReviews.value.length !== previousLength
}

function getPrimaryClassificationLevelKey(classification: AnnotationClassification): string | null {
  return classificationLevels.value.find((level) => Boolean(classification[level.key]))?.key ?? null
}

function annotationMatchesInterval(annotation: SavedAnnotation, interval: SelectedInterval): boolean {
  return toTimestamp(annotation.startDate) === toTimestamp(interval.startDate) && toTimestamp(annotation.endDate) === toTimestamp(interval.endDate)
}

function getSavedAnnotationsForSelectedLevel(levelKey: string): SavedAnnotation[] {
  const annotationIds = new Set<string>()

  if (editingAnnotationId.value) {
    const editingAnnotation = savedAnnotations.value.find((annotation) => annotation.id === editingAnnotationId.value)
    if (editingAnnotation && getPrimaryClassificationLevelKey(editingAnnotation.classification) === levelKey) {
      annotationIds.add(editingAnnotation.id)
    }
  }

  if (selectedInterval.value) {
    currentWellAnnotations.value.forEach((annotation) => {
      if (getPrimaryClassificationLevelKey(annotation.classification) === levelKey && annotationMatchesInterval(annotation, selectedInterval.value!)) {
        annotationIds.add(annotation.id)
      }
    })
  }

  return savedAnnotations.value.filter((annotation) => annotationIds.has(annotation.id))
}

function canDeleteClassificationLevel(levelKey: string): boolean {
  return getSavedAnnotationsForSelectedLevel(levelKey).length > 0
}

function getAverageMetric(points: TimeSeriesPoint[], key: keyof AnalysisWindowMetrics): number | null {
  const values = points
    .map((point) => point[key])
    .filter((value): value is number => Number.isFinite(value))

  if (values.length === 0) {
    return null
  }

  const total = values.reduce((sum, value) => sum + value, 0)
  return total / values.length
}

function roundMetric(value: number | null): number | null {
  return value === null ? null : Number(value.toFixed(2))
}

function getWindowMetrics(points: TimeSeriesPoint[]): AnalysisWindowMetrics {
  return {
    qliq: roundMetric(getAverageMetric(points, 'qliq')),
    qoil: roundMetric(getAverageMetric(points, 'qoil')),
    intake_pressure: roundMetric(getAverageMetric(points, 'intake_pressure')),
    water_cut: roundMetric(getAverageMetric(points, 'water_cut'))
  }
}

function getPointsForRange(startDate: string, endDate: string): TimeSeriesPoint[] {
  const normalizedStartDate = toIsoDateKey(startDate)
  const normalizedEndDate = toIsoDateKey(endDate)
  return chartData.value.filter((point) => {
    const pointDate = toIsoDateKey(point.date)
    return pointDate >= normalizedStartDate && pointDate <= normalizedEndDate
  })
}

function getShiftedDate(baseDate: string, dayDelta: number): string {
  const date = new Date(baseDate)
  date.setDate(date.getDate() + dayDelta)
  return date.toISOString().slice(0, 10)
}

function formatMetric(value: number | null): string {
  return value === null ? '—' : value.toFixed(2)
}

function buildSuggestedActions(
  interval: TimelineAnnotationClickPayload,
  before: AnalysisWindowMetrics,
  during: AnalysisWindowMetrics,
  after: AnalysisWindowMetrics
): string[] {
  const actions: string[] = []
  const oilDrop = (before.qoil ?? 0) - (during.qoil ?? 0)
  const liquidDrop = (before.qliq ?? 0) - (during.qliq ?? 0)
  const waterCutRise = (during.water_cut ?? 0) - (before.water_cut ?? 0)
  const pressureRise = (during.intake_pressure ?? 0) - (before.intake_pressure ?? 0)
  const frequencyResponse = Math.abs((after.qliq ?? 0) - (during.qliq ?? 0))

  if (liquidDrop > 4 && oilDrop > 3 && waterCutRise < 3) {
    actions.push('Проверить состояние ЭЦН, текущие параметры работы и результаты диагностики оборудования.')
  }

  if (waterCutRise > 5 && oilDrop > 2.5) {
    actions.push('Рассмотреть анализ водопритока, профиль притока и кандидата на водоизоляционные мероприятия.')
  }

  if (interval.label.toLowerCase().includes('опз') || interval.label.toLowerCase().includes('эффект опз')) {
    actions.push('Продолжить мониторинг устойчивости эффекта ОПЗ и контролировать скорость последующего падения дебита.')
  }

  if (interval.label.toLowerCase().includes('частот') || frequencyResponse > 3.5) {
    actions.push('Проверить возможность дальнейшей оптимизации частоты ЭЦН на основе отклика дебита.')
  }

  if (pressureRise > 2 && liquidDrop > 3) {
    actions.push('Проверить гидродинамические изменения и выполнить анализ ограничений по приему насоса.')
  }

  if (interval.label.toLowerCase().includes('нестабиль')) {
    actions.push('Проверить устойчивость электропитания, автоматику управления и факторы, вызывающие колебания работы.')
  }

  if (interval.label.toLowerCase().includes('замена эцн')) {
    actions.push('Зафиксировать эффект после замены ЭЦН и использовать его как ориентир для оценки деградации оборудования.')
  }

  return actions.slice(0, 3)
}

function buildAnalysisConfidence(
  interval: TimelineAnnotationClickPayload,
  before: AnalysisWindowMetrics,
  during: AnalysisWindowMetrics,
  after: AnalysisWindowMetrics
): { level: 'Низкая' | 'Средняя' | 'Высокая'; explanation: string } {
  const oilDrop = (before.qoil ?? 0) - (during.qoil ?? 0)
  const liquidDrop = (before.qliq ?? 0) - (during.qliq ?? 0)
  const waterCutRise = (during.water_cut ?? 0) - (before.water_cut ?? 0)
  const frequencyShift = Math.abs((after.intake_pressure ?? during.intake_pressure ?? 0) - (during.intake_pressure ?? 0))
  const afterRecoveryOil = (after.qoil ?? during.qoil ?? 0) - (during.qoil ?? 0)
  const consistentSignals = [
    oilDrop > 2.5,
    liquidDrop > 3,
    waterCutRise > 4,
    interval.layer === 'event',
    Math.abs((during.water_cut ?? 0) - (after.water_cut ?? during.water_cut ?? 0)) < 3.5
  ].filter(Boolean).length
  const contradictorySignals = [
    oilDrop < 1 && liquidDrop > 4,
    waterCutRise > 5 && afterRecoveryOil > 3,
    frequencyShift > 4
  ].filter(Boolean).length

  if (consistentSignals >= 4 && contradictorySignals === 0) {
    return {
      level: 'Высокая',
      explanation: 'Несколько сигналов согласованно поддерживают интерпретацию интервала: изменение дебита, нефти и воды имеет устойчивый и непротиворечивый характер.'
    }
  }

  if (consistentSignals >= 2 && contradictorySignals <= 1) {
    return {
      level: 'Средняя',
      explanation: 'Основные сигналы в целом согласованы, но часть показателей меняется слабее либо интерпретация ограничена переходным характером интервала.'
    }
  }

  return {
    level: 'Низкая',
    explanation: 'Показатели изменяются неоднозначно: сигналы противоречат друг другу, выражены слабо или интервал выглядит переходным и шумным.'
  }
}

function applyPotentialConstraint(potentialOil: number, potentialLiquid: number): { oil: number; liquid: number } {
  const adjustedLiquid = Math.max(0, potentialLiquid)
  const oilLimit = adjustedLiquid * 0.8
  const adjustedOil = Math.min(Math.max(0, potentialOil), oilLimit)

  return {
    oil: Number(adjustedOil.toFixed(2)),
    liquid: Number(adjustedLiquid.toFixed(2))
  }
}

function exportAnalysis(drillDown: AnalysisDrillDown) {
  const payload = {
    interval_start: drillDown.interval.startDate,
    interval_end: drillDown.interval.endDate,
    duration_days: drillDown.interval.durationDays,
    interval_type: drillDown.layerLabel,
    interval_label: drillDown.interval.label,
    before: drillDown.before,
    during: drillDown.during,
    after: drillDown.after,
    cumulative_impact: {
      oil_label: drillDown.oilImpactLabel,
      oil_value: drillDown.oilDelta,
      liquid_label: drillDown.liquidImpactLabel,
      liquid_value: drillDown.liquidDelta
    },
    potential_gain: {
      oil: drillDown.potentialOil,
      liquid: drillDown.potentialLiquid
    },
    suggested_actions: drillDown.actions,
    confidence: drillDown.confidence,
    confidence_explanation: drillDown.confidenceExplanation
  }

  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `analysis_${drillDown.interval.startDate}_${drillDown.interval.endDate}.json`
  link.click()
  URL.revokeObjectURL(url)
}

function triggerCsvDownload(url: string): void {
  const link = document.createElement('a')
  link.href = url
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  link.remove()
}

async function downloadGraphDataExport(): Promise<void> {
  graphDataExporting.value = true

  try {
    triggerCsvDownload(buildGraphDataExportCsvUrl())
    message.success('CSV-выгрузка всех скважин запущена.')
  } catch {
    message.error('Не удалось сформировать CSV-выгрузку.')
  } finally {
    window.setTimeout(() => {
      graphDataExporting.value = false
    }, 800)
  }
}

async function downloadManualGraphDataExport(): Promise<void> {
  manualGraphDataExporting.value = true

  try {
    triggerCsvDownload(buildManualGraphDataExportCsvUrl())
    message.success('CSV-выгрузка скважин с ручной разметкой запущена.')
  } catch {
    message.error('Не удалось сформировать CSV-выгрузку ручной разметки.')
  } finally {
    window.setTimeout(() => {
      manualGraphDataExporting.value = false
    }, 800)
  }
}

async function downloadCurrentWellGraphDataExport(): Promise<void> {
  wellGraphDataExporting.value = true

  try {
    triggerCsvDownload(buildGraphDataExportCsvUrl({ well_id: selectedWell.value }))
    message.success(`CSV-выгрузка ${selectedWell.value} запущена.`)
  } catch {
    message.error('Не удалось сформировать CSV-выгрузку по скважине.')
  } finally {
    window.setTimeout(() => {
      wellGraphDataExporting.value = false
    }, 800)
  }
}

function getAnnotationCategory(annotation: SavedAnnotation): string {
  return getAnnotationClassificationLabel(annotation)
}

function getAnnotationActions(annotation: SavedAnnotation): string[] {
  return annotation.actions ?? []
}

function areStringArraysEqual(left: string[], right: string[]): boolean {
  if (left.length !== right.length) {
    return false
  }

  const sortedLeft = [...left].sort()
  const sortedRight = [...right].sort()
  return sortedLeft.every((value, index) => value === sortedRight[index])
}

function areClassificationsEqual(left: AnnotationClassification, right: AnnotationClassification): boolean {
  const keys = new Set([...Object.keys(left), ...Object.keys(right)])
  return [...keys].every((key) => (left[key] ?? null) === (right[key] ?? null))
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

  return {
    id: idOverride ?? annotation.id,
    wellId: annotation.wellId,
    wellGroupId: annotation.wellGroupId,
    annotationKind: 'event',
    eventType: annotation.eventType,
    classification: { ...annotation.classification },
    confidenceEvent: annotation.confidenceEvent,
    comment: annotation.comment,
    actions: annotation.actions ?? [],
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
      areClassificationsEqual(previous.classification, annotation.classification) &&
      areStringArraysEqual(getAnnotationActions(previous), getAnnotationActions(annotation)) &&
      toTimestamp(annotation.startDate) <= toTimestamp(previous.endDate) + 86400000
    ) {
      const preferredAnnotation =
        previous.id === preferredAnnotationId ? previous : annotation.id === preferredAnnotationId ? annotation : previous
      const mergedInterval = buildInterval(previous.startDate, annotation.endDate)
      const mergedAnnotation = {
        id: preferredAnnotation.id,
        wellId: preferredAnnotation.wellId,
        wellGroupId: preferredAnnotation.wellGroupId,
        annotationKind: 'event' as const,
        eventType: preferredAnnotation.eventType,
        classification: { ...preferredAnnotation.classification },
        confidenceEvent: preferredAnnotation.confidenceEvent,
        comment: preferredAnnotation.comment,
        actions: getAnnotationActions(preferredAnnotation),
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
  savedAnnotations.value = [
    ...savedAnnotations.value.filter((item) => item.id !== incomingAnnotation.id),
    incomingAnnotation
  ].sort(
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

  const existingAnnotation = savedAnnotations.value.find((item) => item.id === editingAnnotationId.value)
  if (!existingAnnotation) {
    return selectedInterval.value !== null
  }

  const intervalChanged =
    existingAnnotation.startDate !== selectedInterval.value?.startDate ||
    existingAnnotation.endDate !== selectedInterval.value?.endDate ||
    existingAnnotation.durationDays !== selectedInterval.value?.durationDays

  return (
    intervalChanged ||
    existingAnnotation.eventType !== buildDraftEpisodeLabel() ||
    !areClassificationsEqual(existingAnnotation.classification, episodeForm.value.classification) ||
    existingAnnotation.confidenceEvent !== episodeForm.value.confidenceEvent ||
    !areStringArraysEqual(getAnnotationActions(existingAnnotation), episodeForm.value.eventActions) ||
    existingAnnotation.comment !== episodeForm.value.comment
  )
}

function getDraftIntervalsForNewAnnotation(): SelectedInterval[] {
  const frequencyIntervals = selectedFrequencySegments.value.map((segment) => buildInterval(segment.startDate, segment.endDate))

  if (frequencyIntervals.length > 0) {
    return frequencyIntervals
  }

  return selectedInterval.value ? [selectedInterval.value] : []
}

function getWellFieldCode(wellId: string): string {
  return getWellFieldCodeFromId(wellId)
}

function buildWellGroupOptions(wellIds: string[]): { label: string; value: WellGroupId }[] {
  const fieldCodes = Array.from(new Set(wellIds.map(getWellFieldCode))).sort((left, right) =>
    left.localeCompare(right, 'ru')
  )

  return fieldCodes.map((fieldCode) => ({
    label: formatFieldGroupLabel(fieldCode),
    value: getFieldGroupId(fieldCode)
  }))
}

function comparePeriodSummaryValues(leftValue: unknown, rightValue: unknown): number {
  if (typeof leftValue === 'number' && typeof rightValue === 'number') {
    return leftValue - rightValue
  }

  return formatPeriodSummaryCell(leftValue).localeCompare(formatPeriodSummaryCell(rightValue), 'ru', {
    numeric: true,
    sensitivity: 'base'
  })
}

function formatPeriodSummaryCell(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return ''
  }

  if (typeof value === 'number') {
    return Number.isFinite(value) ? value.toFixed(2) : ''
  }

  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(value)) {
    return value.replace('T', ' ').slice(0, 16)
  }

  return String(value)
}

function formatPeriodDate(value: string): string {
  if (!value) {
    return '—'
  }

  return value.replace('T', ' ').slice(0, 16)
}

async function loadPeriodSummary(): Promise<void> {
  periodSummaryLoading.value = true
  periodSummaryError.value = ''
  const [start, end] = periodSummaryDateRange.value ?? []
  const params = {
    period: periodSummaryPreset.value,
    date_from: periodSummaryPreset.value === 'custom' ? toIsoDate(start) : undefined,
    date_to: periodSummaryPreset.value === 'custom' ? toIsoDate(end) : undefined,
    field_code: periodSummaryFieldCode.value !== 'all' ? periodSummaryFieldCode.value : undefined,
    well_id: periodSummaryWellId.value !== 'all' ? periodSummaryWellId.value : undefined
  }

  try {
    const summary = await fetchPeriodSummary(params)
    periodSummaryRows.value = summary.rows
    periodSummaryMeta.value = {
      period_start: summary.period_start,
      period_end: summary.period_end,
      window_days: summary.window_days
    }
  } catch {
    periodSummaryRows.value = []
    periodSummaryError.value = 'Не удалось загрузить сводку авторазметки за период.'
    message.error(periodSummaryError.value)
  } finally {
    periodSummaryLoading.value = false
  }
}

async function loadData() {
  if (!selectedWell.value) {
    chartData.value = []
    trMonitoringData.value = []
    vspPeriods.value = []
    artificialLiftPeriods.value = []
    candidateAutoEpisodeIntervals.value = []
    clearCandidateAutoSelection()
    visibleDateRange.value = null
    wellContext.value = null
    return
  }

  loading.value = true
  errorMessage.value = ''
  wellContext.value = null
  trMonitoringData.value = []
  vspPeriods.value = []
  artificialLiftPeriods.value = []
  candidateAutoEpisodeIntervals.value = []
  selectedInterval.value = null
  selectedAnalysisInterval.value = null
  clearCandidateAutoSelection()
  editingAnnotationId.value = null
  editingAnnotationKind.value = null
  selectedFrequencyBreakpointId.value = null
  clearFrequencySegmentSelection()
  episodeForm.value = createDefaultEpisodeForm()
  const [start, end] = dateRange.value ?? []
  const dateFrom = toIsoDate(start)
  const dateTo = toIsoDate(end)
  const trDateFrom = dateFrom
    ? Math.max(
        new Date(`${subtractMonthsIsoDate(dateFrom, 2)}T00:00:00`).getTime(),
        new Date(`${minTrChartStartDate}T00:00:00`).getTime()
      )
    : null
  const params = {
    date_from: dateFrom,
    date_to: dateTo
  }
  const trParams = {
    date_from: trDateFrom ? new Date(trDateFrom).toISOString().slice(0, 10) : undefined,
    date_to: dateTo
  }
  const requestedWell = selectedWell.value

  try {
    const [data, context, trData, liftPeriods, candidateAutoEpisodes] = await Promise.all([
      useMockTelemetry
        ? Promise.resolve(generateMockTimeseries(requestedWell, params))
        : fetchWellTimeseries(requestedWell, params),
      fetchWellContext(requestedWell).catch(() => null),
      fetchTrMonitoring(requestedWell, trParams).catch(() => []),
      fetchArtificialLiftPeriods(requestedWell).catch(() => []),
      fetchCandidateAutoEpisodeIntervals(requestedWell).catch(() => [])
    ])

    chartData.value = data
    wellContext.value = context
    trMonitoringData.value = trData
    artificialLiftPeriods.value = liftPeriods
    candidateAutoEpisodeIntervals.value = candidateAutoEpisodes
    if (pruneStaleAutoEpisodeReviews(requestedWell, candidateAutoEpisodes)) {
      void persistMarkupNow()
    }
    visibleDateRange.value = getFullDateRange(data, trData)
    void fetchVspPeriods(requestedWell)
      .then((items) => {
        if (selectedWell.value === requestedWell) {
          vspPeriods.value = items
        }
      })
      .catch(() => {
        if (selectedWell.value === requestedWell) {
          vspPeriods.value = []
        }
      })
    if (!context) {
      message.warning('Контекст ГТМ/ОПЗ/ГДИ не загружен. Проверьте backend, если нужны реальные маркеры мероприятий.')
    }
  } catch {
    const fallbackData = generateMockTimeseries(selectedWell.value, params)

    chartData.value = fallbackData
    trMonitoringData.value = []
    vspPeriods.value = []
    artificialLiftPeriods.value = []
    candidateAutoEpisodeIntervals.value = []
    wellContext.value = null
    visibleDateRange.value = getFullDateRange(fallbackData)
    errorMessage.value = 'Не удалось загрузить временные ряды. Убедитесь, что backend запущен на http://localhost:8000.'
    message.error(errorMessage.value)
  } finally {
    loading.value = false
  }
}

function createWellGroupAssignments(wellIds: string[]): Record<string, WellGroupId | null> {
  return Object.fromEntries(
    wellIds.map((wellId) => [wellId, getFieldGroupId(getWellFieldCode(wellId))])
  )
}

async function initializeWellOptions() {
  try {
    const wellIds = await fetchWellIds()
    if (wellIds.length === 0) {
      return
    }

    wellOptions.value = wellIds.map((wellId) => ({ label: wellId, value: wellId }))
    wellGroupOptions.value = buildWellGroupOptions(wellIds)
    wellGroupAssignments.value = createWellGroupAssignments(wellIds)
    if (!wellIds.includes(selectedWell.value)) {
      selectedWell.value = wellIds.includes(DEFAULT_WELL_ID) ? DEFAULT_WELL_ID : wellIds[0] ?? ''
    }

    const selectedGroupId = wellGroupAssignments.value[selectedWell.value] ?? null
    if (selectedGroupId && wellGroupOptions.value.some((option) => option.value === selectedGroupId)) {
      navigationGroupId.value = selectedGroupId
      if (!wellGroupOptions.value.some((option) => option.value === modelSelectedGroupId.value)) {
        modelSelectedGroupId.value = selectedGroupId
      }
    } else if (!wellGroupOptions.value.some((option) => option.value === navigationGroupId.value)) {
      navigationGroupId.value = wellGroupOptions.value[0]?.value ?? null
    }

    if (!wellGroupOptions.value.some((option) => option.value === modelSelectedGroupId.value)) {
      modelSelectedGroupId.value = wellGroupOptions.value[0]?.value ?? 'field-au'
    }
  } catch {
    message.warning('Не удалось загрузить список скважин с backend. Используется локальный список.')
  }
}

function saveGroupForWell() {
  let nextGroupId = groupMigrationTarget.value

  if (!nextGroupId) {
    message.error('Выберите новую группу.')
    return
  }

  if (nextGroupId === CREATE_NEW_GROUP_OPTION) {
    const trimmedGroupName = newGroupName.value.trim()
    if (!trimmedGroupName) {
      message.error('Укажите название новой группы.')
      return
    }

    const newGroupId = `group-${Date.now()}`
    wellGroupOptions.value = [...wellGroupOptions.value, { label: trimmedGroupName, value: newGroupId }]
    nextGroupId = newGroupId
    newGroupName.value = ''
  }

  wellGroupAssignments.value = {
    ...wellGroupAssignments.value,
    [selectedWell.value]: nextGroupId
  }
  groupMigrationTarget.value = nextGroupId
  groupSaveFeedback.value = 'saved'
  if (groupSaveFeedbackTimeout) {
    clearTimeout(groupSaveFeedbackTimeout)
  }
  groupSaveFeedbackTimeout = setTimeout(() => {
    groupSaveFeedback.value = 'idle'
    groupSaveFeedbackTimeout = null
  }, 1800)
  message.success('Скважина перемещена в другую группу.')
}

function moveWellToGroup() {
  saveGroupForWell()
}

async function resetCurrentModelGroup() {
  const targetId = currentModelTargetId.value
  modelParamsByGroup.value = {
    ...modelParamsByGroup.value,
    [targetId]: {}
  }

  try {
    const state = await resetModelParamsForTarget(targetId)
    modelParamsByGroup.value = Object.fromEntries(
      Object.entries(state.overrides).map(([key, value]) => [key, normalizeModelParams(value)])
    )
    message.success(`Настройки ${modelRunScopeLabel.value} сброшены.`)
  } catch {
    message.error('Не удалось сбросить настройки модели.')
  }
}

async function saveCurrentModelParams() {
  const targetId = currentModelTargetId.value
  const params = normalizeModelParams(modelParamsByGroup.value[targetId] ?? {})

  try {
    const state = await saveModelParamsForTarget(targetId, toModelParamsPayload(params))
    modelParamsByGroup.value = Object.fromEntries(
      Object.entries(state.overrides).map(([key, value]) => [key, normalizeModelParams(value)])
    )
    message.success(`Настройки ${modelRunScopeLabel.value} сохранены.`)
  } catch {
    message.error('Не удалось сохранить настройки модели.')
  }
}

async function applyCurrentModelParams() {
  await saveCurrentModelParams()
  message.success(`Авторазметка запущена для области: ${modelRunScopeLabel.value}.`)
}

function getFrequencyBreakpointSourceLabel(source: FrequencyBreakpoint['source']): string {
  return source === 'auto' ? 'Авто' : 'Ручной'
}

function clearFrequencySegmentSelection(): void {
  selectedFrequencySegmentIds.value = []
  additiveFrequencySelectionArmed.value = false
}

function armAdditiveFrequencySelection(): void {
  additiveFrequencySelectionArmed.value = true
}

function canAddManualFrequencyBreakpoint(date: string | null | undefined): boolean {
  if (!date || !selectedWell.value) {
    return false
  }

  const fullRange = getFullDateRange(chartData.value)
  if (!fullRange || date < fullRange.startDate || date > fullRange.endDate) {
    return false
  }

  return !currentFrequencyBreakpoints.value.some((breakpoint) => breakpoint.date === date)
}

async function addManualFrequencyBreakpoint(
  date: string | null | undefined,
  options?: { clearSelections?: boolean; selectBreakpoint?: boolean }
): Promise<void> {
  if (!date || !selectedWell.value) {
    return
  }

  if (!canAddManualFrequencyBreakpoint(date)) {
    message.warning('На этой дате уже есть штрих или дата вне диапазона.')
    return
  }

  const breakpoint: FrequencyBreakpoint = {
    id: createFrequencyBreakpointId('manual', selectedWell.value),
    wellId: selectedWell.value,
    date,
    source: 'manual',
    reason: 'Ручной штрих',
    fromFrequency: null,
    toFrequency: null
  }

  manualFrequencyBreakpoints.value = [...manualFrequencyBreakpoints.value, breakpoint].sort(
    (left, right) => left.wellId.localeCompare(right.wellId, 'ru') || left.date.localeCompare(right.date)
  )
  if (options?.clearSelections) {
    clearFrequencySegmentSelection()
    selectedInterval.value = null
    editingAnnotationId.value = null
    editingAnnotationKind.value = null
  }
  selectedFrequencyBreakpointId.value = options?.selectBreakpoint === false ? null : breakpoint.id
  const saved = await persistMarkupNow()
  message[saved ? 'success' : 'warning'](
    saved ? 'Штрих частоты добавлен.' : 'Штрих добавлен в интерфейсе, но не сохранён на backend.'
  )
}

async function mergeFrequencySegmentsAtSelectedBreakpoint(): Promise<void> {
  const breakpoint = selectedFrequencyBreakpoint.value
  if (!breakpoint) {
    return
  }

  if (breakpoint.source === 'manual') {
    manualFrequencyBreakpoints.value = manualFrequencyBreakpoints.value.filter((item) => item.id !== breakpoint.id)
  } else if (!currentSuppressedFrequencyBreakpoints.value.some((item) => item.date === breakpoint.date)) {
    suppressedFrequencyBreakpoints.value = [
      ...suppressedFrequencyBreakpoints.value,
      {
        id: createFrequencyBreakpointId('auto', breakpoint.wellId, breakpoint.date),
        wellId: breakpoint.wellId,
        date: breakpoint.date
      }
    ]
  }

  selectedFrequencyBreakpointId.value = null
  const saved = await persistMarkupNow()
  message[saved ? 'success' : 'warning'](
    saved ? 'Соседние промежутки объединены.' : 'Промежутки объединены в интерфейсе, но не сохранены на backend.'
  )
}

async function restoreAutoFrequencyBreakpoints(): Promise<void> {
  if (!selectedWell.value || currentSuppressedFrequencyBreakpoints.value.length === 0) {
    return
  }

  suppressedFrequencyBreakpoints.value = suppressedFrequencyBreakpoints.value.filter((item) => item.wellId !== selectedWell.value)
  selectedFrequencyBreakpointId.value = null
  const saved = await persistMarkupNow()
  message[saved ? 'success' : 'warning'](
    saved ? 'Автоштрихи восстановлены.' : 'Автоштрихи восстановлены в интерфейсе, но не сохранены на backend.'
  )
}

function handleIntervalSelected(value: SelectedInterval | null) {
  clearCandidateAutoSelection()
  selectedInterval.value = value ? snapIntervalToAnnotationBoundaries(value) : null
  selectedFrequencyBreakpointId.value = null
  clearFrequencySegmentSelection()

  if (!value) {
    editingAnnotationId.value = null
    editingAnnotationKind.value = null
    return
  }

  editingAnnotationId.value = null
  editingAnnotationKind.value = null
  episodeForm.value = createDefaultEpisodeForm()
}

function handleFrequencySegmentClicked(payload: FrequencySegmentClickPayload) {
  if (interactionMode.value !== 'annotate') {
    return
  }

  clearCandidateAutoSelection()
  selectedFrequencyBreakpointId.value = null
  selectedInterval.value = snapIntervalToAnnotationBoundaries(buildInterval(payload.startDate, payload.endDate))
  editingAnnotationId.value = null
  editingAnnotationKind.value = null
  episodeForm.value = createDefaultEpisodeForm()

  if (additiveFrequencySelectionArmed.value) {
    if (!selectedFrequencySegmentIds.value.includes(payload.id)) {
      selectedFrequencySegmentIds.value = [...selectedFrequencySegmentIds.value, payload.id]
    }
    additiveFrequencySelectionArmed.value = false
    return
  }

  selectedFrequencySegmentIds.value = [payload.id]
}

async function handleFrequencySegmentDoubleClicked(payload: FrequencySegmentDoubleClickPayload) {
  if (interactionMode.value !== 'annotate') {
    return
  }

  await addManualFrequencyBreakpoint(payload.date, {
    clearSelections: true,
    selectBreakpoint: false
  })
}

function handleFrequencyBreakpointClicked(payload: FrequencyBreakpointClickPayload) {
  if (interactionMode.value !== 'annotate') {
    return
  }

  clearCandidateAutoSelection()
  clearFrequencySegmentSelection()
  selectedFrequencyBreakpointId.value = payload.id
}

function handleAnnotationClicked(payload: TimelineAnnotationClickPayload) {
  if (payload.source === 'candidateAuto') {
    selectedAnalysisInterval.value = payload
    loadCandidateAutoIntoDraft(payload)
    return
  }

  if (interactionMode.value === 'navigate') {
    clearCandidateAutoSelection()
    selectedAnalysisInterval.value = payload
    return
  }

  if (!payload.annotationId) {
    return
  }

  const episode = currentWellAnnotations.value.find((item) => item.id === payload.annotationId)
  if (!episode) {
    return
  }

  loadEpisodeIntoDraft(episode)
}

async function transferCandidateAutoToManual(): Promise<void> {
  const payload = selectedCandidateAutoAnnotation.value
  const levelKey = payload?.classificationLevelKey
  const levelValue = payload?.classificationValue

  if (!payload || !selectedInterval.value || !levelKey || !levelValue) {
    message.error('Для этого автоэпизода не найдена категория ручной разметки.')
    return
  }

  const interval = buildInterval(payload.startDate, payload.endDate)
  const overlappingAnnotations = currentWellAnnotations.value.filter(
    (annotation) => getPrimaryClassificationLevelKey(annotation.classification) === levelKey && annotationsOverlap(annotation, interval)
  )

  if (overlappingAnnotations.length > 0) {
    const confirmed = window.confirm(
      `В ручной разметке уже есть пересекающиеся интервалы этого уровня: ${overlappingAnnotations.length}. Заменить пересекающиеся данные?`
    )
    if (!confirmed) {
      return
    }

    const overlappingIds = new Set(overlappingAnnotations.map((annotation) => annotation.id))
    savedAnnotations.value = savedAnnotations.value.filter((annotation) => !overlappingIds.has(annotation.id))
  }

  const annotation: SavedEventAnnotation = {
    id: createAnnotationId('event'),
    wellId: selectedWell.value,
    wellGroupId: currentWellGroupId.value,
    ...interval,
    annotationKind: 'event',
    eventType: resolveCandidateAutoEventType(payload),
    classification: {
      ...createDefaultClassification(classificationLevels.value),
      [levelKey]: levelValue
    },
    confidenceEvent: 'medium',
    comment: 'Перенесено из авторазметки 9.7.2.',
    actions: []
  }

  normalizeAnnotationsForLayer(annotation)
  loadEpisodeIntoDraft(annotation)
  const saved = await persistMarkupNow()
  message[saved ? 'success' : 'warning'](
    saved ? 'Автоэпизод перенесён в ручную разметку.' : 'Автоэпизод перенесён в интерфейсе, но не сохранён на backend.'
  )
}

async function saveCandidateAutoErrorReview(): Promise<void> {
  const payload = selectedCandidateAutoAnnotation.value
  if (!payload?.autoEpisodeId || !selectedInterval.value) {
    message.error('Сначала выберите эпизод авторазметки.')
    return
  }

  const review: AutoEpisodeReview = {
    id: createAutoEpisodeReviewId(payload),
    wellId: selectedWell.value,
    autoEpisodeId: payload.autoEpisodeId,
    startDate: payload.startDate,
    endDate: payload.endDate,
    label: payload.label,
    errorType: autoEpisodeErrorType.value,
    comment: autoEpisodeErrorComment.value.trim(),
    sourceVersion: payload.sourceVersion ?? undefined,
    classificationLevelKey: payload.classificationLevelKey,
    classificationValue: payload.classificationValue
  }
  const reviewSignature = getCandidateAutoReviewSignature(review)

  autoEpisodeReviews.value = [
    ...autoEpisodeReviews.value.filter((item) => getCandidateAutoReviewSignature(item) !== reviewSignature),
    review
  ].sort(
    (left, right) =>
      left.wellId.localeCompare(right.wellId, 'ru') ||
      toTimestamp(right.startDate) - toTimestamp(left.startDate)
  )

  const saved = await persistMarkupNow()
  message[saved ? 'success' : 'warning'](
    saved ? 'Ошибка авторазметки сохранена.' : 'Ошибка авторазметки сохранена в интерфейсе, но не сохранена на backend.'
  )
}

function handleVisibleRangeChanged(value: VisibleDateRange | null) {
  visibleDateRange.value = value
}

function openAnnotationForEdit(annotationId: string) {
  const episode = currentWellAnnotations.value.find((item) => item.id === annotationId)
  if (!episode) {
    return
  }

  loadEpisodeIntoDraft(episode)
}

function resetAnnotationSelection() {
  chartRef.value?.clearSelection()
  clearCandidateAutoSelection()
  selectedInterval.value = null
  editingAnnotationId.value = null
  editingAnnotationKind.value = null
  selectedFrequencyBreakpointId.value = null
  clearFrequencySegmentSelection()
  episodeForm.value = createDefaultEpisodeForm()
}

function clearSelection(options?: { force?: boolean }) {
  const hasUiSelection =
    selectedInterval.value ||
    selectedCandidateAutoAnnotation.value ||
    editingAnnotationId.value ||
    editingAnnotationKind.value ||
    selectedFrequencyBreakpointId.value ||
    selectedFrequencySegmentIds.value.length > 0

  if (!hasUiSelection) {
    chartRef.value?.clearSelection()
    return
  }

  if (!options?.force && hasUnsavedChanges.value) {
    const confirmed = window.confirm('Очистить текущее выделение и черновик аннотации?')
    if (!confirmed) {
      return
    }
  }

  resetAnnotationSelection()
}

function handleClearSelectionClick() {
  clearSelection()
}

function zoomToSelection() {
  chartRef.value?.zoomToSelection()
}

function resetZoom() {
  chartRef.value?.resetZoom()
}

function handleChartBackgroundClicked() {
  if (interactionMode.value === 'navigate') {
    selectedAnalysisInterval.value = null
    return
  }

  clearSelection({ force: true })
}

async function saveEvent() {
  const draftIntervals = getDraftIntervalsForNewAnnotation()

  if (!selectedInterval.value && draftIntervals.length === 0) {
    message.error('Перед сохранением эпизода выберите интервал.')
    return
  }

  ensureDraftClassificationOptions()
  const eventType = resolveDraftClass()

  if (!eventType) {
    return
  }

  if (editingAnnotationId.value && editingAnnotationKind.value === 'event') {
    if (!selectedInterval.value) {
      return
    }

    const index = savedAnnotations.value.findIndex((item) => item.id === editingAnnotationId.value)
    if (index >= 0) {
      const existingAnnotation = savedAnnotations.value[index]
      if (!existingAnnotation || existingAnnotation.annotationKind !== 'event') {
        return
      }

      const updatedAnnotation: SavedEventAnnotation = {
        ...existingAnnotation,
        ...selectedInterval.value,
        wellId: selectedWell.value,
        wellGroupId: currentWellGroupId.value,
        eventType,
        classification: { ...episodeForm.value.classification },
        confidenceEvent: episodeForm.value.confidenceEvent,
        comment: episodeForm.value.comment,
        actions: episodeForm.value.eventActions
      }
      normalizeAnnotationsForLayer(updatedAnnotation)
      const saved = await persistMarkupNow()
      message[saved ? 'success' : 'warning'](
        saved ? 'Аннотация эпизода обновлена.' : 'Аннотация обновлена в интерфейсе, но не сохранена на backend.'
      )
      return
    }
  }

  const newAnnotations: SavedEventAnnotation[] = draftIntervals.map((interval) => ({
    id: createAnnotationId('event'),
    wellId: selectedWell.value,
    wellGroupId: currentWellGroupId.value,
    ...interval,
    annotationKind: 'event',
    eventType,
    classification: { ...episodeForm.value.classification },
    confidenceEvent: episodeForm.value.confidenceEvent,
    comment: episodeForm.value.comment,
    actions: episodeForm.value.eventActions
  }))

  newAnnotations.forEach((annotation) => normalizeAnnotationsForLayer(annotation))

  if (newAnnotations.length === 1) {
    editingAnnotationId.value = newAnnotations[0]?.id ?? null
    editingAnnotationKind.value = 'event'
  } else {
    editingAnnotationId.value = null
    editingAnnotationKind.value = null
  }

  const saved = await persistMarkupNow()
  const successMessage =
    newAnnotations.length > 1 ? `Аннотации эпизода сохранены: ${newAnnotations.length}.` : 'Аннотация эпизода сохранена.'
  message[saved ? 'success' : 'warning'](
    saved ? successMessage : 'Аннотация создана в интерфейсе, но не сохранена на backend.'
  )
}

async function saveClassificationLevel(levelKey: string) {
  const draftIntervals = getDraftIntervalsForNewAnnotation()

  if (!selectedInterval.value && draftIntervals.length === 0) {
    message.error('Перед сохранением уровня выберите интервал.')
    return
  }

  const eventType = resolveSingleLevelEventType(levelKey)

  if (!eventType) {
    message.error('Выберите или введите категорию уровня.')
    return
  }

  const classification = buildSingleLevelClassification(levelKey)

  if (editingAnnotationId.value && editingAnnotationKind.value === 'event' && selectedInterval.value) {
    const index = savedAnnotations.value.findIndex((item) => item.id === editingAnnotationId.value)
    if (index >= 0) {
      const existingAnnotation = savedAnnotations.value[index]
      const existingLevelKey = existingAnnotation ? getPrimaryClassificationLevelKey(existingAnnotation.classification) : null
      if (existingAnnotation?.annotationKind === 'event' && existingLevelKey === levelKey) {
        const updatedAnnotation: SavedEventAnnotation = {
          ...existingAnnotation,
          ...selectedInterval.value,
          wellId: selectedWell.value,
          wellGroupId: currentWellGroupId.value,
          eventType,
          classification,
          confidenceEvent: episodeForm.value.confidenceEvent,
          comment: episodeForm.value.comment,
          actions: episodeForm.value.eventActions
        }
        normalizeAnnotationsForLayer(updatedAnnotation)
        const saved = await persistMarkupNow()
        message[saved ? 'success' : 'warning'](
          saved ? 'Уровень разметки обновлён.' : 'Уровень обновлён в интерфейсе, но не сохранён на backend.'
        )
        return
      }
    }
  }

  const newAnnotations: SavedEventAnnotation[] = draftIntervals.map((interval) => ({
    id: createAnnotationId('event'),
    wellId: selectedWell.value,
    wellGroupId: currentWellGroupId.value,
    ...interval,
    annotationKind: 'event',
    eventType,
    classification: { ...classification },
    confidenceEvent: episodeForm.value.confidenceEvent,
    comment: episodeForm.value.comment,
    actions: episodeForm.value.eventActions
  }))

  newAnnotations.forEach((annotation) => normalizeAnnotationsForLayer(annotation))

  if (newAnnotations.length === 1) {
    editingAnnotationId.value = newAnnotations[0]?.id ?? null
    editingAnnotationKind.value = 'event'
  }

  const saved = await persistMarkupNow()
  const successMessage =
    newAnnotations.length > 1 ? `Уровни разметки сохранены: ${newAnnotations.length}.` : 'Уровень разметки сохранён.'
  message[saved ? 'success' : 'warning'](
    saved ? successMessage : 'Уровень создан в интерфейсе, но не сохранён на backend.'
  )
}

async function deleteClassificationLevel(levelKey: string) {
  const annotationsToDelete = getSavedAnnotationsForSelectedLevel(levelKey)

  if (annotationsToDelete.length === 0) {
    return
  }

  const confirmed = window.confirm('Удалить сохранённый эпизод этого уровня?')
  if (!confirmed) {
    return
  }

  const idsToDelete = new Set(annotationsToDelete.map((annotation) => annotation.id))
  savedAnnotations.value = savedAnnotations.value.filter((item) => !idsToDelete.has(item.id))

  if (editingAnnotationId.value && idsToDelete.has(editingAnnotationId.value)) {
    editingAnnotationId.value = null
    editingAnnotationKind.value = null
  }

  setClassificationValue(levelKey, null)
  const saved = await persistMarkupNow()
  message[saved ? 'success' : 'warning'](
    saved ? 'Уровень разметки удалён.' : 'Уровень удалён в интерфейсе, но не сохранён на backend.'
  )
}

async function deleteAnnotation() {
  if (!editingAnnotationId.value) {
    return
  }

  const confirmed = window.confirm('Удалить эту аннотацию?')
  if (!confirmed) {
    return
  }

  savedAnnotations.value = savedAnnotations.value.filter((item) => item.id !== editingAnnotationId.value)
  editingAnnotationId.value = null
  editingAnnotationKind.value = null
  selectedInterval.value = null
  episodeForm.value = createDefaultEpisodeForm()
  const saved = await persistMarkupNow()
  message[saved ? 'success' : 'warning'](
    saved ? 'Аннотация удалена.' : 'Аннотация удалена в интерфейсе, но не сохранена на backend.'
  )
}

watch(
  savedAnnotations,
  () => {
    scheduleMarkupSave()
  },
  { deep: true }
)

watch(
  episodeTypeOptions,
  () => {
    scheduleMarkupSave()
  },
  { deep: true }
)

watch(
  actionOptions,
  () => {
    scheduleMarkupSave()
  },
  { deep: true }
)

watch(
  manualFrequencyBreakpoints,
  () => {
    scheduleMarkupSave()
  },
  { deep: true }
)

watch(
  suppressedFrequencyBreakpoints,
  () => {
    scheduleMarkupSave()
  },
  { deep: true }
)

watch(
  autoEpisodeReviews,
  () => {
    scheduleMarkupSave()
  },
  { deep: true }
)

watch(
  selectedWell,
  (wellId) => {
    groupMigrationTarget.value = wellGroupAssignments.value[wellId] ?? null
    newGroupName.value = ''
    clearCandidateAutoSelection()
    selectedFrequencyBreakpointId.value = null
    clearFrequencySegmentSelection()
    const assignedGroupId = wellGroupAssignments.value[wellId] ?? null
    if (
      assignedGroupId &&
      navigationGroupId.value !== assignedGroupId &&
      wellGroupOptions.value.some((option) => option.value === assignedGroupId)
    ) {
      navigationGroupId.value = assignedGroupId
    }

    if (initialDataLoaded.value) {
      void loadData()
    }
  },
  { immediate: true }
)

watch([selectedWell, interactionMode], persistUiState, { immediate: true })

watch(
  modelSelectedGroupId,
  (groupId) => {
    if (!modelParamsByGroup.value[groupId]) {
      modelParamsByGroup.value = {
        ...modelParamsByGroup.value,
        [groupId]: {}
      }
    }
  },
  { immediate: true }
)

watch(interactionMode, (nextMode, previousMode) => {
  if (previousMode === 'annotate' && nextMode === 'navigate') {
    resetAnnotationSelection()
    selectedAnalysisInterval.value = null
  }

  if (nextMode === 'periodSummary' && periodSummaryRows.value.length === 0 && !periodSummaryLoading.value) {
    void loadPeriodSummary()
  }
})

watch([periodSummaryPreset, periodSummaryDateRange, periodSummaryFieldCode, periodSummaryWellId], () => {
  if (interactionMode.value === 'periodSummary') {
    void loadPeriodSummary()
  }
})

watch(periodSummaryFieldCode, () => {
  if (periodSummaryWellId.value === 'all') {
    return
  }

  const selectedWellStillAvailable = periodSummaryWellOptions.value.some((option) => option.value === periodSummaryWellId.value)
  if (!selectedWellStillAvailable) {
    periodSummaryWellId.value = 'all'
  }
})

watch(navigationGroupId, (groupId) => {
  if (!groupId) {
    return
  }

  const hasSelectedWellInGroup = filteredWellOptions.value.some((option) => option.value === selectedWell.value)
  if (!hasSelectedWellInGroup) {
    const fallbackWell = filteredWellOptions.value[0]?.value
    if (fallbackWell) {
      selectedWell.value = fallbackWell
    }
  }
})

onMounted(async () => {
  await initializeWellOptions()
  await loadModelParamsFromBackend()
  await loadData()
  initialDataLoaded.value = true

  window.setTimeout(() => {
    void restorePersistentMarkup()
  }, 500)
})
</script>
