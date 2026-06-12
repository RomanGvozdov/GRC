import { MantineProvider } from "@mantine/core";
import "@mantine/core/styles.css";
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import { AuthProvider } from "./auth";
import { SystemProvider } from "./systemContext";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <MantineProvider>
      <AuthProvider>
        <SystemProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </SystemProvider>
      </AuthProvider>
    </MantineProvider>
  </React.StrictMode>,
);
