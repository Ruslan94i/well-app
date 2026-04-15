<template>
  <main class="flex min-h-screen w-full flex-col px-3 py-2 md:px-4 md:py-3 lg:px-4 lg:py-3">
    <section class="grid min-h-0 flex-1 gap-3 xl:grid-cols-[248px_minmax(0,1fr)]">
      <aside class="panel rounded-2xl p-4">
        <div class="space-y-4">
          <div>
            <h2 class="text-sm font-semibold uppercase tracking-[0.2em] text-slate-400">Параметры</h2>
          </div>

          <div>
            <label class="mb-2 block text-sm text-slate-300">Группа скважин</label>
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
        <div class="panel rounded-2xl px-4 py-3">
          <div class="space-y-3">
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div class="flex items-center gap-2">
                <span class="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Режим</span>
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
                    Подбор модели
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

      <section v-if="interactionMode !== 'modelTuning'" class="grid gap-3 xl:grid-cols-[minmax(0,1fr)_344px]">
        <div class="panel rounded-2xl p-4">
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
            <TimeSeriesChart
              ref="chartRef"
              :data="chartData"
              :active-series="activeSeries"
              :selected-interval="selectedInterval"
              :event-tracks="eventTracks"
              :interaction-mode="interactionMode"
              :saved-annotations="currentWellAnnotations"
              :selected-annotation-id="editingAnnotationId"
              :visible-date-range="visibleDateRange"
              @interval-selected="handleIntervalSelected"
              @annotation-clicked="handleAnnotationClicked"
              @visible-range-changed="handleVisibleRangeChanged"
              @background-clicked="handleChartBackgroundClicked"
            />
            <div
              v-if="!chartData.length"
              class="rounded-xl border border-dashed border-slate-700 bg-slate-900/50 px-3 py-2 text-sm text-slate-400"
            >
              Нет данных для выбранной скважины и диапазона дат.
            </div>
          </div>
        </div>

        <aside class="panel rounded-2xl p-4">
          <template v-if="interactionMode === 'navigate'">
            <div class="flex items-start justify-between gap-2">
              <div>
                <h2 class="text-base font-semibold text-slate-100">Аналитика интервала</h2>
                <p class="mt-1 text-xs leading-5 text-slate-400">
                  Нажмите на эпизод или режим на timeline, чтобы получить инженерное сравнение до, в периоде и после интервала.
                </p>
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
              Нажмите на интервал на дорожке `Эпизоды (модель)` или `Режимы (модель)`, чтобы открыть аналитическое сравнение.
            </div>
          </template>

          <template v-else>
            <div class="flex items-start justify-between gap-2">
              <div>
                <h2 class="text-base font-semibold text-slate-100">{{ annotationPanelTitle }}</h2>
              </div>
            </div>

            <div
              v-if="selectedInterval"
              class="mt-3 rounded-lg border border-sky-500/40 bg-sky-950/30 px-3 py-2.5"
            >
              <div class="grid grid-cols-[110px_minmax(0,1fr)] items-start gap-x-3 gap-y-1.5 text-sm leading-5">
                <div class="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-400">Дата</div>
                <div class="min-w-0 font-medium text-slate-100">
                  {{ selectedInterval.startDate }} — {{ selectedInterval.endDate }}
                </div>

                <div class="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-400">Длительность</div>
                <div class="min-w-0 text-slate-200">{{ selectedInterval.durationDays }} сут.</div>

                <div class="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-400">Группа</div>
                <div class="min-w-0 text-slate-200">{{ currentWellGroupLabel }}</div>
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

          <div v-if="selectedInterval" class="mt-3 space-y-4 rounded-xl border border-slate-700 bg-slate-800/90 p-4">

            <div>
              <label class="mb-1 block text-xs uppercase tracking-[0.2em] text-slate-400">Тип эпизода</label>
              <n-select v-model:value="episodeForm.episodeType" size="medium" :options="episodeTypeOptions" class="w-full" />
            </div>

            <div>
              <label class="mb-1 block text-xs uppercase tracking-[0.2em] text-slate-400">Уверенность эпизода</label>
              <n-radio-group v-model:value="episodeForm.confidenceEvent" size="small">
                <div class="flex flex-wrap gap-3">
                  <n-radio
                    v-for="option in confidenceOptions"
                    :key="`event-${option.value}`"
                    :value="option.value"
                    :label="option.label"
                  />
                </div>
              </n-radio-group>
              <n-button class="mt-2" type="primary" size="medium" @click="saveEvent">Сохранить событие</n-button>
            </div>

            <div>
              <label class="mb-1 block text-xs uppercase tracking-[0.2em] text-slate-400">Режим</label>
              <n-select v-model:value="episodeForm.rootCause" size="medium" :options="rootCauseOptions" class="w-full" />
            </div>

            <div>
              <label class="mb-1 block text-xs uppercase tracking-[0.2em] text-slate-400">Уверенность режима</label>
              <n-radio-group v-model:value="episodeForm.confidenceCause" size="small">
                <div class="flex flex-wrap gap-3">
                  <n-radio
                    v-for="option in confidenceOptions"
                    :key="`cause-${option.value}`"
                    :value="option.value"
                    :label="option.label"
                  />
                </div>
              </n-radio-group>
              <n-button class="mt-2" type="primary" secondary size="medium" @click="saveRootCause">Сохранить причину</n-button>
            </div>

            <div>
              <label class="mb-1 block text-xs uppercase tracking-[0.2em] text-slate-400">Комментарий</label>
              <n-input
                v-model:value="episodeForm.comment"
                type="textarea"
                size="medium"
                placeholder="Добавьте короткий комментарий"
                :autosize="{ minRows: 4, maxRows: 6 }"
              />
            </div>

            <div class="flex flex-col gap-2">
              <n-button v-if="isEditMode" type="error" secondary @click="deleteAnnotation">Удалить</n-button>
              <n-button secondary @click="handleClearSelectionClick">Очистить выделение</n-button>
              <n-button quaternary @click="zoomToSelection">Приблизить к выделению</n-button>
              <n-button quaternary @click="resetZoom">Сбросить масштаб</n-button>
            </div>
          </div>

          <div
            v-else
            class="mt-3 rounded-xl border border-dashed border-slate-700 bg-slate-900/50 px-3 py-4 text-sm text-slate-400"
          >
            Интервал ещё не выбран. Переключитесь в режим разметки и протяните мышью по графику, чтобы выбрать временное окно.
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
                  {{ episode.annotationKind === 'event' ? `Эпизод: ${getEpisodeTypeLabel(episode.eventType)}` : `Режим: ${getRootCauseLabel(episode.rootCause)}` }}
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

      <section v-else>
        <div class="panel rounded-2xl p-5">
          <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
            <div class="space-y-4">
              <div class="rounded-xl border border-slate-700 bg-slate-900/50 px-4 py-4">
                <div class="grid gap-4 md:grid-cols-2">
                  <div>
                    <label class="mb-2 block text-sm font-medium text-slate-300">Группа</label>
                    <n-select
                      v-model:value="modelSelectedGroupId"
                      :options="wellGroupOptions"
                      placeholder="Выберите группу"
                    />
                  </div>

                  <div>
                    <label class="mb-2 block text-sm font-medium text-slate-300">Использовать настройки из группы</label>
                    <div class="flex gap-2">
                      <n-select
                        v-model:value="copySettingsFromGroupId"
                        :options="copySourceGroupOptions"
                        clearable
                        placeholder="Выберите группу"
                        class="flex-1"
                      />
                      <n-button secondary @click="copyModelSettingsFromGroup">Копировать</n-button>
                    </div>
                  </div>
                </div>
              </div>

              <div class="rounded-xl border border-slate-700 bg-slate-800/90 px-4 py-4">
                <div class="text-sm font-semibold text-slate-100">Влияние параметров</div>
                <div class="mt-1 text-xs text-slate-400">
                  Оценивайте относительную важность инженерных признаков поведения скважины и реакции на воздействия.
                </div>

                <div class="mt-3 space-y-3">
                  <div
                    v-for="group in modelInfluenceParameterGroups"
                    :key="group.key"
                    class="rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-3"
                  >
                    <div class="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">{{ group.label }}</div>
                    <div class="mt-3 grid gap-3 md:grid-cols-2">
                      <div
                        v-for="parameter in group.features"
                        :key="parameter.key"
                        class="rounded-lg border border-slate-700 bg-slate-800/90 px-3 py-2.5"
                      >
                        <label class="mb-2 block text-sm text-slate-300">{{ parameter.label }}</label>
                        <n-select
                          v-model:value="currentModelSettings.parameterImportances[parameter.key]"
                          :options="importanceLevelOptions"
                          size="small"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div class="rounded-xl border border-slate-700 bg-slate-900/50 px-4 py-4">
                <div class="text-sm font-semibold text-slate-100">Расширенные настройки</div>

                <div class="mt-3 rounded-lg border border-slate-700 bg-slate-800/90 px-3 py-3">
                  <div class="text-sm font-semibold text-slate-100">Алгоритм модели</div>
                  <div class="mt-3 grid gap-2 md:grid-cols-2">
                    <button
                      v-for="option in modelAlgorithmOptions"
                      :key="option.value"
                      class="rounded-xl border px-3 py-3 text-left transition"
                      :class="
                        currentModelSettings.algorithm === option.value
                          ? 'border-sky-400 bg-sky-950/30'
                          : 'border-slate-700 bg-slate-900/50 hover:bg-slate-800'
                      "
                      @click="currentModelSettings.algorithm = option.value"
                    >
                      <div class="text-sm font-semibold text-slate-100">{{ option.label }}</div>
                      <div class="mt-1 text-xs leading-5 text-slate-300">{{ option.help }}</div>
                    </button>
                  </div>
                </div>

                <div class="mt-3 rounded-lg border border-slate-700 bg-slate-800/90 px-3 py-3">
                  <div class="text-sm font-semibold text-slate-100">Разделение данных</div>
                  <div class="mt-1 text-xs text-slate-400">Обучение / проверка модели</div>
                  <n-radio-group v-model:value="currentModelSettings.split" class="mt-3 block">
                    <div class="flex flex-wrap gap-4">
                      <n-radio
                        v-for="option in modelSplitOptions"
                        :key="option.value"
                        :value="option.value"
                        :label="option.label"
                      />
                    </div>
                  </n-radio-group>
                </div>
              </div>
            </div>

            <aside class="space-y-4">
              <div class="rounded-xl border border-slate-700 bg-slate-800/90 px-4 py-4">
                <div class="text-sm font-semibold text-slate-100">R² для выбранной группы</div>
                <div class="mt-3 text-4xl font-semibold text-slate-100">
                  {{ currentGroupR2 !== null ? currentGroupR2.toFixed(2) : '—' }}
                </div>
                <div class="mt-2 text-xs leading-5 text-slate-400">
                  Качество рассчитывается mock-логикой и зависит от алгоритма, разбиения и важности выбранных признаков.
                </div>
                <n-button class="mt-4" type="primary" block @click="recalculateModelQuality">Пересчитать</n-button>
              </div>

              <div class="rounded-xl border border-slate-700 bg-slate-800/90 px-4 py-4">
                <div class="text-sm font-semibold text-slate-100">Качество по группам</div>
                <div class="mt-3 space-y-2">
                  <div
                    v-for="row in modelQualityRows"
                    :key="row.groupId"
                    class="flex items-center justify-between rounded-lg border border-slate-700 bg-slate-900/50 px-3 py-2"
                  >
                    <div class="text-sm text-slate-300">{{ row.label }}</div>
                    <div class="text-sm font-semibold text-slate-100">{{ row.r2 !== null ? row.r2.toFixed(2) : '—' }}</div>
                  </div>
                </div>
              </div>
            </aside>
          </div>
        </div>
      </section>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { NButton, NCheckbox, NCheckboxGroup, NDatePicker, NInput, NRadio, NRadioGroup, NSelect, useMessage } from 'naive-ui'
