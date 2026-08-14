/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Growth / agriculture - refined forest green
        leaf: {
          50: '#f0f9f1', 100: '#dcf0de', 200: '#bbelc0', 300: '#8ecb97',
          400: '#5aad68', 500: '#379046', 600: '#277537', 700: '#205d2e',
          800: '#1d4a28', 900: '#193d23', 950: '#0a2110',
        },
        // Indian warmth - saffron / amber accent
        saffron: {
          50: '#fff8ed', 100: '#ffefd4', 200: '#ffdba8', 300: '#ffc171',
          400: '#ff9f38', 500: '#fe8316', 600: '#ef680b', 700: '#c64d0b',
          800: '#9d3d11', 900: '#7e3411', 950: '#441806',
        },
        // Warm neutrals - sand / parchment
        sand: {
          50: '#faf8f3', 100: '#f1ece0', 200: '#e3d8c3', 300: '#d0bd9d',
          400: '#bb9d76', 500: '#ac8659', 600: '#9e744d', 700: '#835d41',
          800: '#6b4c39', 900: '#583f30', 950: '#2f2019',
        },
        // Deep ink backgrounds for dark mode
        ink: {
          800: '#16201c', 900: '#0f1714', 950: '#080d0b',
        },
      },
      fontFamily: {
        sans: ['"Segoe UI"', 'system-ui', '-apple-system', 'Roboto', 'Helvetica', 'Arial', 'sans-serif'],
        display: ['"Segoe UI"', 'system-ui', 'sans-serif'],
        deva: ['"Nirmala UI"', '"Noto Sans Devanagari"', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        glow: '0 0 40px -10px rgba(254, 131, 22, 0.45)',
        leaf: '0 18px 40px -16px rgba(32, 93, 46, 0.55)',
        card: '0 10px 30px -12px rgba(8, 13, 11, 0.35)',
      },
      backgroundImage: {
        'mesh': 'radial-gradient(at 18% 18%, rgba(55,144,70,0.20) 0px, transparent 45%), radial-gradient(at 82% 12%, rgba(254,131,22,0.18) 0px, transparent 45%), radial-gradient(at 75% 85%, rgba(32,93,46,0.22) 0px, transparent 45%)',
      },
      keyframes: {
        floaty: {
          '0%,100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-10px)' },
        },
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
        sheen: {
          '0%': { backgroundPosition: '0% 50%' },
          '100%': { backgroundPosition: '200% 50%' },
        },
      },
      animation: {
        floaty: 'floaty 6s ease-in-out infinite',
        fadeUp: 'fadeUp 0.5s ease-out both',
        shimmer: 'shimmer 1.6s infinite',
        sheen: 'sheen 6s linear infinite',
      },
    },
  },
  plugins: [],
}