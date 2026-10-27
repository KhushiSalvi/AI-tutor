// Playful, chunky icons. Same names as lucide-react so the rest of the UI keeps working.
// Thick rounded strokes + a soft colour blob (--pop-a/b/c) so they look hand-drawn and friendly.
const Svg = ({ size = 20, children, ...rest }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2.6"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    {...rest}
  >
    {children}
  </svg>
);

const A = { fill: "var(--pop-a)" };
const B = { fill: "var(--pop-b)" };
const C = { fill: "var(--pop-c)" };

export const ArrowUp = (p) => (
  <Svg {...p}>
    <path d="M12 19.5V5.5" />
    <path d="M5.5 11.5L12 5l6.5 6.5" />
  </Svg>
);
export const Plus = (p) => (
  <Svg {...p}>
    <path d="M12 5v14M5 12h14" />
  </Svg>
);
export const Square = (p) => (
  <Svg {...p} strokeWidth="0">
    <rect x="5" y="5" width="14" height="14" rx="4.5" fill="currentColor" />
  </Svg>
);
export const Video = (p) => (
  <Svg {...p}>
    <rect x="2.5" y="6" width="13" height="12" rx="3.8" style={A} />
    <path d="M15.5 10.5l5-3v9l-5-3z" style={B} />
  </Svg>
);
export const PanelLeft = (p) => (
  <Svg {...p}>
    <rect x="3" y="4" width="18" height="16" rx="5" />
    <path d="M9.5 4.5v15" />
  </Svg>
);
export const SquarePen = (p) => (
  <Svg {...p}>
    <path d="M11 4H7a3.5 3.5 0 00-3.5 3.5v9A3.5 3.5 0 007 20h9a3.5 3.5 0 003.5-3.5V13" />
    <path d="M17.2 3.6a2.1 2.1 0 013 3L12 14.8l-4 1 1-4 8.2-8.2z" style={A} />
  </Svg>
);
export const Search = (p) => (
  <Svg {...p}>
    <circle cx="10.5" cy="10.5" r="6.5" style={C} />
    <path d="M15.5 15.5L21 21" />
  </Svg>
);
export const Trash2 = (p) => (
  <Svg {...p}>
    <path d="M4 7h16" />
    <path d="M9.5 7V4.5h5V7" />
    <path d="M6 7l1 12.5a1.5 1.5 0 001.5 1.5h7a1.5 1.5 0 001.5-1.5L18 7z" style={B} />
  </Svg>
);
export const Zap = (p) => (
  <Svg {...p}>
    <path d="M13.5 2.5L4.5 13.5h6.5l-1 8 9-11.5h-6.5l1-7.5z" style={A} />
  </Svg>
);
export const Check = (p) => (
  <Svg {...p}>
    <path d="M5 12.5l4.5 4.5L19 7.5" />
  </Svg>
);
export const ChevronDown = (p) => (
  <Svg {...p}>
    <path d="M6 9.5l6 6 6-6" />
  </Svg>
);
export const Copy = (p) => (
  <Svg {...p}>
    <rect x="8.5" y="8.5" width="12" height="12" rx="3.5" style={A} />
    <path d="M15.5 8.5V6.5a3 3 0 00-3-3h-6a3 3 0 00-3 3v6a3 3 0 003 3h2" />
  </Svg>
);
export const RefreshCw = (p) => (
  <Svg {...p}>
    <path d="M20 12a8 8 0 01-13.7 5.6" />
    <path d="M4 12a8 8 0 0113.7-5.6" />
    <path d="M18.5 3v4h-4" />
    <path d="M5.5 21v-4h4" />
  </Svg>
);
export const ThumbsUp = (p) => (
  <Svg {...p}>
    <path d="M7 11v9H4.5A1.5 1.5 0 013 18.5v-6A1.5 1.5 0 014.5 11H7z" style={B} />
    <path d="M7 11l3.8-7.5A2.5 2.5 0 0113.4 6L12.6 9.5h5.7a2 2 0 012 2.4l-1.3 6.2a2 2 0 01-2 1.6H7" />
  </Svg>
);
export const ThumbsDown = (p) => (
  <Svg {...p}>
    <g transform="rotate(180 12 12)">
      <path d="M7 11v9H4.5A1.5 1.5 0 013 18.5v-6A1.5 1.5 0 014.5 11H7z" style={C} />
      <path d="M7 11l3.8-7.5A2.5 2.5 0 0113.4 6L12.6 9.5h5.7a2 2 0 012 2.4l-1.3 6.2a2 2 0 01-2 1.6H7" />
    </g>
  </Svg>
);
export const AlertTriangle = (p) => (
  <Svg {...p}>
    <path d="M12 3.5L3 19.2a1.3 1.3 0 001.1 2h15.8a1.3 1.3 0 001.1-2L12 3.5z" style={C} />
    <path d="M12 10v4.2M12 17.6v.01" />
  </Svg>
);
export const Clapperboard = (p) => (
  <Svg {...p}>
    <rect x="3" y="9" width="18" height="12" rx="3.2" style={A} />
    <path d="M3.8 9L3 5.6a1.5 1.5 0 011.1-1.8L18.9 2.5a1.5 1.5 0 011.7 1.2L21 7" />
    <path d="M8 4l1.8 4.6M13.5 3.2l1.8 4.6" />
  </Svg>
);
export const Film = (p) => (
  <Svg {...p}>
    <rect x="3" y="4" width="18" height="16" rx="4.5" style={B} />
    <path d="M8 4.5v15M16 4.5v15M3 9.5h5M3 14.5h5M16 9.5h5M16 14.5h5" />
  </Svg>
);
export const Sun = (p) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="4.4" style={A} />
    <path d="M12 2.5v2.4M12 19.1v2.4M2.5 12h2.4M19.1 12h2.4M5.3 5.3l1.7 1.7M17 17l1.7 1.7M5.3 18.7L7 17M17 7l1.7-1.7" />
  </Svg>
);
export const Moon = (p) => (
  <Svg {...p}>
    <path d="M20.5 14.2A8.6 8.6 0 019.8 3.5a8.6 8.6 0 1010.7 10.7z" style={A} />
    <path d="M17 3v3M15.5 4.5h3" strokeWidth="2" />
  </Svg>
);

export const BookOpen = (p) => (
  <Svg {...p}>
    <path d="M12 6.8C10.2 5.2 7.4 4.6 3.8 5v13.2c3.6-.4 6.4.2 8.2 1.8z" style={A} />
    <path d="M12 6.8c1.8-1.6 4.6-2.2 8.2-1.8v13.2c-3.6-.4-6.4.2-8.2 1.8z" style={B} />
    <path d="M12 6.8V20" />
  </Svg>
);
