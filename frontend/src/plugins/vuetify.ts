/**
 * plugins/vuetify.ts
 *
 * Framework documentation: https://vuetifyjs.com`
 */

// Styles
import '@mdi/font/css/materialdesignicons.css'
import 'vuetify/styles/main.css'

import colors from 'vuetify/util/colors'
import { fa, en, vi, zhHans, zhHant, ru } from 'vuetify/locale'

// Composables
import { createVuetify } from 'vuetify'

// https://vuetifyjs.com/en/introduction/why-vuetify/#feature-guides
export default createVuetify({
  defaults: {
    VRow: { density: 'compact' },
    VBtn: { rounded: 'lg' },
    VCard: { rounded: 'lg', elevation: 2 },
    VTextField: {
      variant: 'solo-filled',
      rounded: 'lg',
    },
    VSelect: {
      variant: 'solo-filled',
      rounded: 'lg',
    },
    VCombobox: {
      variant: 'solo-filled',
      rounded: 'lg',
    },
    VTextarea: {
      variant: 'solo-filled',
      rounded: 'lg',
    },
  },
  theme: {
    defaultTheme: localStorage.getItem('theme') ?? 'system',
    themes: {
      light: {
        colors: {
          primary: '#2563EB',
          secondary: '#64748B',
          success: '#16A34A',
          warning: '#EA580C',
          error: '#DC2626',
          info: '#0284C7',
          background: '#F4F6FB',
          surface: '#FFFFFF',
        },
      },
      dark: {
        colors: {
          primary: '#3B82F6',
          secondary: '#94A3B8',
          success: '#22C55E',
          warning: '#F97316',
          error: colors.red.accent3,
          info: '#38BDF8',
          background: '#0F172A',
          surface: '#1E293B',
        },
      },
    },
  },
  locale: {
    locale: localStorage.getItem("locale") ?? 'zhHans',
    fallback: 'zhHans',
    messages: { en, fa, vi, zhHans, zhHant, ru },
  },
})
