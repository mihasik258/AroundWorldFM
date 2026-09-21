/** @type {import('tailwindcss').Config} */


// The receiver palette. `slate` and `indigo` are deliberately remapped onto it so
// that existing utility-class markup (the modals) picks up the new design without
// a rewrite: bg-slate-900 becomes recessed panel, indigo becomes the dial lamp.
const void_ = '#070a10';
const bone = '#e8e3d8';
const lamp = '#ffb347';

export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        void: void_,
        deep: '#0c1018',
        raise: '#121824',
        bone,
        ash: '#8b8a85',
        lamp,
        twilight: '#5b8bb0',

        slate: {
          50: bone,
          100: bone,
          200: '#d3cec4',
          300: '#a9a7a1',
          400: '#8b8a85',
          500: '#6f7178',
          600: '#4a4e57',
          700: '#2a303c',
          800: '#171d28',
          900: '#0c1018',
          950: void_,
        },

        indigo: {
          200: '#ffd9a3',
          300: '#ffc670',
          400: lamp,
          500: lamp,
          600: '#e89a33',
          700: '#c8811f',
        },
      },

      fontFamily: {
        sans: ['Onest', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },

      // Flattened radii: an instrument panel has tight corners, not bubbles.
      borderRadius: {
        lg: '5px',
        xl: '6px',
        '2xl': '8px',
        '3xl': '10px',
      },
    },
  },
  plugins: [],
};
