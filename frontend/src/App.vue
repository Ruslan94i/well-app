<template>
  <n-config-provider :theme-overrides="themeOverrides">
    <n-message-provider>
      <div class="min-h-screen bg-[linear-gradient(180deg,_#f8fafc_0%,_#e2e8f0_100%)] text-slate-900">
        <header class="border-b border-slate-200 bg-white/90 shadow-sm backdrop-blur">
          <div class="mx-auto max-w-7xl px-4 py-4 md:px-6 lg:px-8">
            <h1 class="text-2xl font-semibold tracking-tight text-slate-900">Well Time Series App</h1>
          </div>
        </header>

        <WellTimeSeriesView />
      </div>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { NConfigProvider, NMessageProvider } from 'naive-ui'
import WellTimeSeriesView from '@/views/WellTimeSeriesView.vue'

const themeOverrides = {
  common: {
    primaryColor: '#0f766e',
    primaryColorHover: '#0d9488',
    primaryColorPressed: '#115e59',
    bodyColor: '#f8fafc',
    cardColor: '#ffffff',
    textColorBase: '#0f172a',
    borderColor: '#cbd5e1'
  }
}
</script>
