import React, { useEffect } from 'react';
import { X } from 'lucide-react';
import '../styles/sheet.css';

interface ToastProps {
  text: string;
  tone: 'success' | 'error';
  onClose: () => void;
  timeoutMs?: number;
}

export const Toast: React.FC<ToastProps> = ({ text, tone, onClose, timeoutMs = 5000 }) => {
  useEffect(() => {
    const id = window.setTimeout(onClose, timeoutMs);
    return () => window.clearTimeout(id);
  }, [text, onClose, timeoutMs]);

  return (
    <div className={`toast${tone === 'error' ? ' is-error' : ''}`} role={tone === 'error' ? 'alert' : 'status'}>
      <span className="toast-dot" />
      <span>{text}</span>
      <button className="key" style={{ width: 24, height: 24 }} onClick={onClose} aria-label="Закрыть">
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
};
