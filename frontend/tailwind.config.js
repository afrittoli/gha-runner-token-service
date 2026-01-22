/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // GitHub-inspired colors
        'gh-blue': '#0366d6',
        'gh-green': '#28a745',
        'gh-red': '#d73a49',
        'gh-orange': '#f66a0a',
        'gh-gray': {
          50: '#f6f8fa',
          100: '#eaecef',
          200: '#d1d5da',
          300: '#959da5',
          400: '#6a737d',
          500: '#586069',
          600: '#444d56',
          700: '#2f363d',
          800: '#24292e',
          900: '#1b1f23',
        },
      },
    },
  },
  plugins: [],
}
