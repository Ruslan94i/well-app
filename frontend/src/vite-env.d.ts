/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_USE_MOCK_TELEMETRY?: string
  readonly VITE_USE_MOCK_EVENTS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
