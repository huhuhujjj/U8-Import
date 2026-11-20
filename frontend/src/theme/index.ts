import { createSystem, defaultConfig, defineConfig } from "@chakra-ui/react"

const config = defineConfig({
  theme: {
    tokens: {
      colors: {
        // Brand colors matching current Tailwind blue
        brand: {
          50: { value: "#eff6ff" },   // blue-50
          100: { value: "#dbeafe" },  // blue-100
          200: { value: "#bfdbfe" },  // blue-200
          300: { value: "#93c5fd" },  // blue-300
          400: { value: "#60a5fa" },  // blue-400
          500: { value: "#3b82f6" },  // blue-500
          600: { value: "#2563eb" },  // blue-600 (primary)
          700: { value: "#1d4ed8" },  // blue-700
          800: { value: "#1e40af" },  // blue-800
          900: { value: "#1e3a8a" },  // blue-900
        },
        // Success colors (green)
        success: {
          50: { value: "#f0fdf4" },
          100: { value: "#dcfce7" },
          500: { value: "#22c55e" },  // green-500
          600: { value: "#16a34a" },  // green-600
          700: { value: "#15803d" },
        },
        // Error colors (red)
        error: {
          50: { value: "#fef2f2" },
          100: { value: "#fee2e2" },
          500: { value: "#ef4444" },  // red-500
          600: { value: "#dc2626" },  // red-600
          700: { value: "#b91c1c" },
        },
        // Warning colors (yellow)
        warning: {
          50: { value: "#fefce8" },
          100: { value: "#fef9c3" },
          500: { value: "#eab308" },  // yellow-500
          600: { value: "#ca8a04" },  // yellow-600
          700: { value: "#a16207" },
        },
      },
      fonts: {
        body: { value: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" },
        heading: { value: "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif" },
      },
      spacing: {
        contentWrapper: { value: "1920px" },
      },
    },
    semanticTokens: {
      colors: {
        primary: {
          value: { base: "{colors.brand.600}", _dark: "{colors.brand.400}" },
        },
        "primary.hover": {
          value: { base: "{colors.brand.700}", _dark: "{colors.brand.500}" },
        },
        "primary.active": {
          value: { base: "{colors.brand.800}", _dark: "{colors.brand.600}" },
        },
      },
    },
  },
})

export const system = createSystem(defaultConfig, config)
