import { useEffect, useState } from "react";
import { BookOpen, Moon, Sun } from "./Icons.jsx";

const THEMES = [
  { id: "dark", title: "Galaxy", Icon: Moon },
  { id: "light", title: "Pastel", Icon: Sun },
  { id: "library", title: "Library", Icon: BookOpen },
];

function initialTheme() {
  const saved = localStorage.getItem("theme");
  if (THEMES.some((t) => t.id === saved)) return saved;
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export default function ThemeToggle() {
  const [theme, setTheme] = useState(initialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("theme", theme);
  }, [theme]);

  return (
    <div className="theme-switch" role="group" aria-label="Theme">
      {THEMES.map(({ id, title, Icon }) => (
        <button
          key={id}
          className={"ts-btn" + (theme === id ? " on" : "")}
          onClick={() => setTheme(id)}
          title={title + " theme"}
          aria-pressed={theme === id}
        >
          <Icon size={16} />
        </button>
      ))}
    </div>
  );
}
