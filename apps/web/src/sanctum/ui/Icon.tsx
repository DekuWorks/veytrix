type IconName =
  | "home"
  | "chart"
  | "case"
  | "users"
  | "shield"
  | "book"
  | "vault"
  | "grid"
  | "pulse"
  | "podium"
  | "camera"
  | "list"
  | "clock"
  | "target"
  | "calendar"
  | "bars"
  | "monitor"
  | "gear"
  | "globe";

export function Icon({ name }: { name: IconName }) {
  const common = {
    width: 16,
    height: 16,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.7,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true as const,
  };
  switch (name) {
    case "home":
      return (
        <svg {...common}>
          <path d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1z" />
        </svg>
      );
    case "chart":
      return (
        <svg {...common}>
          <path d="M4 19h16M7 16V9M12 16V5M17 16v-4" />
        </svg>
      );
    case "case":
      return (
        <svg {...common}>
          <rect x="3" y="7" width="18" height="13" rx="1.5" />
          <path d="M9 7V5h6v2M3 12h18" />
        </svg>
      );
    case "users":
      return (
        <svg {...common}>
          <circle cx="9" cy="8" r="3" />
          <path d="M3 19c1-3 3.2-4.5 6-4.5S14 16 15 19" />
          <circle cx="17" cy="9" r="2.2" />
          <path d="M16 14.6c2.2.3 3.8 1.6 4.7 4.4" />
        </svg>
      );
    case "shield":
      return (
        <svg {...common}>
          <path d="M12 3 5 6v6c0 4.2 2.8 7 7 8.5 4.2-1.5 7-4.3 7-8.5V6z" />
        </svg>
      );
    case "book":
      return (
        <svg {...common}>
          <path d="M5 4.5h6.5a3 3 0 0 1 3 3V20a2.5 2.5 0 0 0-2.5-2.5H5zM19 4.5h-6.5a3 3 0 0 0-3 3V20a2.5 2.5 0 0 1 2.5-2.5H19z" />
        </svg>
      );
    case "vault":
      return (
        <svg {...common}>
          <rect x="3" y="4" width="18" height="16" rx="1.5" />
          <circle cx="12" cy="12" r="3" />
          <path d="M12 9v3l2 1" />
        </svg>
      );
    case "grid":
      return (
        <svg {...common}>
          <rect x="4" y="4" width="6" height="6" />
          <rect x="14" y="4" width="6" height="6" />
          <rect x="4" y="14" width="6" height="6" />
          <rect x="14" y="14" width="6" height="6" />
        </svg>
      );
    case "pulse":
      return (
        <svg {...common}>
          <path d="M3 12h4l2-5 4 10 2-5h6" />
        </svg>
      );
    case "podium":
      return (
        <svg {...common}>
          <path d="M8 21V10M12 21V4M16 21v-7M4 21h16" />
        </svg>
      );
    case "camera":
      return (
        <svg {...common}>
          <path d="M4 8h3l2-2h6l2 2h3v10H4z" />
          <circle cx="12" cy="13" r="3" />
        </svg>
      );
    case "list":
      return (
        <svg {...common}>
          <path d="M8 7h12M8 12h12M8 17h12M4 7h.01M4 12h.01M4 17h.01" />
        </svg>
      );
    case "clock":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="8" />
          <path d="M12 8v5l3 2" />
        </svg>
      );
    case "target":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="7" />
          <circle cx="12" cy="12" r="3" />
          <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
        </svg>
      );
    case "calendar":
      return (
        <svg {...common}>
          <rect x="4" y="5" width="16" height="15" rx="1.5" />
          <path d="M8 3v4M16 3v4M4 10h16" />
        </svg>
      );
    case "bars":
      return (
        <svg {...common}>
          <path d="M5 19V10M10 19V5M15 19v-7M20 19V8" />
        </svg>
      );
    case "monitor":
      return (
        <svg {...common}>
          <rect x="3" y="4" width="18" height="12" rx="1.5" />
          <path d="M8 20h8M12 16v4" />
        </svg>
      );
    case "gear":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="3" />
          <path d="M12 3v2.2M12 18.8V21M3 12h2.2M18.8 12H21M5.6 5.6l1.6 1.6M16.8 16.8l1.6 1.6M18.4 5.6l-1.6 1.6M7.2 16.8l-1.6 1.6" />
        </svg>
      );
    case "globe":
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="8" />
          <path d="M4 12h16M12 4c2.2 2.4 3.3 5 3.3 8s-1.1 5.6-3.3 8c-2.2-2.4-3.3-5-3.3-8s1.1-5.6 3.3-8z" />
        </svg>
      );
    default:
      return null;
  }
}
