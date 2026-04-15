<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="themeOverrides">
    <n-message-provider>
      <div class="min-h-screen bg-[linear-gradient(180deg,_#0f172a_0%,_#111827_100%)] text-slate-100">
        <WellTimeSeriesView />
      </div>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup lang="ts">
import { NConfigProvider, NMessageProvider, darkTheme } from 'naive-ui'
import WellTimeSeriesView from '@/views/WellTimeSeriesView.vue'

const themeOverrides = {
  common: {
    primaryColor: '#38bdf8',
    primaryColorHover: '#7dd3fc',
    primaryColorPressed: '#0ea5e9',
    bodyColor: '#0f172a',
    cardColor: '#1f2937',
    modalColor: '#1f2937',
    popoverColor: '#1f2937',
    tableColor: '#1f2937',
    actionColor: '#1e293b',
    textColorBase: '#e5e7eb',
    textColor1: '#e5e7eb',
    textColor2: '#9ca3af',
    textColor3: '#6b7280',
    placeholderColor: '#9ca3af',
    placeholderColorDisabled: '#6b7280',
    iconColor: '#9ca3af',
    iconColorHover: '#e5e7eb',
    borderColor: '#374151',
    dividerColor: '#374151',
    inputColor: '#0f172a',
    codeColor: '#0f172a'
  },
  Button: {
    textColorPrimary: '#e5e7eb',
    textColorHoverPrimary: '#e5e7eb',
    textColorPressedPrimary: '#e5e7eb',
    colorPrimary: '#0ea5e9',
    colorHoverPrimary: '#38bdf8',
    colorPressedPrimary: '#0284c7',
    borderPrimary: '#0ea5e9',
    borderHoverPrimary: '#38bdf8',
    borderPressedPrimary: '#0284c7'
  },
  Input: {
    color: '#0f172a',
    colorFocus: '#0f172a',
    colorDisabled: '#111827',
    border: '#374151',
    borderFocus: '#38bdf8',
    borderHover: '#60a5fa',
    textColor: '#e5e7eb',
    placeholderColor: '#9ca3af'
  },
  Select: {
    peers: {
      InternalSelection: {
        color: '#0f172a',
        border: '#374151',
        textColor: '#e5e7eb',
        placeholderColor: '#9ca3af'
      }
    }
  },
  DatePicker: {
    panelColor: '#1f2937'
  }
}
</script>
