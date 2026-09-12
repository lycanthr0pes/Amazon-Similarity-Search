import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/noto-sans-jp";
import "./global.css";
import App from "./App";
import ConnectedApp from "./ConnectedApp";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {new URLSearchParams(window.location.search).get("mode") === "connected" ? (
      <ConnectedApp />
    ) : (
      <App />
    )}
  </StrictMode>,
);
