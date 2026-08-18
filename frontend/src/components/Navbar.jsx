import React from "react";
import logo from "../assets/logo.svg"; // Путь к твоему логотипу

export default function Navbar() {
  return (
    <nav className="navbar glass-navbar">
      <div className="navbar-left">
        {/* Если файла logo.svg пока нет, можно временно выводить иконку 🌪️ */}
        
        <div className="brand-group">
          <span className="navbar-icon">🌪️</span>
          <span className="brand-name">Eroventis</span>
          <span className="brand-badge">v2.0 Beta</span>
        </div>
      </div>

      <div className="navbar-right">
        <div className="status-indicator">
          <span className="status-dot online"></span>
          <span className="status-text">AI Core Connected</span>
        </div>
      </div>
    </nav>
  );
}