import TimeSeriesChart from '@/components/TimeSeriesChart.vue'
import { fetchWellIds, fetchWellTimeseries } from '@/services/api'
import { generateMockEventTracks } from '@/services/mockEventTracksV2'
import type {
  AnnotationKind,
  ConfidenceLevel,
  EpisodeFormState,
  EpisodeType,
  InteractionMode,
  RootCause,
  SavedAnnotation,
  SavedEventAnnotation,
  SavedRootCauseAnnotation,
  SelectedInterval,
  SeriesKey,
  TimelineAnnotationClickPayload,
  TimeSeriesPoint,
  VisibleDateRange,
  WellGroupId
} from '@/types/timeseries'

const message = useMessage()
const chartRef = ref<InstanceType<typeof TimeSeriesChart> | null>(null)
let groupSaveFeedbackTimeout: ReturnType<typeof setTimeout> | null = null
const CREATE_NEW_GROUP_OPTION = '__create_new_group__'

const defaultWellOptions = [
  { label: 'WELL-101', value: 'WELL-101' },
  { label: 'WELL-102', value: 'WELL-102' },
  { label: 'WELL-103', value: 'WELL-103' },
  { label: 'WELL-104', value: 'WELL-104' },
  { label: 'WELL-105', value: 'WELL-105' },
  { label: 'WELL-201', value: 'WELL-201' },
  { label: 'WELL-202', value: 'WELL-202' },
  { label: 'WELL-203', value: 'WELL-203' },
  { label: 'WELL-204', value: 'WELL-204' },
  { label: 'WELL-301', value: 'WELL-301' },
  { label: 'WELL-302', value: 'WELL-302' },
  { label: 'WELL-303', value: 'WELL-303' },
  { label: 'WELL-304', value: 'WELL-304' },
  { label: 'WELL-305', value: 'WELL-305' },
  { label: 'WELL-306', value: 'WELL-306' }
]
const wellOptions = ref(defaultWellOptions)

