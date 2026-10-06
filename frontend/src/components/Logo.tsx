import { useId } from 'react';

const LETTERS = [
  '20,49 20,23 26,23 31,33 36,23 42,23 42,49 36.5,49 36.5,34 31,44 25.5,34 25.5,49',
  '48,49 48,23 54,23 54,33 60,23 67,23 58,36 67,49 60,49 54,39.5 54,49',
  '72,23 94,23 94,29 86,29 86,49 80,49 80,29 72,29',
];

export function Logo({ width = 60, className = '' }: { width?: number; className?: string }) {
  const grad = useId();
  return (
    <svg
      className={`logo ${className}`.trim()}
      viewBox="0 0 120 72"
      width={width}
      height={(width * 72) / 120}
      aria-hidden="true"
      focusable="false"
    >
      <defs>
        <linearGradient id={grad} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#7fb0f0" />
          <stop offset="55%" stopColor="#6b8fd6" />
          <stop offset="100%" stopColor="#8a74d6" />
        </linearGradient>
      </defs>

      <polygon
        points="18,6 116,6 102,66 4,66"
        fill="none"
        stroke={`url(#${grad})`}
        strokeWidth={3.2}
        strokeLinejoin="round"
      />

      <g transform="translate(11.4 0) skewX(-13.13)">
        {LETTERS.map((points) => (
          <polygon
            key={points}
            points={points}
            fill={`url(#${grad})`}
            fillOpacity={0.22}
            stroke={`url(#${grad})`}
            strokeWidth={1.8}
            strokeLinejoin="round"
          />
        ))}
      </g>
    </svg>
  );
}
