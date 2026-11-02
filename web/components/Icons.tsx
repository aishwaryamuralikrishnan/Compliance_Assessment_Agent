// Inline stroke icons for the rail (no icon font, no emoji).

const base = { width: 20, height: 20, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true };

export const IconAssistant = () => (
  <svg {...base}><path d="M4 5h16v11H8l-4 4z" /><path d="M8 9h8M8 12h5" /></svg>
);
export const IconReview = () => (
  <svg {...base}><path d="M9 11l2 2 4-5" /><rect x="4" y="4" width="16" height="16" rx="3" /></svg>
);
export const IconRegister = () => (
  <svg {...base}><path d="M5 4h11l3 3v13H5z" /><path d="M8 11h8M8 15h8" /></svg>
);
export const IconMemory = () => (
  <svg {...base}><path d="M12 3a7 7 0 0 0-4 12.7V19h8v-3.3A7 7 0 0 0 12 3z" /><path d="M10 22h4" /></svg>
);
export const IconLogout = () => (
  <svg {...base}><path d="M10 4H5v16h5" /><path d="M14 8l4 4-4 4M18 12H9" /></svg>
);