const baseWellGroupOptions: { label: string; value: WellGroupId }[] = [
  { label: 'Группа 1', value: 'group-1' },
  { label: 'Группа 2', value: 'group-2' },
  { label: 'Группа 3', value: 'group-3' }
]

const seriesOptions: { label: string; value: SeriesKey }[] = [
  { label: 'Дебит жидкости', value: 'qliq' },
  { label: 'Дебит нефти', value: 'qoil' },
  { label: 'Добыча газа', value: 'qgas' },
  { label: 'Газовый фактор', value: 'gas_factor' },
  { label: 'Газожидкостный фактор', value: 'gas_liquid_factor' },
  { label: 'Дебит жидкости (в.расходомер)', value: 'qliq_wfm' },
  { label: 'Обводненность', value: 'water_cut' },
  { label: 'Давление на приеме', value: 'intake_pressure' },
  { label: 'Частота ЭЦН', value: 'esp_frequency' },
  { label: 'Загрузка', value: 'load' }
]

const episodeTypeOptions: { label: string; value: EpisodeType }[] = [
  { label: 'снижение', value: 'decline' },
  { label: 'нестабильность', value: 'instability' },
  { label: 'рост обводненности', value: 'water_cut_growth' },
  { label: 'останов', value: 'downtime' },
  { label: 'восстановление', value: 'recovery' },
  { label: 'смена режима', value: 'regime_change' },
  { label: 'после вмешательства', value: 'post_intervention' },
  { label: 'неизвестно', value: 'unknown' }
]

