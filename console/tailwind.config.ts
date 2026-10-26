import type { Config } from 'tailwindcss';

/**
 * witness console design tokens.
 *
 * Rules of the palette:
 *  - ONE accent (orange #FF9F0A) — reserved for the playhead, focus and CTAs.
 *  - Severity colours (info / warn / stop) appear ONLY as state, never decoration.
 *  - Lane colours are low-chroma so a red STOP band is the loudest thing on screen.
 */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: { DEFAULT: '#0a0d14', deep: '#06080d', well: '#080b11' },
        card: { DEFAULT: '#111722', raised: '#161e2c', hover: '#1a2333' },
        line: { DEFAULT: '#1f2836', strong: '#2c3749', faint: '#171e2a' },
        fg: { DEFAULT: '#F5F8FD', 2: '#C3CCD9', 3: '#8590A2', 4: '#566179', 5: '#3a4458' },
        accent: { DEFAULT: '#FF9F0A', soft: '#FFC24D', deep: '#c77700' },
        ok: '#3ddc97',
        info: '#6f9bff',
        warn: '#f2b23e',
        stop: '#ff5d5d',
        lane: {
          claim: '#b8a2ff',
          proc: '#7fb4cc',
          fs: '#5fd0b5',
          net: '#ff9f6a',
          witness: '#FF9F0A',
          meta: '#8590A2',
        },
      },
      fontFamily: {
        ui: ['"Inter Variable"', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono Variable"', '"JetBrains Mono"', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      fontSize: {
        label: ['10.5px', { lineHeight: '1', letterSpacing: '0.16em' }],
        micro: ['11.5px', { lineHeight: '1.35' }],
        data: ['12.5px', { lineHeight: '1.45' }],
      },
      borderRadius: { sm: '4px', md: '8px', lg: '10px', xl: '14px' },
      boxShadow: {
        card: '0 1px 0 0 rgba(255,255,255,0.035) inset, 0 24px 60px -32px rgba(0,0,0,0.9)',
        'glow-accent': '0 0 0 1px #FF9F0A40, 0 0 28px -6px #FF9F0A80',
        'glow-stop': '0 0 0 1px #ff5d5d55, 0 0 48px -10px #ff5d5d99',
        'glow-warn': '0 0 0 1px #f2b23e44, 0 0 36px -10px #f2b23e88',
        'glow-ok': '0 0 0 1px #3ddc9744, 0 0 32px -10px #3ddc9788',
        'glow-info': '0 0 0 1px #6f9bff44, 0 0 32px -10px #6f9bff88',
      },
      transitionTimingFunction: {
        enter: 'cubic-bezier(0.2, 0.8, 0.2, 1)',
        exit: 'cubic-bezier(0.4, 0, 1, 1)',
        stamp: 'cubic-bezier(0.1, 0.9, 0.2, 1.05)',
      },
      keyframes: {
        heartbeat: { '0%, 100%': { opacity: '0.35' }, '50%': { opacity: '1' } },
        'row-in': { from: { opacity: '0', transform: 'translateY(6px)' }, to: { opacity: '1', transform: 'none' } },
        'fade-in': { from: { opacity: '0' }, to: { opacity: '1' } },
        'pop-in': {
          '0%': { opacity: '0', transform: 'scale(0.96) translateY(4px)' },
          '100%': { opacity: '1', transform: 'none' },
        },
        stamp: {
          '0%': { opacity: '0', transform: 'rotate(-9deg) scale(1.9)' },
          '60%': { opacity: '1', transform: 'rotate(-7deg) scale(0.96)' },
          '100%': { opacity: '1', transform: 'rotate(-7deg) scale(1)' },
        },
        flash: {
          '0%': { boxShadow: '0 0 0 0 rgba(255,159,10,0.0)' },
          '25%': { boxShadow: '0 0 0 2px rgba(255,159,10,0.9), 0 0 32px 0 rgba(255,159,10,0.35)' },
          '100%': { boxShadow: '0 0 0 1px rgba(255,159,10,0.35), 0 0 0 0 rgba(255,159,10,0)' },
        },
        'pulse-ring': {
          '0%': { transform: 'scale(1)', opacity: '0.7' },
          '100%': { transform: 'scale(2.6)', opacity: '0' },
        },
        sweep: { from: { transform: 'translateX(-100%)' }, to: { transform: 'translateX(100%)' } },
        'band-in': { from: { opacity: '0', transform: 'scaleY(0.2)' }, to: { opacity: '1', transform: 'scaleY(1)' } },
      },
      animation: {
        heartbeat: 'heartbeat 1.6s ease-in-out infinite',
        'row-in': 'row-in 220ms cubic-bezier(0.2,0.8,0.2,1) both',
        'fade-in': 'fade-in 240ms cubic-bezier(0.2,0.8,0.2,1) both',
        'pop-in': 'pop-in 260ms cubic-bezier(0.2,0.8,0.2,1) both',
        stamp: 'stamp 320ms cubic-bezier(0.1,0.9,0.2,1.05) both',
        flash: 'flash 1100ms cubic-bezier(0.2,0.8,0.2,1) both',
        'pulse-ring': 'pulse-ring 1.4s cubic-bezier(0.2,0.8,0.2,1) infinite',
        sweep: 'sweep 2.4s cubic-bezier(0.4,0,0.2,1) infinite',
        'band-in': 'band-in 360ms cubic-bezier(0.2,0.8,0.2,1) both',
      },
      maxWidth: { canvas: '1680px' },
    },
  },
  plugins: [],
} satisfies Config;