const rootCauseOptions: { label: string; value: RootCause }[] = [
  { label: 'деградация ЭЦН', value: 'esp_degradation' },
  { label: 'прорыв воды', value: 'water_breakthrough' },
  { label: 'нестабильная работа', value: 'unstable_operation' },
  { label: 'останов ВСП', value: 'downtime_vsp' },
  { label: 'эффект ОПЗ', value: 'opz_effect' },
  { label: 'замена ЭЦН', value: 'esp_replacement' },
  { label: 'ошибка телеметрии', value: 'telemetry_issue' },
  { label: 'неизвестно', value: 'unknown' }
]

function createDefaultEpisodeForm(): EpisodeFormState {
  return {
    episodeType: 'unknown',
    rootCause: 'unknown',
    confidenceEvent: 'medium',
    confidenceCause: 'medium',
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

type ModelAlgorithm = 'catboost' | 'gradient_boosting'
type ModelSplit = '70_30' | '80_20' | '90_10'
type ImportanceLevel = 'none' | 'medium' | 'high'

type ModelInfluenceKey =
  | 'qliq'
  | 'qoil'
  | 'water_cut'
  | 'intake_pressure'
  | 'esp_frequency'
  | 'load'
  | 'rate_change_speed'
  | 'water_cut_change_speed'
  | 'pressure_change_speed'
  | 'frequency_change_speed'
  | 'sharp_change'
  | 'instability'
  | 'oscillation'
  | 'deviation_from_mean'
  | 'deviation_from_trend'
  | 'reaction_to_frequency_change'
  | 'opz'
  | 'esp_change'

interface ModelGroupSettings {
  algorithm: ModelAlgorithm
  split: ModelSplit
  parameterImportances: Record<ModelInfluenceKey, ImportanceLevel>
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

const modelAlgorithmOptions = [
  { value: 'catboost' as const, label: 'CatBoost', help: 'CatBoost — устойчив к шуму' },
  { value: 'gradient_boosting' as const, label: 'Gradient Boosting', help: 'Gradient Boosting — быстрее, но менее устойчив' }
]

const modelSplitOptions = [
  { value: '70_30' as const, label: '70 / 30' },
  { value: '80_20' as const, label: '80 / 20' },
  { value: '90_10' as const, label: '90 / 10' }
]

const importanceLevelOptions = [
  { value: 'none' as const, label: 'Нет' },
  { value: 'medium' as const, label: 'Средняя' },
  { value: 'high' as const, label: 'Высокая' }
]

const modelInfluenceParameterGroups: {
  key: string
  label: string
  features: { key: ModelInfluenceKey; label: string }[]
}[] = [
  {
    key: 'base-parameters',
    label: 'Базовые параметры',
    features: [
      { key: 'qliq', label: 'Дебит жидкости' },
      { key: 'qoil', label: 'Дебит нефти' },
      { key: 'water_cut', label: 'Обводненность' },
      { key: 'intake_pressure', label: 'Давление на приеме' },
      { key: 'esp_frequency', label: 'Частота ЭЦН' },
      { key: 'load', label: 'Загрузка' }
    ]
  },
  {
    key: 'change-dynamics',
    label: 'Динамика изменений',
    features: [
      { key: 'rate_change_speed', label: 'Скорость изменения дебита' },
      { key: 'water_cut_change_speed', label: 'Скорость изменения обводненности' },
      { key: 'pressure_change_speed', label: 'Скорость изменения давления' },
      { key: 'frequency_change_speed', label: 'Скорость изменения частоты' },
      { key: 'sharp_change', label: 'Резкие изменения' }
    ]
  },
  {
    key: 'stability',
    label: 'Устойчивость',
    features: [
      { key: 'instability', label: 'Нестабильность параметров' },
      { key: 'oscillation', label: 'Колебания' }
    ]
  },
  {
    key: 'deviations',
    label: 'Отклонения',
    features: [
      { key: 'deviation_from_mean', label: 'Отклонение от среднего' },
      { key: 'deviation_from_trend', label: 'Отклонение от тренда' }
    ]
  },
  {
    key: 'control-actions',
    label: 'Управляющие воздействия',
    features: [
      { key: 'reaction_to_frequency_change', label: 'Реакция на изменение частоты ЭЦН' },
      { key: 'esp_change', label: 'Смена ЭЦН' },
      { key: 'opz', label: 'ОПЗ' }
    ]
  }
]

function createDefaultModelSettings(): ModelGroupSettings {
  return {
    algorithm: 'catboost',
    split: '80_20',
    parameterImportances: {
      qliq: 'medium',
      qoil: 'medium',
      water_cut: 'medium',
      intake_pressure: 'medium',
      esp_frequency: 'medium',
      load: 'medium',
      rate_change_speed: 'medium',
      water_cut_change_speed: 'medium',
      pressure_change_speed: 'medium',
      frequency_change_speed: 'medium',
      sharp_change: 'medium',
      instability: 'medium',
      oscillation: 'medium',
      deviation_from_mean: 'medium',
      deviation_from_trend: 'medium',
      reaction_to_frequency_change: 'medium',
      opz: 'medium',
      esp_change: 'medium'
    }
  }
}

function getEpisodeTypeLabel(value: EpisodeType): string {
  return episodeTypeOptions.find((option) => option.value === value)?.label ?? value
}

function getRootCauseLabel(value: RootCause): string {
  return rootCauseOptions.find((option) => option.value === value)?.label ?? value
}

function getWellGroupLabel(value: WellGroupId | null | undefined): string {
  if (!value) {
    return 'Не назначена'
  }

  return wellGroupOptions.value.find((option) => option.value === value)?.label ?? value
}

function cloneModelSettings(settings: ModelGroupSettings): ModelGroupSettings {
  return {
    algorithm: settings.algorithm,
    split: settings.split,
    parameterImportances: { ...settings.parameterImportances }
  }
}

function ensureModelSettings(groupId: WellGroupId | null | undefined): ModelGroupSettings {
  const resolvedGroupId = groupId ?? wellGroupOptions.value[0]?.value ?? 'group-1'

  if (!modelSettingsByGroup.value[resolvedGroupId]) {
    modelSettingsByGroup.value = {
      ...modelSettingsByGroup.value,
      [resolvedGroupId]: createDefaultModelSettings()
    }
  }

  return modelSettingsByGroup.value[resolvedGroupId]!
}

function simulateModelQuality(groupId: WellGroupId, settings: ModelGroupSettings): number {
  const groupHash = groupId.split('').reduce((sum, char) => sum + char.charCodeAt(0), 0)
  const algorithmBonus = settings.algorithm === 'catboost' ? 0.045 : 0.022
  const splitBonusMap: Record<ModelSplit, number> = {
    '70_30': 0.012,
    '80_20': 0.028,
    '90_10': 0.018
  }
  const importanceWeightMap: Record<ImportanceLevel, number> = {
    none: 0,
    medium: 0.55,
    high: 1
  }
  const parameterWeights: Record<ModelInfluenceKey, number> = {
    qliq: 0.08,
    qoil: 0.08,
    water_cut: 0.1,
    intake_pressure: 0.07,
    esp_frequency: 0.06,
    load: 0.06,
    rate_change_speed: 0.12,
    water_cut_change_speed: 0.11,
    pressure_change_speed: 0.1,
    frequency_change_speed: 0.08,
    sharp_change: 0.09,
    instability: 0.1,
    oscillation: 0.07,
    deviation_from_mean: 0.08,
    deviation_from_trend: 0.09,
    reaction_to_frequency_change: 0.09,
    opz: 0.08,
    esp_change: 0.07
  }

  const allModelInfluenceParameters = modelInfluenceParameterGroups.flatMap((group) => group.features)
  const weightedImportance = allModelInfluenceParameters.reduce((sum, parameter) => {
    const level = settings.parameterImportances[parameter.key]
    return sum + parameterWeights[parameter.key] * importanceWeightMap[level]
  }, 0)

  const normalizedImportance = weightedImportance / 1
  const groupAdjustment = ((groupHash % 11) - 5) * 0.004
  const rawScore = 0.48 + algorithmBonus + splitBonusMap[settings.split] + normalizedImportance * 0.22 + groupAdjustment

  return Math.max(0.5, Math.min(0.94, Number(rawScore.toFixed(2))))
}

const selectedWell = ref(defaultWellOptions[0]?.value ?? '')
const navigationGroupId = ref<WellGroupId | null>('group-1')
const dateRange = ref<[number, number] | null>(null)
const hiddenGasSeries: SeriesKey[] = ['qgas', 'gas_factor', 'gas_liquid_factor']
const activeSeries = ref<SeriesKey[]>(
  seriesOptions
    .map((series) => series.value)
    .filter((series) => !hiddenGasSeries.includes(series))
)
const chartData = ref<TimeSeriesPoint[]>([])
const selectedInterval = ref<SelectedInterval | null>(null)
const selectedAnalysisInterval = ref<TimelineAnnotationClickPayload | null>(null)
const visibleDateRange = ref<VisibleDateRange | null>(null)
const interactionMode = ref<InteractionMode>('navigate')
const episodeForm = ref<EpisodeFormState>(createDefaultEpisodeForm())
const modelSelectedGroupId = ref<WellGroupId>('group-1')
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
const modelSettingsByGroup = ref<Record<string, ModelGroupSettings>>({})
const modelQualityByGroup = ref<Record<string, number>>({})
const wellGroupOptions = ref(baseWellGroupOptions)
const wellGroupAssignments = ref<Record<string, WellGroupId | null>>({
  'WELL-101': 'group-1',
  'WELL-102': 'group-1',
  'WELL-103': 'group-1',
  'WELL-104': 'group-1',
  'WELL-105': 'group-1',
  'WELL-201': 'group-2',
  'WELL-202': 'group-2',
  'WELL-203': 'group-2',
  'WELL-204': 'group-2',
  'WELL-301': 'group-3',
  'WELL-302': 'group-3',
  'WELL-303': 'group-3',
  'WELL-304': 'group-3',
  'WELL-305': 'group-3',
  'WELL-306': 'group-3'
})
const savedAnnotations = ref<SavedAnnotation[]>([])
const editingAnnotationId = ref<string | null>(null)
const editingAnnotationKind = ref<AnnotationKind | null>(null)
const groupSaveFeedback = ref<'idle' | 'saved'>('idle')
const groupMigrationTarget = ref<WellGroupId | typeof CREATE_NEW_GROUP_OPTION | null>(null)
const newGroupName = ref('')
const loading = ref(false)
const errorMessage = ref('')

const eventTracks = computed(() => generateMockEventTracks(chartData.value))
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
const currentModelSettings = computed(() => ensureModelSettings(modelSelectedGroupId.value))
const copySourceGroupOptions = computed(() =>
  wellGroupOptions.value.filter((option) => option.value !== modelSelectedGroupId.value)
)
const currentGroupR2 = computed(() => {
  const groupId = modelSelectedGroupId.value
  return groupId ? (modelQualityByGroup.value[groupId] ?? null) : null
})
const modelQualityRows = computed(() =>
  wellGroupOptions.value.map((option) => ({
    groupId: option.value,
    label: option.label,
    r2: modelQualityByGroup.value[option.value] ?? null
  }))
)
const interactionModeHint = computed(() => {
  if (interactionMode.value === 'navigate') {
    return 'Масштабирование, панорамирование и анализ'
  }

  if (interactionMode.value === 'annotate') {
    return 'Протяните мышью для выбора интервала'
  }

  return 'Настройка алгоритма и оценка качества по группе'
})
const currentTabTitle = computed(() => {
  if (interactionMode.value === 'navigate') {
    return 'Анализ скважинной динамики'
  }

  if (interactionMode.value === 'annotate') {
    return 'Разметка'
  }

  return 'Подбор модели'
})
const currentTabDescription = computed(() => {
  if (interactionMode.value === 'navigate') {
    return 'Анализ работы скважины во времени: сверху — телеметрия, снизу — интерпретация (суточные причины, эпизоды и режимы)'
  }

  if (interactionMode.value === 'annotate') {
    return 'Разметка интервалов: выделяйте эпизоды и режимы, чтобы описать поведение скважины и обучить модель'
  }

  return 'Подбор параметров модели: настройте влияние факторов и оцените качество (R²) для выбранной группы скважин'
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
    layerLabel: interval.layer === 'event' ? 'Эпизод' : 'Режим',
    before,
    during,
    after,
    liquidDelta: cumulativeLiquid,
    oilDelta: cumulativeOil,
    liquidImpactLabel: liquidDelta < 0 ? 'Потеря жидкости за период' : 'Прирост жидкости за период',
    oilImpactLabel: oilDelta < 0 ? 'Потеря нефти за период' : 'Прирост нефти за период',
    potentialLiquid: constrainedPotential.liquid,
    potentialOil: constrainedPotential.oil,
    actions: buildSuggestedActions(interval, before, during, after),
    confidence: confidence.level,
    confidenceExplanation: confidence.explanation
  }
})

function isInteractionMode(mode: InteractionMode): boolean {
  return interactionMode.value === mode
}

const currentWellAnnotations = computed(() => savedAnnotations.value.filter((item) => item.wellId === selectedWell.value))
const isEditMode = computed(() => editingAnnotationId.value !== null)
const annotationPanelTitle = computed(() => {
  if (editingAnnotationKind.value === 'event') {
    return 'Редактирование эпизода'
  }

  if (editingAnnotationKind.value === 'rootCause') {
    return 'Редактирование режима'
  }

  return 'Создание аннотации'
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
    confidenceEvent: episode.annotationKind === 'event' ? episode.confidenceEvent : 'medium',
    confidenceCause: episode.annotationKind === 'rootCause' ? episode.confidenceCause : 'medium',
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
  return chartData.value.filter((point) => point.date >= startDate && point.date <= endDate)
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
    actions.push('Проверить состояние ЭЦН, текущий режим работы и результаты диагностики оборудования.')
  }

  if (waterCutRise > 5 && oilDrop > 2.5) {
    actions.push('Рассмотреть анализ водопритока, профиль притока и кандидата на водоизоляционные мероприятия.')
  }

  if (interval.label.toLowerCase().includes('опз') || interval.label.toLowerCase().includes('эффект опз')) {
    actions.push('Продолжить мониторинг устойчивости эффекта ОПЗ и контролировать скорость последующего падения дебита.')
  }

  if (interval.label.toLowerCase().includes('частот') || frequencyResponse > 3.5) {
    actions.push('Проверить возможность дальнейшей оптимизации режима по частоте ЭЦН на основе отклика дебита.')
  }

  if (pressureRise > 2 && liquidDrop > 3) {
    actions.push('Проверить изменение гидродинамического режима и выполнить анализ ограничений по приему насоса.')
  }

  if (interval.label.toLowerCase().includes('нестабиль')) {
    actions.push('Проверить устойчивость электропитания, автоматику управления и факторы, вызывающие колебания режима.')
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
    interval.layer === 'rootCause',
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
        wellId: annotation.wellId,
        wellGroupId: annotation.wellGroupId,
        annotationKind: 'event',
        eventType: annotation.eventType,
        confidenceEvent: annotation.confidenceEvent,
        comment: annotation.comment,
        ...interval
      }
  }

  return {
    id: idOverride ?? annotation.id,
    wellId: annotation.wellId,
    wellGroupId: annotation.wellGroupId,
    annotationKind: 'rootCause',
    rootCause: annotation.rootCause,
    confidenceCause: annotation.confidenceCause,
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
              wellId: preferredAnnotation.wellId,
              wellGroupId: preferredAnnotation.wellGroupId,
              annotationKind: 'event' as const,
              eventType: preferredAnnotation.eventType,
              confidenceEvent: preferredAnnotation.confidenceEvent,
              comment: preferredAnnotation.comment,
              ...mergedInterval
            }
          : {
              id: preferredAnnotation.id,
              wellId: preferredAnnotation.wellId,
              wellGroupId: preferredAnnotation.wellGroupId,
              annotationKind: 'rootCause' as const,
              rootCause: preferredAnnotation.rootCause,
              confidenceCause: preferredAnnotation.confidenceCause,
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
  const untouchedAnnotations = savedAnnotations.value.filter(
    (item) => item.wellId !== incomingAnnotation.wellId || item.annotationKind !== incomingAnnotation.annotationKind
  )
  const sameLayer = savedAnnotations.value.filter(
    (item) =>
      item.wellId === incomingAnnotation.wellId &&
      item.annotationKind === incomingAnnotation.annotationKind &&
      item.id !== incomingAnnotation.id
  )
  const trimmedLayer = resolveLayerOverlap(sameLayer, incomingAnnotation)
  const normalizedLayer = mergeAdjacentAnnotations([...trimmedLayer, incomingAnnotation], incomingAnnotation.id)

  savedAnnotations.value = [...untouchedAnnotations, ...normalizedLayer].sort(
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

  if (existingAnnotation.annotationKind === 'event') {
    return (
      intervalChanged ||
      existingAnnotation.eventType !== episodeForm.value.episodeType ||
      existingAnnotation.confidenceEvent !== episodeForm.value.confidenceEvent ||
      existingAnnotation.comment !== episodeForm.value.comment
    )
  }

  return (
    intervalChanged ||
    existingAnnotation.rootCause !== episodeForm.value.rootCause ||
    existingAnnotation.confidenceCause !== episodeForm.value.confidenceCause ||
    existingAnnotation.comment !== episodeForm.value.comment
  )
}

async function loadData() {
  if (!selectedWell.value) {
    chartData.value = []
    visibleDateRange.value = null
    return
  }

  loading.value = true
  errorMessage.value = ''
  selectedInterval.value = null
  selectedAnalysisInterval.value = null
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
    errorMessage.value = 'Не удалось загрузить временные ряды. Убедитесь, что backend запущен на http://localhost:8000.'
    message.error(errorMessage.value)
  } finally {
    loading.value = false
  }
}

function createWellGroupAssignments(wellIds: string[]): Record<string, WellGroupId | null> {
  const groupIds = baseWellGroupOptions.map((group) => group.value)

  return Object.fromEntries(
    wellIds.map((wellId, index) => [
      wellId,
      wellGroupAssignments.value[wellId] ?? groupIds[index % Math.max(groupIds.length, 1)] ?? null
    ])
  )
}

async function initializeWellOptions() {
  try {
    const wellIds = await fetchWellIds()
    if (wellIds.length === 0) {
      return
    }

    wellOptions.value = wellIds.map((wellId) => ({ label: wellId, value: wellId }))
    wellGroupAssignments.value = createWellGroupAssignments(wellIds)

    if (!wellIds.includes(selectedWell.value)) {
      selectedWell.value = wellIds[0] ?? ''
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

function copyModelSettingsFromGroup() {
  if (!modelSelectedGroupId.value) {
    message.error('Выберите группу, для которой нужно настроить модель.')
    return
  }

  if (!copySettingsFromGroupId.value) {
    message.error('Выберите группу-источник.')
    return
  }

  const sourceSettings = ensureModelSettings(copySettingsFromGroupId.value)
  modelSettingsByGroup.value = {
    ...modelSettingsByGroup.value,
    [modelSelectedGroupId.value]: cloneModelSettings(sourceSettings)
  }
  message.success('Настройки модели скопированы в текущую группу.')
}

function recalculateModelQuality() {
  const groupId = modelSelectedGroupId.value
  if (!groupId) {
    message.error('Выберите группу для расчёта качества.')
    return
  }

  const nextScore = simulateModelQuality(groupId, currentModelSettings.value)
  modelQualityByGroup.value = {
    ...modelQualityByGroup.value,
    [groupId]: nextScore
  }
  message.success(`Качество для ${getWellGroupLabel(groupId)} пересчитано.`)
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

function handleAnnotationClicked(payload: TimelineAnnotationClickPayload) {
  if (interactionMode.value === 'navigate') {
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
  selectedInterval.value = null
  editingAnnotationId.value = null
  editingAnnotationKind.value = null
  episodeForm.value = createDefaultEpisodeForm()
}

function clearSelection(options?: { force?: boolean }) {
  if (!selectedInterval.value && !editingAnnotationId.value) {
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

function saveEvent() {
  if (!selectedInterval.value) {
    message.error('Перед сохранением эпизода выберите интервал.')
    return
  }

  if (!episodeForm.value.episodeType) {
    message.error('Выберите тип эпизода.')
    return
  }

  if (editingAnnotationId.value && editingAnnotationKind.value === 'event') {
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
        eventType: episodeForm.value.episodeType,
        confidenceEvent: episodeForm.value.confidenceEvent,
        comment: episodeForm.value.comment
      }
      normalizeAnnotationsForLayer(updatedAnnotation)
      message.success('Аннотация эпизода обновлена.')
      return
    }
  }

  const newAnnotation: SavedEventAnnotation = {
    id: createAnnotationId('event'),
    wellId: selectedWell.value,
    wellGroupId: currentWellGroupId.value,
    ...selectedInterval.value,
    annotationKind: 'event',
    eventType: episodeForm.value.episodeType,
    confidenceEvent: episodeForm.value.confidenceEvent,
    comment: episodeForm.value.comment
  }

  normalizeAnnotationsForLayer(newAnnotation)
  editingAnnotationId.value = newAnnotation.id
  editingAnnotationKind.value = 'event'
  message.success('Аннотация эпизода сохранена.')
}

function saveRootCause() {
  if (!selectedInterval.value) {
    message.error('Перед сохранением режима выберите интервал.')
    return
  }

  if (!episodeForm.value.rootCause) {
    message.error('Выберите причину.')
    return
  }

  if (editingAnnotationId.value && editingAnnotationKind.value === 'rootCause') {
    const index = savedAnnotations.value.findIndex((item) => item.id === editingAnnotationId.value)
    if (index >= 0) {
      const existingAnnotation = savedAnnotations.value[index]
      if (!existingAnnotation || existingAnnotation.annotationKind !== 'rootCause') {
        return
      }

      const updatedAnnotation: SavedRootCauseAnnotation = {
        ...existingAnnotation,
        ...selectedInterval.value,
        wellId: selectedWell.value,
        wellGroupId: currentWellGroupId.value,
        rootCause: episodeForm.value.rootCause,
        confidenceCause: episodeForm.value.confidenceCause,
        comment: episodeForm.value.comment
      }
      normalizeAnnotationsForLayer(updatedAnnotation)
      message.success('Аннотация режима обновлена.')
      return
    }
  }

  const newAnnotation: SavedRootCauseAnnotation = {
    id: createAnnotationId('rootCause'),
    wellId: selectedWell.value,
    wellGroupId: currentWellGroupId.value,
    ...selectedInterval.value,
    annotationKind: 'rootCause',
    rootCause: episodeForm.value.rootCause,
    confidenceCause: episodeForm.value.confidenceCause,
    comment: episodeForm.value.comment
  }

  normalizeAnnotationsForLayer(newAnnotation)
  editingAnnotationId.value = newAnnotation.id
  editingAnnotationKind.value = 'rootCause'
  message.success('Аннотация режима сохранена.')
}

function deleteAnnotation() {
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
  message.success('Аннотация удалена.')
}

watch(
  selectedWell,
  (wellId) => {
    groupMigrationTarget.value = wellGroupAssignments.value[wellId] ?? null
    newGroupName.value = ''
  },
  { immediate: true }
)

watch(
  modelSelectedGroupId,
  (groupId) => {
    ensureModelSettings(groupId)
  },
  { immediate: true }
)

watch(interactionMode, (nextMode, previousMode) => {
  if (previousMode === 'annotate' && nextMode === 'navigate') {
    resetAnnotationSelection()
    selectedAnalysisInterval.value = null
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
  wellGroupOptions.value.forEach((group) => {
    const settings = ensureModelSettings(group.value)
    modelQualityByGroup.value[group.value] = simulateModelQuality(group.value, settings)
  })

  await initializeWellOptions()
  await loadData()
})
</script>
